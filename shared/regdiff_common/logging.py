"""Structured JSON logging to stdout (Section 5.3).

Every line carries the same core fields so Filebeat -> Logstash ->
Elasticsearch can index them and Kibana can chart them:
timestamp, service, level, event, request_id, build_number, plus any
event-specific fields such as document_id, duration_ms or status.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

from regdiff_common.config import get_settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_RESERVED = set(vars(logging.makeLogRecord({})))


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, build_number: str) -> None:
        super().__init__()
        self.service = service
        self.build_number = build_number

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "service": self.service,
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", None) or record.getMessage(),
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "build_number": self.build_number,
        }
        for key, value in vars(record).items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(service: str) -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service, settings.build_number))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    # Uvicorn's own access log is replaced by our request middleware.
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields) -> None:
    """Log one structured event: `log_event(log, "job_done", job_id=3, duration_ms=120)`."""
    logger.log(level, event, extra={"event": event, **fields})
