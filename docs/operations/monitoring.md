# Monitoring, logging and alerting

AI-assisted (role area: Operations & Reliability, Nana Owusu). Not yet reviewed by a team member.
The monitoring stack runs on the deployed host. What has and has not been tested is stated below.

## What watches what

| Failure | Detected by | Notification |
|---|---|---|
| Production app stopped, crashed or not answering | Prometheus `CloverAppDown` (`up == 0` for 1 min) | Alertmanager -> SNS -> email |
| Production database not answering the app | Prometheus `CloverDatabaseDown` (`clover_database_up == 0` for 1 min); **unit-tested only, never drilled** | Alertmanager -> SNS -> email |
| Staging app not answering | `CloverStagingDown` (warning) | None. Visible in Prometheus and Alertmanager only |
| Host or its network failed | CloudWatch EC2 status-check alarm (in the CloudFormation stack) | SNS -> email |
| Failed deployment | `deploy.sh` health check, then automatic rollback | Result of the GitHub Actions run |

Staging is warning-only so that a deliberately stopped staging environment does not page anyone.
There is no on-call rota: the "page" in this proof of concept is one email.

## Flow and timing

```
app /metrics  <- scrape 15 s -  Prometheus  -> rule held 1 min -> Alertmanager (wait 10 s) -> SNS -> email
```

Design figure for the worst case before SNS is called: 15 s scrape + 15 s evaluation + 60 s hold +
10 s grouping = about 100 s. This is a calculation, not a measurement, and it excludes SNS email
delivery. The target is under 5 minutes to the email; measure it with the drill in
[drills.md](drills.md).

Measured on 26 November 2026 with the production app container stopped: alert firing after 65 s and
78 s, SNS accepted after 76 s and 88 s. The run 1 email arrived within 112 s (reported by a team member
(operator)); the run 2 email was not checked. Stopping staging showed `CloverStagingDown` without an
email. The host status-check alarm is in the OK state but has not been tested. A resolved message is sent when the alert clears; an unresolved alert is
repeated every 4 hours.

The one-minute hold means a restart during a normal deployment should not alert. A release that stays
down for more than a minute will alert even if automatic rollback follows.

## Logs

| Source | Where | Retention |
|---|---|---|
| Staging app and database | CloudWatch `/th-clover/staging` (`awslogs` driver) | 14 days |
| Production app and database | CloudWatch `/th-clover/production` | 14 days |
| Prometheus, Alertmanager | Docker `json-file` on the host, 3 x 5 MB each | By size |
| Deployments and rollbacks | `/opt/th-clover/<env>/deployments.log` | Kept on the host |

The application writes one JSON object per event and is designed not to log names, email addresses or
message text. A rejected staff login was seen in CloudWatch without username or password. A wider
sample, including PostgreSQL's own log lines, has not been reviewed (Quality's control).

Useful CloudWatch Logs Insights queries (select the log group first):

```
fields @timestamp, @message | filter @message like /"level":"error"/ | sort @timestamp desc | limit 50
```

```
fields @timestamp, @message | filter @message like /health_check_failed/ | sort @timestamp desc | limit 50
```

## Looking at the monitoring

Prometheus and Alertmanager listen on the host loopback only. Tunnel and browse as described in
[`monitoring/README.md`](../../monitoring/README.md).

## Tool choice

| Option | For | Against |
|---|---|---|
| Prometheus + Alertmanager (chosen) | Rules and routing are files in Git; the app already exposes `/metrics`; light enough for one 2 GB host | Runs on the same host it watches; we maintain it |
| Nagios (course lab) | Taught on the module; strong host and service checks | Separate server and object configuration to learn and keep; less natural with container metrics |
| CloudWatch only | Managed and independent of the host | Needs custom metrics or an agent for app health; brief warns against relying only on managed services |
| Grafana added | Dashboards | Extra memory and a login to secure; not needed to meet the target, so left out |

## Limits

- A database failure does not raise `CloverAppDown`: `/metrics` still answers, so `up` stays 1. The app
  exports the gauge `clover_database_up` and `CloverDatabaseDown` covers this case. The rule is
  unit-tested only; it has never been drilled on the host.
- Prometheus and Alertmanager run on the monitored host. If the host fails, only the EC2
  status-check alarm remains. If a monitoring container fails, nothing reports it.
- Nothing is monitored while the instance is stopped by the evening schedule.
- No check from outside: a security-group or public network fault is not detected.
- No application error-rate, latency, CPU, memory or disk alerts.
- "SNS accepted the message" does not prove the email arrived. An unconfirmed subscription drops it.
- Both application containers share the `clover-monitoring` network with Prometheus and Alertmanager,
  which have no authentication. A compromised app container could reach them (and the other app).
- Instance metadata hop limit 2 lets any container, not only Alertmanager, obtain the instance role's
  credentials. The role is limited to log writing, SNS publish and Systems Manager core access, with an
  explicit Deny on reading SSM parameters.
