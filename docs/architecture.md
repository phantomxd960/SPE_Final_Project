# Architecture

## Runtime view

```text
 browser ──► Ingress ──► frontend (Nginx, React build)
                    └──► backend (FastAPI) ──► PostgreSQL + pgvector ◄── ai-worker
                             │   writes jobs            ▲    reads jobs, writes results
                             └── documents volume ──────┘
 all pods ──stdout JSON──► Filebeat ──► Logstash ──► Elasticsearch ──► Kibana
 Vault agent ──► /vault/secrets/*.env in backend, ai-worker and postgres pods
```

| Service | Code | Responsibility |
| --- | --- | --- |
| frontend | `frontend/` | Dashboard: upload, side-by-side diff, dependency graph, cited reports, search, build footer |
| backend | `backend/regdiff_api` | REST API, JWT auth, upload validation and storage, job creation, search, graph and report reads, migrations |
| ai-worker | `ai-engine/regdiff_ai` | Clause extraction, alignment, classification, graph rebuild, retrieval, LLM impact reports |
| shared | `shared/regdiff_common` | Models, settings, JSON logging, embeddings, hybrid retrieval, graph traversal |

The backend and the worker never call each other. They share only the database: the backend inserts a row
in `jobs`, and the worker claims it with `SELECT … FOR UPDATE SKIP LOCKED`, so worker replicas scale
without a message broker.

## Comparison pipeline

1. **Ingest** (`ingest_version` job). The parser splits text, Markdown or PDF into clauses by their numbering
   and records the section and page. Every clause is embedded (BGE-small, 384 dimensions) and stored. The
   dependency graph is then rebuilt.
2. **Align**. Passes: same number and same text → same text under another number → same number
   (unless the texts are unrelated, which signals a shift) → greedy best `difflib` similarity ≥ 0.60.
3. **Classify**. Amounts, percentages, durations, dates, numbers and obligation level (must / should / may /
   must not) are extracted from both sides. Any difference makes the clause *substantially changed*, even
   if the wording is 99 % identical. Otherwise the result is *renumbered*, *semantically equivalent*
   (embeddings), *modified*, *added* or *deleted*.
4. **Trace**. From the changed clause, the graph is walked against its edges, up to depth 3:
   regulation clause ← policy clause ← policy ← process / control. An explicit citation ("see clause
   4.2.1") is a **confirmed** edge. A semantic match above the threshold is an **inferred** edge.
5. **Retrieve**. Related policy passages come from a hybrid search: pgvector cosine plus PostgreSQL full-text
   search, merged by reciprocal-rank fusion.
6. **Explain**. The LLM receives numbered evidence (E1, E2, …) and the candidate items as JSON, and must
   answer with JSON that cites evidence ids. The validator rejects unknown ids, invented policies and any
   claim of legal non-compliance. One retry is allowed; after that the report is stored as *unverified*
   with deterministic content.

Whether an item is affected, and whether that link is confirmed or inferred, is always decided by the
graph. The LLM contributes only the wording.

## Data model

`documents` → `document_versions` → `clauses` (text, page, embedding) · `comparisons` → `clause_changes`
(type, word diff, facts) → `impact_reports` (summary, affected, impacts, actions, evidence, verified) ·
`graph_nodes` / `graph_edges` (confirmed or inferred, with evidence clause) · `jobs` · `users`.

Migrations run at backend start-up under a PostgreSQL advisory lock, so only one replica migrates. Every
schema change must be backward-compatible, because old and new pods run side by side during a rolling update.

## Delivery and operations

| Concern | Implementation |
| --- | --- |
| CI/CD | `jenkins/Jenkinsfile`, triggered by the GitHub webhook |
| Images | Multi-stage, non-root, pinned base images, embedding model baked in; tagged with the build number and `latest` |
| Deploy | Ansible `application` role renders `kubernetes/overlays/<dev or vault>` with the build's image tag and waits for the rollout |
| Zero downtime | `maxUnavailable: 0`, readiness probes, `preStop` delay, worker finishes its job on SIGTERM |
| Scaling | HPA: backend 2–5, ai-worker 1–3 replicas at 70 % CPU |
| Secrets | Vault agent (pre-populate only) renders `/vault/secrets/app.env`, which the entrypoint sources |
| Rollback | Smoke test checks the new build number; on failure `scripts/ci/rollback.sh` runs `kubectl rollout undo` |
| Logs | One JSON line per event: `timestamp, service, level, event, request_id, build_number, duration_ms, status, …` |
