"""Unit checks for dora.py using FAKE fixtures only (AI-assisted). Not project results.

    python3 -m unittest discover -s scripts/ops -p 'test_*.py' -v
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dora  # noqa: E402

A, B, C = "a" * 40, "b" * 40, "c" * 40
# FAKE commit times
COMMITS = {A: "2000-01-01T09:00:00Z", B: "2000-01-01T10:00:00Z", C: "2000-01-08T09:00:00Z"}


def line(event, sha, started, finished, result, env="production"):
    return json.dumps({"event": event, "env": env, "sha": sha, "image": "FAKE", "started": started,
                       "finished": finished, "seconds": 0, "result": result})


class DoraTest(unittest.TestCase):
    def run_calc(self, lines):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "FAKE-deployments.log")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            events, bad = dora.load_events([path], "production")
        return dora.calculate(events, COMMITS), bad

    def test_all_four_measures(self):
        result, bad = self.run_calc([
            line("deploy", A, "2000-01-01T09:10:00Z", "2000-01-01T09:15:00Z", "success"),
            line("deploy", B, "2000-01-01T10:10:00Z", "2000-01-01T10:13:00Z", "rolled_back"),
            line("deploy", C, "2000-01-08T09:10:00Z", "2000-01-08T09:25:00Z", "success"),
            line("rollback", A, "2000-01-08T09:30:00Z", "2000-01-08T09:35:00Z", "success"),
            line("deploy", B, "2000-01-08T09:40:00Z", "2000-01-08T09:41:00Z", "success", env="staging"),
            "not json",
        ])
        self.assertEqual(bad, 1)
        self.assertEqual(result["deploy_attempts"], 3)
        self.assertEqual(result["successful_deploys"], 2)
        # lead times: A 15 min, C 25 min
        self.assertEqual(result["lead_time_seconds"]["median"], 1200)
        # B rolled back automatically, C rolled back by hand
        self.assertEqual(result["failed_changes"], 2)
        self.assertEqual(result["change_failure_rate"], 0.667)
        # restore: B 180 s; C 09:25 -> 09:35 = 600 s
        self.assertEqual(result["time_to_restore_seconds"]["min"], 180)
        self.assertEqual(result["time_to_restore_seconds"]["max"], 600)
        self.assertGreaterEqual(result["window_days"], 7)
        self.assertIsNotNone(result["deployments_per_week"])

    def test_failed_deploy_restored_by_later_rollback(self):
        result, _ = self.run_calc([
            line("deploy", A, "2000-01-01T09:00:00Z", "2000-01-01T09:05:00Z", "success"),
            line("deploy", B, "2000-01-01T10:00:00Z", "2000-01-01T10:02:00Z", "failed"),
            line("rollback", A, "2000-01-01T10:05:00Z", "2000-01-01T10:06:00Z", "success"),
        ])
        self.assertEqual(result["failed_changes"], 1)
        self.assertEqual(result["time_to_restore_seconds"]["median"], 360)
        self.assertEqual(result["unrestored_failures"], 0)
        self.assertIsNone(result["deployments_per_week"])

    def test_unrestored_and_unknown_commit(self):
        result, _ = self.run_calc([
            line("deploy", "d" * 40, "2000-01-01T09:00:00Z", "2000-01-01T09:05:00Z", "success"),
            line("deploy", B, "2000-01-01T10:00:00Z", "2000-01-01T10:02:00Z", "failed"),
            line("rollback", A, "2000-01-01T10:05:00Z", "2000-01-01T10:06:00Z", "failed"),
        ])
        self.assertEqual(result["unrestored_failures"], 1)
        self.assertEqual(result["time_to_restore_seconds"]["count"], 0)
        self.assertEqual(result["lead_time_missing_commits"], ["d" * 40])

    def test_automatic_rollback_lines_are_not_counted_twice(self):
        auto = json.loads(line("rollback", A, "2000-01-01T10:01:00Z", "2000-01-01T10:02:00Z", "success"))
        auto["trigger"] = "auto"
        result, _ = self.run_calc([
            line("deploy", C, "2000-01-01T09:00:00Z", "2000-01-01T09:05:00Z", "success"),
            json.dumps(auto),
            line("deploy", B, "2000-01-01T10:00:00Z", "2000-01-01T10:02:00Z", "rolled_back"),
        ])
        self.assertEqual(result["failed_changes"], 1)
        self.assertEqual(result["deploy_attempts"], 2)

    def test_time_formats(self):
        self.assertEqual(dora.parse_time("1970-01-01T00:01:00+0000"), dora.parse_time(60))
        self.assertEqual(dora.parse_time("1970-01-01T01:01:00+01:00"), dora.parse_time("1970-01-01T00:01:00Z"))


if __name__ == "__main__":
    unittest.main()
