# Development and source management: task log

AI-assisted work (Agent 2, 2026-11-26) in the role area of AbdulQuadri Sanusi. No team
member has reviewed it yet. Evidence paths are relative to the project folder
(`evidence/development/`). Nothing here has been committed, pushed or run on GitHub.

## Task 1: Customer-service application

**Function & agent.** Development and source management; Agent 2 (AI).

**Objective.** Replace the starter "tickets" API with the application interface agreed in the
project contract, storing name, email, message, status and creation time.

**Tools.** Python 3.12.3, Flask 3.1.3, SQLAlchemy 2.1.9, Werkzeug 3.1.9, gunicorn 27.0.1,
prometheus-client 0.26.0, PostgreSQL via psycopg2 (SQLite locally).

**Steps.** Wrote `app/main.py` (app factory, model, validation, CSRF, Basic auth, headers,
logging, error handling, health, metrics), four templates, one stylesheet and `app/seed.py`.
Ran gunicorn locally and exercised it with curl.

**Key configuration.**
- Limits: name 100, email 254, message 2000 characters; request body 128 KiB.
- Tables are created on first use under a PostgreSQL advisory lock. If the database is not
  ready, the app still starts, `/health` returns 503 and later requests retry.
- One gunicorn worker with 8 threads, so the in-memory counter is correct.
- Session cookie `clover_session_<env>` (HttpOnly, SameSite=Strict); the name differs per
  environment because staging and production share a host and cookies ignore ports.
- Logs: one JSON line with method, route name, status and duration. No path, query, IP
  address, form value or exception message. SQLAlchemy `hide_parameters` is on.

**Verification (real output).** `gunicorn-smoke.txt` (SQLite):
```
{"database":"ok","environment":"development","status":"ok","version":"local"}
Seed complete: 3 synthetic request(s) added.
Seed complete: 0 synthetic request(s) added.
{"id":4}
 HTTP 201
--- GET /api/requests without auth
HTTP 401
clover_http_requests_total{endpoint="health"} 22.0
```
`bandit.txt`: "No issues identified" (`bandit -r app -ll`).

**Screenshots needed (by a team member).** Public form; success message; staff list showing
synthetic seed rows; browser sign-in prompt and a refused login; `/health` on staging.

**Problems & solutions.**
- Concurrent table creation can fail with several processes: advisory lock plus lazy retry.
- NUL characters and lone surrogates would cause database errors: rejected with 400.
- Deeply nested JSON raises `RecursionError`: handled as 400.
- A first body limit of 32 KiB made one security test (100,000-character message) receive
  413 where it expects 400: limit raised to 128 KiB.

**Limitations.** HTTP only (no TLS), one shared staff account, no rate limiting or lockout,
no schema migrations, no data retention or deletion function, unauthenticated `/health` and
`/metrics`. The pages have not been checked visually or for accessibility.

## Task 2: Automated tests

**Function & agent.** Development and source management; Agent 2 (AI).

**Objective.** Functional and integration tests of the interface that need no network.

**Tools.** pytest 9.2.0, pytest-cov 7.1.0, Ruff 0.17.6.

**Steps.** Wrote `tests/conftest.py` and `tests/test_app.py`; ran them together with the
Quality area's `tests/test_security.py`.

**Key configuration.** Temporary SQLite by default; `TEST_DATABASE_URL` switches
`test_app.py` to a disposable PostgreSQL database. Staff password generated per run.
`ruff.toml` fixes the rule set (E4, E7, E9, F, W, I, B, UP; line length 100).

**Verification (real output).** `pytest.txt`, `ruff.txt`:
```
app/__init__.py       0      0   100%
app/main.py         266      7    97%
app/seed.py          20      3    85%
TOTAL               286     10    97%
============================= 140 passed in 20.20s =============================
All checks passed!
```
Of the 140, 65 are from `test_app.py` and 75 from `test_security.py`.

**Screenshots needed.** The `test-build` job and its test-result artifact in GitHub Actions;
a failing check blocking a pull request.

**Problems & solutions.** Ruff 0.17 enables many more rules by default and flagged lines in
the tests: the rule set is now explicit.

**Limitations.** PostgreSQL tests have **not** run (no PostgreSQL locally); the CI job
`postgres-integration` is the first real check, including the table-creation race. No
browser or load tests.

## Task 3: Dependencies and container image

**Function & agent.** Development and source management; Agent 2 (AI).

**Objective.** Consistent, pinned, non-root build (compare course lab 4).

**Tools.** pip-audit 2.10.1, Docker (in CI only).

**Steps.** Checked current versions on PyPI, pinned direct and transitive runtime packages,
audited them, wrote `Dockerfile`, `.dockerignore`, `.gitignore`, `.env.example`.

**Key configuration.** `python:3.12.16-slim-trixie` pinned by digest; user 10001; pip removed
from the image; HEALTHCHECK on `/health`; OCI labels with `REVISION` build argument;
allow-list `.dockerignore`; `--no-control-socket` because the app user has no home folder.

