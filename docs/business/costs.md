# AWS cost ESTIMATE

> **Update 2026-11-26:** the AWS free-plan project is locked to Europe (Stockholm), `eu-north-1`, so the stack is
> built there, not in London. The estimates below used London prices; read them as indicative only. The console
> shows US$100.00 credit remaining until 26 May 2027 and states that a free-plan account is not charged.

> **ESTIMATE only, not a bill or a quote.** AI-assisted (Agent 1), 26 November 2026. Role area:
> Galen Kudwoli. Not reviewed by a team member. Prices accessed 26 November 2026. US dollars,
> excluding tax; exchange rates not applied.

## Recommendation

- **Instance: `t3.small`** (2 vCPU, 2 GiB).
- **Monthly estimate at list price: about $7.68 with weekday-evening shutdown, $22.36 running 24/7.**
- **Budget: $15 a month**, alerting at 80% actual spend ($12) and 100% forecast.

## Assumptions

1. Region `eu-west-2` (London), on-demand Linux pricing, one instance, no Elastic IP.
2. A month is 730 hours when running continuously.
3. Shutdown case: 10 hours a day, 5 days a week, 52/12 weeks, about **217 hours**. The schedule only
   **stops** the instance (weekdays 19:00 London). This case assumes someone starts it at about 09:00
   on weekdays and leaves it off at weekends. More evening or weekend work raises the figure.
4. 16 GB gp3 root volume at the included 3,000 IOPS and 125 MB/s; charged while stopped.
5. One auto-assigned public IPv4 address while running. A stopped instance gets a new address when
   started again (Amazon Web Services, 2026a), and no address charge is assumed while stopped.
6. At most 1 GB of logs a month, 14-day retention, one CloudWatch alarm.
7. Under 1,000 alert emails and 100 GB of internet data out a month.
8. CPU credits in `standard` mode (as drafted in the template), so no surplus-credit charges.
9. No snapshots, load balancer, NAT gateway, custom domain or custom CloudWatch metrics.
10. The GitHub repository is public and uses standard GitHub-hosted runners.

## Unit prices used

| Item | Price | Source |
|---|---|---|
| `t3.micro` / `t3.small` | $0.0118 / $0.0236 per hour | Amazon Web Services (2026b) |
| gp3 storage / snapshot | $0.0928 / $0.053 per GB-month | Amazon Web Services (2026c) |
| Public IPv4 | $0.005 per hour | Amazon Web Services (2026d) |
| CloudWatch Logs ingest / store | $0.5985 per GB / $0.0315 per GB-month | Amazon Web Services (2026e) |
| CloudWatch standard alarm | $0.10 per month | Amazon Web Services (2026e) |
| CloudWatch free allowance | 5 GB logs, 10 alarm metrics a month | Amazon Web Services (2026f) |
| SNS email | first 1,000 free, then $0.00002 each | Amazon Web Services (2026g) |
| EventBridge Scheduler | 14 million invocations free a month | Amazon Web Services (2026h) |
| AWS Budgets (notifications only) | free | Amazon Web Services (2026i) |
| Systems Manager Run Command on EC2 | no additional charge | Amazon Web Services (2026j) |
| CloudFormation (AWS resource types) | no additional charge | Amazon Web Services (2026k) |
| KMS AWS-managed key (`aws/ebs`) | no monthly fee; 20,000 requests free | Amazon Web Services (2026l) |
| Internet data out | first 100 GB free a month | Amazon Web Services (2026m) |
| GitHub Actions, public repository, standard runners | free | GitHub (2026a) |
| GitHub Packages / GHCR | public packages free; container storage and bandwidth currently free | GitHub (2026b) |

## Monthly ESTIMATE (list price, no sign-up credits)

