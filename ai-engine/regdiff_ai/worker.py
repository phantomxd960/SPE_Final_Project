"""ai-worker entry point: poll the job queue, run jobs, expose /health.

Stops cleanly on SIGTERM: the current job finishes before the process exits,
so rolling updates never cut a comparison in half.
"""

import json
import logging
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from regdiff_ai import jobs
from regdiff_ai.llm import get_llm_client
from regdiff_ai.pipeline import PermanentJobError, RetryLater, ingest_version, run_comparison
from regdiff_common.config import get_settings
from regdiff_common.db import get_sessionmaker
from regdiff_common.embeddings import get_embedder
from regdiff_common.logging import configure_logging, log_event

log = logging.getLogger("regdiff_ai.worker")

HEARTBEAT_LIMIT_SECONDS = 60


class Worker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.sessions = get_sessionmaker()
        self.embedder = get_embedder()
        self.llm = get_llm_client(self.settings)
        self.stopping = threading.Event()
        self.heartbeat = time.monotonic()

    def run(self) -> None:
        log_event(log, "worker_started", llm=self.llm.name, embedder=self.embedder.name)
        while not self.stopping.is_set():
            self.heartbeat = time.monotonic()
            try:
                worked = self.run_one()
            except Exception:  # database unavailable and similar: keep the loop alive
                log.exception("worker_loop_error", extra={"event": "worker_loop_error"})
                worked = False
            if not worked:
                self.stopping.wait(self.settings.worker_poll_seconds)
        log_event(log, "worker_stopped")

    def run_one(self) -> bool:
        with self.sessions() as session:
            job = jobs.claim_next(session)
            if job is None:
                return False
            started = time.perf_counter()
            fields = {"job_id": job.id, "job_type": job.type, "attempt": job.attempts}
            log_event(log, "job_started", **fields)
            try:
                result = self._dispatch(session, job)
                jobs.complete(session, job)
                log_event(log, "job_done", status="done", duration_ms=_ms(started), **fields, **result)
            except RetryLater as exc:
                session.rollback()
                jobs.retry_later(session, job, str(exc), delay_seconds=5)
                log_event(log, "job_deferred", status="queued", reason=str(exc), **fields)
            except Exception as exc:
                session.rollback()
                permanent = isinstance(exc, PermanentJobError)
                if permanent or job.attempts >= self.settings.worker_max_attempts:
                    jobs.fail(session, job, str(exc))
                    log_event(
                        log,
                        "job_failed",
                        level=logging.ERROR,
                        status="failed",
                        error=str(exc),
                        duration_ms=_ms(started),
                        **fields,
                    )
                else:
                    jobs.retry_later(session, job, str(exc), delay_seconds=2**job.attempts * 5)
                    log_event(log, "job_retry", level=logging.WARNING, status="queued", error=str(exc), **fields)
            return True

    def _dispatch(self, session, job) -> dict:
        if job.type == "ingest_version":
            return ingest_version(session, job.payload["version_id"], self.embedder, self.settings)
        if job.type == "compare":
            return run_comparison(session, job.payload["comparison_id"], self.embedder, self.llm, self.settings)
        raise PermanentJobError(f"Unknown job type '{job.type}'")

    def healthy(self) -> bool:
        return time.monotonic() - self.heartbeat < HEARTBEAT_LIMIT_SECONDS


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _serve_health(worker: Worker, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server naming
            healthy = worker.healthy()
            body = json.dumps({"status": "ok" if healthy else "stalled", "service": "ai-worker"}).encode()
            self.send_response(200 if healthy and self.path.startswith("/health") else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:  # probes are not worth a log line
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    configure_logging("ai-worker")
    worker = Worker()
    server = _serve_health(worker, worker.settings.worker_health_port)
    signal.signal(signal.SIGTERM, lambda *_: worker.stopping.set())
    signal.signal(signal.SIGINT, lambda *_: worker.stopping.set())
    try:
        worker.run()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
