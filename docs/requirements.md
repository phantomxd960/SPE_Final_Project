# RegulationDiff – Software Requirements Specification

Nov 20, 2026 · @Georgiee

RegulationDiff compares two versions of a financial regulation, finds the clauses that changed, traces them to the internal policies and processes they affect, and produces an evidence-cited impact assessment, delivered through an automated Git-to-Kubernetes pipeline for CSE 816 Software Production Engineering.

## 1. Introduction

### 1.1 Purpose

This document defines the requirements, architecture, data design, AI pipeline, DevOps framework, testing approach and acceptance criteria for RegulationDiff. It is the reference for design, implementation, demonstration and evaluation.

### 1.2 Problem statement

When a regulator publishes a new version of a regulation, a financial institution must know which clauses changed, which compliance requirements and internal policies are affected, what actions to take, and what evidence supports that assessment. RegulationDiff automates this chain, for example when Version 2 lowers a transaction reporting threshold.

### 1.3 Scope

In scope: document upload and versioning, clause extraction, change detection and classification, semantic search over regulations and policies, a compliance dependency graph, AI-generated impact reports with citations, a React dashboard, and the full DevOps toolchain (GitHub, Jenkins, Docker, Ansible, Kubernetes, ELK, Vault). Out of scope: legal advice, real regulator or customer data, automatic policy rewriting, and multi-tenant production hardening.

### 1.4 Definitions

| Term | Meaning |
| --- | --- |
| Clause | A numbered unit of a regulation or policy (for example 4.2.1) |
| Confirmed change | A difference found deterministically by text diff or clause alignment |
| Inferred impact | A possible effect suggested by semantic similarity, graph traversal or the LLM |
| RAG | Retrieval-augmented generation: LLM answers grounded in retrieved passages |
| HPA | Kubernetes Horizontal Pod Autoscaler |
| Priority tags | **M** mandatory for the course, **A** advanced feature, **I** innovation, **D** domain |

### 1.5 Design principles

1. A deterministic pipeline detects changes; the LLM only explains them.
2. Every statement in an impact report cites a stored clause (document, version, clause, page).
3. Confirmed changes and inferred impacts are always labelled separately.
4. The whole system runs end to end without an LLM API key (mock mode) so CI tests are deterministic.
5. Few technologies: PostgreSQL with pgvector and NetworkX instead of a separate vector database, graph database or message broker.

### 1.6 Scope decisions

The scope is kept lean so the mandatory DevOps path can be finished and demonstrated first.

| Area | Decision | Reason |
| --- | --- | --- |
| Embeddings | fastembed (ONNX, BGE-small, 384 dimensions) instead of sentence-transformers | No PyTorch, so the ai-worker image is about 300 MB and builds, pushes and rollouts stay fast |
| Reranking | Reciprocal-rank fusion of vector and keyword results; no cross-encoder | Smaller image, simpler code |
| Clause alignment | Clause number first, then difflib text similarity; embeddings only for search and inferred graph edges | Enough for clean sample documents and fully deterministic |
| Input files | Text and Markdown first, plus PDFs generated from the same text; no OCR | PDF parsing is the main source of lost time |
| Security scan | Trivy fails the build only on critical findings that have a fix | Large images often have unfixable critical findings that would block every deploy |
| CI integration tests | pytest against a single PostgreSQL container, not the full compose stack | Avoids Docker-in-Docker setup inside Jenkins |
| Migrations | Run at backend start-up under a database lock; every schema change is backward-compatible (add columns, never rename or drop in the same release) | One fewer Kubernetes Job; old and new pods run side by side during a rolling update |
| Users | One admin login, in Tier 1; no separate roles | Simpler authentication |
| Graph | Edges from regex references and semantic matches; no manual editing | Keeps the UI small |
| Reports | JSON only; no PDF export | Saves time without losing evidence |
| Classifier | Rules only; no learned classifier | Rules are enough and are easier to explain |

## 2. Overall Description

### 2.1 Users

| User | Needs |
| --- | --- |
| Compliance analyst | Upload versions, review changes, read impact reports, export findings |
| Compliance manager | See affected policies and recommended actions, mark items reviewed |
| DevOps engineer | Push code, watch the pipeline, deploy, scale, monitor logs |
| Administrator | Manage users and policy-to-regulation links |

In the lean scope all of these roles use one admin login.

### 2.2 Operating environment

