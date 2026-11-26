# Risks, issues, decisions, ethics and sustainability

> **Decision 2026-11-26:** region changed from London to Stockholm (`eu-north-1`) because the free-plan project is
> restricted to it. The proof of concept holds synthetic data only. A team member (operator) approved creating the
> stack.

> AI-assisted (Agent 1, Business & Delivery), 26 November 2026. Role area: Galen Kudwoli.
> Not reviewed by a team member. "Owner" is the role area expected to act; nobody has accepted an
> item yet. Issue and decision statuses were updated after deployment on 26 November.

L = likelihood, I = impact (H high, M medium, L low).

## Risks

| ID | Risk | L | I | Owner | Mitigation | Status |
|---|---|---|---|---|---|---|
| R01 | Too little time to integrate, deploy and drill before 4 December | H | H | Business | Follow the recovery plan; protect Musts; freeze on 3 December | Open |
| R02 | No human review, so work cannot meet the Definition of Done or be defended | H | H | All | Each member reviews an area by pull request and records it | Open |
| R03 | Plain HTTP exposes staff passwords and request data | H | H | Platform, Quality | Synthetic data only; one authorised CIDR; add TLS before real use | Open |
| R04 | Single host: failure or exhaustion takes down both environments and monitoring | M | H | Platform | `t3.small`; memory limits; status-check alarm; rebuild from code | Open |
| R05 | Scheduled stop also stops production; no automatic start; public IP changes | H | M | Platform, Operations | Start-up checklist; disable schedule before demonstrations; update IP-dependent settings | Open |
| R06 | Database lost: no backup; rollback does not reverse schema changes | M | H | Operations | No incompatible schema change; synthetic data; define backup for production use | Open |
| R07 | One `cloveradmin` key shared between people would break REQ-01 | M | H | Platform | One holder, or an account and key per person | Open |
| R08 | Containers may reach the instance role (metadata hop limit 2), including the application | L | M | Platform, Quality | Role limited to SSM agent, log writes and one SNS topic; record as residual risk | Open |
| R09 | Compromised third-party action or image | M | H | Development, Quality | Pin actions to commit SHAs and images to versions or digests; minimal permissions | Open |
| R10 | Unexpected AWS charges | L | M | Business | $15 budget; stop schedule; delete stack after moderation | Open |
| R11 | Alert email not received (subscription unconfirmed or filtered) | M | H | Operations | Confirm subscription; test end to end | Reduced: subscription confirmed; run 1 email arrived |
| R12 | Authorised CIDR changes (home or university network), locking the team out | M | M | Platform | Update the stack parameter; rehearse on the demo network | Open |
| R13 | Live demonstration fails | M | H | All | Keep timestamped evidence and a recording as contingency | Open |
| R14 | Members cannot explain AI-assisted work in the viva | M | H | All | Each member runs and explains their area before 4 December | Open |

## Issues

| ID | Issue (finding) | Impact | Owner | Action | Status at 26 Nov |
|---|---|---|---|---|---|
| I01 | Brief and Viva 1 slides were outside the module folder (Downloads and Desktop) | Wrong or missed requirements | Business | Text copies placed in `plan/sources/` | Worked around |
| I02 | Duplicate course PDFs (identical checksums, `(1)` copies) | Confusion only | Business | Ignore duplicates | Noted |
| I03 | Workflows were nested in `TH-Clover-DevOps/.github`, so Actions never ran | No CI evidence | Development | Files moved to the root; merged in PR #1; workflows have run | Fixed |
| I04 | `main` had no branch protection; no issues, pull requests or runs | REQ-02 and REQ-05 not enforceable | Development, Business | Protect `main`, require review and checks, disallow bypass (administrators can bypass by default: GitHub, 2026f); create issues | Open: still unprotected; PRs #1 and #4 merged without review |
| I05 | A separate local copy has an uncommitted change to `app/main.py` that breaks its imports | Could be committed by mistake | Development | Left untouched; do not merge it | Open |
| I06 | Course labs use Jenkins and Nagios; team chose GitHub Actions and Prometheus | Needs justification | Business | Compared in `tool-selection.md` | Documented |
| I07 | The starter `release.yml` used `trivy-action@0.30.0`, within the tag range affected by the March 2026 compromise (Aqua Security, 2026) | Unsafe or broken release job | Development, Quality | `release.yml` and `security.yml` run Trivy from a digest-pinned image | Fixed; both have run |
| I08 | This repository's OIDC subject includes numeric owner and repository IDs (GitHub, 2026c) | A plain `repo:owner/name` trust policy would refuse deployments | Platform | CloudFormation uses the immutable form | Fixed: pipeline deployments succeeded |
| I09 | A job with `environment:` changes the OIDC subject (GitHub, 2026c) | Approval and role trust can conflict | Platform | `deploy.yml` approves in a separate job; add required reviewers to the environments | Partly: deployments work; no required reviewers |
| I10 | Container packages are private when first published on a personal account (GitHub, 2026g) | Host cannot pull anonymously | Development, Platform | Make the package public after the first release | Closed in practice: the host pulled both releases (visibility setting not recorded) |
| I11 | `CODEOWNERS` had placeholder user names; only one account-to-role mapping is confirmed | Review routing incomplete | Development, all | Draft leaves other paths commented out; each member confirms their account | Open |
| I12 | `sprint-report.yml` used a label that did not exist | Weekly report would fail | Business | Workflow now creates the label first | Merged in PR #1; no run recorded |
| I13 | Node 20 has been removed from Actions runners (GitHub, 2026h) and the starter workflows used older action versions | Older actions may warn or fail | Development, Operations | Workflows pin actions to commit SHAs | Fixed: CI, Security, release, deploy and monitoring workflows have run |
| I14 | The application has no way to delete or expire requests | Cannot meet storage limits with real data | Development | Record as limitation; add before real use | Open |

