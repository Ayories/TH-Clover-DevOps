# Sustainability and resource use

AI-assisted (role area: Operations & Reliability). No utilisation has been measured yet.

## Scheduled stop (REQ-08)

- EventBridge Scheduler `th-clover-weekday-stop` stops the instance Monday to Friday at 19:00
  Europe/London (`StopHourLondon`; `StopScheduleState` can be set to `DISABLED` for an evening demo).
- It does not start the instance again. Someone starts it when needed, and the public IP changes.
  Left stopped, it also stays off over the weekend.
- Because staging and production share one host, the stop takes both down, plus monitoring. That is
  acceptable only for a proof of concept; with separate hosts only non-production would stop.
- Stopped instances incur no instance-hour charge; the EBS volume is still charged.
- Cost estimates: `docs/business/costs.md` (estimates, not bills).

### Recording the run-hour reduction

1. Choose a period, for example Monday 00:00 to Friday 00:00 UTC.
2. Note each start and stop time from CloudTrail event history (`StartInstances`, `StopInstances`) or
   the instance's state transition reason.
3. Reduction % = (hours in period - hours running) / hours in period x 100.

| Period | Hours in period | Hours running | Reduction % | Source | Status |
|---|---|---|---|---|---|
| | | | | | not yet measured |

## Right-sizing

| Container | Memory limit |
|---|---|
| Staging app and database | 256 MiB each |
| Production app and database | 256 MiB each |
| Prometheus | 256 MiB |
| Alertmanager | 64 MiB |
| Total of limits | 1,344 MiB, plus Ubuntu, Docker and the SSM agent |

Limits are ceilings, not measured use. The instance default is `t3.small` (2 GiB) with a swap file;
`t3.micro` (1 GiB) is allowed but likely to swap. Grafana was left out to save memory. Decide on size
only after measuring: if peak use stays well under 1 GiB with no swapping, test `t3.micro`.

## Log and metric retention

| Data | Retention |
|---|---|
| CloudWatch application logs | 14 days |
| Prometheus metrics | 3 days or 500 MB, whichever comes first |
| Alertmanager notification log and silences | 72 hours |
| Monitoring container logs | 3 files of 5 MB each |
| `deployments.log`, drill log | Kept (small; no personal data) |

Shorter retention saves storage but limits later investigation: export anything needed as evidence
within the period.

## How to check CPU and memory utilisation

On the host, while idle and again during a deployment:

```bash
date -u
uptime                      # load average; compare with 2 vCPUs
free -h                     # memory and swap
vmstat 5 6                  # si/so above zero means swapping
df -h /
sudo docker stats --no-stream
sudo docker system df       # old images use disk; remove unused ones with `sudo docker image prune`
```

`docker image prune` removes only dangling images. Do not use `-a` without checking: it can remove the
image needed for rollback.

From a machine with AWS access (or the EC2 console, Monitoring tab):

```bash
aws cloudwatch get-metric-statistics --region eu-north-1 --namespace AWS/EC2 \
  --metric-name CPUUtilization --dimensions Name=InstanceId,Value=<instance-id> \
  --start-time <ISO-time> --end-time <ISO-time> --period 3600 --statistics Average Maximum
```

Repeat with `--metric-name CPUCreditBalance` (the instance uses `standard` credits, so a zero balance
means it is throttled). CloudWatch has no memory metric without an extra agent, so use `free` and
`docker stats`. Save outputs to `evidence/operations/` with the date and what the host was doing.

## Trade-offs

- Stopping saves energy and money but makes the service unavailable and unmonitored.
- A smaller instance saves cost but risks failed deployments and slower recovery.
- One shared host uses less than three, at the price of weak isolation between environments.
