# Evaluation plan

> AI-assisted (Agent 1, Business & Delivery), 26 November 2026. Role area: Galen Kudwoli.
> Not reviewed by a team member. **No target has been measured yet.**

## Rules

- Record every run, including failures. Use UTC timestamps.
- Report each value, the minimum, median and maximum. A target is met only if every counted run is
  within it. A few runs show feasibility, not a service level.
- Keep raw output under `evidence/` with the command and date. Do not edit it.
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

Design figure for REQ-06, from the drafted configuration: scrape 15 s + evaluation 15 s + hold 1 min
+ group wait 10 s = about 100 s, plus email delivery. This is a calculation, not a result.

REQ-08 over so short a period gives an indication only; the monthly figures in `costs.md` are
estimates.

## Results

| ID | Target | Result | Runs completed | Met? | Evidence link |
|---|---|---|---:|---|---|
| REQ-01 | No shared admin login; scoped, logged access | not yet measured | 0 | not yet measured | |
| REQ-02 | Every release traceable | not yet measured | 0 | not yet measured | |
| REQ-03 | Deploy < 20 min | not yet measured | 0 | not yet measured | |
| REQ-04 | Recovery < 10 min | not yet measured | 0 | not yet measured | |
| REQ-05 | Failing test blocks promotion | not yet measured | 0 | not yet measured | |
| REQ-06 | Failure reported < 5 min | not yet measured | 0 | not yet measured | |
| REQ-07 | Built from definitions, no manual steps | not yet measured | 0 | not yet measured | |
| REQ-08 | Idle shutdown with run-hour reduction logged | not yet measured | 0 | not yet measured | |

## Business evaluation after testing

State for each requirement: met, partly met or not met; the business value shown; the limitation;
and the next step with its likely cost. Where a test cannot be run before 4 December, explain how it
would be run, as the brief requires (Birmingham City University, 2026).

References: [references.md](references.md).
