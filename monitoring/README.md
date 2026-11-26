# TH-CLOVER monitoring (AI-assisted; role area: Operations & Reliability)

Prometheus scrapes both application environments; Alertmanager publishes critical alerts to the SNS
topic `th-clover-alerts`, which emails the subscriber. Behaviour and limits:
`../docs/operations/monitoring.md`.

| File | Purpose |
|---|---|
| `docker-compose.monitoring.yml` | `prom/prometheus:v3.13.5` (LTS line) and `prom/alertmanager:v0.35.1` |
| `prometheus.yml` | Scrapes `staging-app:8000` and `production-app:8000`, labelled `environment` |
| `alert-rules.yml` | `CloverAppDown` (production, critical), `CloverStagingDown` (warning, not sent) |
| `alert-rules.test.yml` | `promtool test rules` cases (synthetic series) |
| `alertmanager.yml.tmpl` | Alertmanager configuration with two placeholders |

## What the host needs (Platform / Ansible)

1. Copy these files to `/opt/th-clover/monitoring/`, mode `0644` (the containers run as `nobody`),
   with LF line endings.
2. Write `/opt/th-clover/monitoring/.env` (Compose reads it automatically):

   ```
   SNS_TOPIC_ARN=arn:aws:sns:eu-north-1:<account-id>:th-clover-alerts
   AWS_REGION=eu-north-1
   ```

3. `docker network create clover-monitoring` (once, before any application or monitoring `up`).
4. Start from that folder:

   ```bash
   cd /opt/th-clover/monitoring
   sudo docker compose -f docker-compose.monitoring.yml up -d
   ```

   After changing any file here, or `.env`, add `--force-recreate`: single-file bind mounts keep the
   old content until the container is recreated.
5. Instance role: `sns:Publish` on the topic. Instance metadata: IMDSv2 with
   `HttpPutResponseHopLimit: 2`, otherwise the container cannot obtain role credentials.
6. The email subscription must be confirmed once, by the recipient, or nothing is delivered.

## How the template is filled in

Alertmanager does not expand environment variables. The container entrypoint runs `sed` to replace
`__SNS_TOPIC_ARN__` and `__AWS_REGION__` in `alertmanager.yml.tmpl`, writes
`/alertmanager/alertmanager.rendered.yml` inside the container and starts Alertmanager with that file.
Compose stops with an error if `SNS_TOPIC_ARN` is not set. No access keys are used or stored.

## Access

Both UIs listen on the host's loopback address only and have no login. Use an SSH tunnel:

```bash
ssh -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 cloveradmin@<host>
```

Then open `http://localhost:9090/alerts` and `http://localhost:9093`.

## Check on the host

```bash
cd /opt/th-clover/monitoring
sudo docker compose -f docker-compose.monitoring.yml ps
curl -s 'http://127.0.0.1:9090/api/v1/query?query=up'
curl -s http://127.0.0.1:9093/metrics | grep 'alertmanager_notification_requests.*sns'
sudo docker compose -f docker-compose.monitoring.yml logs --tail 50 alertmanager
```

To test email delivery without stopping the application (this sends a real, clearly named test email):

```bash
sudo docker compose -f docker-compose.monitoring.yml exec alertmanager \
  amtool alert add TestNotification severity=critical environment=test \
  --annotation=summary='TEST ONLY - no action needed' --alertmanager.url=http://127.0.0.1:9093
```

Limits: 256 MiB (Prometheus) and 64 MiB (Alertmanager) memory; metrics kept 3 days or 500 MB.
