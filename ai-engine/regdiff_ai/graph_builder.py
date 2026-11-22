"""Rebuild the compliance dependency graph from the stored documents (GRF-1 to GRF-4).

The graph is small, so it is rebuilt from scratch after every ingestion: this
keeps it deterministic and always consistent with the latest versions.
"""

import logging
import re
from dataclasses import dataclass

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from regdiff_common.graph import clause_ref, node_key
from regdiff_common.logging import log_event
from regdiff_common.models import Clause, Document, DocumentVersion, GraphEdge, GraphNode
from regdiff_common.retrieval import latest_version_ids

log = logging.getLogger(__name__)

REFERENCE = re.compile(
    r"\b(?:(?P<code>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)\s+)?(?:clause|section|article|paragraph)\s+(?P<num>\d+(?:\.\d+)*)",
    re.IGNORECASE,
)


@dataclass
class _Edge:
    status: str
    confidence: float
    evidence_clause_id: int | None


class _GraphDraft:
    def __init__(self) -> None:
        self.nodes: dict[str, tuple[str, str, str]] = {}  # key -> (type, ref, label)
        self.edges: dict[tuple[str, str, str], _Edge] = {}

    def node(self, node_type: str, ref_id: str, label: str) -> str:
        key = node_key(node_type, ref_id)
        self.nodes.setdefault(key, (node_type, ref_id, label))
        return key

    def edge(self, src: str, dst: str, rel_type: str, status: str, confidence: float, evidence: int | None) -> None:
        self.edges.setdefault((src, dst, rel_type), _Edge(status, round(confidence, 4), evidence))

    def has_edge(self, src: str, dst: str) -> bool:
        return any((src, dst, rel) in self.edges for rel in ("REFERENCES", "IMPLEMENTS"))


def rebuild_graph(session: Session, inferred_threshold: float) -> dict[str, int]:
    draft = _GraphDraft()
    documents = {doc.id: doc for doc in session.scalars(select(Document))}
    regulation_codes = {doc.doc_code for doc in documents.values() if doc.doc_type == "regulation"}
    latest_ids = set(session.scalars(latest_version_ids()))

    # Regulation clauses of every processed version, so deleted clauses still have a node.
    latest_regulation_clauses: list[tuple[str, Clause]] = []
    rows = session.execute(
        select(Clause, DocumentVersion, Document)
        .join(DocumentVersion, Clause.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Document.doc_type == "regulation", DocumentVersion.status == "ready")
    ).all()
    for clause, version, document in rows:
        key = draft.node(
            "reg_clause",
            clause_ref(document.doc_code, clause.clause_number),
            f"{document.doc_code} §{clause.clause_number}",
        )
        if version.id in latest_ids and clause.embedding is not None:
            latest_regulation_clauses.append((key, clause))

    regulation_matrix = (
        np.array([np.asarray(clause.embedding, dtype=float) for _, clause in latest_regulation_clauses])
        if latest_regulation_clauses
        else None
    )

    policy_versions = session.scalars(
        select(DocumentVersion)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Document.doc_type != "regulation", DocumentVersion.id.in_(latest_ids))
    ).all()
    for version in policy_versions:
        document = documents[version.document_id]
        meta = version.meta or {}
        policy = draft.node("policy", document.doc_code, document.title)
        default_regulations = [code for code in meta.get("regulation", []) if code in regulation_codes]
        if not default_regulations and len(regulation_codes) == 1:
            default_regulations = list(regulation_codes)

        for name in meta.get("process", []):
            draft.edge(draft.node("process", name, name), policy, "DEPENDS_ON", "confirmed", 1.0, None)
        for name in meta.get("control", []):
            draft.edge(draft.node("control", name, name), policy, "DEPENDS_ON", "confirmed", 1.0, None)

        for clause in version.clauses:
            policy_clause = draft.node(
                "policy_clause",
                clause_ref(document.doc_code, clause.clause_number),
                f"{document.doc_code} §{clause.clause_number}",
            )
            draft.edge(policy, policy_clause, "DEPENDS_ON", "confirmed", 1.0, clause.id)

            for match in REFERENCE.finditer(clause.text):  # explicit citation: confirmed (GRF-3)
                code = (match.group("code") or "").upper()
                targets = [code] if code in regulation_codes else default_regulations
                for regulation in targets:
                    target = draft.node(
                        "reg_clause", clause_ref(regulation, match.group("num")), f"{regulation} §{match.group('num')}"
                    )
                    draft.edge(policy_clause, target, "REFERENCES", "confirmed", 1.0, clause.id)

            if regulation_matrix is not None and clause.embedding is not None:  # semantic: inferred (GRF-4)
                scores = _cosine_scores(regulation_matrix, np.asarray(clause.embedding, dtype=float))
                best = int(np.argmax(scores))
                target = latest_regulation_clauses[best][0]
                if scores[best] >= inferred_threshold and not draft.has_edge(policy_clause, target):
                    draft.edge(policy_clause, target, "IMPLEMENTS", "inferred", float(scores[best]), clause.id)

    stats = _persist(session, draft)
    log_event(log, "graph_rebuilt", **stats)
    return stats


def _cosine_scores(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(vector) or 1.0)
    return (matrix @ vector) / np.where(norms == 0, 1.0, norms)


def _persist(session: Session, draft: _GraphDraft) -> dict[str, int]:
    session.execute(delete(GraphEdge))
    session.execute(delete(GraphNode))
    rows = {key: GraphNode(node_type=t, ref_id=ref, label=label) for key, (t, ref, label) in draft.nodes.items()}
    session.add_all(rows.values())
    session.flush()
    session.add_all(
        GraphEdge(
            src=rows[src].id,
            dst=rows[dst].id,
            rel_type=rel,
            status=e.status,
            confidence=e.confidence,
            evidence_clause_id=e.evidence_clause_id,
        )
        for (src, dst, rel), e in draft.edges.items()
    )
    session.flush()
    inferred = sum(1 for e in draft.edges.values() if e.status == "inferred")
    return {"nodes": len(rows), "edges": len(draft.edges), "inferred_edges": inferred}
