import time

import pytest

from regdiff_ai import worker as worker_module
from regdiff_ai.worker import Worker
from regdiff_common.config import get_settings
from regdiff_common.embeddings import get_embedder


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    """Never depend on a developer's .env (real model, real API key)."""
    monkeypatch.setenv("EMBEDDINGS_MODE", "mock")
    monkeypatch.setenv("LLM_MODE", "mock")
    get_settings.cache_clear()
    get_embedder.cache_clear()
    yield
    get_settings.cache_clear()
    get_embedder.cache_clear()


def test_idle_worker_is_healthy_only_while_polling():
    worker = Worker()
    assert worker.healthy()
    worker.heartbeat = time.monotonic() - worker_module.IDLE_LIMIT_SECONDS - 1
    assert not worker.healthy()


def test_long_running_job_is_not_mistaken_for_a_hung_worker():
    worker = Worker()
    worker.heartbeat = time.monotonic() - 300  # the loop has not come round for 5 minutes...
    worker.job_started = time.monotonic() - 240  # ...because a comparison has run for 4 minutes
    assert worker.healthy()


def test_job_over_its_time_budget_is_unhealthy():
    worker = Worker()
    worker.job_started = time.monotonic() - worker_module.JOB_LIMIT_SECONDS - 1
    assert not worker.healthy()
