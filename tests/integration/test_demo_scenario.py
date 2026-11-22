"""The full demonstration scenario of SRS Section 11, end to end in mock mode:
upload -> ingest -> compare -> classify -> graph -> cited impact report."""

import pytest


@pytest.fixture
def demo(client, auth, upload, run_worker):
    old = upload(
        "regulations/REG001_v1.0.md", doc_code="REG001", title="Transaction Reporting Regulation", version_label="1.0"
    )
    new = upload("regulations/REG001_v2.0.md", doc_code="REG001", version_label="2.0")
    upload(
        "policies/POL-TM_transaction_monitoring.md",
        doc_code="POL-TM",
        title="Transaction Monitoring Policy",
        doc_type="policy",
    )
    upload(
        "policies/POL-RPT_regulatory_reporting.md",
        doc_code="POL-RPT",
        title="Regulatory Reporting Policy",
        doc_type="policy",
    )
    upload(
        "policies/POL-KYC_know_your_customer.md",
        doc_code="POL-KYC",
        title="Know Your Customer Policy",
        doc_type="policy",
    )
    run_worker()

    response = client.post(
        "/api/comparisons",
        headers=auth,
        json={"old_version_id": old["version"]["id"], "new_version_id": new["version"]["id"]},
    )
    comparison_id = response.json()["id"]
    run_worker()
    changes = client.get(f"/api/comparisons/{comparison_id}/changes", headers=auth).json()
    return comparison_id, {(c["new_clause"] or c["old_clause"])["clause_number"]: c for c in changes}


def test_changes_are_classified(demo):
    _, changes = demo
    assert changes["4.2.1"]["change_type"] == "substantially_changed"
    assert changes["4.2.1"]["numeric_changes"] == [{"kind": "amount", "old": ["EUR 10,000"], "new": ["EUR 5,000"]}]
    assert changes["4.2.2"]["change_type"] == "substantially_changed"  # should -> must
    assert changes["4.2.2"]["numeric_changes"][0]["kind"] == "obligation"
    assert changes["3.2"]["change_type"] == "added"
    assert changes["3.3"]["change_type"] == "renumbered"
    assert changes["4.4"]["change_type"] == "added"
    assert changes["6.1"]["change_type"] == "modified"
    assert "4.1" not in changes  # unchanged clauses are hidden


def test_graph_links_the_changed_clause_to_the_right_policies(client, auth, demo):
    comparison_id, _ = demo
    graph = client.get(f"/api/graph/{comparison_id}", headers=auth).json()
    ids = {node["id"] for node in graph["nodes"]}
    assert {"policy:POL-TM", "policy:POL-RPT", "process:Transaction Monitoring"} <= ids
    assert "policy:POL-KYC" not in ids  # the unrelated policy is left out


def test_impact_report_is_verified_and_cites_stored_clauses(client, auth, demo):
    _, changes = demo
    report = client.get(f"/api/reports/{changes['4.2.1']['report_id']}", headers=auth).json()
    assert report["verified"] is True
    assert "not legal advice" in report["confirmed"]["disclaimer"]

    affected = {item["id"]: item for item in report["affected"]}
    assert affected["policy:POL-TM"]["relation"] == "confirmed"
    assert affected["policy:POL-RPT"]["relation"] == "confirmed"
    assert "policy:POL-KYC" not in affected

    evidence = {item["id"]: item for item in report["evidence"]}
    new_clause = next(e for e in evidence.values() if e["role"] == "new_clause")
    assert (new_clause["doc_code"], new_clause["version_label"], new_clause["clause_number"], new_clause["page"]) == (
        "REG001",
        "2.0",
        "4.2.1",
        3,
    )
    cited = set(report["confirmed"]["evidence_ids"])
    for group in (report["actions"], report["impacts"]):
        for entry in group:
            cited.update(entry["evidence_ids"])
    assert cited <= set(evidence)  # every citation points at supplied evidence

    source = client.get(f"/api/clauses/{new_clause['clause_id']}", headers=auth).json()
    assert "EUR 5,000" in source["text"]


def test_report_downloads_as_json(client, auth, demo):
    _, changes = demo
    response = client.get(f"/api/reports/{changes['4.2.1']['report_id']}?download=true", headers=auth)
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.json()["verified"] is True
