# TH-CLOVER: Evolving Ltd DevOps transformation

CMP6237 student proof of concept: a small customer-service web application (Flask +
PostgreSQL) with automated testing, security checks, release, deployment and monitoring.
Parts of this repository were produced with AI assistance; the team members named below
mark role areas, not authorship. **Do not enter real customer data.**

## Roles
| Area | Member | Main paths |
|---|---|---|
| Business and delivery | Galen Kudwoli | `docs/business/` |
| Development and source management | AbdulQuadri Sanusi | `app/`, `tests/`, `Dockerfile`, CI and release workflows |
| Platform and infrastructure | Jesutofunmi Jinadu | `infrastructure/`, `scripts/deploy.sh` |
| Quality and security | Timilehin A. Ibrahim | security tests and scans, `docs/quality/` |
| Operations and reliability | Nana Owusu | `monitoring/`, rollback and health scripts |

## Application
| Route | Purpose | Protection |
|---|---|---|
| `GET /`, `POST /requests` | Public contact form | CSRF token |
| `POST /api/requests` | Public JSON API (`name`, `email`, `message`) | JSON content type, validation |
| `GET /api/requests` | List requests | Staff HTTP Basic |
| `GET /staff`, `POST /staff/requests/<id>/status` | Staff list and status change | Staff HTTP Basic, CSRF on POST |
| `GET /health` | Database and release check (200 or 503) | none |
| `GET /metrics` | Prometheus counter `clover_http_requests_total` | none |

Stored per request: name (max 100), email (max 254), message (max 2000), status
(`new`, `in_progress`, `resolved`) and creation time (UTC). Request logs are one JSON line
on stdout holding method, route name, status and duration only: no personal data.

### Settings
| Variable | Meaning |
|---|---|
| `DATABASE_URL` | e.g. `postgresql+psycopg2://user:password@db:5432/name`; SQLite if unset |
| `SECRET_KEY` | Signs the session cookie; a random one is used (with a warning) if unset |
| `STAFF_USERNAME`, `STAFF_PASSWORD_HASH` | Werkzeug hash; staff access is refused if unset |
| `APP_ENV`, `RELEASE_SHA` | Reported by `/health` |

## Local development
Compose definitions live in `infrastructure/`. From the repository root:

```bash
cp infrastructure/local.env.example infrastructure/local.env   # then edit the values
docker compose --env-file infrastructure/local.env \
  -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.local.yml up --build -d
curl http://127.0.0.1:8000/health
# Synthetic demo rows (safe to repeat):
docker compose --env-file infrastructure/local.env \
  -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.local.yml \
  exec app python -m app.seed
```

To create the staff password hash after the image is built (it prompts for the password),
then paste the result into `local.env` inside **single quotes**:

```bash
docker run --rm -it th-clover:local python -c \
  "from getpass import getpass; from werkzeug.security import generate_password_hash as g; print(g(getpass()))"
```

### Without Docker (tests and a quick run)
Python 3.12:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check app tests
pytest -q tests --cov=app
pip-audit -r requirements-dev.txt
flask --app app.main run          # SQLite; variables are listed in .env.example
```

Tests need no network. To run them against a **disposable** PostgreSQL database (tables are
dropped), set `TEST_DATABASE_URL` and run `pytest -q tests/test_app.py`.

## Branching and review
- `main` is always releasable and is to be protected. No direct or force pushes.
- Work on a short-lived branch from `main`: `feature/<topic>`, `fix/<topic>` or `docs/<topic>`.
  Aim to merge within a few days.
- Open a pull request, fill in the template and link the issue and acceptance criterion.
- One peer who is not the author reviews and approves. All required checks must pass.
- Merge, then delete the branch.

Branch protection is a GitHub setting, not a file, so the team must apply it to `main`:
require a pull request with 1 approval, dismiss stale approvals, require the checks
`test-build`, `postgres-integration`, `secret-scan`, `dependency-scan`, `sast`,
`image-scan` and `iac-lint`, include administrators, and block force pushes and deletion.
`CODEOWNERS` currently names only the one confirmed account.

## Pipeline
| Workflow | When | What it does |
|---|---|---|
| `ci.yml` | pull request, push to `main` | Ruff, pytest (JUnit and coverage artifact), image build and container smoke test, PostgreSQL integration tests |
| `security.yml` | pull request, push to `main` | Secret, dependency, code, image and infrastructure checks |
| `release.yml` | push to `main` | Tests, waits for a successful Security run, builds once, Trivy-scans that image, pushes to GHCR, writes the release manifest |
| `deploy.yml` | manual | Deploys a chosen digest to `staging` or `production` |

## Versioning and traceability
- A release is identified by its 40-character commit SHA on `main`. The image is
  `ghcr.io/ayories/th-clover-devops:<sha>` and is **deployed by digest**, never by a moving tag.
- The image label `org.opencontainers.image.revision` and `/health` both show the SHA.
- The `release-manifest` artifact (kept 90 days) holds:
  - `release-manifest.json`: image digest, commit SHA, release run URL (with test results),
    Security run URL, pull request number, approving reviewers and time;
  - `release.env`: `APP_IMAGE` and `RELEASE_SHA`;
  - `trivy-release.txt`: the image scan output.

Chain: issue → pull request (review, checks) → commit SHA → release run → image digest →
deployment record. If no pull request or approval is found, the manifest records `null` or
an empty list and the run shows a warning; it does not invent one.

To release, merge a pull request. To deploy, run **Deploy** with the SHA and digest from the
manifest. Rollback redeploys the previous digest (see `scripts/rollback.sh`). Save the
manifests needed as assessment evidence before the 90 days end.

Supply chain: actions are pinned to commit SHAs, container images used by the pipeline and
the base image to digests, and Python packages to exact versions. Dependabot proposes updates.

## Known limitations
- HTTP only: Basic auth credentials and form data are not encrypted in transit. Access must
  stay restricted to the authorised network, with test accounts and synthetic data only.
  TLS is required before any real use.
- One shared staff account: no individual staff identity, audit trail, lockout or rate limit.
- Tables are created on first use; there are no schema migrations, so a schema change needs a
  migration plan before it can be deployed or rolled back safely.
- No data retention or deletion function for personal data.
- One gunicorn worker (8 threads) keeps metrics correct; counters reset on restart.
- `/metrics` and `/health` are unauthenticated.
