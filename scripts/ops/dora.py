#!/usr/bin/env python3
"""DORA measures from TH-CLOVER deployments.log files (AI-assisted).

Definitions and limits: docs/operations/dora.md.

    python3 scripts/ops/dora.py deployments.log [more.log ...] --repo . --env production

Log lines are JSON objects written by deploy.sh / rollback.sh:
    {"event":"deploy|rollback","env","sha","image","started","finished","seconds",
     "result":"success|failed|rolled_back"}   (rollback lines also carry "trigger":"manual|auto")
Commit times come from `git` in --repo, or from --commits (JSON object: sha -> ISO 8601 time).
Standard library only.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from statistics import median

SMALL_SAMPLE = 30


def parse_time(value):
    """Accept ISO 8601 (with Z or an offset) or epoch seconds; always return aware UTC."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_events(paths, env):
    """Return (events for env sorted by finish time, number of unreadable lines)."""
    events, bad, seen = [], 0, set()
    for path in paths:
        with open(path, encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line or line in seen:
                    continue
                seen.add(line)
                try:
                    record = json.loads(line)
                    if record["event"] not in ("deploy", "rollback"):
                        raise ValueError("unknown event")
                    if record["result"] not in ("success", "failed", "rolled_back"):
                        raise ValueError("unknown result")
                    record["started"] = parse_time(record["started"])
                    record["finished"] = parse_time(record["finished"])
                    if record["env"] == env:
                        events.append(record)
                except (ValueError, KeyError, TypeError):
                    bad += 1
    events.sort(key=lambda r: (r["finished"], r["started"]))
    return events, bad


def commit_time(sha, commits, repo):
    if commits is not None:
        return parse_time(commits[sha]) if sha in commits else None
    try:
        result = subprocess.run(
            ["git", "-C", repo, "show", "-s", "--format=%cI", f"{sha}^{{commit}}"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return parse_time(result.stdout.strip().splitlines()[-1])


def failed_changes(events):
    """Map deploy index -> (failure start, restore time or None, how it was restored)."""
    failures = {}
    last_good = None  # index of the successful deploy that is currently live
    for index, record in enumerate(events):
        if record["event"] == "deploy":
            if record["result"] == "rolled_back":
                failures[index] = (record["started"], record["finished"], "automatic rollback")
            elif record["result"] == "failed":
                failures[index] = (record["started"], None, "not restored")
                last_good = None
            else:
                last_good = index
        elif record.get("trigger") == "auto":
            continue  # already counted on the deploy line that reports rolled_back
        elif record["result"] == "success" and last_good is not None:
            # A manual rollback after a successful deploy marks that deploy as a failed change.
            if record["sha"] != events[last_good]["sha"]:
                failures[last_good] = (events[last_good]["finished"], record["finished"], "manual rollback")
                last_good = None

    # An unrestored failure is closed by the next event that leaves a healthy release running.
    for index, (start, restored, how) in list(failures.items()):
        if restored is None:
            for later in events[index + 1:]:
                if later["result"] in ("success", "rolled_back"):
                    failures[index] = (start, later["finished"], f"later {later['event']}")
                    break
    return failures


def summarise(values):
    if not values:
        return {"count": 0, "median": None, "min": None, "max": None}
    return {"count": len(values), "median": median(values), "min": min(values), "max": max(values)}


def calculate(events, commits=None, repo="."):
    deploys = [(i, r) for i, r in enumerate(events) if r["event"] == "deploy"]
    good = [r for _, r in deploys if r["result"] == "success"]
    failures = failed_changes(events)

    window_days = None
    per_week = None
    if events:
        span = max(r["finished"] for r in events) - min(r["started"] for r in events)
        window_days = span.total_seconds() / 86400
        # A rate from less than a week of data would be misleading.
        if window_days >= 7:
            per_week = len(good) / window_days * 7

    lead_times, missing, counted = [], [], set()
    for record in good:
        sha = record["sha"]
        if sha in counted:  # redeploying the same commit is not a new change
            continue
        counted.add(sha)
        committed = commit_time(sha, commits, repo)
        if committed is None:
            missing.append(sha)
        else:
            lead_times.append(round((record["finished"] - committed).total_seconds()))

    restore_times = [round((restored - start).total_seconds())
                     for start, restored, _ in failures.values() if restored is not None]

    return {
        "deploy_attempts": len(deploys),
        "successful_deploys": len(good),
        "days_with_a_successful_deploy": len({r["finished"].date() for r in good}),
        "window_days": None if window_days is None else round(window_days, 2),
        "deployments_per_week": None if per_week is None else round(per_week, 2),
        "lead_time_seconds": summarise(lead_times),
        "lead_time_missing_commits": missing,
        "failed_changes": len(failures),
        "logged_failed": sum(1 for _, r in deploys if r["result"] == "failed"),
        "change_failure_rate": None if not deploys else round(len(failures) / len(deploys), 3),
        "time_to_restore_seconds": summarise(restore_times),
        "unrestored_failures": sum(1 for _, restored, _ in failures.values() if restored is None),
    }


def duration(seconds):
    if seconds is None:
        return "n/a"
    hours, rest = divmod(int(round(seconds)), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}h {minutes:02d}m {secs:02d}s"


def report(env, result, bad_lines):
    lead, restore = result["lead_time_seconds"], result["time_to_restore_seconds"]
    rate = result["deployments_per_week"]
    cfr = result["change_failure_rate"]
    lines = [
        f"DORA measures for environment: {env}",
        f"Deployment frequency : {result['successful_deploys']} successful deploys on "
        f"{result['days_with_a_successful_deploy']} day(s) in a {result['window_days']} day window; "
        + (f"{rate} per week" if rate is not None else "no weekly rate (window under 7 days)"),
        f"Lead time for change : median {duration(lead['median'])} (n={lead['count']}, "
        f"min {duration(lead['min'])}, max {duration(lead['max'])})",
        "Change failure rate  : "
        + ("n/a" if cfr is None else f"{result['failed_changes']}/{result['deploy_attempts']} = {cfr:.1%}"),
        f"Time to restore      : median {duration(restore['median'])} (n={restore['count']}, "
        f"min {duration(restore['min'])}, max {duration(restore['max'])}); "
        f"unrestored {result['unrestored_failures']}",
    ]
    if result["lead_time_missing_commits"]:
        lines.append("Commits not found    : " + ", ".join(result["lead_time_missing_commits"]))
    if result["logged_failed"]:
        lines.append(f"Check: {result['logged_failed']} deploy line(s) say 'failed'. Some may have stopped "
                     "before changing the service (see docs/operations/dora.md).")
    if bad_lines:
        lines.append(f"Warning: {bad_lines} unreadable log line(s) were skipped.")
    if result["deploy_attempts"] < SMALL_SAMPLE:
        lines.append(f"Small sample ({result['deploy_attempts']} deploy attempts): "
                     "describes these runs only, not a performance level.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("logs", nargs="+", help="deployments.log file(s)")
    parser.add_argument("--env", default="production", choices=["staging", "production"])
    parser.add_argument("--repo", default=".", help="git clone used for commit times")
    parser.add_argument("--commits", help="JSON file mapping sha to commit time (instead of git)")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)

    commits = None
    if args.commits:
        with open(args.commits, encoding="utf-8-sig") as handle:
            commits = json.load(handle)
    events, bad = load_events(args.logs, args.env)
    if not events:
        print(f"No {args.env} events found ({bad} unreadable line(s)).", file=sys.stderr)
        return 1
    result = calculate(events, commits, args.repo)
    print(json.dumps(result, indent=2) if args.json else report(args.env, result, bad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
