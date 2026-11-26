# Security review findings

AI review by Agent 4 (2026-11-26) of files written by other AI agents. **This is not a human peer
review** and does not count towards the Definition of Done. Read-only review: no deployment, no AWS
access. Files were still being edited, so check line numbers.

Statuses marked "26 Nov" were added after deployment by an AI documentation pass, not by a new review.

## Open

| ID | Severity | Finding | Where | Recommendation | Owner |
|---|---|---|---|---|---|
| F01 | High | `main` has no protection or ruleset and no environments exist, in a public repository with four write collaborators plus an admin. The OIDC trust accepts any workflow on `main`; the approval in `deploy.yml` does nothing until an environment has reviewers | GitHub settings; `infrastructure/cloudformation/th-clover.yml:46`; `.github/workflows/deploy.yml:39` | Apply [access-control.md](access-control.md) section 3 **before** creating the stack. **26 Nov: open.** Not done before the stack was created; PRs #1 and #4 merged without review | Repository admin, Orchestrator |
| F02 | High | HTTP only: staff Basic password and customer data cross the network unencrypted | `th-clover.yml:76-77` | Synthetic data; `/32`; use staff pages through `ssh -L`; TLS before real use. Rotate the staff password after a demonstration over HTTP | Platform |
| F03 | Medium | The application connects to PostgreSQL as the bootstrap superuser | `infrastructure/docker-compose.yml:8,37` | Create a role with only table privileges for the app | Platform, Development |
| F04 | Medium | Metadata hop limit 2 gives every container the instance role; `AmazonSSMManagedInstanceCore` allows `ssm:GetParameter(s)` on `*` | `th-clover.yml:123,159` | Add an explicit Deny for `ssm:GetParameter*` (then test Run Command), or drop metadata traffic from app networks in `DOCKER-USER`. **26 Nov: partly fixed.** Deny added and Run Command deployments work; the Deny itself was not tested; hop limit 2 remains | Platform |
| F05 | Medium | Failed staff logins are not identifiable events, there is no rate limit, and status changes do not record which request changed | `app/main.py:239` (`staff_required`), `:405` (`update_status`) | Log `auth_failed` and the request id; add a simple rate limit. **26 Nov: partly fixed.** Failed logins are logged as `staff_login_failed` (PR #4); no rate limit; status changes still do not record the request | Development |
| F06 | Medium | Shared `staff` login and role account `cloveradmin`; plain staff password file stays on the host | `ansible/files/generate_secrets.py:56,61`; `th-clover.yml:175` | One holder per credential, stated in the access record; delete the password file after reading | Platform |
| F07 | Medium | PostgreSQL logs go to CloudWatch and by default quote the failing statement, which would contain names, emails and messages (not observed) | `infrastructure/docker-compose.aws.yml:18`; `docker-compose.yml:34` | `command: ["postgres","-c","log_min_error_statement=panic","-c","log_error_verbosity=terse"]` | Platform |
| F08 | Medium | No function or job to delete or expire requests; dumps keep deleted rows | `app/main.py`; `scripts/deploy.sh:97` | Documented manual SQL now; retention job before real use | Development, Operations |
| F09 | Low | Containers keep default capabilities and a writable filesystem | `infrastructure/docker-compose.yml:5` | `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `read_only` with `tmpfs` for the app | Platform |
| F10 | Low | Staging and production apps share the monitoring network and can reach an unauthenticated Alertmanager | `infrastructure/docker-compose.yml:55`; `monitoring/docker-compose.monitoring.yml` | One scrape network per environment; keep Alertmanager off them | Platform, Operations |
| F11 | Low | `postgres:16-alpine`, Prometheus and Alertmanager use tags (CI pins PostgreSQL by digest); only the app image is scanned | `docker-compose.yml:35`; `docker-compose.monitoring.yml:12,33` | Pin digests; scan these images too | Platform, Operations |
| F12 | Low | Systems Manager sessions give a shell that ignores the SSH hardening; the deploy role can read any command's output | `th-clover.yml:123,348` | Limit people's `ssm:StartSession` and `ssm:SendCommand`; record as residual | Platform |
| F13 | Low | A release without an approving review is published with only a warning | `.github/workflows/release.yml:137-139` | Enforce by branch protection (F01), or fail the job. **26 Nov: open.** Both releases came from unreviewed pull requests | Development |
| F14 | Low | No rate limit on the public API; only the newest 200 requests are shown, so a flood hides genuine ones | `app/main.py:47,380` | Rate limit and paging | Development |
| F15 | Info | `deploy.yml` prints host command output into logs of a public repository. Current scripts print no secrets | `.github/workflows/deploy.yml:138-140` | Keep scripts free of secrets and data; check when they change | Platform |
| F16 | Info | No `LICENSE` file; a personal email address is in public commit metadata | Repository | Agree a licence; use no-reply addresses | Team |

## Fixed in the current working tree

| ID | Finding in the starting repository | Resolution |
|---|---|---|
| C01 | `security.yml` and `release.yml` used `aquasecurity/trivy-action@0.30.0`, inside the range whose tags were hijacked in March 2026; the tag no longer resolves | Both run the official Trivy image by digest |
| C02 | Actions pinned to movable tags | Full commit SHAs, checked with the GitHub API |
| C03 | Unauthenticated API | Staff authentication and CSRF, covered by tests |
| C04 | Deployment by SSH from CI with run-time `ssh-keyscan` | OIDC and a single SSM document |
| C05 | `gitleaks-action` (separate licence, movable tag) | Release binary with pinned checksum |

C01 to C05 were merged to `main` in pull request #1, which had no review.

## Checked and found satisfactory

IMDSv2 required; encrypted volume; SSH limited to one CIDR and `0.0.0.0/0` refused by the parameter
pattern; no `ubuntu` user created; SSH drop-in validated before reload with a lock-out check; SSM
parameters restricted by pattern and re-validated in `deploy.sh`; digest-only images; OIDC trust
fixed to audience, repository IDs and `main`; Scheduler role limited to stopping one instance;
secrets generated on the host and not printed; database port not published; non-root app container
with root-owned files.

Application tests found no defect in authentication, CSRF, validation, escaping, headers or
application logging (`evidence/quality/security-tests.txt`).
