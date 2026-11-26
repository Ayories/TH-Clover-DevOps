# Requirements: Evolving Ltd DevOps transformation (TH-CLOVER)

> AI-assisted draft (Agent 1, Business & Delivery), 26 November 2026. Role area: Galen Kudwoli.
> No team member has reviewed it yet.

## Problem

Evolving Ltd runs a small Linux customer-service application (web service and database) that holds
customer names, email addresses and support requests. Development and operations still work through
manual handovers (Birmingham City University, 2026):

| Current problem | Business effect | Requirement |
|---|---|---|
| Inconsistent development, test and production environments | Defects appear only after release | REQ-07 |
| Changes merged without consistent review or checks | Poor changes reach users; no clear owner | REQ-02, REQ-05 |
| Manual deployment by operations | Slow, error-prone releases | REQ-03 |
| Shared administrator credentials; secrets in configuration files | No accountability; data exposure | REQ-01 |
| Manual testing just before release | Late discovery of faults | REQ-05 |
| Logs on individual servers; no alerting | Failures found by users | REQ-06 |
| No dependable rollback | A bad release becomes an outage | REQ-04 |
| Non-production running when idle | Wasted money and energy | REQ-08 |

## Stakeholders

| Stakeholder | Needs | How they are served |
|---|---|---|
| Business sponsor (Evolving Ltd; module team as client) | Reliable, affordable releases; honest reporting | Evaluation results, cost estimate, risk log |
| Development team | Same environment everywhere; fast feedback | Compose definitions, CI checks, pull requests |
| Operations team | Repeatable deploy, visible faults, safe recovery | Scripted deploy and rollback, alerts, runbooks |
| Customer-service staff | A working request queue | Authenticated staff pages |
| End customers (data subjects) | Their data kept private and only as needed | Access control, minimal logging, synthetic data in tests |
| Security and compliance | Least privilege, audit trail, licence compliance | Role-based access, scans, traceability |

## Scope and assumptions

- In scope: a proof of concept with development (local), staging and production on one EC2 host in
  `eu-west-2`.
- Out of scope: high availability, autoscaling, a custom domain, TLS certificates and real customer
  data. The service runs over plain HTTP, so only synthetic data may be entered.
- The brief's targets are design and evaluation targets, not guaranteed service levels.

## User stories

| ID | Story | Requirement |
|---|---|---|
| US-01 | As a customer, I want to send a support request so that someone can help me. | Application baseline |
| US-02 | As a support agent, I want to sign in, see requests and update their status so that I can handle them. | Application baseline, REQ-01 |
| US-03 | As a security lead, I want each person and automation to have only the access it needs so that actions are attributable. | REQ-01 |
| US-04 | As a sponsor, I want every release traced to a reviewed and tested change so that I can account for what is live. | REQ-02 |
| US-05 | As an operator, I want to deploy with one controlled action so that releases are repeatable and quick. | REQ-03 |
| US-06 | As an operator, I want to restore the last good version quickly so that a bad release does little harm. | REQ-04 |
| US-07 | As a developer, I want failing tests to stop promotion so that faults are caught early. | REQ-05 |
| US-08 | As an operator, I want to be told about a critical failure so that I act before customers report it. | REQ-06 |
| US-09 | As a developer, I want environments built from files in Git so that they behave the same. | REQ-07 |
| US-10 | As a sponsor, I want idle resources shut down so that we pay for and consume less. | REQ-08 |

## Requirements and acceptance criteria

IDs, wording, priorities and "Then" clauses follow the Viva 1 slide. The "Given" and "When" clauses
were added here to make each criterion testable.

