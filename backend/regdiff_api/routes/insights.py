"""Search, dependency graph, impact reports and job status (RAG-2, GRF-7, IMP-7, UI-5)."""

import json
from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import select

from regdiff_api.core.errors import ApiError
from regdiff_api.deps import CurrentUser, DbSession
from regdiff_api.schemas import JobOut, ReportOut, SearchHitOut
from regdiff_common.config import get_settings
from regdiff_common.embeddings import get_embedder
from regdiff_common.graph import clause_ref, load_graph, node_key, subgraph_view
from regdiff_common.models import ClauseChange, Comparison, ImpactReport, Job
from regdiff_common.retrieval import SearchFilters, hybrid_search

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/search", response_model=list[SearchHitOut])
def search(
    db: DbSession,
    _: CurrentUser,
    q: str = Query(min_length=2, max_length=500),
    doc_code: str | None = None,
    doc_type: str | None = Query(None, pattern="^(regulation|policy|guideline)$"),
    version: str | None = None,
    clause: str | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    latest_only: bool = False,
    limit: int = Query(10, ge=1, le=50),
) -> list[SearchHitOut]:
    filters = SearchFilters(
        doc_code=doc_code.upper() if doc_code else None,
        doc_types=[doc_type] if doc_type else [],
        version_label=version,
        clause_number=clause,
        effective_from=effective_from,
        effective_to=effective_to,
        latest_only=latest_only,
    )
    vector = get_embedder().embed([q])[0]
    hits = hybrid_search(db, q, vector, filters, limit=limit, candidates=max(limit * 2, 10))
    return [SearchHitOut(**vars(hit)) for hit in hits]


@router.get("/graph/{comparison_id}")
def comparison_graph(comparison_id: int, db: DbSession, _: CurrentUser) -> dict:
    """Changed clauses of this comparison and everything that depends on them."""
    comparison = db.get(Comparison, comparison_id)
    if comparison is None:
        raise ApiError(404, "Comparison not found")
    doc_code = comparison.old_version.document.doc_code
    changes = db.scalars(
        select(ClauseChange).where(ClauseChange.comparison_id == comparison_id, ClauseChange.change_type != "unchanged")
    ).all()
    starts = {}
    for change in changes:
        clause = change.new_clause or change.old_clause
        if clause is not None:
            starts[node_key("reg_clause", clause_ref(doc_code, clause.clause_number))] = change.change_type
    view = subgraph_view(load_graph(db), list(starts), get_settings().graph_max_depth)
    for node in view["nodes"]:
        node["change_type"] = starts.get(node["id"])
    return view


@router.get("/comparisons/{comparison_id}/reports", response_model=list[ReportOut])
def comparison_reports(comparison_id: int, db: DbSession, _: CurrentUser) -> list[ImpactReport]:
    return list(
        db.scalars(select(ImpactReport).where(ImpactReport.comparison_id == comparison_id).order_by(ImpactReport.id))
    )


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: DbSession, _: CurrentUser, download: bool = False):
    report = db.get(ImpactReport, report_id)
    if report is None:
        raise ApiError(404, "Report not found")
    if download:
        body = ReportOut.model_validate(report).model_dump(mode="json")
        return Response(
            json.dumps(body, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="impact-report-{report_id}.json"'},
        )
    return report


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: DbSession, _: CurrentUser) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise ApiError(404, "Job not found")
    return job
