# Runbook

Setting up, running and demonstrating the full delivery chain on one Windows laptop with Docker Desktop
(Kubernetes enabled) and WSL Ubuntu. Every step below was run on the development laptop. On plain Linux,
use Minikube instead with `K8S_FLAVOUR=minikube`.

| Service | Address | Login |
| --- | --- | --- |
| Application (ingress) | http://regulationdiff.localhost:8880 | `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env` |
| API documentation | http://regulationdiff.localhost:8880/api/docs | |
| Jenkins | http://localhost:8090 | `admin` / `jenkins/secrets/jenkins-admin-password.txt` |
| Kibana, dashboard *RegulationDiff overview* | http://localhost:30601 | none (security disabled locally) |
| Vault | `kubectl -n vault exec -it vault-0 -- sh` | root token `root` (dev mode) |

`*.localhost` always resolves to 127.0.0.1, so there is no hosts-file entry to edit. Port 8880 (ingress) and 8090
(Jenkins) avoid 80/8080/8081, which other local tools commonly use.

## 1. Prerequisites

- Docker Desktop with **Kubernetes enabled**. Give WSL enough memory in `%UserProfile%\.wslconfig`, then run
  `wsl --shutdown` and restart Docker Desktop:
  ```ini
  [wsl2]
  memory=11GB
  swap=8GB
  ```
- Ansible in WSL, no sudo needed: `python3 -m pip install --user --break-system-packages ansible==10.6.0`.
- A GitHub repository (public, or give Jenkins a read-only token) and a Docker Hub access token (Read & Write).

## 2. Local configuration (git-ignored)

| File | Content |
| --- | --- |
| `.env` | Copy of `.env.example` with `DB_PASSWORD`, `JWT_SECRET`, `ADMIN_PASSWORD`, `LLM_MODE`, `LLM_MODEL`, `LLM_API_KEY` |
| `jenkins/.env` | Copy of `jenkins/.env.example`: Docker Hub user, repository URL, kubeconfig path, smee channel |
| `jenkins/secrets/dockerhub-token.txt` | Docker Hub access token |
| `jenkins/secrets/jenkins-admin-password.txt` | Any password for the Jenkins `admin` user |

## 3. Bring the environment up with Ansible (one command)

From WSL, in the repository (the wrapper loads `.env` and works around Ansible ignoring `ansible.cfg` on
world-writable Windows mounts):

```bash
bash scripts/ansible.sh site.yml --skip-tags common   # common needs sudo for apt; skip it if packages exist
```

Roles in order: `common`, `docker`, `kubernetes` (metrics-server, ingress-nginx on port 8880, namespaces), `vault`
(Helm chart in dev mode, Kubernetes auth, read-only policy, secrets), `monitoring` (ELK in `logging`, Kibana
data view and dashboard) and `application` (deploy, wait for rollout). Run one part with `--tags vault`.

## 4. Jenkins and the webhook (no clicks)

```bash
docker compose -f jenkins/docker-compose.yml up -d --build
```

Jenkins configures itself from `jenkins/casc/jenkins.yaml` (Configuration as Code): the admin user, the
`dockerhub-credentials` and `kubeconfig` credentials, global environment variables and the `regulationdiff`
pipeline job with the GitHub push trigger. The `webhook-relay` container forwards the smee.io channel to Jenkins.

In GitHub → Settings → Webhooks, add the smee channel URL (`https://smee.io/<channel>`, from
https://smee.io/new), content type `application/json`, push events only. Run the job once manually; after that
every push to `main` starts it ("Started by GitHub push").

## 5. Pause and resume

The full stack needs about 9 GB. Pause it when it is not in use; no data is lost:

```bash
bash scripts/environment.sh stop     # scale app, ELK and Vault to zero; stop Jenkins and the relay
bash scripts/environment.sh start    # from WSL: resume everything and re-seed Vault
```

## 6. Demonstration script (SRS Section 11)

Before the demo: run `environment.sh start`, close other heavy applications, and open the three addresses above.

1. **Live patching.** In one terminal: `bash scripts/request-loop.sh` (polls `/api/version`, counts failures).
2. **Push to deploy.** Change something visible (for example the subtitle in
   `frontend/src/pages/ComparisonsPage.jsx`), commit, `git push`.
3. **Jenkins** (about 12 minutes): started by the GitHub push; lint, unit tests, image builds, API and integration
   tests against a throwaway PostgreSQL, Trivy scan, Docker Hub push, Ansible deploy, smoke test.
4. **Refresh the application.** The footer shows the new UI and API build number. The request loop shows the
   switch from the old to the new build with `failed: 0`.
5. **Kibana**, dashboard *RegulationDiff overview*: request rate, latency, errors, requests per build, jobs,
   detected changes, LLM calls, verified reports. In Discover, filter by `build_number` or `request_id`.
6. **Autoscaling.** `python scripts/load_test.py --password <admin password>` while watching
   `kubectl -n regulationdiff get hpa backend -w`: the backend grows from 2 to 5 replicas and back.
7. **Vault.** `kubectl -n vault exec vault-0 -- env VAULT_TOKEN=root vault kv get secret/regulationdiff/app`,
   then show that the backend pod has a `vault-agent-init` container and that no Kubernetes Secret exists.
8. **Domain flow.** `python scripts/seed_demo.py --url http://regulationdiff.localhost:8880 --password <admin password>`
   (skip if already loaded), open the comparison:
   - clause 4.2.1 is *substantially changed* (EUR 10,000 → EUR 5,000), 4.2.2 changed from *should* to *must*;
   - the dependency graph reaches POL-TM and POL-RPT with their processes and controls, but not POL-KYC;
   - the impact report (Gemini) cites REG001 v2.0 §4.2.1, page 3; click a citation to open the source clause.
9. **Quality gate and rollback.** Build #2 shows a failing test stopping the pipeline before anything is pushed.
   A build whose new pods never become healthy fails the Ansible rollout wait or the smoke test, and the
   pipeline runs `scripts/ci/rollback.sh` (`kubectl rollout undo`): the previous build keeps serving.
10. **Evaluation.** `docs/evaluation.md`: change detection precision and recall 1.00 on 31 labelled clause pairs.

## 7. Kibana dashboard

`monitoring/kibana/build_dashboards.py` generates `monitoring/kibana/dashboards.ndjson` (8 panels), and
`monitoring/kibana/setup.sh` imports it together with the `regulationdiff-*` data view. Logstash drops Filebeat's
ECS `event` object and indexes `status` as text, so the application fields never conflict.

## 8. Troubleshooting

| Symptom | Fix |
| --- | --- |
| Everything slow, probes time out, `kubectl` hangs | The laptop is out of memory: pause with `environment.sh stop`, close other applications, or scale ELK down |
| Backend `OOMKilled` under load | Should not happen any more (one embedding at a time per pod, 1 GiB limit); check `kubectl top pods` |
| HPA shows `<unknown>` | Pods just restarted, or metrics-server is not ready: `kubectl -n kube-system get deploy metrics-server` |
| Backend `CrashLoopBackOff` after a restart | Vault (dev mode) lost its secrets: `bash scripts/ansible.sh site.yml --tags vault`, then restart the pods |
| Webhook delivers but nothing builds | The job must have run once manually; check `docker logs webhook-relay` |
| Jenkins cannot fetch the repository | A private repository needs a GitHub token credential, or make it public |
| Gemini answers slowly or with HTTP 503 | Set `LLM_MODEL` to another model; reports fall back to unverified deterministic content after one retry |
