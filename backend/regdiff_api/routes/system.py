"""Health probes and build information (UI-6, DEV-8)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from regdiff_api.deps import DbSession
from regdiff_api.schemas import VersionInfo
from regdiff_common.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def liveness() -> dict:
    """Liveness: the process is up. Does not touch the database."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: DbSession) -> JSONResponse:
    """Readiness: the pod may receive traffic only when the database answers."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unavailable", "database": "down"}, status_code=503)
    return JSONResponse({"status": "ok", "database": "up"})


@router.get("/api/version", response_model=VersionInfo)
def version() -> VersionInfo:
    settings = get_settings()
    return VersionInfo(
        service="backend",
        build_number=settings.build_number,
        git_commit=settings.git_commit,
        build_time=settings.build_time,
    )
