"""PostgreSQL job queue: `SELECT ... FOR UPDATE SKIP LOCKED` lets several
worker replicas share the queue without a message broker."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from regdiff_common.models import Comparison, DocumentVersion, Job

STALE_AFTER = timedelta(minutes=10)

_CLAIM = text(
    """
    UPDATE jobs SET status = 'running', locked_at = now(), attempts = attempts + 1
    WHERE id = (
        SELECT id FROM jobs
        WHERE (status = 'queued' AND run_after <= now())
           OR (status = 'running' AND locked_at < now() - make_interval(secs => :stale_seconds))
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id
    """
)


def claim_next(session: Session) -> Job | None:
    """Lock the oldest runnable job; a job left 'running' by a crashed worker is picked up again."""
    job_id = session.execute(_CLAIM, {"stale_seconds": STALE_AFTER.total_seconds()}).scalar()
    session.commit()
    return session.get(Job, job_id) if job_id else None


def complete(session: Session, job: Job) -> None:
    job.status, job.error, job.finished_at = "done", None, datetime.now(UTC)
    session.commit()


def retry_later(session: Session, job: Job, reason: str, delay_seconds: float) -> None:
    job.status, job.error = "queued", reason
    job.run_after = datetime.now(UTC) + timedelta(seconds=delay_seconds)
    session.commit()


def fail(session: Session, job: Job, reason: str) -> None:
    """Fail the job and the object it was working on, without touching other jobs (ING-5)."""
    job.status, job.error, job.finished_at = "failed", reason, datetime.now(UTC)
    if job.type == "ingest_version":
        version = session.get(DocumentVersion, job.payload.get("version_id"))
        if version:
            version.status, version.error = "failed", reason
    elif job.type == "compare":
        comparison = session.get(Comparison, job.payload.get("comparison_id"))
        if comparison:
            comparison.status, comparison.error = "failed", reason
    session.commit()
