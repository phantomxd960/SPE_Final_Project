"""Document storage on a persistent volume, behind a tiny interface so MinIO
could replace it later without touching the routes."""

import hashlib
import re
from pathlib import Path

from regdiff_common.config import get_settings

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(name: str) -> str:
    return _UNSAFE.sub("_", Path(name).name).strip("._") or "document"


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_document(doc_code: str, version_label: str, file_name: str, content: bytes) -> str:
    directory = Path(get_settings().storage_dir) / safe_name(doc_code) / safe_name(version_label)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / safe_name(file_name)
    path.write_bytes(content)
    return str(path)