Linux host or VM running Minikube (or any Kubernetes cluster), Docker, Jenkins, Ansible 2.14+, Python 3.11, Node 18+. The application runs on Kubernetes; Docker Compose runs the same stack locally for development.

### 2.3 Constraints

- The whole stack must run on one developer machine (suggested minimum 16 GB RAM, 4 CPUs for Minikube).
- Training and demonstration data are synthetic or public regulations; no confidential documents.
- LLM API keys and database credentials are never committed to Git.

### 2.4 Assumptions

- Input documents are text, Markdown or text-based PDFs with a recognisable clause structure; scanned PDFs and OCR are out of scope.
- Internal policies are supplied by the user as PDFs or text, in the same clause-numbered form.
- Thresholds in this document are proposed defaults, tuned on the labelled evaluation set.

## 3. System Architecture

### 3.1 Changes from the initial proposal

The initial architecture was adjusted so every course requirement is met and demonstrable.

| Change | Reason |
| --- | --- |
| Three application images (frontend, backend, ai-worker) are each built and pushed to Docker Hub; the sample Jenkinsfile built one image | Mandatory: push generated images; deploy all services |
| Jenkins starts from a GitHub webhook with GitHub hook trigger for GITScm polling | Mandatory trigger on incremental updates |
| Ansible roles deploy the exact image tag built by the pipeline | Mandatory automated deployment; roles earn advanced marks |
| `GET /api/version` and a dashboard footer show the running build number and commit | Proves that new changes are visible on refresh |
| Mock mode for LLM and embeddings (`LLM_MODE=mock`) used in CI | Deterministic automated tests without keys or network |
| fastembed (ONNX, BGE-small, 384 dimensions) is baked into the ai-worker image | Small image (about 300 MB) without PyTorch, fast builds and rollouts, offline pod start |
| PostgreSQL job queue (`SELECT ... FOR UPDATE SKIP LOCKED`) instead of Redis or Celery | Removes a component; still supports scaling workers |
| Documents stored on a persistent volume behind a storage interface (MinIO optional) | Fewer moving parts, still persistent |
| Database migrations (Alembic) run at backend start-up under a database lock | Seamless updates when the schema changes, with no extra Job |
| Filebeat DaemonSet to Logstash to Elasticsearch to Kibana | Mandatory ELK with Logstash |
| Vault injects LLM key and database credentials at pod start | Advanced marks; no secrets in Git or images |
| Post-deploy smoke test and automatic rollback in the pipeline | Reliable demo and live patching proof |
| Trivy scans images and fails the build on fixable critical findings | Security of the pipeline |

### 3.2 Logical components and deployment mapping

| Logical component | Deployed as |
| --- | --- |
| User interface | frontend (React built and served by Nginx) |
| API gateway and backend (auth, validation, job management) | backend (FastAPI) |
| Document processing, regulatory analysis, RAG engine, impact engine, LLM analysis | ai-worker (Python) |
| Persistence | postgres (PostgreSQL with pgvector), documents volume |
| Logging | Filebeat, Logstash, Elasticsearch, Kibana |
| Secrets | Vault |
| Delivery | GitHub, Jenkins, Docker Hub, Ansible |

### 3.3 Data flow

1. The analyst uploads an old and a new regulation version (and optional policies) through the dashboard.
2. The backend validates and stores the files, records the versions, and enqueues a comparison job.
3. The ai-worker extracts clauses, aligns old and new clauses, and classifies each change.
4. For each significant change it retrieves related clauses and policies, traverses the dependency graph, and calls the LLM with the evidence.
5. The impact report is validated (citations must exist), stored, and shown in the dashboard.
6. All services write structured JSON logs to stdout, which flow into Kibana.

### 3.4 Delivery flow

Developer push, GitHub webhook, Jenkins pipeline (test, build, scan), push images to Docker Hub, Ansible deploy to Kubernetes, rollout with readiness probes, smoke test, new version live on refresh.

## 4. Functional Requirements

### 4.1 Document management

| ID | Pri | Requirement |
| --- | --- | --- |
| DOC-1 | D | The system shall let an authenticated user upload a regulation version with document code, title, authority, version label and effective date. |
| DOC-2 | D | The system shall store each uploaded file with its SHA-256 hash and reject duplicate uploads of the same version. |
| DOC-3 | D | The system shall list documents and their versions and let users select any two versions of one document to compare. |
| DOC-4 | D | The system shall accept internal compliance policies and supporting guidelines as separate document types. |

