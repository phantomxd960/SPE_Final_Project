"""Request id + one structured log line per request (the API rows in Kibana)."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from regdiff_common.logging import log_event, request_id_var

log = logging.getLogger("regdiff_api.http")

QUIET_PATHS = ("/health",)  # probes run every few seconds; keep them out of Kibana


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            if not request.url.path.startswith(QUIET_PATHS):
                log_event(
                    log,
                    "http_request",
                    method=request.method,
                    path=request.url.path,
                    status=status,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )
            request_id_var.reset(token)
