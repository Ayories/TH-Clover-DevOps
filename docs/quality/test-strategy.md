# Test strategy and quality gates

AI-assisted (Agent 4, 2026-11-26), role area Quality and Security. Not reviewed by a team member.
States updated after integration on 2026-11-26. "Local" means run in WSL; "CI" means GitHub Actions.

Local test counts: 146 at the first push and 147 after pull request #4 (functional and security).
Coverage of 97% was measured before integration.

## 1. Levels

| Level | What | Where | State |
|---|---|---|---|
| Static | Ruff, Bandit, shellcheck, cfn-lint, Gitleaks | `ci.yml`, `security.yml` | Local and CI pass (Ruff, Bandit, shellcheck, cfn-lint, Gitleaks) |
| Unit and integration | `tests/test_app.py` (SQLite; PostgreSQL in CI) | `ci.yml` | Local and CI pass on SQLite; CI PostgreSQL job passed |
| Security behaviour | `tests/test_security.py` (SQLite) | `ci.yml` `test-build`, `release.yml` | Local and CI pass |
| Dependencies and image | pip-audit, Trivy | `security.yml` | pip-audit pass; Trivy first failed on libzstd1 (CVE-2026-124851, HIGH, fix available), then passed after the Dockerfile fix |
| Container smoke | Build, healthy, non-root, revision label | `ci.yml` | CI pass |
| Monitoring and scripts | promtool, script unit checks, `test_dora.py` | `monitoring.yml` | Passed on pull request #1 |
| Deployment verification | `health-check.sh` with expected SHA, automatic rollback | `deploy.sh` | Seven deployments passed the health check; automatic rollback not tested live |
| Acceptance drills | Timed deploy, rollback, alert, denied access | Manual with records | Timed deploys, manual rollback, application-stop alert and SSH refusals done; others not |

Local results (see `evidence/quality/`): `security-tests.txt`, `all-tests.txt`, `bandit.txt`,
`pip-audit.txt`, `gitleaks-history.txt`, `gitleaks-worktree.txt`, `iac-lint.txt`. These files are held by
the team outside the repository.

## 2. What the security tests cover

Staff refusal (none, wrong, Bearer, malformed, unset or malformed hash); CSRF (missing, forged,
other session); validation including NUL bytes and oversize bodies; escaping of stored input;
SQL-injection-looking input; security headers, cookie flags and `no-store`; `/health` and `/metrics`
content; no personal data or credentials in application logs, including when the database breaks.

To check the tests are not vacuous, CSRF, authentication and parameter hiding were each disabled
**in memory** by a throwaway plugin; the related tests failed
(`security-tests-detect-removed-controls.txt`). No repository file was changed for this.

## 3. Quality gates

| Gate | Fails when | Blocks |
|---|---|---|
| `test-build` | Lint, test, build or smoke failure | Merge (once required) |
| `postgres-integration` | Integration test failure on PostgreSQL | Merge |
| `secret-scan` | Any Gitleaks finding in history | Merge and release |
| `dependency-scan` | Any known vulnerability in pinned requirements | Merge and release |
| `sast` | Bandit medium or high | Merge and release |
| `image-scan` | HIGH or CRITICAL with a fix available | Merge and release |
| `iac-lint` | cfn-lint or shellcheck finding | Merge and release |
| `release.yml` `security-gate` | Security run for that commit not successful | Image publication |
| `deploy.yml` `verify` | Digest does not match the commit, or commit not on `main` | Deployment |
| `deploy.sh` | Unhealthy or wrong version | Keeps or restores previous release |

"Merge" blocking depends on branch protection, which is **not configured**. Until it is, these
gates report but do not prevent. `release.yml` does wait for a successful Security run before it
publishes. One real block was seen: Security run 45752682107 failed on the Trivy gate and was fixed.

Reports are kept as Actions artifacts (Gitleaks redacted, pip-audit, Bandit, Trivy, lint).

### Exceptions

Prefer upgrading. If a finding must be accepted, add it to `.trivyignore` or `.gitleaks.toml` (neither
exists today) in a reviewed pull request with: identifier, reason, owner, expiry date and the
compensating control. Never disable a whole job.

## 4. Demonstrating a failing quality gate (REQ-05)

Local, no change to files:

```bash
QUALITY_GATE_DEMO=1 pytest -q tests/test_security.py   # exit code 1
pytest -q tests/test_security.py                        # exit code 0
```

Recorded in `evidence/quality/quality-gate-demo.txt`. This shows the test run fails, not that GitHub
blocks anything.

On GitHub (after branch protection exists; **not yet done**):

1. `git switch -c demo/failing-gate`
2. In `tests/test_security.py`, on that branch only, change the condition in the last test from
   `== "1"` to `!= "never"`.
3. Open a pull request. Expect `test-build` to fail and the merge button to be blocked.
4. Capture the run and the blocked merge, close the pull request **without merging** and delete the
   branch.

Never merge it and never commit a real or realistic secret to demonstrate the secret scan.

## 5. Requirement mapping

| Requirement | Verification | Evidence now | Still needed |
|---|---|---|---|
| REQ-01 access, least privilege | Staff refusal tests; [access-control.md](access-control.md); denied-access checks | Tests; live 401; root and password SSH refused | Account settings, IAM and network refusals; successful staff login on AWS |
| REQ-02 traceability | Release manifest, image label, deploy verification | One release traced to its PR and checks; no approver | A reviewed release and enforced approval |
| REQ-03 deploy under 20 min | Timed `deploy.yml` runs | Seven runs, 42 to 58 s | None for the target |
| REQ-04 recovery under 10 min | Timed rollback drill, then health and security smoke check | Three manual drills, 6.7 to 6.8 s, health and row counts | Automatic rollback; database restore; security smoke check |
| REQ-05 tests before promotion | Gates above; failing-gate demonstration | Local failing and passing run; real Trivy failure | Blocked pull request; branch protection |
| REQ-06 alert within 5 min | Failure drill | Two application-stop drills; one email time | Third run; database-down and host alarm tests |
| REQ-07 environment consistency | cfn-lint, same Compose file, Ansible second run, same digest | Third Ansible run `changed=0`; same digest in both environments | Local environment run; rebuild |
| REQ-08 idle resources stopped | Scheduler stop and run-hour record | Schedule enabled | Observed stop |

## 6. Test data and limits

- Synthetic data only; the staff password in tests is random for each run.
- Security tests run on SQLite, not PostgreSQL.
- No load, penetration, accessibility, browser or TLS testing.
- Header and CSRF checks use Flask's test client, not a running gunicorn behind a network.
- Scanners miss flaws and results age: rerun before each release and consider a weekly schedule.
