# Tool selection, contracts and licences

> AI-assisted (Agent 1, Business & Delivery), 26 November 2026. Role area: Galen Kudwoli.
> Not reviewed by a team member. This is not legal advice.

## Method

Each option is treated as a bid. Score 1 (poor) to 5 (strong); weighted score = sum of weight times
score, divided by 100. Weights reflect a small team, about one week of build time left, a small budget
and the brief's rule that the assessed infrastructure must be configured and explained by the team
(Birmingham City University, 2026). **Scores are judgements, not measurements.**

## CI/CD

| Criterion (why) | Weight | GitHub Actions | Jenkins | GitLab CI |
|---|---:|---:|---:|---:|
| Link from change to review, test and release (REQ-02) | 25 | 5 | 3 | 3 |
| Set-up and upkeep effort (little time) | 25 | 5 | 2 | 3 |
| Cost (small budget) | 15 | 5 | 2 | 4 |
| Security of credentials and supply chain (REQ-01) | 20 | 4 | 3 | 4 |
| Team and course familiarity | 15 | 3 | 5 | 2 |
| **Weighted score** | **100** | **4.50** | **2.90** | **3.20** |

- **Chosen: GitHub Actions.** Code is already on GitHub, standard runners are free for public
  repositories (GitHub, 2026a), and OIDC removes long-lived AWS keys (GitHub, 2026c).
- Jenkins is used in the course labs, but needs a server we would run and secure; its documentation
  recommends 4 GB or more of RAM for a small team (Jenkins, 2026).
- GitLab's free tier gives 400 compute minutes a month on GitLab.com (GitLab, 2026) and would mean
  moving or mirroring the repository.
- Trade-offs: dependence on GitHub; third-party actions are a supply-chain risk (see
  [risks-ethics.md](risks-ethics.md)).
- Equal weights give the same ranking (4.4, 3.0, 3.2).

## Infrastructure as Code

| Criterion | Weight | CloudFormation | Terraform |
|---|---:|---:|---:|
| Fit with an AWS-only scope | 25 | 5 | 4 |
| State handling (AWS-managed stack against a state file to protect) | 25 | 5 | 2 |
| Learning in the time available | 20 | 3 | 3 |
| Portability to another provider | 15 | 1 | 4 |
| Licence and cost | 15 | 5 | 3 |
| **Weighted score** | **100** | **4.00** | **3.15** |

- **Chosen: CloudFormation**, with no extra charge for AWS resource types (Amazon Web Services,
  2026k). Ansible configures the operating system.
- Terraform 1.6 and later is under the Business Source Licence, which limits competing hosted or
  embedded offerings (HashiCorp, 2023; IBM, 2024). OpenTofu is an MPL-2.0 alternative.
- If portability were the main goal, the result could reverse.

## Runtime platform

| Criterion | Weight | EC2 + Docker Compose | Amazon ECS | Kubernetes (EKS) |
|---|---:|---:|---:|---:|
| Team configures and explains the infrastructure | 25 | 5 | 3 | 4 |
| Cost | 25 | 5 | 3 | 1 |
| Operating effort in the time available | 20 | 4 | 3 | 1 |
| Consistent deployment and rollback | 20 | 4 | 5 | 5 |
| Resilience and scaling | 10 | 1 | 4 | 5 |
| **Weighted score** | **100** | **4.20** | **3.50** | **2.95** |

- **Chosen: EC2 with Compose.** An EKS cluster fee alone is $0.10 an hour, about $73 for a 730-hour
  month (Amazon Web Services, 2026u), against $22.36 for the whole 24/7 estimate.
- Accepted weakness: one host is a single point of failure for both environments.

## Monitoring

| Criterion | Weight | Prometheus + Alertmanager, with CloudWatch | Nagios Core |
|---|---:|---:|---:|
| Detect and report within 5 minutes (REQ-06) | 25 | 5 | 4 |
| Application metrics | 20 | 5 | 2 |
| Set-up effort | 20 | 4 | 3 |
| Resource use and cost | 15 | 3 | 4 |
| Team and course familiarity | 10 | 2 | 5 |
| Notification by SNS email | 10 | 5 | 3 |
| **Weighted score** | **100** | **4.20** | **3.40** |

