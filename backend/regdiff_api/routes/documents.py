"""Upload and list documents and their versions (DOC-1 to DOC-4, SEC-2)."""

import logging
import re
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from regdiff_api.core.errors import ApiError
from regdiff_api.deps import CurrentUser, DbSession
from regdiff_api.schemas import ClauseDetail, ClauseOut, DocType, DocumentOut, UploadResponse, VersionOut
from regdiff_api.services import storage
from regdiff_api.services.queue import enqueue
from regdiff_common.config import get_settings
from regdiff_common.logging import log_event
from regdiff_common.models import Clause, Document, DocumentVersion

router = APIRouter(prefix="/api", tags=["documents"])

ALLOWED_SUFFIXES = {".txt", ".md", ".pdf"}
DOC_CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,63}$")

log = logging.getLogger(__name__)


def _clause_counts(db: DbSession, version_ids: list[int]) -> dict[int, int]:
    if not version_ids:
        return {}
    rows = db.execute(
        select(Clause.version_id, func.count()).where(Clause.version_id.in_(version_ids)).group_by(Clause.version_id)
    )
    return dict(rows.all())


def _document_out(document: Document, counts: dict[int, int]) -> DocumentOut:
    versions = [
        VersionOut.model_validate(v).model_copy(update={"clause_count": counts.get(v.id, 0)}) for v in document.versions
    ]
    return DocumentOut.model_validate(document).model_copy(update={"versions": versions})


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: DbSession, _: CurrentUser) -> list[DocumentOut]:
    documents = db.scalars(select(Document).options(selectinload(Document.versions)).order_by(Document.doc_code)).all()
    counts = _clause_counts(db, [v.id for d in documents for v in d.versions])
    return [_document_out(d, counts) for d in documents]


@router.post("/documents", response_model=UploadResponse, status_code=201)
async def upload_document(
    db: DbSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    doc_code: Annotated[str, Form()],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    doc_type: Annotated[DocType, Form()],
    version_label: Annotated[str, Form(min_length=1, max_length=64)],
    authority: Annotated[str | None, Form(max_length=255)] = None,
    effective_date: Annotated[date | None, Form()] = None,
) -> UploadResponse:
    doc_code = doc_code.strip().upper()
    if not DOC_CODE.match(doc_code):
        raise ApiError(422, "doc_code must be 2-64 characters: letters, digits and dashes")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ApiError(422, "Only .txt, .md and .pdf files are accepted")
    content = await _read_limited(file, get_settings().max_upload_mb * 1024 * 1024)
    if not content.strip():
        raise ApiError(422, "The file is empty")

    document = db.scalar(select(Document).where(Document.doc_code == doc_code))
    if document is None:
        document = Document(doc_code=doc_code, title=title.strip(), doc_type=doc_type, authority=authority)
        db.add(document)
        db.flush()
    elif document.doc_type != doc_type:
        raise ApiError(409, f"{doc_code} already exists as a {document.doc_type}")

    digest = storage.sha256(content)
    existing = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            (DocumentVersion.version_label == version_label) | (DocumentVersion.sha256 == digest),
        )
    )
    if existing is not None:
        reason = "this version label" if existing.version_label == version_label else "an identical file"
        raise ApiError(409, f"{doc_code} already has {reason} (version {existing.version_label})")

    path = storage.save_document(doc_code, version_label, file.filename or f"document{suffix}", content)
    version = DocumentVersion(
        document_id=document.id,
        version_label=version_label,
        effective_date=effective_date,
        file_name=storage.safe_name(file.filename or ""),
        file_path=path,
        sha256=digest,
        status="queued",
        uploaded_by=user.id,
        meta={},
    )
    db.add(version)
    db.flush()
    job = enqueue(db, "ingest_version", version_id=version.id)
    db.commit()
    db.refresh(document)
    log_event(
        log,
        "document_uploaded",
        document_id=document.id,
        doc_code=doc_code,
        version=version_label,
        size_bytes=len(content),
        job_id=job.id,
    )
    return UploadResponse(
        document=_document_out(document, {}), version=VersionOut.model_validate(version), job_id=job.id
    )


@router.get("/versions/{version_id}/clauses", response_model=list[ClauseOut])
def version_clauses(version_id: int, db: DbSession, _: CurrentUser) -> list[Clause]:
    if db.get(DocumentVersion, version_id) is None:
        raise ApiError(404, "Version not found")
    return list(db.scalars(select(Clause).where(Clause.version_id == version_id).order_by(Clause.position)))


@router.get("/clauses/{clause_id}", response_model=ClauseDetail)
def clause_detail(clause_id: int, db: DbSession, _: CurrentUser) -> ClauseDetail:
    """The source of a citation in an impact report (UI-4)."""
    clause = db.get(Clause, clause_id)
    if clause is None:
        raise ApiError(404, "Clause not found")
    version, document = clause.version, clause.version.document
    return ClauseDetail(
        **ClauseOut.model_validate(clause).model_dump(),
        doc_code=document.doc_code,
        doc_title=document.title,
        doc_type=document.doc_type,
        version_label=version.version_label,
    )


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise ApiError(413, f"File is larger than {limit // (1024 * 1024)} MB")
    return content
