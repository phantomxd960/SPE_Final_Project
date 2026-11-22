"""FastAPI application factory. Run with `uvicorn regdiff_api.main:app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from regdiff_api.bootstrap import bootstrap
from regdiff_api.core.errors import register_error_handlers
from regdiff_api.core.middleware import RequestContextMiddleware
from regdiff_api.routes import auth, comparisons, documents, insights, system
from regdiff_common.config import get_settings
from regdiff_common.logging import configure_logging, log_event

log = logging.getLogger("regdiff_api")


def create_app(run_bootstrap: bool = True) -> FastAPI:
    configure_logging("backend")
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if run_bootstrap:
            bootstrap()
        log_event(log, "backend_started", git_commit=settings.git_commit, llm_mode=settings.llm_mode)
        yield

    app = FastAPI(
        title="RegulationDiff API",
        version=settings.build_number,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    for module in (system, auth, documents, comparisons, insights):
        app.include_router(module.router)
    return app


app = create_app()
