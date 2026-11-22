# Runbook

Step-by-step setup of the full delivery chain on one Windows laptop with Docker Desktop and WSL (Ubuntu).
The same steps work on Linux, using Minikube instead of Docker Desktop Kubernetes (`K8S_FLAVOUR=minikube`).

## 1. Prerequisites

- Docker Desktop with **Kubernetes enabled** (Settings → Kubernetes). Give WSL 10–12 GB of memory in
  `%UserProfile%\.wslconfig`:
  ```ini
  [wsl2]
  memory=12GB
  ```
- In WSL Ubuntu: `sudo apt install -y ansible python3-venv`, and the Docker Desktop WSL integration turned on.
- A Docker Hub account and a GitHub repository for this code.

## 2. Bring the environment up with Ansible (one command)

From WSL, in the repository:

```bash
cd ansible
export DOCKERHUB_NAMESPACE=<your-dockerhub-user>
export DB_PASSWORD=... JWT_SECRET=... ADMIN_PASSWORD=...   # LLM_API_KEY only if LLM_MODE is not mock
ansible-playbook playbooks/site.yml
```

The roles run in order: `common`, `docker`, `kubernetes` (metrics-server, ingress-nginx, namespaces), `vault`
(Helm chart in dev mode, Kubernetes auth, policy, secrets), `monitoring` (ELK in the `logging` namespace,
Kibana data view) and `application` (first deploy, `image_tag=latest`). Run a single part with
`--tags vault` and similar.

> Vault runs in dev mode, which keeps data in memory. After restarting Docker Desktop, run
> `ansible-playbook playbooks/site.yml --tags vault` to re-seed the secrets, then
> `kubectl -n regulationdiff rollout restart deploy`.

## 3. Jenkins

```bash
docker compose -f jenkins/docker-compose.yml up -d --build
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Open http://localhost:8081, finish the setup wizard (the plugins are pre-installed), then:

1. **Credentials** (Manage Jenkins → Credentials → Global):
   - `dockerhub-credentials`: *Username with password*, your Docker Hub user and an access token.
   - `kubeconfig`: *Secret file*, your `~/.kube/config`. The Docker Desktop server address
     `kubernetes.docker.internal:6443` also resolves inside the Jenkins container.
2. **Global environment** (Manage Jenkins → System → Global properties): `DOCKERHUB_NAMESPACE=<your user>`.
   For Vault mode also set `DB_PASSWORD`, `JWT_SECRET` and `ADMIN_PASSWORD`, so redeploys re-seed the same values.
3. **Job**: New Item → *Pipeline* → "Pipeline script from SCM" → Git → your repository URL, branch `main`,
   script path `jenkins/Jenkinsfile`. Tick **GitHub hook trigger for GITScm polling**.

## 4. GitHub webhook through a tunnel

GitHub cannot reach `localhost`, so expose Jenkins with a tunnel:

```bash
ngrok http 8081            # or: npx smee-client --url https://smee.io/<channel> --target http://localhost:8081/github-webhook/
```

In GitHub → Settings → Webhooks, add `https://<tunnel-host>/github-webhook/`, content type
`application/json`, event "Just the push event". Push a commit: Jenkins starts without a manual click.

## 5. Demonstration script (SRS Section 11)

1. `scripts/request-loop.sh http://regulationdiff.localhost/api/version` in one terminal: it counts failed requests.
2. Change something visible (for example a heading in `frontend/src/pages/ComparisonsPage.jsx`), commit and push.
3. Show Jenkins: tests, Trivy, Docker Hub push, the Ansible deploy, the smoke test.
4. Refresh http://regulationdiff.localhost: the footer shows the new UI and API build number. The request loop
   shows the build switching with `failed: 0`.
5. Kibana (http://localhost:30601): Discover with data view *RegulationDiff logs*, filtered by `build_number`.
6. Autoscaling: `python scripts/load_test.py --password <admin password>` while running
   `kubectl -n regulationdiff get hpa -w`.
7. Vault: `kubectl -n vault exec vault-0 -- vault kv get secret/regulationdiff/app` (root token from the role defaults).
8. Domain flow: `python scripts/seed_demo.py --url http://regulationdiff.localhost --password <admin password>`,
   then open the comparison:
   - clause 4.2.1 is *substantially changed* (EUR 10,000 → EUR 5,000);
   - the dependency graph reaches POL-TM and POL-RPT and their processes and controls, but not POL-KYC;
   - the impact report cites REG001 v2.0 §4.2.1, page 3; click a citation to open the source clause.
9. Rollback: push a commit that breaks the API's start-up (for example raise an exception in
   `regdiff_api/main.py`). The smoke test fails and Jenkins runs `kubectl rollout undo`.

## 6. Kibana dashboards

`monitoring/kibana/setup.sh` creates the `regulationdiff-*` data view and imports
`monitoring/kibana/dashboards.ndjson` if that file exists. Useful fields: `service`, `event`, `level`, `status`,
`duration_ms`, `build_number`, `request_id`, `outcome`. To build the dashboard:

| Panel | Visualization |
| --- | --- |
| API requests over time | `event: http_request`, count over `@timestamp`, split by `service` |
| Error rate | `outcome: error`, count over time |
| Latency | `event: http_request`, average and 95th percentile of `duration_ms` |
| Documents processed / failed jobs | `event: job_done` and `event: job_failed`, count |
| Changes detected by type | `event: comparison_done`, sum of `substantially_changed`, `added`, … |
| LLM calls and failures | `event: llm_call` and `event: impact_llm_failed` |
| Deployments | unique count of `build_number` over time |

Then export it (Stack Management → Saved objects → Export) to `monitoring/kibana/dashboards.ndjson` and commit it.

## 7. Troubleshooting

| Symptom | Fix |
| --- | --- |
| Pods `Pending`, events show insufficient memory | Raise the WSL memory limit, or scale ELK down: `kubectl -n logging scale deploy/kibana --replicas=0` |
| HPA shows `<unknown>` targets | metrics-server is not ready yet; check `kubectl -n kube-system get deploy metrics-server` |
| Backend `CrashLoopBackOff` in Vault mode | Vault was restarted and lost its data: run the `vault` role again |
| Webhook delivers but nothing builds | The job must have "GitHub hook trigger for GITScm polling" ticked and must have run once manually |
| Integration stage cannot reach the test database | Jenkins must have access to the Docker socket (`/var/run/docker.sock` volume) |
