#!/usr/bin/env bash
# Throwaway pgvector database for the pipeline's API and integration tests.
#   url=$(scripts/ci/test-db.sh start)   ...   scripts/ci/test-db.sh stop
# Works whether Jenkins runs directly on the host or inside a container
# (then the Jenkins container joins the database's network).
set -euo pipefail

NAME="rd-ci-db-$(echo "${BUILD_TAG:-local}" | tr -c 'a-zA-Z0-9_.-' '-')"
NETWORK="${NAME}-net"
in_container() { [ -f /.dockerenv ]; }

case "${1:-}" in
  start)
    docker network create "$NETWORK" >/dev/null
    docker run -d --name "$NAME" --network "$NETWORK" --network-alias testdb \
      -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
      -p 127.0.0.1::5432 pgvector/pgvector:pg16 >/dev/null
    if in_container; then
      docker network connect "$NETWORK" "$(hostname)"
      address="testdb:5432"
    else
      address="127.0.0.1:$(docker port "$NAME" 5432/tcp | head -n1 | cut -d: -f2)"
    fi
    # The image restarts PostgreSQL once after initialisation; wait for the final server.
    for _ in $(seq 1 60); do
      if docker logs "$NAME" 2>&1 | grep -q "PostgreSQL init process complete" \
        && docker exec "$NAME" pg_isready -U test -d test >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    echo "postgresql+psycopg://test:test@${address}/test"
    ;;
  stop)
    if in_container; then docker network disconnect "$NETWORK" "$(hostname)" >/dev/null 2>&1 || true; fi
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true
    ;;
  *)
    echo "usage: $0 start|stop" >&2
    exit 2
    ;;
esac
