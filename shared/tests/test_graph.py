import networkx as nx

from regdiff_common.graph import impact_of, subgraph_view

REG = "reg_clause:REG001#4.2.1"


def build_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    nodes = {
        REG: "reg_clause",
        "policy_clause:POL-TM#3.1": "policy_clause",
        "policy:POL-TM": "policy",
        "process:Transaction Monitoring": "process",
        "policy_clause:POL-KYC#2.1": "policy_clause",
        "policy:POL-KYC": "policy",
        "reg_clause:REG001#5.1": "reg_clause",
    }
    for key, node_type in nodes.items():
        graph.add_node(key, node_type=node_type, label=key)

    def edge(src, dst, rel, status="confirmed", confidence=1.0):
        graph.add_edge(src, dst, rel_type=rel, status=status, confidence=confidence)

    edge("policy_clause:POL-TM#3.1", REG, "REFERENCES")
    edge("policy:POL-TM", "policy_clause:POL-TM#3.1", "DEPENDS_ON")
    edge("process:Transaction Monitoring", "policy:POL-TM", "DEPENDS_ON")
    edge("policy_clause:POL-KYC#2.1", "reg_clause:REG001#5.1", "REFERENCES")
    edge("policy:POL-KYC", "policy_clause:POL-KYC#2.1", "DEPENDS_ON")
    return graph


def test_impact_reaches_policy_and_process_but_not_unrelated_policy():
    items = {item.key: item for item in impact_of(build_graph(), REG, max_depth=3)}
    assert set(items) == {"policy_clause:POL-TM#3.1", "policy:POL-TM", "process:Transaction Monitoring"}
    assert items["process:Transaction Monitoring"].depth == 3
    assert all(item.status == "confirmed" for item in items.values())


def test_depth_limit_is_respected():
    keys = {item.key for item in impact_of(build_graph(), REG, max_depth=2)}
    assert "process:Transaction Monitoring" not in keys


def test_inferred_edge_marks_the_whole_path_inferred():
    graph = build_graph()
    graph.add_edge("policy_clause:POL-KYC#2.1", REG, rel_type="IMPLEMENTS", status="inferred", confidence=0.8)
    items = {item.key: item for item in impact_of(graph, REG)}
    assert items["policy:POL-KYC"].status == "inferred"
    assert items["policy:POL-KYC"].confidence == 0.8
    assert items["policy:POL-TM"].status == "confirmed"


def test_confirmed_path_is_preferred_over_inferred_path():
    graph = build_graph()
    graph.add_edge("policy:POL-TM", REG, rel_type="IMPLEMENTS", status="inferred", confidence=0.9)
    item = next(i for i in impact_of(graph, REG) if i.key == "policy:POL-TM")
    assert item.status == "confirmed"
    assert item.depth == 2


def test_subgraph_view_contains_only_reachable_nodes():
    view = subgraph_view(build_graph(), [REG])
    ids = {node["id"] for node in view["nodes"]}
    assert REG in ids and "policy:POL-KYC" not in ids
    assert all(edge["source"] in ids and edge["target"] in ids for edge in view["edges"])
