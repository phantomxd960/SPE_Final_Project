#!/usr/bin/env bash
# Pause or resume the whole RegulationDiff environment without losing data.
#   scripts/environment.sh stop    scale app, ELK and Vault to zero; stop Jenkins and the webhook relay
#   scripts/environment.sh start   bring everything back (run from WSL so Vault can be re-seeded)
#   SKIP_ELK=1 scripts/environment.sh start   ... without ELK, saving about 2.5 GB of memory
# Databases, Jenkins history and Docker Hub images are kept; nothing is deleted.
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

scale() {  # scale <namespace> <kind/name> <replicas>
  kubectl -n "$1" scale "$2" --replicas="$3" >/dev/null 2>&1 && echo "  $1/$2 -> $3"
}

case "${1:-}" in
  stop)
    echo "Scaling the application to zero"
    for d in frontend backend ai-worker; do scale regulationdiff "deployment/$d" 0; done
    scale regulationdiff statefulset/postgres 0
    echo "Scaling ELK to zero"
    for d in kibana logstash; do scale logging "deployment/$d" 0; done
    scale logging statefulset/elasticsearch 0
    # A DaemonSet cannot be scaled: park it on a node label that does not exist.
    kubectl -n logging patch daemonset filebeat --type=merge \
      -p '{"spec":{"template":{"spec":{"nodeSelector":{"regulationdiff/paused":"true"}}}}}' >/dev/null 2>&1 \
      && echo "  logging/daemonset/filebeat -> paused"
    echo "Scaling Vault to zero (dev mode: secrets are re-seeded on start)"
    scale vault statefulset/vault 0
    scale vault deployment/vault-agent-injector 0
    echo "Stopping Jenkins and the webhook relay"
    docker compose -f "$root/jenkins/docker-compose.yml" stop >/dev/null 2>&1 && echo "  jenkins, webhook-relay stopped"
    docker compose -f "$root/docker/docker-compose.yml" stop >/dev/null 2>&1
    echo "Done. Resume with: scripts/environment.sh start"
    ;;
  start)
    echo "Starting Vault and re-seeding its secrets"
    scale vault deployment/vault-agent-injector 1
    scale vault statefulset/vault 1
    kubectl -n vault wait --for=condition=Ready pod/vault-0 --timeout=300s >/dev/null
    bash "$root/scripts/ansible.sh" site.yml --tags vault
    echo "Starting the application"
    scale regulationdiff statefulset/postgres 1
    kubectl -n regulationdiff rollout status statefulset/postgres --timeout=300s >/dev/null
    for d in backend frontend; do scale regulationdiff "deployment/$d" 2; done
    scale regulationdiff deployment/ai-worker 1
    if [ "${SKIP_ELK:-0}" != 1 ]; then
      echo "Starting ELK"
      scale logging statefulset/elasticsearch 1
      for d in logstash kibana; do scale logging "deployment/$d" 1; done
      kubectl -n logging patch daemonset filebeat --type=json \
        -p '[{"op":"remove","path":"/spec/template/spec/nodeSelector"}]' >/dev/null 2>&1
    fi
    echo "Starting Jenkins and the webhook relay"
    docker compose -f "$root/jenkins/docker-compose.yml" start >/dev/null 2>&1
    for d in backend ai-worker frontend; do
      kubectl -n regulationdiff rollout status "deployment/$d" --timeout=300s >/dev/null
    done
    echo "Ready: http://regulationdiff.localhost:8880  (Jenkins :8090, Kibana :30601)"
    ;;
  *)
    echo "usage: $0 stop|start" >&2
    exit 2
    ;;
esac
