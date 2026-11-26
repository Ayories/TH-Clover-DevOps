# DORA measures

AI-assisted (role area: Operations & Reliability). Results below come from the deployment logs of
26 November 2026. Do not fill this page from test fixtures.

## Results (26 November 2026)

| Measure | Production | Staging |
|---|---|---|
| Deployment frequency | 3 successful deploys on 1 day | 4 successful deploys on 1 day |
| Lead time for change, median (min to max) | 4 min 36 s (4 min 05 s to 5 min 07 s), n=2 | 3 min 27 s (3 min 10 s to 3 min 44 s), n=2 |
| Change failure rate | 1/3 | 2/4 |
| Time to restore, median | 3 min 10 s, n=1 | 1 min 10 s (27 s to 1 min 52 s), n=2 |

**The failure rate and restore times come entirely from deliberate rollback drills.** No deployment
actually failed. The window is under an hour on one day, so there is no weekly rate and these figures
are not a performance level. The input logs and `dora.py` output are held by the team outside the
repository.

## Definitions used here

| Measure | Definition in this project | Data |
|---|---|---|
| Deployment frequency | Successful `deploy` events per environment; also a weekly rate once the log spans 7 days or more | `deployments.log` |
| Lead time for change | Commit time to the end of its first successful deployment; median, minimum, maximum | Log plus `git` commit time |
| Change failure rate | Deploy attempts that ended `failed` or `rolled_back`, or were later rolled back by hand, divided by all deploy attempts | Log |
| Time to restore (failed deployment recovery time) | Automatic rollback: that run's start to finish. Manual rollback: end of the bad deploy to end of the rollback. Unrestored failure: its start to the next run that left a healthy release | Log |

Default environment is production (`--env staging` for the other). An automatic rollback writes two
lines: `rollback` (with `"trigger":"auto"`, giving the restore duration alone) and then `deploy` with
result `rolled_back`. Only the `deploy` line is counted. A manual rollback writes one `rollback` line
with `"trigger":"manual"`.

## How to produce them

On the host, copy the log (it is root-readable only):

```bash
sudo cat /opt/th-clover/production/deployments.log
```

Save it as `evidence/operations/production-deployments.log`, then from a full clone of the repository:

```bash
python3 scripts/ops/dora.py ../evidence/operations/production-deployments.log --repo . --env production
```

Without a clone, pass `--commits commits.json` (`{"<40-char sha>": "2026-..T..Z"}`).
Keep the input log next to the output so the figures can be checked.

## Limits

- The sample will be a handful of runs over a few days. Report counts and ranges, not a performance
  band; a single run can move the change failure rate by tens of percentage points.
- Deliberate bad-release drills count as failures. Report them separately from real changes (run
  drills in staging, or state how many of the failures were deliberate).
- Commit time is not when work started. Rebasing or squash-merging changes it, so lead time here is
  mostly "merge to deployed".
- `deploy.sh` also writes `failed` when it stops before changing anything (backup or image pull
  failed). The log cannot tell these apart from a failed release, so `dora.py` counts them and may
  overstate failure rate and restore time. Check the deploy output for each `failed` line and say how
  many left the service untouched.
- Time to restore comes only from deployments. A container or host outage with no deployment is not in
  the log; use the drill records for that.
- For a manual rollback the failure is assumed to start when the bad release finished deploying, so
  the figure includes the time to notice.
- If a run is interrupted before it writes its line, it is missing from the data.
