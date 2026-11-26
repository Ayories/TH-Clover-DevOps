# Recovery and detection drills

AI-assisted (role area: Operations & Reliability). On 26 November 2026 drill 1 was run twice (of three
planned) and drill 3 three times; **drill 2 has not been run**. Fill the tables only from real runs,
and keep the raw output in `evidence/operations/` (held by the team outside the repository).

Use synthetic data only. Tell the team before a drill: drill 1 takes production down for a few minutes.

## Before any drill

- Stack deployed, Ansible run, SNS email subscription **confirmed**.
- The evening stop is not about to run.
- On the host:

```bash
sudo docker compose -f /opt/th-clover/monitoring/docker-compose.monitoring.yml --project-directory /opt/th-clover/monitoring ps
curl -s 'http://127.0.0.1:9090/api/v1/query?query=up'      # production value must be 1
curl -s http://127.0.0.1/health
```

## Drill 1: failure detection (REQ-06, target under 5 minutes to the email)

Needs a healthy production deployment and no active `CloverAppDown`. On the host:

```bash
sudo /opt/th-clover/ops/failure-drill.sh --yes 2>&1 | tee ~/drill1-$(date -u +%Y%m%dT%H%M%SZ).txt
```

The script records T0, stops the production app container, waits (up to 300 s) for the alert to fire
and for SNS to accept the publish, starts the same container, checks health and appends one JSON line
to `/opt/th-clover/drills/failure-drills.log`. It restores the app even if interrupted; if the host
connection is lost, check `sudo docker ps` and start the container by hand.

Then, by hand: open the email, record the **received** time (message headers) and convert to UTC.
Time to email = received time - T0. This is the figure that counts for REQ-06.

Wait at least 5 minutes (for the `RESOLVED` email) before another run. Three runs are planned.

| Run | Date | T0 (UTC) | Alert firing (s) | SNS accepted (s) | Email received (s) | App healthy after restore (s) | Pass (< 300 s to email) |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-26 | 07:46:08 | 65 | 76 | within 112 s (07:47 minute) | 2 | Yes |
| 2 | 2026-11-26 | 08:18:12 | 78 | 88 | not checked | 2 | Not established: email not checked |
| 3 | not run | | | | | | |

The run 1 email time was reported by a team member (operator); no headers or screenshot were kept.

## Drill 2: bad release, automatic rollback (staging, REQ-04)

You need a harmless image that starts but never becomes healthy. The pipeline refuses images that were
not built from `main`, so this drill runs `deploy.sh` on the host. Staging must already run a good
release.

1. Build and push the drill image from a machine that has Docker and **your own** permission to push to
   the package (do not leave a write token on the host). `<good>` is a released digest:

```bash
printf 'FROM ghcr.io/ayories/th-clover-devops@sha256:<good>\nCMD ["python", "-c", "import time; time.sleep(3600)"]\n' |
  docker build -t ghcr.io/ayories/th-clover-devops:drill-unhealthy -
docker push ghcr.io/ayories/th-clover-devops:drill-unhealthy      # note the "digest: sha256:..." line
```

2. On the host (the all-zero SHA ending `bad` marks a drill in the log):

```bash
date -u +%FT%TZ
sudo /opt/th-clover/bin/deploy.sh staging \
  ghcr.io/ayories/th-clover-devops@sha256:<drill digest> 0000000000000000000000000000000000000bad
echo "exit=$?"        # expected: 10
date -u +%FT%TZ
curl -s http://127.0.0.1:8080/health
sudo tail -n 2 /opt/th-clover/staging/deployments.log
```

Expected: health attempts fail for about two minutes, then a `rollback` line (`trigger` `auto`) and a
`deploy` line with `rolled_back`. `/health` shows the previous SHA. Delete the `drill-unhealthy` tag
from the package afterwards.

Failure injected = the `started` time on the `deploy` line; recovered = its `finished` time.

**Not run.** Automatic rollback has not been tested on the live host; only a simulation with stub
`docker` and `curl` exists (29 of 29 checks passed).

| Run | Date | Exit code | Deploy line seconds (inject to recovered) | Rollback line seconds | Previous SHA healthy | Pass (< 600 s) |
|---|---|---|---|---|---|---|
| 1 | not run | | | | | |

## Drill 3: manual rollback (REQ-04)

Needs two different good releases, A then B, deployed to the environment (staging shown; use port 80
and `production` for the production run).

```bash
sudo -i
cd /opt/th-clover
dc() { docker compose -p clover-staging --env-file staging/secrets.env --env-file staging/release.env \
  -f docker-compose.yml -f docker-compose.aws.yml "$@"; }
count() { dc exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from support_requests"'; }

grep RELEASE_SHA staging/previous.env staging/release.env     # A and B must differ
curl -s http://127.0.0.1:8080/health; echo                    # shows B
count
date -u +%FT%TZ
./bin/rollback.sh staging; echo "exit=$?"
date -u +%FT%TZ
curl -s http://127.0.0.1:8080/health; echo                    # shows A
count                                                         # same or higher than before
tail -n 1 staging/deployments.log
```

For another run, deploy B again first. Timing starts when rollback starts, so it excludes the time to
notice a fault and decide; state this with the result.

| Run | Date | Environment | From SHA | To SHA | Seconds (log) | Row count before / after | Pass (< 600 s) |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-26 | staging | `36c9a46` | `291ac6b` | 7 (6.8 wall) | 3 / 3 | Yes |
| 2 | 2026-11-26 | staging | `36c9a46` | `291ac6b` | 7 (6.7 wall) | 3 / 3 | Yes |
| 3 | 2026-11-26 | production | `36c9a46` | `291ac6b` | 7 (6.8 wall) | 4 / 4 | Yes |

Each run was followed by a redeploy of `36c9a46`. Rollback restores the application image only;
database restore was not tested.

## Evidence to keep

Terminal output of each drill, the `deployments.log` and drill log lines, the firing and resolved
emails (hide addresses), a screenshot of the Prometheus alert, and the CloudWatch log lines from the
period. The firing and resolved emails were not captured for the 26 November runs.
