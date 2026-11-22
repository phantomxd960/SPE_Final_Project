#!/usr/bin/env bash
# Roll every application Deployment back to its previous ReplicaSet (DEV-16).
set -uo pipefail
namespace="${NAMESPACE:-regulationdiff}"
for deployment in backend ai-worker frontend; do
  echo "Rolling back deployment/${deployment}"
  kubectl -n "$namespace" rollout undo "deployment/${deployment}" || true
done
for deployment in backend ai-worker frontend; do
  kubectl -n "$namespace" rollout status "deployment/${deployment}" --timeout=180s || true
done
