"""One error shape for every failure: {code, message, request_id} (Section 7)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from regdiff_common.logging import log_event, request_id_var

log = logging.getLogger(__name__)

_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
}


class ApiError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.status, self.message, self.code = status, message, code or _CODES.get(status, "error")


def _body(code: str, message: str) -> dict:
    return {"code": code, "message": message, "request_id": request_id_var.get()}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(_body(_CODES.get(exc.status_code, "error"), str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in exc.errors())
        return JSONResponse(_body("validation_error", problems), status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        log_event(log, "unhandled_error", level=logging.ERROR, error=repr(exc))
        return JSONResponse(_body("internal_error", "Unexpected server error"), status_code=500)