### 4.2 Ingestion and clause extraction

| ID | Pri | Requirement |
| --- | --- | --- |
| ING-1 | D | The worker shall accept text, Markdown and PDF files and extract text, headings and page numbers (PyMuPDF for PDFs). |
| ING-2 | D | The worker shall detect clause numbers and section headings and split text by clause structure, not by character count. |
| ING-3 | D | Each clause shall be stored with document id, version, clause id, section, page and text. |
| ING-4 | D | OCR is out of scope; sample regulations are generated as clean numbered text. |
| ING-5 | D | Parsing failures shall mark the job failed with a clear error and shall not stop other jobs. |

Example extracted clause:

```json
{"document_id": "REG001", "version": "2.0", "clause_id": "4.2.1", "page": 17, "section": "Transaction Reporting", "text": "Institutions must report..."}
```

### 4.3 Change detection and classification

| ID | Pri | Requirement |
| --- | --- | --- |
| CHG-1 | I | The system shall align old and new clauses using clause number first, then text similarity (difflib) for unmatched clauses. |
| CHG-2 | I | The system shall classify each clause as added, deleted, modified, renumbered, semantically equivalent, substantially changed, or unchanged. |
| CHG-3 | I | The system shall extract numbers, units, currencies, dates and modal verbs (may, should, must, shall) from both versions and flag differences as numeric or obligation changes. |
| CHG-4 | I | A change of a number or obligation level shall classify the clause as substantially changed even when wording similarity is high. |
| CHG-5 | I | Each change shall record the text diff, similarity score, change type and a confidence value. |
| CHG-6 | D | The system shall not use the LLM to decide whether a clause changed; the LLM only explains detected changes. |

### 4.4 Semantic search and RAG

| ID | Pri | Requirement |
| --- | --- | --- |
| RAG-1 | D | The system shall create embeddings for regulation clauses, historical versions, internal policies and guidelines and store them in pgvector. |
| RAG-2 | D | The system shall provide semantic search across regulations and policies with filters for document id, version, clause number, document type and effective date. |
| RAG-3 | D | For each significant change, the system shall retrieve the top related passages and combine vector and keyword rankings by reciprocal-rank fusion before passing evidence to the LLM. |
| RAG-4 | D | Search results shall show the clause text, source document, version, clause and page. |

### 4.5 Compliance dependency graph

| ID | Pri | Requirement |
| --- | --- | --- |
| GRF-1 | I | The system shall maintain a graph of regulations, clauses, policies, business processes and controls. |
| GRF-2 | I | Edges shall use the types MODIFIES, REFERENCES, IMPLEMENTS, DEPENDS\_ON and AFFECTS, and each edge shall be marked confirmed or inferred with a confidence value. |
| GRF-3 | I | Explicit citations of a clause inside a policy (for example, see clause 4.2.1) shall create confirmed REFERENCES edges. |
| GRF-4 | I | Semantic matches above a threshold shall create inferred edges awaiting review. |
| GRF-5 | I | Manual editing of nodes and edges is out of scope; edges come only from explicit references and semantic matches. |
| GRF-6 | I | For each changed clause the system shall traverse the graph (depth up to 3) to list potentially affected policies, processes and controls. |
| GRF-7 | I | The graph shall be built with NetworkX from tables persisted in PostgreSQL and be shown visually in the dashboard as a layered SVG view (no extra graph library). |

### 4.6 Impact assessment

| ID | Pri | Requirement |
| --- | --- | --- |
| IMP-1 | D | For each significant change the system shall generate an impact assessment with change summary, affected policies, potential impact, recommended actions and evidence. |
| IMP-2 | D | The LLM input shall contain the old and new clause, the change classification, retrieved policies, related clauses and graph dependencies. |
| IMP-3 | D | The LLM shall return structured JSON, and every claim shall cite evidence ids from the supplied context. |
| IMP-4 | D | The system shall reject and retry once any output that cites evidence not in the supplied context; if it still fails, the report is marked unverified. |
| IMP-5 | D | Reports shall separate Confirmed changes from Inferred impacts, and shall never state that a policy is legally non-compliant. |
| IMP-6 | D | Reports shall include a fixed disclaimer that findings need human review. |
| IMP-7 | D | Reports shall be viewable in the dashboard and downloadable as JSON. |

