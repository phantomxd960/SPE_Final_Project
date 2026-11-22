"""Create comparisons and read their classified changes (CHG, UI-2, UI-5)."""

import logging

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from regdiff_api.core.errors import ApiError
from regdiff_api.deps import CurrentUser, DbSession
from regdiff_api.schemas import ChangeOut, ClauseOut, ComparisonCreate, ComparisonOut
from regdiff_api.services.queue import enqueue
from regdiff_common.logging import log_event
from regdiff_common.models import ClauseChange, Comparison, DocumentVersion, ImpactReport, Job

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])
log = logging.getLogger(__name__)


def _comparison_out(db: Session, comparison: Comparison) -> ComparisonOut:
    counts = dict(
        db.execute(
            select(ClauseChange.change_type, func.count())
            .where(ClauseChange.comparison_id == comparison.id)
            .group_by(ClauseChange.change_type)
        ).all()
    )
    job_id = db.scalar(
        select(Job.id)
        .where(Job.type == "compare", Job.payload["comparison_id"].as_integer() == comparison.id)
        .order_by(Job.id.desc())
        .limit(1)
    )
    document = comparison.old_version.document
    return ComparisonOut(
        id=comparison.id,
        status=comparison.status,
        error=comparison.error,
        doc_code=document.doc_code,
        doc_title=document.title,
        old_version=comparison.old_version.version_label,
        new_version=comparison.new_version.version_label,
        created_at=comparison.created_at,
        finished_at=comparison.finished_at,
        counts=counts,
        job_id=job_id,
    )


def _get(db: Session, comparison_id: int) -> Comparison:
    comparison = db.get(Comparison, comparison_id)
    if comparison is None:
        raise ApiError(404, "Comparison not found")
    return comparison


@router.post("", response_model=ComparisonOut, status_code=201)
def create_comparison(body: ComparisonCreate, db: DbSession, user: CurrentUser) -> ComparisonOut:
    if body.old_version_id == body.new_version_id:
        raise ApiError(422, "Choose two different versions")
    old, new = db.get(DocumentVersion, body.old_version_id), db.get(DocumentVersion, body.new_version_id)
    if old is None or new is None:
        raise ApiError(404, "Version not found")
    if old.document_id != new.document_id:
        raise ApiError(422, "Both versions must belong to the same document")

    comparison = Comparison(old_version_id=old.id, new_version_id=new.id, status="queued", created_by=user.id)
    db.add(comparison)
    db.flush()
    job = enqueue(db, "compare", comparison_id=comparison.id)
    db.commit()
    log_event(log, "comparison_created", comparison_id=comparison.id, document_id=old.document_id, job_id=job.id)
    return _comparison_out(db, comparison)


@router.get("", response_model=list[ComparisonOut])
def list_comparisons(db: DbSession, _: CurrentUser) -> list[ComparisonOut]:
    comparisons = db.scalars(select(Comparison).order_by(Comparison.id.desc()).limit(100)).all()
    return [_comparison_out(db, c) for c in comparisons]


@router.get("/{comparison_id}", response_model=ComparisonOut)
def get_comparison(comparison_id: int, db: DbSession, _: CurrentUser) -> ComparisonOut:
    return _comparison_out(db, _get(db, comparison_id))


@router.get("/{comparison_id}/changes", response_model=list[ChangeOut])
def list_changes(comparison_id: int, db: DbSession, _: CurrentUser, include_unchanged: bool = False) -> list[ChangeOut]:
    _get(db, comparison_id)
    query = (
        select(ClauseChange)
        .where(ClauseChange.comparison_id == comparison_id)
        .options(selectinload(ClauseChange.old_clause), selectinload(ClauseChange.new_clause))
        .order_by(ClauseChange.id)
    )
    if not include_unchanged:
        query = query.where(ClauseChange.change_type != "unchanged")
    reports = dict(
        db.execute(
            select(ImpactReport.change_id, ImpactReport.id).where(ImpactReport.comparison_id == comparison_id)
        ).all()
    )
    return [
        ChangeOut(
            id=change.id,
            change_type=change.change_type,
            similarity=change.similarity,
            confidence=change.confidence,
            numeric_changes=change.numeric_changes,
            text_diff=change.text_diff,
            old_clause=ClauseOut.model_validate(change.old_clause) if change.old_clause else None,
            new_clause=ClauseOut.model_validate(change.new_clause) if change.new_clause else None,
            report_id=reports.get(change.id),
        )
        for change in db.scalars(query)
    ]
