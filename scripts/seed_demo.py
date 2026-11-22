"""Load the demonstration data (SRS Section 11) and start the REG001 comparison.

    python scripts/seed_demo.py --url http://localhost:3000
    python scripts/seed_demo.py --url http://regulationdiff.localhost --password <admin password>

Standard library only. Safe to re-run: existing versions are skipped.
"""

import argparse
import json
import mimetypes
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
DOCUMENTS = [
    (
        "regulations/REG001_v1.0.md",
        "REG001",
        "Transaction Reporting and Record-Keeping Regulation",
        "regulation",
        "1.0",
        "2025-01-01",
    ),
    (
        "regulations/REG001_v2.0.md",
        "REG001",
        "Transaction Reporting and Record-Keeping Regulation",
        "regulation",
        "2.0",
        "2026-07-01",
    ),
    ("policies/POL-TM_transaction_monitoring.md", "POL-TM", "Transaction Monitoring Policy", "policy", "1.0", None),
    ("policies/POL-RPT_regulatory_reporting.md", "POL-RPT", "Regulatory Reporting Policy", "policy", "1.0", None),
    ("policies/POL-KYC_know_your_customer.md", "POL-KYC", "Know Your Customer Policy", "policy", "1.0", None),
]


class Api:
    def __init__(self, base: str) -> None:
        self.base, self.token = base.rstrip("/"), None

    def call(self, method: str, path: str, body: bytes | None = None, content_type: str | None = None):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(f"{self.base}{path}", data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    def json(self, method: str, path: str, payload: dict):
        return self.call(method, path, json.dumps(payload).encode(), "application/json")

    def upload(self, fields: dict, file_path: Path):
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in fields.items():
            if value is not None:
                parts.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
                )
        mime = mimetypes.guess_type(file_path.name)[0] or "text/markdown"
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n".encode()
            + file_path.read_bytes()
            + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode())
        return self.call("POST", "/api/documents", b"".join(parts), f"multipart/form-data; boundary={boundary}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--email", default="admin@regulationdiff.local")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()

    api = Api(args.url)
    api.token = api.json("POST", "/api/auth/login", {"email": args.email, "password": args.password})["access_token"]

    for path, code, title, doc_type, version, effective in DOCUMENTS:
        fields = {
            "doc_code": code,
            "title": title,
            "doc_type": doc_type,
            "version_label": version,
            "effective_date": effective,
            "authority": "Financial Conduct Board (fictional)",
        }
        try:
            api.upload(fields, SAMPLES / path)
            print(f"uploaded  {code} v{version}")
        except urllib.error.HTTPError as error:
            if error.code != 409:
                raise
            print(f"exists    {code} v{version}")

    print("waiting for the ai-worker to process the documents ...")
    for _ in range(120):
        documents = api.call("GET", "/api/documents")
        statuses = [v["status"] for d in documents for v in d["versions"]]
        if all(status in ("ready", "failed") for status in statuses):
            break
        time.sleep(2)

    reg = next(d for d in documents if d["doc_code"] == "REG001")
    versions = {v["version_label"]: v["id"] for v in reg["versions"]}
    comparison = api.json(
        "POST", "/api/comparisons", {"old_version_id": versions["1.0"], "new_version_id": versions["2.0"]}
    )
    print(f"comparison started: {args.url.rstrip('/')}/comparisons/{comparison['id']}")


if __name__ == "__main__":
    main()