**Verification (real output).** `pip-audit-runtime.txt` and `pip-audit-dev.txt`:
```
No known vulnerabilities found
```
This is a result for 2026-11-26 only. Base image digest: `supply-chain-pins.txt`.

**Screenshots needed.** Successful image build and smoke test in CI; Trivy result.

**Problems & solutions.** No build was possible locally, so a container smoke test was added
to CI.

**Limitations.** Docker is not installed locally: **the image has never been built or run,
and has not been scanned.** CI performs the first build and smoke test. Development
dependencies are pinned at top level only, and no package hashes are enforced.

## Task 4: CI and release workflows

**Function & agent.** Development and source management; Agent 2 (AI).

**Objective.** Automatic checks before merge, and a traceable, scanned release image.

**Tools.** GitHub Actions, GHCR, Trivy 0.76.2, `gh`, `jq`.

**Steps.** Rewrote `ci.yml` and `release.yml`; verified action commit SHAs and image digests;
read the Trivy security advisory (GHSA-69fq-xp46-6x23).

**Key configuration.**
- CI: Ruff, pytest with JUnit and coverage, image build, container smoke test, PostgreSQL job.
- Release: tests, then wait for a successful Security run for the same commit, build once,
  scan that image, push to `ghcr.io/ayories/th-clover-devops`, write the manifest (digest,
  SHA, run URLs, pull request, approvers).
- `aquasecurity/trivy-action` removed. In March 2026 most of its tags were repointed to
  credential-stealing code. Trivy now runs from its image pinned by digest, without the
  Docker socket or any token. 0.76.2 is newer than the fixed versions of the advisories checked.
- Only official `actions/*` actions remain, pinned to full commit SHAs.

**Verification (real output).** `workflow-syntax.txt` (YAML parsed, every `run` block passed
`bash -n`, exit code 0) and `supply-chain-pins.txt`, for example:
```
actions/checkout v7.0.1 3d3c42e5aac5ba805825da76410c181273ba90b1 signature_verified=true
ghcr.io aquasecurity/trivy:0.76.2 sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb
```

**Screenshots needed.** CI run; release run with all jobs; manifest in the job summary; GHCR
package showing the digest and linked repository.

**Problems & solutions.** `security.yml` cannot be called as a reusable workflow, so the
release waits for its run on the same commit (up to about 25 minutes plus API time).

**Limitations.** **Neither workflow has run on GitHub.** The Security wait, image push,
digest capture and manifest steps are untested. Re-running a release rebuilds the image and
moves the SHA tag to a new digest. The image is not signed and has no provenance attestation
or SBOM.

## Task 5: Source management and documentation

**Function & agent.** Development and source management; Agent 2 (AI).

**Objective.** A clear Git workflow with peer review and release traceability (course lab 3).

**Tools.** Git, GitHub pull requests, CODEOWNERS.

**Steps.** Wrote `README.md`, `.github/CODEOWNERS`, the pull request template and this log.

**Key configuration.** Short-lived branches, pull request, one peer approval, protected
`main`; release identified by commit SHA and deployed by digest.

**Verification (real output).** Not verifiable offline. The Compose commands in the README
follow `infrastructure/docker-compose.local.yml` but have not been run.

**Screenshots needed.** Branch protection settings; a reviewed and merged pull request.

**Problems & solutions.** Only one GitHub account's role is confirmed (`@Cre8ivexiv`), so
other CODEOWNERS entries are commented out rather than guessed.

**Limitations.** Branch protection is not configured by these files and, per the task board,
`main` was unprotected. No peer review has happened yet.

## Update after deployment (26 November 2026)

AI-assisted. No team member has reviewed this work. The text above is kept as written before
integration. Raw evidence is held by the team outside the repository.

**What happened since.**
- Merged to `main` through pull requests #1 and #4 (neither reviewed). #4 added logging of rejected
  staff logins without credentials. A `clover_database_up` gauge was also added.
- CI passed, including the PostgreSQL integration job and the container build and smoke test. The first
  Security run failed on a libzstd1 vulnerability, fixed in the Dockerfile.
- Two release runs (110 s each) published images that were deployed by digest to staging and
  production. A synthetic form submission on production was read back from PostgreSQL.
- Local tests: 146 at the first push, 147 after pull request #4.

**Statements above that no longer apply.** "Nothing here has been committed, pushed or run on GitHub";
PostgreSQL tests have not run; the image has never been built, run or scanned; neither workflow has run
and the release steps are untested; 140 tests as the current count.

**Still true.** No branch protection or peer review. The local Docker environment has not been run.

**Differing records.** Task 1 says a 32 KiB body limit caused a 413 and the limit was raised to
128 KiB. The [quality log](../quality/TASKLOG.md) says the failure was the test's own mistake. The two
records differ and the repository history does not settle it. The current code caps requests at
128 KiB.