### 4.7 User interface and access

| ID | Pri | Requirement |
| --- | --- | --- |
| UI-1 | D | The dashboard shall support upload and management of document versions. |
| UI-2 | D | The dashboard shall show a side-by-side clause comparison with highlighted differences and change-type badges. |
| UI-3 | D | The dashboard shall provide semantic search and a visual dependency graph. |
| UI-4 | D | The dashboard shall show impact reports with clickable citations that open the source clause. |
| UI-5 | D | The dashboard shall show job status (queued, running, done, failed) with automatic refresh. |
| UI-6 | M | The dashboard footer shall show the running build number, commit and build time from `GET /api/version`. |
| SEC-1 | D | Users shall log in with email and password (JWT) as a single admin user; passwords are stored hashed. |
| SEC-2 | D | All inputs shall be validated; uploads limited to PDF or text and to a maximum size. |

## 5. DevOps Requirements

These requirements implement every item in the course guidelines.

| ID | Pri | Requirement |
| --- | --- | --- |
| DEV-1 | M | Application code, tests, Dockerfiles, Jenkinsfile, Ansible roles and Kubernetes manifests shall be in one GitHub repository with incremental commits and feature branches. |
| DEV-2 | M | A push to GitHub shall trigger Jenkins automatically through a webhook, with GitHub hook trigger for GITScm polling enabled on the pipeline job. |
| DEV-3 | M | Jenkins shall fetch the updated code and run the pipeline defined in the repository Jenkinsfile. |
| DEV-4 | M | The pipeline shall run unit, integration and API tests; any failure shall stop the pipeline before images are pushed. |
| DEV-5 | M | The pipeline shall build separate Docker images for frontend, backend and ai-worker and push them to Docker Hub tagged with the build number and latest. |
| DEV-6 | M | Docker Hub credentials shall be held in the Jenkins credentials store and never in the repository. |
| DEV-7 | M | The pipeline shall deploy by running an Ansible playbook that applies the Kubernetes manifests with the new image tags and waits for the rollout to finish. |
| DEV-8 | M | After deployment, refreshing the application shall show the new changes without manual steps, verified by UI-6. |
| DEV-9 | M | Docker Compose shall start the complete application and database locally. |
| DEV-10 | M | Application logs shall flow Filebeat to Logstash to Elasticsearch, and Kibana dashboards shall visualize them (Section 5.2). |
| DEV-11 | A | Vault shall store the LLM API key and database credentials and deliver them to pods at start. |
| DEV-12 | A | Ansible shall be organised in roles: common, docker, kubernetes, vault, monitoring and application, with per-environment inventories and variables. |
| DEV-13 | A | The backend and ai-worker Deployments shall have an HPA and shall be shown scaling under load. |
| DEV-14 | A | Updates shall be applied live using rolling updates with maxUnavailable 0, readiness probes and at least two backend replicas, shown by a request loop with no failed responses during a deployment. |
| DEV-15 | A | Trivy shall scan the images; critical findings that have a fix fail the build. |
| DEV-16 | A | The pipeline shall verify the new version with a smoke test and run `kubectl rollout undo` automatically if it fails. |
| DEV-17 | A | Kubernetes RBAC shall restrict service accounts to the resources they need. |

### 5.1 Jenkins pipeline stages

1. Checkout, triggered by the GitHub webhook.
2. Lint (ruff, which covers the flake8 rules, and eslint).
3. Unit tests (pytest, frontend tests) with coverage report.
4. Build the three images in parallel.
5. Integration and API tests (pytest) against a single PostgreSQL container in mock LLM mode, with no Docker-in-Docker.
6. Trivy image scan (critical findings with a fix only).
7. Push images to Docker Hub with the build number and latest.
8. Deploy with the Ansible `application` role, passing the image tag.
9. Wait for rollout, run the smoke test (the version endpoint must report the new build number).
10. On failure, roll back automatically; always archive test and scan reports.

For a local Jenkins, the webhook reaches it through a tunnel (for example ngrok or smee.io); the tunnel setup is documented in the runbook.

### 5.2 Containers and Kubernetes

