# Acceptance criteria

AI-assisted. IDs, priorities and "Then" clauses follow the Viva 1 slide; the Given/When wording is in
[business/requirements.md](business/requirements.md) and methods and results are in
[business/evaluation.md](business/evaluation.md). These are design targets, not service levels.
A criterion is met only when real evidence exists. Statuses below are from testing on
26 November 2026 and are AI judgements that the team has not yet agreed. Raw evidence is held by the
team outside the repository.

| ID | Priority | Acceptance criterion ("Then") | How it is checked | Evidence | Status |
|---|---|---|---|---|---|
| REQ-01 Access control | Must | Access is granted individually, scoped and logged; no shared admin login | Access matrix; root and password SSH, unauthenticated staff API and non-`main` role use are refused | Root and password-only SSH refused; `/staff` 401 anonymous and with wrong credentials; rejected login in CloudWatch. Non-`main` role use not tested | partly met: one shared staff login, one admin account, no branch protection |
| REQ-02 Traceability | Must | Any deployment traces to its commit, PR, reviewer and passing test run | Trace one running release backwards | Commit, PR, checks, release run, image digest and deployment record link up | partly met: no reviewer |
| REQ-03 Deployment | Must | Pipeline-triggered deployment verified complete in under 20 minutes | Five timed runs of the Deploy workflow, from trigger to healthy; approval wait shown separately | Seven runs, all successful, 42 to 58 s from dispatch to complete; no approval wait | met |
| REQ-04 Recovery | Must | A timed rollback drill restores and verifies the prior version in under 10 minutes | Drills 2 and 3 in [operations/drills.md](operations/drills.md), three timed recoveries; data and schema compatibility checked | Three manual rollbacks, 6.7 to 6.8 s; row counts unchanged. Drill 2 (automatic) not run | met for manual rollback of the application only |
| REQ-05 Testing | Should | A failing automated test blocks promotion to the next environment | Pull request with a deliberately failing test | Tests run on pull requests and `main`; release waits for Security. A failing test blocking a merge was not shown | partly met |
| REQ-06 Monitoring | Should | A simulated failure raises an alert to the owner within 5 minutes | Drill 1, three runs, measured to the email being received | Two of three runs. Run 1 email within 112 s; run 2 email not checked | met for application stop only |
| REQ-07 Environment consistency | Should | An environment built from IaC/config matches its target with no manual steps | Build from one commit; second Ansible run; list every manual step | Stack and Ansible built the host; third Ansible run `changed=0`. Local environment not run | partly met: manual steps remain |
| REQ-08 Sustainability | Could | A scheduled policy shuts down idle dev/test and logs the run-hour reduction | Instance run hours with the schedule enabled ([operations/sustainability.md](operations/sustainability.md)) | Schedule enabled; no stop observed and no run-hour record | not tested |

## Known gaps against these criteria

- REQ-04: rollback restores the application image only, one release back; it does not reverse database
  changes.
- REQ-06: a database failure with the app still answering is covered by the `CloverDatabaseDown`
  rule, which is unit-tested only and has never been drilled. The host status-check alarm is not
  tested either (see [operations/monitoring.md](operations/monitoring.md)).
- REQ-07: stack launch, running Ansible, the budget script, confirming the email subscription,
  setting the GitHub variable and registry access are manual steps.
- REQ-08: staging shares a host with production, so the scheduled stop stops both; development is
  local and is not stopped by the schedule.
