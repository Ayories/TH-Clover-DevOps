# TH Clover — Evolving Ltd DevOps transformation

Reference implementation for CMP6237 Checkpoint 2. Flask + PostgreSQL are illustrative choices pending team agreement. **Do not use real customer data.**

## Ownership
- Galen: Issues, Projects, weekly sprint summary, acceptance criteria.
- AbdulQuadri: application, Git, CI, Docker, release manifest.
- Jesutofunmi: Compose, Ansible, staging deployment.
- Timilehin: Gitleaks, Trivy, pytest and security gate.
- Nana: Prometheus, Grafana, Alertmanager, health probes, rollback, shutdown.

## Local checks
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check app tests
pytest -q

docker build -t th-clover:local .
```

## Local Compose demonstration
Build an image, and set APP_IMAGE=th-clover:local and RELEASE_SHA=local in an untracked .env file, plus POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB. Then:
```bash
docker compose --env-file .env -f infrastructure/docker-compose.yml up -d
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/tickets -H 'Content-Type: application/json' -d '{"subject":"Demo"}'
```
Note: the digest restriction applies to the production-like deploy script, not local Compose testing.

## GitHub configuration (required)
1. Replace CODEOWNERS placeholders with real GitHub usernames; create labels `sprint-report`, `bug`, `feature`, `security`.
2. Protect `main`: require one independent PR review, CI `test-build`, Security `secret-scan` and `image-scan`, and prevent bypasses.
3. Configure `staging` environment approval and secrets `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY`; use an isolated deployment account. Restrict production separately.
4. Provision Ubuntu staging host with Ansible. Put `secrets.env` in `/opt/th-clover` on host, mode 0600; never commit it.
5. Configure GHCR package access for the staging host; `docker login ghcr.io` on host using a narrowly scoped token.
6. Merge to main, download `release-manifest` from the Publish verified image workflow, and dispatch Deploy staging with the exact digest and SHA. **Manually verify that the digest and SHA belong to the successful release workflow** before dispatch; this starter does not cryptographically enforce provenance.
7. Configure `STAGING_HEALTH_URL` for the uptime probe, or disable its schedule until a reachable endpoint exists. GitHub scheduled jobs can be delayed.
8. Set up monitoring via `monitoring/docker-compose.monitoring.yml`; configure an authenticated alert receiver before using Alertmanager. Grafana needs a Prometheus data source and dashboard configured.
9. For the shutdown workflow, configure the `staging-shutdown` environment and its own approved access. Stopping containers is not equivalent to stopping billable VM hours.

## Known limitations / hardening
- **Do not use as-is for production.** Pin third-party Actions to full commit SHAs, pin base images, use SSH host-key pinning instead of runtime ssh-keyscan, and replace manually entered deployment digests with provenance-verified promotion.
- `deploy.sh` keeps only one previous release pointer and does not automatically roll back after failed health verification; investigate and invoke rollback under authorised supervision.
- PostgreSQL data volume persists during rollback. Incompatible schema migrations require a separate migration/restore plan.
- The demo API has no authentication: synthetic test data only, never internet-expose it.
- Grafana/Prometheus bind to localhost and need access control if shared. Alertmanager configuration is a placeholder; a receiver must be deployed.
- GitHub Actions scheduled uptime checks are not a substitute for Prometheus alerting.
- Weekly sprint summary is an issue snapshot, not full GitHub Projects automation. Project board field updates need additional GraphQL/API permissions and configuration.
- Collect timestamps and screenshots to substantiate the 20-minute deployment, 10-minute recovery, and 5-minute alert targets; none are asserted as achieved.
