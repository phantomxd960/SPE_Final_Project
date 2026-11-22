# RegulationDiff

RegulationDiff compares two versions of a financial regulation, finds the clauses that changed, traces them
to the internal policies, processes and controls they affect, and writes an evidence-cited impact report.
It is delivered through an automated GitHub → Jenkins → Docker Hub → Ansible → Kubernetes pipeline, with
logs in ELK and secrets in Vault (CSE 816 Software Production Engineering, final project).

> A deterministic pipeline decides **what** changed. The LLM only **explains** it, and every statement it
> makes must cite a stored clause, or the report is marked unverified.

## Repository layout

```text
regulationdiff/
├── frontend/            React + Vite dashboard, served by Nginx (Dockerfile, nginx/)
├── backend/             FastAPI service: auth, uploads, comparisons, search, graph, reports
│   └── regdiff_api/       routes/, core/ (security, errors, middleware), services/, migrations/
├── ai-engine/           ai-worker: job queue consumer
│   └── regdiff_ai/        ingestion/ (parser), analysis/ (align, classify, facts), llm/, graph_builder, pipeline
├── shared/              regdiff_common: config, JSON logging, models, embeddings, retrieval, graph traversal
├── tests/               api/ and integration/ tests against PostgreSQL (unit tests live in each package)
├── samples/             demo regulation REG001 v1.0/v2.0 and three internal policies
├── docker/              docker-compose.yml for local development, shared container entrypoint
├── jenkins/             Jenkinsfile, plus a ready-made Jenkins image (Dockerfile, plugins, compose)
├── ansible/             playbooks/ (site, deploy) and roles/ (common, docker, kubernetes, vault, monitoring, application)
├── kubernetes/          Kustomize base/, overlays/ (dev, vault) and components/vault
├── monitoring/          Filebeat, Logstash pipeline, ELK manifests, Kibana setup
├── scripts/             seed_demo.py, load_test.py, request-loop.sh, ci/ helpers
└── docs/                requirements (SRS), architecture, runbook
```

## Quick start (Docker Compose)

```bash
cp .env.example .env                                     # adjust passwords; LLM_MODE=mock needs no key
docker compose -f docker/docker-compose.yml up --build   # first build downloads the embedding model
python scripts/seed_demo.py --url http://localhost:3000 --password <ADMIN_PASSWORD>
```

Open http://localhost:3000 and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`. The API docs are at
http://localhost:8000/api/docs. Add `--profile elk` to the compose command for Elasticsearch, Logstash,
Kibana (http://localhost:5601) and Filebeat; then run `monitoring/kibana/setup.sh`.

## Development without containers

```bash
python -m venv .venv && . .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e "shared[dev]" -e "ai-engine[dev]" -e "backend[dev]"
docker run -d --name rd-db -p 5432:5432 -e POSTGRES_USER=regulationdiff \
  -e POSTGRES_PASSWORD=regulationdiff pgvector/pgvector:pg16
EMBEDDINGS_MODE=mock uvicorn regdiff_api.main:app --reload    # terminal 1, applies migrations
EMBEDDINGS_MODE=mock regdiff-worker                           # terminal 2
cd frontend && npm install && npm run dev                     # terminal 3, http://localhost:5173
```

## Tests and lint

| Command | What it covers |
| --- | --- |
| `pytest shared/tests ai-engine/tests backend/tests` | Unit: parsing, facts, alignment, classification, validator, graph, RRF, security |
| `TEST_DATABASE_URL=postgresql+psycopg://... pytest tests` | API and the full SRS Section 11 demo scenario against PostgreSQL |
| `ruff check . && ruff format --check .` | Python lint and formatting |
| `cd frontend && npm run lint && npm test` | ESLint and Vitest |

All tests run in mock mode (`LLM_MODE=mock`, `EMBEDDINGS_MODE=mock`): no API key and no network.

## Delivery pipeline

A push to GitHub triggers [jenkins/Jenkinsfile](jenkins/Jenkinsfile) through the webhook:
checkout → lint → unit tests → build three images → API/integration tests on a throwaway PostgreSQL →
Trivy scan (fixable critical findings fail the build) → push to Docker Hub with the build number and `latest`
→ `ansible-playbook playbooks/deploy.yml` → smoke test (the API must report the new build number) →
automatic `kubectl rollout undo` if anything after the deploy fails.

Setting up Jenkins (configured as code), the webhook relay, the cluster, Vault and ELK, pausing the
environment, and the demonstration script are in [docs/runbook.md](docs/runbook.md). Design decisions are in
[docs/architecture.md](docs/architecture.md), requirements in [docs/requirements.md](docs/requirements.md).

## Measured results

| What | Result |
| --- | --- |
| Change detection on 31 hand-labelled clause pairs ([docs/evaluation.md](docs/evaluation.md)) | precision 1.00, recall 1.00, alignment 1.00, exact type 0.94 |
| Push to running deployment | about 12 minutes, started by the GitHub webhook |
| Rolling update under a request loop | 450 requests, 0 failed |
| Autoscaling under load (`scripts/load_test.py`) | backend 2 → 5 replicas, about 32 searches/s, 99.85 % success |
| LLM impact reports (Gemini) | every report verified: all citations point at supplied clauses |

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | `localhost`, `5432`, `regulationdiff`… | PostgreSQL (pgvector) |
| `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | dev values | Authentication; the admin user is created at start-up |
| `LLM_MODE`, `LLM_MODEL`, `LLM_API_KEY` | `mock` | `mock`, `openai` or `gemini` |
| `EMBEDDINGS_MODE` | `mock` (images: `fastembed`) | BGE-small via fastembed, or deterministic hashing |
| `GRAPH_INFERRED_THRESHOLD` | `0.75` | Minimum similarity for an inferred policy → clause edge |
| `BUILD_NUMBER`, `GIT_COMMIT`, `BUILD_TIME` | set by the pipeline | Shown in the dashboard footer |

No secret is ever committed: `.env` is git-ignored, Jenkins holds the Docker Hub credentials, and in
Kubernetes the Vault agent injects secrets at pod start.