| Item | `t3.micro` 24/7 | `t3.small` 24/7 | `t3.micro` shutdown | `t3.small` shutdown |
|---|---:|---:|---:|---:|
| EC2 compute | 8.61 | 17.23 | 2.56 | 5.11 |
| 16 GB gp3 | 1.48 | 1.48 | 1.48 | 1.48 |
| Public IPv4 | 3.65 | 3.65 | 1.08 | 1.08 |
| CloudWatch, SNS (within allowances) | 0.00 | 0.00 | 0.00 | 0.00 |
| Scheduler, Budgets, SSM, CloudFormation, KMS | 0.00 | 0.00 | 0.00 | 0.00 |
| GitHub Actions and GHCR | 0.00 | 0.00 | 0.00 | 0.00 |
| **Total (US$)** | **13.75** | **22.36** | **5.12** | **7.68** |

Totals are calculated before rounding.

Possible extras: if the CloudWatch allowances are already used elsewhere in the account, add about
$0.72 (1 GB of logs and one alarm). A retained 16 GB snapshot would add up to $0.85 a month.

Shutdown saves $14.68 (about 66%) for `t3.small`. For a short project: seven days of continuous
running (28 November to 4 December) is about **$5.15** for `t3.small`.

## Instance size

The drafted container memory limits are 256 MB for each of two applications and two PostgreSQL
databases, plus 256 MB for Prometheus and 64 MB for Alertmanager: 1,344 MB in total, before Ubuntu,
Docker and the SSM agent. `t3.micro` has 1 GiB; `t3.small` has 2 GiB (Amazon Web Services, 2026n).
Limits are ceilings rather than measured use, but a 1 GiB host risks swapping or killed containers
during a deployment or demonstration. The extra cost is about $2.56 a month with shutdown. Memory use
should be measured after deployment.

**CPU caveat.** Baseline is 20% per vCPU for `t3.small` (Amazon Web Services, 2026n). T3 instances
get no launch credits (Amazon Web Services, 2026o), so in `standard` mode a new instance is held near
baseline until it earns credits; the first configuration run may be slow. T3 defaults to `unlimited`,
where sustained excess use is billed at $0.05 per vCPU-hour (Amazon Web Services, 2026p; 2026m).
`standard` caps the cost; switch temporarily only if provisioning is too slow.

## Free Tier: check the account type first

The rules depend on when the AWS account was created. We have not checked the team's account.

| | Created on or after 15 July 2025 | Created before 15 July 2025 |
|---|---|---|
| Model | $100 credit, up to $100 more for activities; choice of free or paid plan | 12 months of free usage limits from account creation |
| Duration | Free plan ends after 6 months or when credits are used | Nothing from the 12-month offer after month 12 |
| EC2 | `t3.micro` and `t3.small` are marked eligible; usage draws on credits | 750 hours a month of `t2.micro`, or `t3.micro` only where `t2.micro` is unavailable |
| London | Covered by credits | `t2.micro` is priced in London, so we infer `t3.micro` and `t3.small` are **not** covered |
| Public IPv4 | Drawn from credits | 750 hours a month |
| Sources | Amazon Web Services (2026q; 2026r; 2026s) | Amazon Web Services (2026t; 2026b) |

Also for new accounts: setting up a cost budget is one of the activities that earns $20 (Amazon Web
Services, 2026s), and a free plan restricts some services (Amazon Web Services, 2026q), so confirm
that every service above is available before creating the stack. The legacy EBS allowance was not
confirmed by the pages we could read, so it is not relied on.

## Budget alert

Use **$15**. It leaves room above the $7.68 expected for evening demonstrations, while a month of
24/7 running ($22.36) triggers the forecast alert. The drafted template defaults to $20; pass
`MonthlyBudgetUsd=15` when creating the stack, or change the default. Keep credits excluded from the
budget calculation (the draft does) so that usage stays visible. A budget **warns**; it does not stop
spending.

## Operating consequences

- Stopping the one host stops staging, **production** and monitoring together.
- Nothing starts it again automatically, and its public IP changes each time.
- Disable the stop schedule (`StopScheduleState=DISABLED`) for evening rehearsals and re-enable it.
- A Friday-evening stop lasts until someone starts the instance; a weekend start runs until Monday.
- After assessment and moderation, delete the stack and check for leftover volumes, snapshots and
  log groups.
