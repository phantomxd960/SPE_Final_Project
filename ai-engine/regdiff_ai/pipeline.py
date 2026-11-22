"""The two jobs the worker runs: ingest a document version, compare two versions."""

import logging
import time
from datetime import UTC, datetime

import networkx as nx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from regdiff_ai.analysis.align import ClauseInput, align
from regdiff_ai.analysis.classify import Thresholds, classify
from regdiff_ai.analysis.text import text_hash
from regdiff_ai.graph_builder import rebuild_graph
from regdiff_ai.ingestion import ParseError, parse_file
from regdiff_ai.llm import LLMClient
from regdiff_ai.llm.assess import DISCLAIMER, assess
from regdiff_ai.llm.context import Candidate, Evidence, ImpactContext
from regdiff_common.config import Settings
from regdiff_common.embeddings import Embedder
from regdiff_common.graph import clause_ref, impact_of, load_graph, node_key
from regdiff_common.logging import log_event
from regdiff_common.models import (
    Clause,
    ClauseChange,
    Comparison,
    Document,
    DocumentVersion,
    ImpactReport,
)
from regdiff_common.retrieval import SearchFilters, hybrid_search

log = logging.getLogger(__name__)


class RetryLater(Exception):
    """The job cannot run yet (for example a version is still being processed)."""


class PermanentJobError(Exception):
    """Retrying will not help; fail the job straight away."""


# --------------------------------------------------------------------------- ingestion


def ingest_version(session: Session, version_id: int, embedder: Embedder, settings: Settings) -> dict:
    version = session.get(DocumentVersion, version_id)
    if version is None:
        raise PermanentJobError(f"Document version {version_id} does not exist")
    version.status, version.error = "processing", None
    session.commit()

    try:
        parsed = parse_file(version.file_path)
    except (ParseError, FileNotFoundError) as exc:
        raise PermanentJobError(str(exc)) from exc

    session.execute(delete(Clause).where(Clause.version_id == version.id))  # idempotent on retry
    vectors = embedder.embed([clause.text for clause in parsed.clauses])
    session.add_all(
        Clause(
            version_id=version.id,
            position=position,
            clause_number=clause.number,
            section=clause.section,
            page=clause.page,
            text=clause.text,
            text_hash=text_hash(clause.text),
            embedding=vector,
        )
        for position, (clause, vector) in enumerate(zip(parsed.clauses, vectors, strict=True))
    )
    version.title, version.meta, version.status = parsed.title, parsed.metadata, "ready"
    session.flush()
    rebuild_graph(session, settings.graph_inferred_threshold)
    return {"document_id": version.document_id, "clauses": len(parsed.clauses)}


# --------------------------------------------------------------------------- comparison


def run_comparison(
    session: Session, comparison_id: int, embedder: Embedder, llm: LLMClient, settings: Settings
) -> dict:
    comparison = session.get(Comparison, comparison_id)
    if comparison is None:
        raise PermanentJobError(f"Comparison {comparison_id} does not exist")
    old_version, new_version = comparison.old_version, comparison.new_version
    for version in (old_version, new_version):
        if version.status == "failed":
            raise PermanentJobError(f"Version {version.version_label} failed to process: {version.error}")
        if version.status != "ready":
            raise RetryLater(f"Version {version.version_label} is still {version.status}")

    comparison.status, comparison.error = "running", None
    session.execute(delete(ClauseChange).where(ClauseChange.comparison_id == comparison.id))
    session.execute(delete(ImpactReport).where(ImpactReport.comparison_id == comparison.id))
    session.commit()

    document = old_version.document
    thresholds = Thresholds(
        settings.renumbered_min_similarity,
        settings.equivalent_min_embedding_similarity,
        settings.equivalent_max_word_overlap,
    )
    pairs = align(_inputs(old_version), _inputs(new_version), settings.align_min_similarity)

    changes: list[tuple[ClauseChange, object]] = []
    for pair in pairs:
        result = classify(pair, thresholds)
        row = ClauseChange(
            comparison_id=comparison.id,
            old_clause_id=pair.old.id if pair.old else None,
            new_clause_id=pair.new.id if pair.new else None,
            change_type=result.change_type,
            text_diff=result.text_diff,
            similarity=result.similarity,
            numeric_changes=result.numeric_changes,
            confidence=result.confidence,
        )
        session.add(row)
        changes.append((row, result))
    session.flush()

    graph = load_graph(session)
    reports = 0
    for row, result in changes:
        if not result.significant:
            continue
        started = time.perf_counter()
        context = _impact_context(session, graph, document, old_version, new_version, row, embedder, settings)
        assessment = assess(context, llm)
        session.add(
            ImpactReport(
                comparison_id=comparison.id,
                change_id=row.id,
                summary=assessment.summary,
                confirmed={
                    "change_type": row.change_type,
                    "clause": context.clause_number,
                    "old_version": context.old_version,
                    "new_version": context.new_version,
                    "differences": row.numeric_changes,
                    "evidence_ids": assessment.summary_evidence_ids,
                    "disclaimer": DISCLAIMER,
                    "validation_errors": assessment.errors,
                },
                affected=assessment.affected,
                impacts=assessment.impacts,
                actions=assessment.actions,
                evidence=[vars(item) for item in context.evidence],
                verified=assessment.verified,
                model=assessment.model,
            )
        )
        reports += 1
        log_event(
            log,
            "impact_report_created",
            comparison_id=comparison.id,
            change_id=row.id,
            verified=assessment.verified,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )

    comparison.status, comparison.finished_at = "done", datetime.now(UTC)
    counts: dict[str, int] = {}
    for row, _ in changes:
        counts[row.change_type] = counts.get(row.change_type, 0) + 1
    log_event(log, "comparison_done", comparison_id=comparison.id, document_id=document.id, reports=reports, **counts)
    return {"changes": counts, "reports": reports}


