"""Generate CPU load on the backend so the HPA scales it (DEV-13).

    python scripts/load_test.py --url http://regulationdiff.localhost:8880 --seconds 180 --workers 20
    kubectl -n regulationdiff get hpa -w          # in another terminal

Uses only the standard library. Semantic search embeds every query, so it is
CPU-heavy enough to push the backend over the 70 percent target.
"""

import argparse
import json
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

QUERIES = [
    "reporting threshold for cash transactions",
    "beneficial owner identification",
    "record retention period",
    "linked transactions within seven days",
    "training on reporting obligations",
    "electronic submission of reports",
]


def login(base: str, email: str, password: str) -> str:
    request = urllib.request.Request(
        f"{base}/api/auth/login",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)["access_token"]


def worker(base: str, token: str, deadline: float, stats: dict, lock: threading.Lock) -> None:
    while time.monotonic() < deadline:
        query = urllib.parse.urlencode({"q": random.choice(QUERIES), "limit": 10})
        request = urllib.request.Request(f"{base}/api/search?{query}", headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                response.read()
            key = "ok"
        except urllib.error.HTTPError as error:
            key = f"http_{error.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            key = type(getattr(error, "reason", error)).__name__
        with lock:
            stats[key] = stats.get(key, 0) + 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://regulationdiff.localhost:8880")
    parser.add_argument("--email", default="admin@regulationdiff.local")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()

    token = login(args.url, args.email, args.password)
    stats, lock = {"ok": 0}, threading.Lock()
    deadline = time.monotonic() + args.seconds
    threads = [
        threading.Thread(target=worker, args=(args.url, token, deadline, stats, lock), daemon=True)
        for _ in range(args.workers)
    ]
    for thread in threads:
        thread.start()
    started = time.monotonic()
    while any(thread.is_alive() for thread in threads):
        time.sleep(5)
        elapsed = time.monotonic() - started
        failures = {k: v for k, v in stats.items() if k != "ok"}
        print(f"{elapsed:5.0f}s  ok={stats['ok']}  rate={stats['ok'] / elapsed:.1f}/s  failures={failures}")
    print(f"Done: {stats}")


if __name__ == "__main__":
    main()
