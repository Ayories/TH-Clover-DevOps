# Operations and reliability task log (AI-assisted)

Date: 2026-11-26. Role area: Nana Owusu. All work below was done by an AI agent (Agent 5). **No team
member has reviewed or contributed to it.** Nothing was run on AWS, a browser or a real server.
"Verified" means static checks or local runs with fake parts. Evidence is in `evidence/operations/`
(outside the repository).

## Task 1: Monitoring and alerting

**Function & agent:** Operations and Reliability; AI agent 5.

**Objective:** a production application failure is emailed to the owner within 5 minutes, on a 2 GB host.

**Tools:** Prometheus 3.13.5 (LTS line), Alertmanager 0.35.1, promtool, amtool. Versions checked on
prometheus.io, GitHub releases and Docker Hub on 2026-11-26.

**Steps:** rewrote `monitoring/` (removed Grafana, the placeholder webhook and `alertmanager.yml`);
added the SNS receiver as a template, rule unit tests and a README for Platform.

**Key configuration:** scrape and evaluation 15 s; `for: 1m`; `group_wait: 10s`; production critical,
staging warning and not sent; loopback ports; limits 256 MiB and 64 MiB; retention 3 days / 500 MB;
external network `clover-monitoring`; `SNS_TOPIC_ARN` and `AWS_REGION` from `monitoring/.env`.

**Verification (real output, local):**

```
SUCCESS: prometheus.check.yml is valid prometheus config file syntax
SUCCESS: 2 rules found
promtool test rules alert-rules.test.yml  -> SUCCESS
amtool check-config                       -> SUCCESS (2 receivers)
severity=critical -> sns-email ; severity=warning -> visible-only
```

Files: `monitoring-config-validation.txt`, `compose-and-workflow-parse.txt`,
`local-alert-pipeline-SIMULATION.txt` (real binaries, fake application and fake SNS endpoint).

**Screenshots needed:** confirmed SNS subscription; `docker compose ps`; Prometheus targets and alert
firing; Alertmanager alert; firing and resolved emails.

**Problems & solutions:** the old configuration had no working receiver; Alertmanager cannot read
environment variables, so the entrypoint renders a template; container access to the instance role
needs metadata hop limit 2 (present in the CloudFormation template).

**Limitations:** the containers have not been started (no Docker here); SNS publish with the instance
role and email delivery are untested. A database failure raises no alert, because the app's `/metrics`
has no database signal. Monitoring shares the host it watches. Alertmanager 0.35.1 was two days old
when pinned.

## Task 2: Health check and rollback

**Function & agent:** as above. `deploy.sh` belongs to Platform and was not edited.

**Objective:** restore the previous release in one command, verify it and record how long it took.

**Tools:** Bash, Docker Compose (stubbed in tests), flock, ShellCheck 0.11.0.

**Steps:** rewrote `scripts/rollback.sh` and `scripts/health-check.sh` to match Platform's `deploy.sh`.

**Key configuration:** `previous.env` is the target; same `deploy.lock` as `deploy.sh`, skipped when
`deploy.sh` calls it with `CLOVER_LOCK_HELD=1`; never calls `deploy.sh`; JSON line with
`"trigger":"manual|auto"`; health check compares the exact `version` value.

**Verification (real output, fake docker/curl/releases):**

```
ok   - deploy: bad release exits 10 (rolled back, no deadlock)
ok   - rollback: lock held by another run
ok   - rollback: manual
ok   - rollback: unhealthy target fails
failures: 0
```

Files: `unit-checks-FAKE-fixtures.txt`, `shellcheck.txt`.

**Screenshots needed:** a real rollback with exit code, `/health` SHA before and after, and the log line.

**Problems & solutions:** the lock held by `deploy.sh` would have blocked its own rollback call
(solved with the agreed variable). Automatic rollback writes two log lines, so rollback lines carry a
trigger and DORA counts the failure once.

**Limitations:** never run against real containers. One release back only. No database reversal. After
an automatic rollback there is no older target for a manual one. No timing measured.

## Task 3: Drill and DORA tooling

**Function & agent:** as above.

**Objective:** measure detection time and compute the four DORA measures from real records.

**Tools:** Bash, Python 3 standard library, Prometheus and Alertmanager HTTP APIs.

**Steps:** wrote `scripts/ops/failure-drill.sh`, `dora.py`, `test_dora.py`, `test_scripts.sh`.