def _inputs(version: DocumentVersion) -> list[ClauseInput]:
    return [
        ClauseInput(
            id=clause.id,
            number=clause.clause_number,
            text=clause.text,
            embedding=tuple(float(x) for x in clause.embedding) if clause.embedding is not None else None,
        )
        for clause in version.clauses
    ]


def _impact_context(
    session: Session,
    graph: nx.DiGraph,
    document: Document,
    old_version: DocumentVersion,
    new_version: DocumentVersion,
    change: ClauseChange,
    embedder: Embedder,
    settings: Settings,
) -> ImpactContext:
    old_clause = session.get(Clause, change.old_clause_id) if change.old_clause_id else None
    new_clause = session.get(Clause, change.new_clause_id) if change.new_clause_id else None
    clause_number = (new_clause or old_clause).clause_number

    evidence: list[Evidence] = []
    by_clause: dict[int, str] = {}

    def add_evidence(role: str, clause: Clause, doc: Document, version_label: str) -> str:
        if clause.id in by_clause:
            return by_clause[clause.id]
        item = Evidence(
            f"E{len(evidence) + 1}",
            role,
            doc.doc_code,
            doc.title,
            version_label,
            clause.clause_number,
            clause.page,
            clause.text,
            clause.id,
        )
        evidence.append(item)
        by_clause[clause.id] = item.id
        return item.id

    if old_clause:
        add_evidence("old_clause", old_clause, document, old_version.version_label)
    if new_clause:
        add_evidence("new_clause", new_clause, document, new_version.version_label)

    # Graph: who depends on this clause (GRF-6)?
    candidates: list[Candidate] = []
    start = node_key("reg_clause", clause_ref(document.doc_code, clause_number))
    for item in impact_of(graph, start, settings.graph_max_depth):
        if item.node_type not in ("policy", "process", "control"):
            continue
        evidence_ids = []
        for key in item.path:
            clause_id = _evidence_clause(graph, key)
            if clause_id:
                clause = session.get(Clause, clause_id)
                version = clause.version
                evidence_ids.append(add_evidence("dependent_clause", clause, version.document, version.version_label))
        candidates.append(
            Candidate(item.key, item.node_type, item.label, item.status, "graph", item.path, evidence_ids)
        )

    # Retrieval: related policy passages as extra context (RAG-3).
    query = (new_clause or old_clause).text
    hits = hybrid_search(
        session,
        query,
        embedder.embed([query])[0],
        SearchFilters(doc_types=["policy", "guideline"], latest_only=True),
        limit=settings.retrieval_top_k,
        candidates=settings.retrieval_candidates,
    )
    for hit in hits:
        clause = session.get(Clause, hit.clause_id)
        add_evidence("related_passage", clause, clause.version.document, hit.version_label)

    return ImpactContext(
        doc_code=document.doc_code,
        doc_title=document.title,
        clause_number=clause_number,
        old_version=old_version.version_label if old_clause else None,
        new_version=new_version.version_label if new_clause else None,
        change_type=change.change_type,
        differences=change.numeric_changes,
        evidence=evidence,
        candidates=candidates,
    )


def _evidence_clause(graph: nx.DiGraph, key: str) -> int | None:
    """The stored clause behind a policy-clause node, taken from its edges."""
    if graph.nodes[key]["node_type"] != "policy_clause":
        return None
    for _, _, data in graph.out_edges(key, data=True):
        if data.get("evidence_clause_id"):
            return data["evidence_clause_id"]
    for _, _, data in graph.in_edges(key, data=True):
        if data.get("evidence_clause_id"):
            return data["evidence_clause_id"]
    return None
