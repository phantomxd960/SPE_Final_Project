DOC_V1 = b"# Test\n\n1.1 Firms must report payments of EUR 10,000 or more.\n1.2 Reports go to the authority.\n"
DOC_V2 = b"# Test\n\n1.1 Firms must report payments of EUR 5,000 or more.\n1.2 Reports go to the authority.\n"


def test_upload_creates_document_version_and_job(client, auth, upload):
    body = upload(content=DOC_V1, doc_code="tst-1")
    assert body["document"]["doc_code"] == "TST-1"
    assert body["version"]["status"] == "queued"
    job = client.get(f"/api/jobs/{body['job_id']}", headers=auth).json()
    assert job["type"] == "ingest_version" and job["status"] == "queued"


def test_duplicate_version_label_and_identical_file_are_rejected(upload):
    upload(content=DOC_V1, doc_code="TST")
    upload(content=DOC_V2, doc_code="TST", version_label="1.0", expect=409)
    upload(content=DOC_V1, doc_code="TST", version_label="2.0", expect=409)


def test_unsupported_file_type_and_bad_code_are_rejected(upload):
    upload(content=b"x", file_name="evil.exe", doc_code="TST", expect=422)
    upload(content=DOC_V1, doc_code="bad code!", expect=422)


def test_worker_ingests_versions_into_clauses(client, auth, upload, run_worker):
    version_id = upload(content=DOC_V1, doc_code="TST")["version"]["id"]
    assert run_worker() == 1
    clauses = client.get(f"/api/versions/{version_id}/clauses", headers=auth).json()
    assert [c["clause_number"] for c in clauses] == ["1.1", "1.2"]
    documents = client.get("/api/documents", headers=auth).json()
    assert documents[0]["versions"][0]["status"] == "ready"
    assert documents[0]["versions"][0]["clause_count"] == 2


def test_comparison_needs_two_versions_of_one_document(client, auth, upload):
    a = upload(content=DOC_V1, doc_code="AAA")["version"]["id"]
    b = upload(content=DOC_V1, doc_code="BBB")["version"]["id"]
    response = client.post("/api/comparisons", headers=auth, json={"old_version_id": a, "new_version_id": b})
    assert response.status_code == 422
    response = client.post("/api/comparisons", headers=auth, json={"old_version_id": a, "new_version_id": a})
    assert response.status_code == 422


def test_comparison_classifies_changes(client, auth, upload, run_worker):
    old = upload(content=DOC_V1, doc_code="TST", version_label="1.0")["version"]["id"]
    new = upload(content=DOC_V2, doc_code="TST", version_label="2.0")["version"]["id"]
    comparison = client.post("/api/comparisons", headers=auth, json={"old_version_id": old, "new_version_id": new})
    assert comparison.status_code == 201
    run_worker()

    detail = client.get(f"/api/comparisons/{comparison.json()['id']}", headers=auth).json()
    assert detail["status"] == "done"
    assert detail["counts"] == {"substantially_changed": 1, "unchanged": 1}

    changes = client.get(f"/api/comparisons/{detail['id']}/changes", headers=auth).json()
    assert len(changes) == 1  # unchanged clauses hidden by default
    change = changes[0]
    assert change["new_clause"]["clause_number"] == "1.1"
    assert change["numeric_changes"] == [{"kind": "amount", "old": ["EUR 10,000"], "new": ["EUR 5,000"]}]
    assert change["report_id"] is not None


def test_search_finds_clauses(client, auth, upload, run_worker):
    upload(content=DOC_V1, doc_code="TST")
    run_worker()
    hits = client.get("/api/search", params={"q": "report payments"}, headers=auth).json()
    assert hits and hits[0]["doc_code"] == "TST"
    filtered = client.get("/api/search", params={"q": "report payments", "doc_type": "policy"}, headers=auth).json()
    assert filtered == []
