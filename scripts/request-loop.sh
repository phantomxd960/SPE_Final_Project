#!/usr/bin/env bash
# Live-patching proof (DEV-14): keep calling the API during a rolling update and
# count failures. Run it, push a change, watch Jenkins deploy, then press Ctrl+C.
#   scripts/request-loop.sh http://regulationdiff.localhost/api/version
set -uo pipefail

url="${1:-http://regulationdiff.localhost/api/version}"
ok=0
failed=0
last_build=""

summary() {
  echo
  echo "Requests: $((ok + failed))  ok: ${ok}  failed: ${failed}"
  exit 0
}
trap summary INT

while true; do
  if body="$(curl -fsS --max-time 2 "$url" 2>/dev/null)"; then
    ok=$((ok + 1))
    build="$(sed -n 's/.*"build_number":"\([^"]*\)".*/\1/p' <<<"$body")"
    if [ -n "$build" ] && [ "$build" != "$last_build" ]; then
      echo "$(date +%T) now serving build ${build}"
      last_build="$build"
    fi
  else
    failed=$((failed + 1))
    echo "$(date +%T) request failed"
  fi
  sleep 0.2
done