## Decisions

| ID | Decision | Reason | Status |
|---|---|---|---|
| DEC01 | GitHub with pull requests, GitHub Actions | See `tool-selection.md` | Agreed (team) |
| DEC02 | Flask and PostgreSQL, Docker Compose, Ansible | Small, explainable stack | Agreed (team) |
| DEC03 | Gitleaks, Trivy, pytest | Quality gate | Agreed (team) |
| DEC04 | Prometheus and Alertmanager; Ubuntu on AWS | See `tool-selection.md` | Agreed (team) |
| DEC05 | CloudFormation; one `eu-north-1` host; two Compose environments | Cost and time; free-plan account locked to Stockholm | Built; team to confirm |
| DEC06 | Deploy through OIDC and one SSM document; CI never uses SSH | No long-lived keys | Built and used; team to confirm |
| DEC07 | Instance `t3.small`, budget $15 | See `costs.md` | Applied (budget made by script); team to confirm |
| DEC08 | Synthetic data only | No TLS, proof of concept | Applied; team to confirm |

## Ethics

**Customer data.** Names, email addresses and free-text requests are personal data, and free text may
contain more than intended. Collect only what the purpose needs (Information Commissioner's Office,
2026b). Use synthetic data in every environment of this project, keep personal data out of logs and
metrics, restrict staff access, and delete the database with the stack. Before real use: TLS, a
privacy notice, retention and deletion, backups and a controller-processor contract.

**Proportionate monitoring.** Monitor the service, not people. Metrics count requests by endpoint;
logs record events and errors. Log retention is set to 14 days and Prometheus retention to 3 days.
Only a critical production failure sends email, to reduce alert fatigue. Deployment and access records
name who acted: use them for accountability and learning, not for ranking colleagues.

**AI use.** Work in this folder has been produced with AI assistance (Claude), including these
business documents. A member's name marks a role area, not authorship. As at 26 November no team
member had reviewed the AI-assisted work. The only human actions recorded are by a team member
(operator): approving the work, the merges and the AWS creation, confirming the alert subscription
and reporting when the first alert email arrived. The team should check the module's rules on AI use
and declare it as required.

**Contribution records.** Count only what can be shown: commits, pull-request reviews, issue comments
and dated notes. Record each human review (who, what, when, link). Do not back-date, assign
commits to people who did not make them, or describe AI checks as peer review. The two commits on
19 November predate this work and carry their authors' names.

## Sustainability

| Measure | Effect | Limit |
|---|---|---|
| One small shared host, not one per environment | Less provisioned capacity | Less isolation |
| Scheduled weekday-evening stop (EventBridge Scheduler) | About 217 hours instead of 730 if started only on weekdays | Needs a manual start; also stops production |
| Short log and metric retention, small gp3 volume | Less storage | Less history |
| Prometheus without Grafana | Fewer running containers | Basic visualisation |
| Delete the stack after moderation | No idle resources | Keep evidence first |

These follow the aim of AWS sustainability guidance to maximise efficiency and reduce waste (Amazon
Web Services, 2024). We have not measured energy or carbon. Run hours are the proxy (see
`evaluation.md`).

References: [references.md](references.md).