- **Chosen: Prometheus and Alertmanager** for application metrics (Prometheus, 2026), plus a
  CloudWatch status-check alarm because on-host monitoring cannot report the loss of its own host.
  CloudWatch Logs holds the application logs centrally.
- Nagios is used in the course material and remains a reasonable alternative for host checks.

## Contracts and terms

| Agreement | Points that affect this project |
|---|---|
| AWS Customer Agreement, last updated 29 October 2026 (Amazon Web Services, 2026v) | The account holder is responsible for all activity, correct configuration, security and backups. Customers choose where content is stored. Liability is capped at fees paid in the previous 12 months. Its table assigns European customers to AWS EMEA SARL under Luxembourg law; confirm the entity on the account. |
| AWS shared responsibility model (Amazon Web Services, 2026w) | AWS secures facilities, hardware and virtualisation. We patch Ubuntu and the application, set security groups and IAM, and protect the data. |
| EC2 SLA (Amazon Web Services, 2022) | A single instance has a 99.5% monthly uptime commitment with service credits. Credits do not compensate business loss. |
| GitHub Terms of Service, effective 27 April 2026 (GitHub, 2026d) | One login per person (supports REQ-01). Public content may be viewed and forked by other users. Service is provided as is; GitHub may suspend access. |
| GitHub terms for Actions and Packages (GitHub, 2026e) | Hosted runners are for work on the repository's software; misuse or disproportionate load is prohibited. |

**Ownership gap.** The repository is public, sits on a personal account and has no `LICENSE` file.
The team and client should agree who owns the work and what licence applies before any handover.

## Open-source licences

Checked on 26 November 2026 from each project's default-branch licence file, not from the pinned
version (`evidence/business/licence-check.txt`). Container base images include further packages that
were not checked.

| Component | Licence |
|---|---|
| Flask, Werkzeug, Jinja, MarkupSafe, Click, ItsDangerous | BSD-3-Clause |
| SQLAlchemy, Blinker, pytest, pytest-cov, Ruff, Gitleaks | MIT |
| Gunicorn | MIT-style permissive text |
| psycopg2 | LGPL-3.0-or-later (see its licence file for exceptions) |
| prometheus_client, Prometheus, Alertmanager, Docker Engine (Moby), Compose | Apache-2.0 |
| Trivy, pip-audit, Bandit | Apache-2.0 |
| packaging | Apache-2.0 or BSD |
| Python, typing_extensions | Python Software Foundation licence |
| PostgreSQL | PostgreSQL Licence (permissive) |
| Ansible, ShellCheck | GPL-3.0 |
| cfn-lint | MIT-0 |

- Permissive licences require notices to be kept. psycopg2's LGPL matters if the image is
  distributed: keep its notices and do not prevent users replacing the library.
- GPL tools are used to operate or check the system; they are not part of the application.
- `gitleaks-action` has its own end-user licence and needs a key for organisation accounts
  (Gitleaks, 2026). The drafted security workflow runs the MIT-licensed binary instead.
- Grafana (AGPL-3.0) is not part of the agreed architecture.

## Supplier lock-in

| Dependency | Lock-in | Mitigation or exit |
|---|---|---|
| CloudFormation, SSM document, IAM OIDC, SNS, Scheduler, CloudWatch | High: AWS-specific | Keep them thin; deploy logic lives in `deploy.sh` |
| GitHub Actions, environments, GHCR | Medium | Git history is portable; rewrite workflows; push images elsewhere |
| Dockerfile, Compose, Ansible, PostgreSQL, Prometheus | Low | Run on another Linux host; replace the `awslogs` override and SNS receiver |

## What an SLA with Evolving Ltd would cover

This proof of concept offers **no** SLA; the brief's figures are evaluation targets. A later
agreement should set out:

1. Service scope, environments, supported hours and exclusions (including AWS and GitHub outages).
2. Availability target and how it is measured. It should not promise more than the design supports:
   one host, with a scheduled stop, cannot support a 24/7 commitment.
3. Incident severity levels, response times, and detection and recovery targets.
4. Backup, restore, recovery point and recovery time. **No backup exists today.**
5. Change, approval and maintenance windows; patching times.
6. Data protection roles and a written controller-processor contract (Information Commissioner's
   Office, 2026a), breach notification, retention and deletion.
7. Reporting, reviews, remedies, price, ownership, termination and handover.

References: [references.md](references.md).
