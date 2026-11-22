"""Fixtures for the API and end-to-end tests, which need PostgreSQL with pgvector.

Set TEST_DATABASE_URL, for example:
    postgresql+psycopg://regulationdiff:regulationdiff@localhost:5433/regulationdiff_test
The database is wiped at the start of the session. Without the variable these
tests are skipped, so the unit tests still run anywhere.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
SAMPLES = Path(__file__).resolve().parents[1] / "samples"

if TEST_DATABASE_URL:
    os.environ.update(
        DATABASE_URL=TEST_DATABASE_URL,
        LLM_MODE="mock",
        EMBEDDINGS_MODE="mock",
        GRAPH_INFERRED_THRESHOLD="0.6",
        JWT_SECRET="test-secret",
        ADMIN_EMAIL="admin@test.local",
        ADMIN_PASSWORD="test-password",
        BUILD_NUMBER="42",
        GIT_COMMIT="abc1234",
    )

TABLES = (
    "impact_reports, clause_changes, comparisons, graph_edges, graph_nodes, "
    "clauses, document_versions, documents, jobs"
)


@pytest.fixture(scope="session")
def database(tmp_path_factory) -> Iterator[None]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set")
    os.environ["STORAGE_DIR"] = str(tmp_path_factory.mktemp("documents"))

    from sqlalchemy import text

    from regdiff_common.config import get_settings
    from regdiff_common.db import get_engine, get_sessionmaker
    from regdiff_common.embeddings import get_embedder

    for cached in (get_settings, get_engine, get_sessionmaker, get_embedder):
        cached.cache_clear()
    with get_engine().begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))

    from regdiff_api.bootstrap import bootstrap

    bootstrap()
    yield
    get_engine().dispose()


@pytest.fixture
def clean_db(database) -> None:
    from sqlalchemy import text

    from regdiff_common.db import get_engine

    with get_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(clean_db):
    from fastapi.testclient import TestClient

    from regdiff_api.main import create_app

    with TestClient(create_app(run_bootstrap=False)) as test_client:
        yield test_client


@pytest.fixture
def auth(client) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "test-password"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def upload(client, auth):
    """Upload a file from samples/ (or raw content) and return the JSON response."""

    def _upload(
        path: str | None = None,
        *,
        content: bytes | None = None,
        file_name: str = "doc.md",
        doc_code: str,
        title: str = "Test document",
        doc_type: str = "regulation",
        version_label: str = "1.0",
        expect: int = 201,
    ) -> dict:
        if path is not None:
            file_path = SAMPLES / path
            content, file_name = file_path.read_bytes(), file_path.name
        response = client.post(
            "/api/documents",
            headers=auth,
            files={"file": (file_name, content, "text/markdown")},
            data={"doc_code": doc_code, "title": title, "doc_type": doc_type, "version_label": version_label},
        )
        assert response.status_code == expect, response.text
        return response.json()

    return _upload


@pytest.fixture
def run_worker():
    """Process every queued job in-process, exactly as the ai-worker would."""

    def _run(max_jobs: int = 50) -> int:
        from regdiff_ai.worker import Worker

        worker = Worker()
        processed = 0
        while processed < max_jobs and worker.run_one():
            processed += 1
        return processed

    return _run