| Item | Specification |
| --- | --- |
| Images | frontend (Nginx), backend (FastAPI), ai-worker (Python, embedding model included), postgres (pgvector) |
| Compose services | frontend, backend, ai-worker, postgres, and optional elasticsearch, logstash, kibana |
| Workloads | Deployments for frontend (2), backend (2 to 5), ai-worker (1 to 3); postgres as a StatefulSet; migrations run at backend start-up under a lock |
| Networking | ClusterIP Services, Nginx Ingress, `/` to frontend and `/api` to backend |
| Configuration | ConfigMaps for non-secret settings; secrets from Vault |
| Storage | PersistentVolumeClaims for postgres, documents and Elasticsearch |
| Health | Readiness and liveness probes on `/health` for every service |
| Scaling | HPA on CPU (target 70 percent) using metrics-server |
| Updates | RollingUpdate with maxUnavailable 0 and maxSurge 1 |

### 5.3 Logging and dashboards

Every service writes JSON logs to stdout with fields timestamp, service, level, event, request\_id, document\_id, duration\_ms, status and build\_number. Kibana dashboards show documents processed, changes detected by type, failed jobs, average analysis time, LLM latency and failures, API request rate and errors, and deployments by build number.

## 6. Data Design

| Table | Key columns |
| --- | --- |
| `users` | id, email, password\_hash, role |
| `documents` | id, doc\_code, title, doc\_type (regulation, policy, guideline), authority |
| `document_versions` | id, document\_id, version\_label, effective\_date, file\_path, sha256, uploaded\_by, uploaded\_at |
| `clauses` | id, version\_id, clause\_number, section, page, text, text\_hash, embedding (vector 384), ocr\_flag |
| `comparisons` | id, old\_version\_id, new\_version\_id, status, created\_by, created\_at |
| `clause_changes` | id, comparison\_id, old\_clause\_id, new\_clause\_id, change\_type, text\_diff, similarity, numeric\_changes (JSONB), confidence, reviewed |
| `graph_nodes` | id, node\_type, ref\_id, label |
| `graph_edges` | id, src, dst, rel\_type, status (confirmed, inferred), confidence, evidence\_clause\_id |
| `impact_reports` | id, comparison\_id, change\_id, summary, affected (JSONB), actions (JSONB), evidence (JSONB), verified, model, created\_at |
| `jobs` | id, type, status, payload, attempts, error, locked\_at, created\_at, finished\_at |

Indexes: HNSW or IVFFlat on `clauses.embedding`; B-tree on `clauses(version_id, clause_number)`; `jobs(status, created_at)`.

## 7. API Specification

| Method and path | Purpose |
| --- | --- |
| `POST /api/auth/login` | Obtain a JWT |
| `POST /api/documents` | Upload a document version |
| `GET /api/documents` | List documents and versions |
| `POST /api/comparisons` | Create a comparison job for two versions |
| `GET /api/comparisons/{id}` | Status, changes and report links |
| `GET /api/comparisons/{id}/changes` | Classified clause changes with diffs |
| `GET /api/search?q=` | Semantic search with filters |
| `GET /api/graph/{comparison_id}` | Dependency graph nodes and edges |
| `GET /api/reports/{id}` | Impact report (JSON) |
| `GET /api/jobs/{id}` | Job status |
| `GET /api/version` | Build number, commit and build time |
| `GET /health` | Liveness and readiness |

Errors use one shape: code, message, request\_id.

## 8. AI Pipeline Specification

### 8.1 Change detection (hybrid)

1. Align by clause number. Identical text hash means unchanged.
2. For unmatched clauses, compute difflib text similarity and match greedily above 0.60.
3. Classify with rules (thresholds configurable, tuned on the labelled set):
   - similarity 0.95 or higher with a different clause number: renumbered
   - high embedding similarity (0.92 or higher), low word overlap and no numeric or modal difference: semantically equivalent (the one classification rule that uses the stored clause embeddings; alignment itself stays text-based)
   - any numeric, currency, date or modal-verb difference: substantially changed
   - otherwise a text difference: modified
   - no match in the old version: added; no match in the new version: deleted
4. Rules only; a learned classifier is out of scope.

### 8.2 Retrieval and graph

Embeddings use fastembed (ONNX, BGE-small, 384 dimensions) baked into the image and are used only for search and inferred graph edges. Search filters apply before ranking. Vector and keyword rankings of the top 10 candidates are combined by reciprocal-rank fusion and the best 5 are passed on; there is no cross-encoder. Graph traversal runs from the changed clause along REFERENCES, IMPLEMENTS, DEPENDS\_ON and AFFECTS edges, depth 3, and each result keeps its confirmed or inferred label.

