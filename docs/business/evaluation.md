# Evaluation plan and results

> AI-assisted (Agent 1, Business & Delivery), 26 November 2026. Role area: Galen Kudwoli.
> Not reviewed by a team member. Results added after testing on 26 November 2026.

## Rules

- Record every run, including failures. Use UTC timestamps.
- Report each value, the minimum, median and maximum. A target is met only if every counted run is
  within it. A few runs show feasibility, not a service level.
- Keep raw output under `evidence/` with the command and date. Do not edit it. The team holds this
  folder outside the repository.
- Note the commit, image digest, instance type and who ran the test.

## How each target is measured

| ID | Test | Clock starts / stops, or pass rule | Runs | Evidence source |
|---|---|---|---:|---|
| REQ-01 | Review the access matrix; try root SSH, password SSH, a connection from outside the CIDR, staff API without credentials, and role use from a non-`main` ref | All refused; every person and automation has its own identity; actions appear in logs | 1 each | SSH output, HTTP status, AWS and GitHub logs |
| REQ-02 | Pick a running release and trace it backwards | Digest, commit, pull request, human reviewer, test run, approver and deployment record all link up | 1 per production release | GitHub, `deployments.log`, `/health` version |
| REQ-03 | Dispatch the deploy workflow for a published image | From workflow trigger to health check passing with the expected commit; under 20 min. Record approval wait separately and report both with and without it | 5 | Workflow run times, job summary, `deployments.log` |
| REQ-04 | Release a known-bad but safe version, or run `rollback.sh` | From failure injected (or rollback started; state which) to previous commit healthy; under 10 min. Check existing data is intact | 3 | `deployments.log`, health output |
| REQ-05 | Open a pull request with a deliberately failing test | Merge and promotion are blocked | 1 | Failed check and blocked-merge screenshot |
| REQ-06 | Stop the production application container (`scripts/ops/failure-drill.sh --yes`) | From stop to **email received**; under 5 min. SNS acceptance alone is not receipt | 3 | Drill log, email timestamp |
| REQ-06 (host) | Test the status-check alarm notification | Email received. Setting the alarm state by hand proves delivery only, not detection | 1 | Alarm history, email |
| REQ-07 | Build from the definitions at one commit, then run Ansible again | Health passes; second run reports no unexpected changes; every manual step listed | 1 | Stack events, Ansible recap |
| REQ-08 | Compare instance run hours over a stated period with the schedule enabled | Reduction % = (hours in period - hours running) / hours in period x 100 | At least 2 weekday evenings | Instance state history, scheduler records, billing |

Design figure for REQ-06, from the configuration: scrape 15 s + evaluation 15 s + hold 1 min
+ group wait 10 s = about 100 s, plus email delivery. This is a calculation, not a result.

REQ-08 over so short a period gives an indication only; the monthly figures in `costs.md` are
estimates.

## Results

Measured on 26 November 2026. Verdicts are AI judgements that the team has not yet agreed. Evidence
names are files held by the team outside the repository.

| ID | Target | Result | Runs completed | Met? | Evidence link |
|---|---|---|---:|---|---|
| REQ-01 | No shared admin login; scoped, logged access | Key-only non-root admin; root and password-only SSH refused; `/staff` 401 without or with wrong credentials. One shared staff login, one admin account, database superuser. Outside-CIDR connection, non-`main` role use and successful staff login on AWS not tested | 1 (SSH, HTTP) | Partly | SSH and live-check outputs |
| REQ-02 | Every release traceable | Release `36c9a46` traces to PR #4, passing checks, release run, digest `sha256:d18e9d1f…` and deployment record. No reviewer; approval is only the manual dispatch | 1 | Partly | PR, run and `deployments.log` records |
| REQ-03 | Deploy < 20 min | Dispatch to complete: min 42 s, median 50 s, max 58 s; all successful; no approval wait | 7 | Yes | `pipeline-deploy-timings.tsv`, `deployments.jsonl` |
| REQ-04 | Recovery < 10 min | Manual `rollback.sh`: 6.7, 6.8 and 6.8 s from the command to healthy; row counts unchanged. Excludes noticing and deciding. Automatic rollback not tested live; no database restore | 3 | Yes, manual application rollback only | rollback drill outputs |
| REQ-05 | Failing test blocks promotion | Tests run on pull requests and `main`; release waits for Security. A real Trivy failure was found and fixed. A failing test blocking a merge was not shown, and `main` is unprotected | 0 | Partly | Security run 45752682107 |
| REQ-06 | Failure reported < 5 min | App stopped: alert firing +65 s and +78 s, SNS accepted +76 s and +88 s. Run 1 email within 112 s (reported by a team member (operator)); run 2 email not checked | 2 of 3 | Yes, application stop only | `failure-drills.jsonl`, drill outputs |
| REQ-07 | Built from definitions, no manual steps | CloudFormation stack and Ansible built the host; third Ansible run `changed=0`. Manual steps remain; local environment not run | 1 | Partly | stack and Ansible outputs |
| REQ-08 | Idle shutdown with run-hour reduction logged | Weekday stop schedule enabled; stop not yet observed; no run-hour record | 0 | Not tested | schedule screenshot |

Not tested: the host status-check alarm (REQ-06 host row), the database-down alert and the scheduled
stop.

## Business evaluation after testing

State for each requirement: met, partly met or not met; the business value shown; the limitation;
and the next step with its likely cost. Where a test cannot be run before 4 December, explain how it
would be run, as the brief requires (Birmingham City University, 2026).

References: [references.md](references.md).
