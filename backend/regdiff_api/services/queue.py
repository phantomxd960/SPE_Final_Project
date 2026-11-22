"""Enqueue work for the ai-worker (PostgreSQL job table)."""

from sqlalchemy.orm import Session

from regdiff_common.models import Job


def enqueue(session: Session, job_type: str, **payload) -> Job:
    job = Job(type=job_type, status="queued", payload=payload, attempts=0)
    session.add(job)
    session.flush()
    return job