### 8.3 LLM contract

A provider interface supports OpenAI, Gemini or a mock. The prompt supplies numbered evidence blocks and requires JSON with change, affected\_policies, potential\_impact, recommended\_actions and evidence\_ids. Output is validated against a schema and all evidence ids must exist; otherwise one retry, then the report is marked unverified. Temperature is low and prompts and responses are logged with ids only, never secrets.

## 9. Non-Functional Requirements

| Category | Requirement (proposed targets) |
| --- | --- |
| Performance | Non-AI API p95 under 500 ms; a 50-page version pair compared in under 3 minutes in mock mode |
| Scalability | Backend scales to 5 replicas and ai-worker to 3 through HPA |
| Availability | Zero failed requests during a rolling update with two or more backend replicas |
| Reliability | A failed job never blocks others; LLM failures are retried with backoff |
| Security | Hashed passwords, JWT, validated uploads, secrets in Vault, non-root containers, RBAC, scanned images |
| Traceability | Every impact statement links to a stored clause; every deployment links to a commit and build number |
| Maintainability | Modular code, typed schemas, at least 70 percent unit-test coverage on core modules |
| Portability | The same images run under Compose and Kubernetes |

## 10. Testing and Evaluation

| Level | Scope |
| --- | --- |
| Unit | Clause parsing, clause alignment, change classification, numeric and modal extraction, citation validation |
| Integration | PDF to clauses to embeddings to retrieval to report, in mock mode |
| API | Upload, compare, search, report and version endpoints; auth and validation errors |
| Deployment | Health, rollout status and smoke test on Kubernetes |
| Load | Request loop during a rolling update; load to trigger the HPA |

AI evaluation uses a small labelled dataset (at least two synthetic regulation pairs and about 30 labelled clause pairs) built by the team. Metrics: change detection precision and recall, clause alignment accuracy, retrieval precision at 5, correct identification of affected policies, and citation accuracy. Proposed targets are 0.85 or higher for change precision and recall and retrieval precision at 5, and 100 percent of cited evidence existing in the stored clauses.

## 11. Demonstration Data and Scenario

Synthetic regulation REG001 has Version 1.0 and Version 2.0 where clause 4.2.1 lowers a transaction reporting threshold. Internal policies are a Transaction Monitoring Policy and a Reporting Policy (both reference clause 4.2.1) and an unrelated KYC Policy.

1. Push a visible UI change to GitHub; show Jenkins triggered by the webhook, tests, scans, images on Docker Hub, the Ansible deploy, and the new build number after a browser refresh while a request loop runs with no failures.
2. Show the same activity in Kibana and the HPA scaling under load; show the secrets in Vault.
3. Upload REG001 v1 and v2 and the policies; show the side-by-side comparison with clause 4.2.1 classified as substantially changed.
4. Show the dependency graph from clause 4.2.1 to the affected policies and the unrelated policy left out.
5. Open the impact report: confirmed change, inferred impacts, recommended actions and citations to REG001 v2.0, clause 4.2.1, page 17.

## 12. Repository Structure

```text
regulationdiff/
  frontend/        React app, Nginx config, Dockerfile
  backend/         FastAPI: routes, core (security, errors, middleware), services, migrations, Dockerfile
  ai-engine/       ingestion, analysis (alignment, facts, classification), llm, graph builder, worker, Dockerfile
  shared/          code used by both Python services: config, logging, models, embeddings, retrieval, graph
  tests/           api and integration tests against PostgreSQL (unit tests live inside each package)
  samples/         demonstration regulation and policies (Section 11)
  docker/          docker-compose.yml, container entrypoint
  jenkins/         Jenkinsfile, Jenkins image with the pipeline's tools
  ansible/         playbooks (site, deploy); roles: common, docker, kubernetes, vault, monitoring, application
  kubernetes/      Kustomize base, overlays (dev, vault), vault component
  monitoring/      filebeat, logstash pipeline, ELK manifests, kibana setup
  scripts/ docs/   demo, load and CI helpers; requirements, architecture, runbook
  .env.example  .gitignore  README.md
```

No API keys, Vault tokens, `.env` files or large datasets are committed.

## 13. Implementation Plan

