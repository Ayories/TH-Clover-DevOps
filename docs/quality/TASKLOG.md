# Quality and security: task log

AI-assisted work (Agent 4, 2026-11-26) in the role area of Timilehin Ayokunumi Ibrahim. No team
member has reviewed it yet. Evidence paths are relative to the project folder
(`evidence/quality/`). Nothing here has been committed, pushed or run on GitHub.

## Task 1: Security tests

**Function & agent.** Quality and Security; Agent 4 (AI).

**Objective.** Automated evidence for staff access control, CSRF, validation, escaping, injection,
headers and no data leakage (REQ-01, REQ-05).

**Tools.** pytest 9.2.0, Flask test client, Python 3.12.3 in WSL.

**Steps.** Wrote `tests/test_security.py` against the contract, ran it against the app, then
disabled controls in memory to confirm that the tests notice.

**Key configuration.** SQLite per test; random staff password and secret key per run; synthetic
marker values searched for in logs, health and metrics output.

**Verification (real output).** `75 passed` (`security-tests.txt`); whole `tests/` folder
`140 passed` at the time of that file (`all-tests.txt`; see the file for the latest count). With CSRF
off: 5 failed; authentication off: 26 failed; parameter hiding off: 1 failed
(`security-tests-detect-removed-controls.txt`). Gate switch: `1 failed, 74 passed`, then `75 passed`
(`quality-gate-demo.txt`).

**Screenshots needed.** Test run in GitHub Actions; a blocked pull request; browser refusal of the
staff page after deployment.

**Problems & solutions.** First run: 1 failure, the test's own mistake (a 100,000-character message
is correctly refused with 413 by the size cap, not 400). An early gate switch used `assert`, which
printed the environment into the output; replaced by `pytest.fail`. A mutation run created an empty
`clover.db` in the repository root; it was deleted.

**Limitations.** SQLite only; test client, not a deployed server; no penetration testing.

## Task 2: Security workflow, Dependabot and supply-chain pins

**Function & agent.** Quality and Security; Agent 4 (AI).

**Objective.** Secret, dependency, code, image and infrastructure gates on pushes to `main` and pull
requests.

**Tools.** GitHub Actions, Gitleaks 8.30.1, pip-audit 2.10.1, Bandit 1.9.4, Trivy 0.76.2 image,
cfn-lint 1.61.0, ShellCheck 0.11.0.

**Steps.** Read the Trivy advisory (GHSA-69fq-xp46-6x23, CVE-2026-33634); compared the image digest on
Docker Hub and GHCR; resolved each action tag to its commit with `gh api`; replaced the starting
workflow.

**Key configuration.** `permissions: contents: read`; no `trivy-action` or `setup-trivy`; Trivy gets
an exported image file, not the Docker socket; gate on fixable HIGH and CRITICAL; reports uploaded;
Dependabot 7-day cooldown. No `.trivyignore` or `.gitleaks.toml` was needed.

**Verification (real output).** `supply-chain-verification.txt`; workflow YAML parses
(`workflow-checks.txt`). **The workflow has never run.**

**Screenshots needed.** Green and failed Security runs; artifact list; Dependabot tab.

**Problems & solutions.** The starting workflows referenced a `trivy-action` tag in the compromised
range that no longer resolves; replaced.

**Limitations.** Image signature not verified; vulnerability database downloaded at run time;
Trivy gate untested because Docker is not available here, so the first run may report base-image
findings.

## Task 3: Local scans

**Function & agent.** Quality and Security; Agent 4 (AI).

**Objective.** Real scan results before anything is pushed.

**Tools.** As above, in WSL (`~/th-clover-venv`, `~/bin/gitleaks`).

**Steps.** Downloaded the official Gitleaks release and checked it against the release checksum file;
ran history and working-tree scans; ran pip-audit, Bandit, cfn-lint and ShellCheck.

**Key configuration.** Bandit gate at medium and above over `app`, `scripts`, `infrastructure`.

**Verification (real output).** Gitleaks: no leaks in 2 commits or the working tree. pip-audit: no
known vulnerabilities (runtime and development). Bandit: 3 low (all `subprocess` use in
`scripts/ops/dora.py`), none medium or high. cfn-lint and ShellCheck: exit 0.

**Screenshots needed.** None beyond the pipeline runs.

**Problems & solutions.** Added `bandit`, `pip-audit` and `cfn-lint` to the shared virtual
environment. Pinned ShellCheck in CI to the locally tested version.

**Limitations.** Point-in-time results; files were still changing while other agents worked.

## Task 4: Review and documents

**Function & agent.** Quality and Security; Agent 4 (AI).

**Objective.** Review Platform's CloudFormation, SSH hardening and IAM; write the risk, access, data
protection and test documents.

**Tools.** File reading, read-only GitHub API queries, AWS managed-policy reference.

**Steps.** Read the template, playbook, Compose files, workflows and scripts; recorded findings in
`review-findings.md`.

**Key configuration.** Not applicable.

**Verification (real output).** `github-settings-readonly.txt`; `iac-lint.txt`.

**Screenshots needed.** Branch ruleset, environments with reviewers, 2FA status, IAM role trust and
policy, refused SSH logins.

**Problems & solutions.** Branch protection and environments are missing: reported as the top action
(F01).

**Limitations.** AI review, not peer review. No AWS account was inspected. Rotation, deletion and
SSH-tunnel procedures are written but not executed.
