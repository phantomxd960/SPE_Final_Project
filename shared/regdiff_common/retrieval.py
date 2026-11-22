"""Hybrid clause search: pgvector similarity + PostgreSQL full-text search,
merged with reciprocal-rank fusion (RAG-2, RAG-3, Section 8.2)."""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from regdiff_common.models import Clause, Document, DocumentVersion

RRF_K = 60


@dataclass
class SearchFilters:
    doc_code: str | None = None
    doc_types: list[str] = field(default_factory=list)
    version_label: str | None = None
    clause_number: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    latest_only: bool = False
    exclude_version_ids: list[int] = field(default_factory=list)


@dataclass
class SearchHit:
    clause_id: int
    doc_code: str
    doc_title: str
    doc_type: str
    version_label: str
    clause_number: str
    section: str | None
    page: int
    text: str
    score: float


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    """Merge several ranked id lists into one score per id: sum of 1 / (k + rank)."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores


def latest_version_ids() -> Select:
    """Subquery: the most recently uploaded *ready* version of every document."""
    return (
        select(DocumentVersion.id)
        .where(DocumentVersion.status == "ready")
        .distinct(DocumentVersion.document_id)
        .order_by(DocumentVersion.document_id, DocumentVersion.uploaded_at.desc())
    )


def _apply_filters(query: Select, filters: SearchFilters) -> Select:
    query = query.join(DocumentVersion, Clause.version_id == DocumentVersion.id).join(
        Document, DocumentVersion.document_id == Document.id
    )
    query = query.where(DocumentVersion.status == "ready")
    if filters.doc_code:
        query = query.where(Document.doc_code == filters.doc_code)
    if filters.doc_types:
        query = query.where(Document.doc_type.in_(filters.doc_types))
    if filters.version_label:
        query = query.where(DocumentVersion.version_label == filters.version_label)
    if filters.clause_number:
        query = query.where(Clause.clause_number == filters.clause_number)
    if filters.effective_from:
        query = query.where(DocumentVersion.effective_date >= filters.effective_from)
    if filters.effective_to:
        query = query.where(DocumentVersion.effective_date <= filters.effective_to)
    if filters.latest_only:
        query = query.where(DocumentVersion.id.in_(latest_version_ids()))
    if filters.exclude_version_ids:
        query = query.where(DocumentVersion.id.not_in(filters.exclude_version_ids))
    return query


def hybrid_search(
    session: Session,
    query_text: str,
    query_vector: list[float],
    filters: SearchFilters | None = None,
    limit: int = 5,
    candidates: int = 10,
) -> list[SearchHit]:
    filters = filters or SearchFilters()

    vector_query = _apply_filters(select(Clause.id), filters)
    vector_query = (
        vector_query.where(Clause.embedding.is_not(None))
        .order_by(Clause.embedding.cosine_distance(query_vector))
        .limit(candidates)
    )
    vector_ids = list(session.scalars(vector_query))

    ts_query = func.plainto_tsquery("english", query_text)
    ts_vector = func.to_tsvector("english", Clause.text)
    keyword_query = _apply_filters(select(Clause.id), filters)
    keyword_query = (
        keyword_query.where(ts_vector.op("@@")(ts_query))
        .order_by(func.ts_rank(ts_vector, ts_query).desc())
        .limit(candidates)
    )
    keyword_ids = list(session.scalars(keyword_query))

    scores = reciprocal_rank_fusion([vector_ids, keyword_ids])
    best = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:limit]
    if not best:
        return []

    rows = session.execute(
        select(Clause, DocumentVersion, Document)
        .join(DocumentVersion, Clause.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Clause.id.in_(best))
    ).all()
    by_id = {clause.id: (clause, version, document) for clause, version, document in rows}
    hits = []
    for clause_id in best:
        clause, version, document = by_id[clause_id]
        hits.append(
            SearchHit(
                clause_id=clause.id,
                doc_code=document.doc_code,
                doc_title=document.title,
                doc_type=document.doc_type,
                version_label=version.version_label,
                clause_number=clause.clause_number,
                section=clause.section,
                page=clause.page,
                text=clause.text,
                score=round(scores[clause_id], 5),
            )
        )
    return hits