| Tier | Scope | Requirements | Done when |
| --- | --- | --- | --- |
| 1. Mandatory path | Login, upload of text, Markdown and PDF, clause extraction, alignment and classification, side-by-side diff, build number in the footer, tests, Jenkins webhook pipeline, Docker Hub, Ansible deploy to Kubernetes, ELK logs | DOC-1 to DOC-3, ING-1 to ING-3, CHG-1 to CHG-5, UI-1, UI-2, UI-6, SEC-1, DEV-1 to DEV-10 | A push reaches the cluster, shows on refresh and appears in Kibana |
| 2. Advanced features | Vault, Ansible roles, HPA, rolling update, Trivy, smoke test and rollback | DEV-11 to DEV-16 | Each shown in the demo |
| 3. AI and graph | Search, dependency graph, LLM impact reports with citations | RAG-1 to RAG-4, GRF-1 to GRF-4, GRF-6, GRF-7, IMP-1 to IMP-6, UI-3 to UI-5 | Chain from changed clause to affected policies with citations |
| 4. If time allows | Kubernetes RBAC, upload hardening, evaluation report, extra Kibana views | DEV-17, SEC-2, Section 10 | Time permitting |

If time is short, drop Tier 4, then simplify Tier 3 (for example keyword-only search without vector retrieval). Tiers 1 and 2 are not reduced. CHG-6 is a design rule that applies to every tier.

## 14. Course Requirements Traceability

| Guideline item | Marks | Requirements | Verified by |
| --- | --- | --- | --- |
| Git and GitHub | 20 | DEV-1 | Repository with incremental history |
| Jenkins, GitHub hook trigger for GITScm polling, pipelines | 20 | DEV-2, DEV-3 | A push starts a build with no manual click |
| Automated tests in the pipeline | 20 | DEV-4 | A failing test stops the pipeline |
| Docker, Docker Compose, Docker Hub | 20 | DEV-5, DEV-6, DEV-9 | Three images on Docker Hub; compose starts the stack |
| Deploy to target system (Ansible, Kubernetes) | 20 | DEV-7 | Pods updated by the pipeline |
| Changes visible on refresh | 20 | DEV-8, UI-6 | Build number changes after refresh |
| Logs feed ELK, Kibana visualizes them | 20 | DEV-10, Section 5.3 | Kibana dashboards shown live |
| Vault, Ansible roles, Kubernetes HPA | 3 | DEV-11, DEV-12, DEV-13 | Secrets from Vault; roles directory; HPA scaling |
| Live patching | Encouraged | DEV-14, DEV-16 | No failed requests during rollout; rollback works |
| Innovation | 2 | CHG-1 to CHG-5, GRF-1 to GRF-4, GRF-6, GRF-7, IMP-3 to IMP-5 | Hybrid change detection, confirmed versus inferred graph, cited reports |
| Domain-specific project (Finance) | 5 | DOC-1 to IMP-7 | Regulatory compliance application |

## 15. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Too much AI work delays the working pipeline | Tier order: pipeline and basic comparison first |
| LLM API cost, limits or outages | Mock mode, caching of results, provider interface, retry with backoff |
| Hallucinated or unsupported claims | Citation validation, structured output, confirmed versus inferred labels |
| Poor clause extraction on messy PDFs | Use well-structured sample documents, accept text and Markdown uploads, no OCR |
| Minikube runs out of memory with ELK | Single-node Elasticsearch with a 512 MB heap, resource limits, compose fallback for the demo |
| Webhook cannot reach local Jenkins | Tunnel (ngrok or smee.io), or Jenkins on a reachable VM |
| Secrets leak | Vault, `.gitignore`, secret scanning in CI |

## 16. Acceptance Criteria and Deliverables

- A GitHub push automatically runs tests, builds and pushes three images to Docker Hub, and deploys to Kubernetes through Ansible.
- Refreshing the application shows the new build number and the changed feature.
- A rolling update completes with no failed requests; a bad release is rolled back automatically.
- Application logs appear in Kibana through Logstash.
- Credentials come from Vault, Ansible uses roles, and the HPA scales under load.
- REG001 v1 and v2 produce classified changes, a dependency graph to affected policies and an evidence-cited impact report that separates confirmed changes from inferred impacts.
- The evaluation report meets the target metrics or documents the gaps.

Deliverables: GitHub repository, Docker Hub images, Jenkinsfile, Ansible roles, Kubernetes manifests, Kibana dashboards, labelled evaluation dataset and results, this specification, a runbook, and the live demonstration.
