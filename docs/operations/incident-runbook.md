# Incident runbook

AI-assisted (role area: Operations & Reliability). The application-stop and manual rollback drills
have been run on the real host; **the runbook as a whole has not been exercised as an incident**, and
the database, host-failure and restore paths are untested.
Responder: the member holding the Operations role (Nana Owusu) and the named
holder of the `cloveradmin` key. A team member must agree this assignment.

Write down UTC times as you go: noticed, acknowledged, action taken, healthy again.

## 1. Detect

| Signal | Meaning |
|---|---|
| Email `TH-CLOVER FIRING CloverAppDown production` | Production app has not answered for over a minute |
| Email `TH-CLOVER FIRING CloverDatabaseDown production` | Production app has not reached its database for over a minute (rule unit-tested only, never drilled) |
| CloudWatch alarm email `th-clover-status-check-failed` | Host or host network problem |
| Deploy workflow fails with exit code 10 | Bad release, already rolled back |
| Deploy workflow fails with exit code 11 | Bad release, **not** restored: treat as an outage |
| A user reports a fault | May be a fault no alert covers: check `/health` and the logs |

## 2. Triage (aim: decide within 3 minutes)

First check whether the instance is simply stopped (evening schedule): EC2 console. If so, start it,
use the new public IP, and wait for the containers to start. That is not an incident unless someone
needed the service.

```bash
ssh -i ~/.ssh/th_clover_ed25519 cloveradmin@<IP>
sudo -i
cd /opt/th-clover
ENV=production          # or staging
PORT=80                 # staging: 8080
dc() { docker compose -p clover-$ENV --env-file $ENV/secrets.env --env-file $ENV/release.env \
  -f docker-compose.yml -f docker-compose.aws.yml "$@"; }

curl -sS -m 5 http://127.0.0.1:$PORT/health; echo
dc ps --all
tail -n 5 $ENV/deployments.log
free -h; df -h /
```

Application logs are in CloudWatch `/th-clover/$ENV` (not readable with `docker logs` if the daemon
cannot cache them). Do not copy customer data into tickets or screenshots.

| What you see | Go to |
|---|---|
| Fault started with a deployment | 3 Roll back |
| App container stopped or restarting, no recent change | `dc up -d`, then 5 Verify. If it fails again, read logs |
| `/health` 503 `"database":"unavailable"`, `db` not healthy | `dc restart db`, check disk space and `db` logs; restore only if data is damaged (4) |
| Disk full | `docker system df`, `docker image prune`; never delete volumes |
| Host unreachable | EC2 status checks; reboot or stop/start. Session Manager is the fallback if SSH fails |
| No fault found, monitoring is wrong | `cd monitoring && docker compose -f docker-compose.monitoring.yml ps` |

## 3. Roll back (target: healthy again within 10 minutes)

Before rolling back, ask: **did the bad release change the database schema or data?** Rollback changes
the application image only. The app creates missing tables and has no migrations; if a release altered
a table, the old code may not work with it. In that case prefer a forward fix, or restore (4).

```bash
/opt/th-clover/bin/rollback.sh $ENV
```

| Exit | Meaning | Action |
|---|---|---|
| 0 | Previous release healthy | Verify (5) |
| 1 | Previous release also unhealthy, or image unavailable | The fault is probably not the release: return to triage |
| 3 | No older release recorded (for example straight after an automatic rollback) | Deploy a known good digest through the Deploy workflow |
| 4 | A deployment or drill holds the lock | Wait for it; check the workflow run |

Rollback goes back one release only. The replaced values are kept in `$ENV/release.env.replaced`.
Do not run the Deploy workflow for the bad digest again.

## 4. Restore the database from a dump (destroys newer data)

Only when data is lost or damaged. Agree it with the team first: every request received after the dump
is lost. `deploy.sh` writes a dump before each deployment after the first (newest 5 kept, same disk as
the database, so a lost host loses them too). There is no scheduled backup. **This procedure has not
been tested.**

```bash
umask 077
ls -l $ENV/backups/
FILE=$ENV/backups/<timestamp>.sql.gz
gzip -t "$FILE"

dc stop app
# Safety copy of the current state, kept outside backups/ so deploy.sh does not prune with it.
dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' |
  gzip > $ENV/pre-restore-$(date -u +%Y%m%dT%H%M%SZ).sql.gz
dc exec -T db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
gunzip -c "$FILE" |
  dc exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > /dev/null
dc start app
```

If any command fails, stop and keep the safety copy. Delete the safety copy once the team accepts the
restore: it contains personal data.

## 5. Verify

```bash
RELEASE=$(sed -n 's/^RELEASE_SHA=//p' $ENV/release.env)
/opt/th-clover/bin/health-check.sh http://127.0.0.1:$PORT/health "$RELEASE"
dc exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from support_requests"'
tail -n 3 $ENV/deployments.log
```

Then: submit a synthetic request on the public form, see it on the staff page, and wait for the
`RESOLVED` email (production).

## 6. Review (within two working days, no blame)

Copy this into an issue:

```
Incident:            Date:            Environment:
Impact (who, how long):
Times (UTC): failure | alert | acknowledged | action | healthy
Detected by:         Was the 5 minute target met?   Was recovery under 10 minutes?
Cause:
What worked:         What did not:
Actions (owner, due date):
Evidence (log lines, screenshots):
```

## Planned work: silence the alert

```bash
cd /opt/th-clover/monitoring
docker compose -f docker-compose.monitoring.yml exec alertmanager amtool silence add \
  alertname=CloverAppDown --duration=30m --author=<your name> --comment='planned work' \
  --alertmanager.url=http://127.0.0.1:9093
```

Do not silence it before a failure-detection drill.
