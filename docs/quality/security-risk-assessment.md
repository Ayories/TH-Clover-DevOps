# Security risk assessment (TH-CLOVER proof of concept)

AI-assisted (Agent 4, 2026-11-26) in the role area of Timilehin Ayokunumi Ibrahim, Quality and
Security. No team member has reviewed it yet. It assesses the files in the repository on that date.
**Nothing has been deployed**, so host, AWS and pipeline controls are "defined", not "observed".

## 1. Scope, assets and trust boundaries

| Asset | Where | Why it matters |
|---|---|---|
| Customer name, email, free-text message | PostgreSQL volume, pre-deployment dumps, staff page, staff API | Personal data |
| Staff password and hash, `SECRET_KEY`, database password | `/opt/th-clover/<env>/` on the host | Give access to personal data |
| SSH private key | Operator's WSL | Root on the host |
| GitHub accounts with write access | GitHub | Change code that can be deployed |
| AWS account, deploy role, instance role | AWS | Control of host, logs, alerts, cost |
| Container image and release record | GHCR, Actions artifacts | Integrity of what runs |

Trust boundaries: internet to Security Group (one CIDR); browser to app over **plain HTTP**; app to
database (private Compose network); containers to host metadata service; GitHub to AWS (OIDC, SSM);
repository (**public**) to everyone.

## 2. Method

Likelihood (L) and impact (I): 1 low, 2 medium, 3 high. Score = L x I. 6 or more needs action or an
explicit decision before real use. Scores are judgement, not measurement. Residual = after the
controls that exist in files today. Evidence names are files in `evidence/quality/`.

## 3. Threats

| ID | Threat | L | I | Score | Controls in place | How verified | Residual | Next step |
|---|---|---|---|---|---|---|---|---|
| T01 | Staff password or customer data read in transit (no TLS) | 2 | 3 | 6 | Ports open to one CIDR only; synthetic data only | Template read; not deployed | **High** | Staff access through an SSH tunnel; TLS with a domain before real use |
| T02 | Unreviewed or malicious change reaches `main` and production | 2 | 3 | 6 | Workflows for tests and scans; OIDC limited to `main`; deploy limited to one SSM document | GitHub API: `main` unprotected, no environments (`github-settings-readonly.txt`) | **High** | Protect `main`, require checks and one review, create environments with reviewers |
| T03 | Staff password guessing | 2 | 2 | 4 | Generated 24-character password; scrypt hash; wrong login gets 401; no hash means no access | `security-tests.txt` | Medium: no rate limit, lockout or failed-login record | Log `auth_failed`; add rate limit |
| T04 | Actions cannot be attributed (shared `staff` login; one `cloveradmin` account) | 2 | 2 | 4 | Key-only SSH; no root or `ubuntu` login in the definitions | Template and playbook read | Medium | One account per person; record which request changed and by whom |
| T05 | Cross-site request forgery on form or status change | 2 | 2 | 4 | Session CSRF token, SameSite=Strict, `form-action 'self'`; JSON API refuses form posts | Tests, including removal check (`security-tests-detect-removed-controls.txt`) | Low | None |
| T06 | Stored cross-site scripting against staff | 2 | 3 | 6 | Jinja auto-escaping; CSP `default-src 'none'`; `nosniff`; frame denial | Tests | Low | Keep `\|safe` out of templates; review template changes |
| T07 | SQL injection | 1 | 3 | 3 | SQLAlchemy bound parameters; integer route ids | Tests (SQLite) | Low | Also run `test_security.py` against PostgreSQL in CI |
| T08 | Flooding or oversize requests | 2 | 2 | 4 | 128 KiB body cap; field limits; container memory limits | Tests | Medium: no rate limit; staff view shows only the newest 200, so a flood can hide genuine requests | Rate limit; paging |
| T09 | Personal data in logs or metrics | 2 | 2 | 4 | App logs route name and status only; SQLAlchemy parameters hidden; fixed metric labels; no access log | Tests on app output; removal check | Medium: PostgreSQL's own error log can quote statements and is sent to CloudWatch (not observed) | Reduce PostgreSQL statement logging; sample real logs |
| T10 | Secret committed to a public repository | 2 | 3 | 6 | Secrets generated on host; `.gitignore`; Gitleaks gate over full history | No leaks in 2 commits and working tree (`gitleaks-*.txt`) | Low | Confirm GitHub secret scanning and push protection are on |
| T11 | Vulnerable library or base image | 2 | 2 | 4 | Pinned dependencies; digest-pinned base image; pip-audit, Bandit, Trivy gates; Dependabot | pip-audit and Bandit clean locally; **Trivy not yet run** | Medium: unfixed CVEs pass; new CVEs appear after release | Run the pipeline; add a weekly scheduled scan |
| T12 | Compromised third-party action or tool (Trivy, March 2026) | 2 | 3 | 6 | Actions pinned to commit SHA; Trivy image by digest without Docker socket or tokens; Gitleaks by checksum; 7-day update cooldown | `supply-chain-verification.txt` | Low to medium: vulnerability database fetched at run time; image signature not verified; database and monitoring images use tags | Pin remaining images by digest; verify signatures |
| T13 | Compromised app container reads or changes all data | 1 | 3 | 3 | Non-root user; no database port published | Dockerfile and Compose read | Medium: app uses the database **superuser**; default capabilities kept | Separate application role; drop capabilities |
| T14 | Container uses the instance role through the metadata service | 1 | 3 | 3 | IMDSv2 required; small inline policy | Template read; AWS policy reference | Medium: hop limit 2; managed SSM policy allows `ssm:GetParameter` on `*` | Deny parameter reads, or block metadata for app networks |
| T15 | Lateral movement on the shared monitoring network | 1 | 2 | 2 | Prometheus and Alertmanager bound to loopback on the host | Compose read | Low to medium: staging app can reach production app and an unauthenticated Alertmanager | Separate networks per environment |
| T16 | Host administration attacked or bypassed | 1 | 3 | 3 | Key-only SSH, root and password login off, one CIDR | Playbook read | Medium: passwordless sudo; Systems Manager sessions bypass `sshd` settings | Limit `ssm:StartSession` and `ssm:SendCommand` for people |
| T17 | Stolen AWS deploy credentials | 1 | 2 | 2 | No stored keys; OIDC subject fixed to repository IDs and `main`; one document, one instance; validated parameters | cfn-lint; template read | Low (depends on T02) | Review trust after any rename |
| T18 | Data loss (host or disk failure, bad migration) | 2 | 2 | 4 | Dump before each deploy (newest 5) | Script read | Medium: same disk, deleted with instance, restore untested | Off-host encrypted backup and a restore drill |
| T19 | Monitoring or log retention used beyond its purpose | 1 | 2 | 2 | Service metrics only; 14-day log retention | Template read | Low | See [data-protection.md](data-protection.md) |

Business risks that overlap: R03 (T01), R07 (T04), R08 (T14), R09 (T12) in
[`../business/risks-ethics.md`](../business/risks-ethics.md).

## 4. Overall position

Acceptable as a classroom proof of concept **only** with synthetic data, a narrow CIDR and after T02
is fixed. **Not acceptable for real customer data**: no TLS (T01), shared accounts (T04), database
superuser (T13), no deletion or off-host backup process, and no human security review.

Scans and tests show that known checks pass. They do not show the system is secure: scanners miss
flaws, no penetration test was done, and every result here comes from a local run.
