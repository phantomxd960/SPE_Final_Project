#!/usr/bin/env bash
# Post-deploy smoke test (DEV-16): the backend must report the new build number
# and be ready. Exits non-zero otherwise, which triggers the pipeline's rollback.
#   scripts/ci/smoke-test.sh <expected-build-number>
set -euo pipefail

expected="${1:?usage: smoke-test.sh <expected-build-number>}"
namespace="${NAMESPACE:-regulationdiff}"
port="${SMOKE_PORT:-18000}"

kubectl -n "$namespace" port-forward svc/backend "${port}:8000" >/dev/null 2>&1 &
forward_pid=$!
trap 'kill "$forward_pid" 2>/dev/null || true' EXIT

version=""
for _ in $(seq 1 60); do
  version="$(curl -fs "http://127.0.0.1:${port}/api/version" || true)"
  if grep -q "\"build_number\":\"${expected}\"" <<<"$version" \
    && curl -fs "http://127.0.0.1:${port}/health/ready" >/dev/null; then
    echo "Smoke test passed: ${version}"
    exit 0
  fi
  sleep 2
done

echo "Smoke test failed: expected build ${expected}, got: ${version:-no response}" >&2
exit 1
