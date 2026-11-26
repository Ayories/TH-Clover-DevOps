# Acceptance criteria

AI-assisted. IDs, priorities and "Then" clauses follow the Viva 1 slide; the Given/When wording is in
[business/requirements.md](business/requirements.md) and methods and results are in
[business/evaluation.md](business/evaluation.md). These are design targets, not service levels.
A criterion is met only when real evidence exists. **None has been verified on the deployed system yet.**

| ID | Priority | Acceptance criterion ("Then") | How it is checked | Evidence | Status |
|---|---|---|---|---|---|
| REQ-01 Access control | Must | Access is granted individually, scoped and logged; no shared admin login | Access matrix; root and password SSH, unauthenticated staff API and non-`main` role use are refused | SSH, HTTP and AWS outputs | not yet verified |
| REQ-02 Traceability | Must | Any deployment traces to its commit, PR, reviewer and passing test run | Trace one running release backwards | Release manifest, PR, run links, `deployments.log` | not yet verified |
| REQ-03 Deployment | Must | Pipeline-triggered deployment verified complete in under 20 minutes | Five timed runs of the Deploy workflow, from trigger to healthy; approval wait shown separately | Run timings, `deployments.log` | not yet measured |
| REQ-04 Recovery | Must | A timed rollback drill restores and verifies the prior version in under 10 minutes | Drills 2 and 3 in [operations/drills.md](operations/drills.md), three timed recoveries; data and schema compatibility checked | `deployments.log`, health output, row counts | not yet measured |
| REQ-05 Testing | Should | A failing automated test blocks promotion to the next environment | Pull request with a deliberately failing test | Failed check, blocked merge | not yet verified |
| REQ-06 Monitoring | Should | A simulated failure raises an alert to the owner within 5 minutes | Drill 1, three runs, measured to the email being received | Drill log, email timestamps | not yet measured |
| REQ-07 Environment consistency | Should | An environment built from IaC/config matches its target with no manual steps | Build from one commit; second Ansible run; list every manual step | Stack events, Ansible recap | not yet verified |
| REQ-08 Sustainability | Could | A scheduled policy shuts down idle dev/test and logs the run-hour reduction | Instance run hours with the schedule enabled ([operations/sustainability.md](operations/sustainability.md)) | State history, scheduler records | not yet measured |

## Known gaps against these criteria

- REQ-04: rollback restores the application image only, one release back; it does not reverse database
  changes.
- REQ-06: a database failure with the app still answering raises no alert (see
  [operations/monitoring.md](operations/monitoring.md)).
- REQ-07: stack launch, running Ansible, confirming the email subscription and registry access are
  manual steps.
- REQ-08: staging shares a host with production, so the scheduled stop stops both; development is
  local and is not stopped by the schedule.
