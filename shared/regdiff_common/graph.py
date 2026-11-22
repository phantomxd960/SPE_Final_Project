"""Compliance dependency graph (GRF-1, GRF-6, GRF-7).

Edges point from the dependent item to what it depends on:

    policy_clause  --REFERENCES-->  reg_clause    (explicit "see clause 4.2.1": confirmed)
    policy_clause  --IMPLEMENTS-->  reg_clause    (semantic match: inferred)
    policy         --DEPENDS_ON-->  policy_clause (structure: confirmed)
    process        --DEPENDS_ON-->  policy        (policy header: confirmed)
    control        --DEPENDS_ON-->  policy        (policy header: confirmed)

So the impact of a changed regulation clause flows *against* the edges:
reg_clause -> policy_clause -> policy -> process / control (depth 3).
"""

from collections import deque
from dataclasses import dataclass

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from regdiff_common.models import GraphEdge, GraphNode


def node_key(node_type: str, ref_id: str) -> str:
    return f"{node_type}:{ref_id}"


def clause_ref(doc_code: str, clause_number: str) -> str:
    return f"{doc_code}#{clause_number}"


@dataclass
class ImpactItem:
    key: str
    node_type: str
    label: str
    depth: int
    status: str  # confirmed only if every edge on the path is confirmed
    confidence: float
    path: list[str]
    via: list[str]  # relation types along the path


def load_graph(session: Session) -> nx.DiGraph:
    graph = nx.DiGraph()
    nodes = {node.id: node for node in session.scalars(select(GraphNode))}
    for node in nodes.values():
        graph.add_node(node_key(node.node_type, node.ref_id), node_type=node.node_type, label=node.label, db_id=node.id)
    for edge in session.scalars(select(GraphEdge)):
        src, dst = nodes[edge.src], nodes[edge.dst]
        graph.add_edge(
            node_key(src.node_type, src.ref_id),
            node_key(dst.node_type, dst.ref_id),
            rel_type=edge.rel_type,
            status=edge.status,
            confidence=edge.confidence,
            evidence_clause_id=edge.evidence_clause_id,
        )
    return graph


def impact_of(graph: nx.DiGraph, start: str, max_depth: int = 3) -> list[ImpactItem]:
    """Everything that (transitively) depends on `start`, best path per node.

    A confirmed path beats an inferred one; then higher confidence wins.
    """
    if start not in graph:
        return []
    best: dict[str, ImpactItem] = {}
    queue: deque[tuple[str, list[str], list[str], bool, float]] = deque([(start, [start], [], True, 1.0)])
    while queue:
        current, path, via, confirmed, confidence = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        for dependent in graph.predecessors(current):
            if dependent in path:
                continue
            edge = graph.edges[dependent, current]
            item = ImpactItem(
                key=dependent,
                node_type=graph.nodes[dependent]["node_type"],
                label=graph.nodes[dependent]["label"],
                depth=len(path),
                status="confirmed" if confirmed and edge["status"] == "confirmed" else "inferred",
                confidence=round(confidence * edge["confidence"], 4),
                path=[*path, dependent],
                via=[*via, edge["rel_type"]],
            )
            previous = best.get(dependent)
            if previous is None or _better(item, previous):
                best[dependent] = item
                queue.append((dependent, item.path, item.via, item.status == "confirmed", item.confidence))
    return sorted(best.values(), key=lambda i: (i.depth, i.status != "confirmed", -i.confidence, i.key))


def _better(new: ImpactItem, old: ImpactItem) -> bool:
    def rank(item: ImpactItem) -> tuple:
        return (item.status == "confirmed", item.confidence, -item.depth)

    return rank(new) > rank(old)


def subgraph_view(graph: nx.DiGraph, starts: list[str], max_depth: int = 3) -> dict:
    """Nodes and edges reachable from the changed clauses, ready for the dashboard."""
    keep: dict[str, int] = {}
    for start in starts:
        if start in graph:
            keep[start] = 0
            for item in impact_of(graph, start, max_depth):
                keep[item.key] = min(keep.get(item.key, item.depth), item.depth)
    nodes = [
        {"id": key, "type": graph.nodes[key]["node_type"], "label": graph.nodes[key]["label"], "depth": depth}
        for key, depth in keep.items()
    ]
    edges = [
        {"source": src, "target": dst, **{k: data[k] for k in ("rel_type", "status", "confidence")}}
        for src, dst, data in graph.edges(data=True)
        if src in keep and dst in keep
    ]
    return {"nodes": nodes, "edges": edges}