| ID | Requirement | MoSCoW | Given | When | Then |
|---|---|---|---|---|---|
| REQ-01 | Access control: remove shared admin accounts; least privilege | Must | a person or pipeline needs access to the repository, host or AWS | access is set up and used | access is granted individually, scoped and logged, with no shared admin login |
| REQ-02 | Traceability: release linked to change, review, test and approval | Must | a version is running in staging or production | someone asks where it came from | any deployment traces to its commit, PR, reviewer and passing test run |
| REQ-03 | Deployment: repeatable deploy completes in under 20 minutes | Must | a built and scanned image from `main` | the deploy workflow is triggered | the pipeline-triggered deployment is verified complete in < 20 min |
| REQ-04 | Recovery: rollback restores a known-good version in under 10 minutes | Must | a faulty release and a recorded previous good release | a rollback is started or triggered by a failed health check | a timed drill restores and verifies the prior version in < 10 min |
| REQ-05 | Testing: automated tests run before deployment or promotion | Should | a change with a deliberately failing test | the pipeline runs | the failing test blocks promotion to the next environment |
| REQ-06 | Monitoring: critical failure detectable within 5 minutes | Should | monitoring is running and the service is healthy | a failure is simulated | an alert reaches the owner within 5 min |
| REQ-07 | Environment consistency: built from version-controlled definitions | Should | the definitions at a given commit | an environment is built from them | it matches its target with no manual steps |
| REQ-08 | Sustainability: idle non-production resources reduced or shut down | Could | the scheduled policy is enabled | the idle period starts | idle dev/test is shut down and the run-hour reduction is logged |

**MoSCoW rationale.** Musts protect access, accountability and the ability to release and recover.
Shoulds strengthen quality and operations and are still planned for the proof of concept. REQ-08 is
a Could because the service still works without it. "Won't (this time)": high availability,
Kubernetes, TLS on a custom domain, automated database backup and restore.

**Honest limits on the criteria**

- REQ-07: the stack launch, the Ansible run and the entry of secrets are started by a person. Report
  these as manual steps rather than claiming a fully unattended build.
- REQ-08: development is local; staging shares one host with production, so the scheduled stop also
  stops production and monitoring. This is acceptable only for a proof of concept.

## Definition of Done

A work item is done only when all of these are true (Birmingham City University, 2026):

1. It is version controlled and merged through a pull request.
2. It is linked to a requirement and acceptance criterion.
3. At least one team member other than the author has reviewed it. AI-assisted work needs a human
   reviewer; an AI check does not count.
4. Relevant tests and security checks pass, with the output kept.
5. No secrets or real customer data are present.
6. It is documented briefly, including limitations.
7. It is integrated into the relevant environment or workflow.

## Traceability to the brief

| Brief target (Birmingham City University, 2026) | ID | Design element | Evidence required | Lead function |
|---|---|---|---|---|
| Access: no shared administrator accounts, least privilege | REQ-01 | Individual GitHub identities, named key-only host admin, OIDC role, root and password login disabled | Access matrix, denied-access tests | Quality & Security, Platform |
| Traceability: change, review, test evidence, approval | REQ-02 | Pull requests, CI, image digest, environment approval, deployment log | One release traced end to end | Development |
| Deployment < 20 minutes | REQ-03 | GitHub Actions and SSM document `th-clover-deploy` | Timed runs | Platform |
| Recovery < 10 minutes | REQ-04 | `rollback.sh`, automatic rollback on failed health check | Timed drills | Operations |
| Testing before deployment or promotion | REQ-05 | pytest, scans, required status checks | Blocked failing change | Quality, Development |
| Failure reportable within 5 minutes | REQ-06 | Prometheus, Alertmanager, SNS email; EC2 status-check alarm | Failure and email timestamps | Operations |
| Environments from version-controlled definitions | REQ-07 | CloudFormation, Ansible, Docker Compose | Rebuild and second-run output | Platform |
| Non-production reduced or shut down | REQ-08 | EventBridge Scheduler stop, AWS Budget | Run-hour comparison | Operations |

The `cloveradmin` host account meets REQ-01 only while one named person holds its private key. If a
second person needs host access, give them their own account and key.

Measurement methods and results are in [evaluation.md](evaluation.md).