**Key configuration:** the drill needs `--yes`, refuses unless production is healthy and no alert is
active, takes the deployment lock, restores on exit, and counts an SNS success as publish requests
minus failed requests. DORA defaults to production.

**Verification (real output):** 5 `dora.py` unit tests `OK` with fake logs; the drill script completed
against the local simulation (`drill exit=0`). No project measurement exists.

**Screenshots needed:** drill terminal output; email received time; `dora.py` output on real logs.

**Problems & solutions:** Alertmanager's `notifications_total` counts attempts, so the drill uses the
request counters instead.

**Limitations:** email arrival is read by hand. A deploy that stops before changing anything is logged
as `failed` and may overstate the change failure rate.

## Task 4: Monitoring workflow

**Function & agent:** as above.

**Objective:** replace a workflow that could not work.

**Tools:** GitHub Actions, Docker, promtool, amtool, ShellCheck.

**Steps:** removed the 5-minute public uptime probe: the security group admits only one authorised
address, so GitHub runners cannot reach `/health`, and the probe would fail on every run. Replaced it
with a check of monitoring files and operations scripts on pull requests. It starts the stack with a
placeholder topic and no credentials.

**Key configuration:** `permissions: contents: read`; checkout pinned to the same SHA as
`security.yml`; no secrets.

**Verification:** the YAML parses. **The workflow has not run.**

**Screenshots needed:** a green run on the pull request.

**Problems & solutions:** see Steps.

**Limitations:** it checks files, not the live service. It has a path filter, so do not make it a
required status check.

## Task 5: Operations documents

**Function & agent:** as above.

**Objective:** runbook, drills, monitoring, DORA, sustainability and acceptance criteria.

**Tools:** Markdown; Viva 1 slides, brief, `docs/business/`.

**Steps:** wrote `docs/operations/*` and updated `docs/acceptance-criteria.md`.

**Key configuration:** every result table says "not yet run" or "not yet measured".

**Verification:** commands were written against the repository files; they have not been run on a host.

**Screenshots needed:** listed in `drills.md`.

**Problems & solutions:** no ready-made bad image exists and the pipeline only accepts images from
`main`, so drill 2 builds a harmless unhealthy image and runs `deploy.sh` on the host.

**Limitations:** the database restore and drill 2 image steps are untested. The responder assignment
needs the team's agreement.

## Software fetched on the development machine

Official release archives from `github.com/prometheus`, each checked against the release
`sha256sums.txt`: `prometheus-3.13.5.linux-amd64.tar.gz` (104,644,132 bytes) and
`alertmanager-0.35.1.linux-amd64.tar.gz` (42,637,642 bytes), fetched twice because the WSL temporary
folder was cleared. `promtool` and `amtool` remain in WSL `~/bin`. `shellcheck-py` was added to
`~/th-clover-venv`.

## Update after deployment (26 November 2026)

AI-assisted. No team member has reviewed this work. The text above is kept as written before
integration. Raw evidence is held by the team outside the repository.

**What happened since.**
- Monitoring runs on the AWS host. The subscription was confirmed by a team member (operator).
- Application-stop drill, two of three planned runs: alert firing +65 s and +78 s, SNS accepted +76 s
  and +88 s, healthy 2 s after restore began. The run 1 email arrived within 112 s (reported by a team
  member (operator)); the run 2 email was not checked.
- Manual rollback drills: staging 6.8 s and 6.7 s, production 6.8 s, row counts unchanged.
- `dora.py` ran on real logs (see `dora.md`); failure figures come from drills.
- A `clover_database_up` gauge and a `CloverDatabaseDown` rule were added (three rules in total). The
  rule is unit-tested only, never drilled.
- The monitoring workflow passed on pull request #1.
- Idle utilisation was measured (see `sustainability.md`).
- Problem found: a drill script's input was swallowed by `docker compose exec`. It was fixed and rerun
  and did not change the server.

**Statements above that no longer apply.** "Nothing was run on AWS, a browser or a real server"; the
containers have not been started; SNS publish and email delivery untested; "2 rules found" as the
current count; "A database failure raises no alert"; rollback never run against real containers; no
timing or project measurement exists; "The workflow has not run".

**Still not tested.** Automatic rollback on the live host (drill 2), database restore, the database-down
alert, the host status-check alarm, the scheduled stop and a third detection run.
