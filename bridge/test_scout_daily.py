import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import scout_daily
from scout_daily import (
    ScoutDailyError,
    bounded_daily_batches,
    research_queue,
    run_daily_research,
    tsx_after_close,
)

TORONTO = ZoneInfo("America/Toronto")


class ScoutDailyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state = root / "daily-state.json"
        self.report = root / "daily-top5.json"
        self.registry = root / "registry.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_batch_bounds(self):
        self.assertEqual(bounded_daily_batches(1), 1)
        self.assertEqual(bounded_daily_batches(3), 3)
        self.assertEqual(bounded_daily_batches(6), 6)
        with self.assertRaises(ScoutDailyError):
            bounded_daily_batches(0)
        with self.assertRaises(ScoutDailyError):
            bounded_daily_batches(7)

    def test_only_runs_after_close_on_weekdays(self):
        monday_before = datetime(2099, 1, 5, 15, 59, tzinfo=TORONTO)
        monday_after = datetime(2099, 1, 5, 16, 20, tzinfo=TORONTO)
        sunday = datetime(2099, 1, 4, 18, 0, tzinfo=TORONTO)
        self.assertFalse(tsx_after_close(monday_before))
        self.assertTrue(tsx_after_close(monday_after))
        self.assertFalse(tsx_after_close(sunday))

    def test_research_queue_skips_pass_and_never_grants_trade(self):
        rows = [
            {"symbol": "AAA:TSX", "latestScore": 90, "tier": "PRIORITY_RESEARCH", "stage": "PASS"},
            {"symbol": "BBB:TSX", "latestScore": 80, "tier": "PRIORITY_RESEARCH", "stage": "RESEARCH_REQUIRED",
             "reasons": ["r1"], "riskFlags": ["x1"]},
        ]
        queue = research_queue(rows)
        self.assertEqual([x["symbol"] for x in queue], ["BBB:TSX"])
        self.assertFalse(queue[0]["tradeEligible"])
        self.assertTrue(queue[0]["researchRequired"])

    def test_daily_run_executes_bounded_cycles_and_writes_private_report(self):
        now = datetime(2099, 1, 5, 16, 30, tzinfo=TORONTO)
        cycles = [
            {"scanned": ["AAA:TSX", "BBB:TSX"]},
            {"scanned": ["CCC:TSX", "DDD:TSX"]},
        ]
        ranked = [
            {"symbol": "AAA:TSX", "latestScore": 88, "tier": "PRIORITY_RESEARCH", "stage": "RESEARCH_REQUIRED",
             "reasons": ["support"], "riskFlags": []},
            {"symbol": "CCC:TSX", "latestScore": 77, "tier": "PRIORITY_RESEARCH", "stage": "WATCH",
             "reasons": ["trend"], "riskFlags": ["news review"]},
        ]
        with patch.object(scout_daily, "run_cycle", side_effect=cycles) as run_cycle,              patch.object(scout_daily, "ranked_candidates", return_value=ranked):
            result = run_daily_research(
                now=now,
                batches=2,
                daily_state_path=self.state,
                daily_report_path=self.report,
                registry_path=self.registry,
            )

        self.assertTrue(result["ran"])
        self.assertEqual(run_cycle.call_count, 2)
        self.assertEqual(result["symbolsScanned"], 4)
        self.assertFalse(result["tradeEligible"])
        self.assertFalse(result["brokerSubmissionEnabled"])

        saved = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(saved["mode"], "RESEARCH_QUEUE_ONLY")
        self.assertTrue(saved["policy"]["jointResearchRequired"])
        self.assertFalse(saved["policy"]["tradeEligible"])
        self.assertEqual(len(saved["researchCards"]), 2)
        self.assertFalse(saved["researchCards"][0]["authority"]["tradeEligible"])

    def test_same_day_does_not_run_twice(self):
        now = datetime(2099, 1, 5, 17, 0, tzinfo=TORONTO)
        self.state.write_text(json.dumps({
            "lastCompletedDate": "2099-01-05",
            "tradeEligible": False,
        }), encoding="utf-8")
        with patch.object(scout_daily, "run_cycle") as run_cycle:
            result = run_daily_research(
                now=now,
                batches=3,
                daily_state_path=self.state,
                daily_report_path=self.report,
                registry_path=self.registry,
            )
        self.assertFalse(result["ran"])
        self.assertEqual(result["reason"], "Daily Scout research already completed")
        run_cycle.assert_not_called()

    def test_before_close_never_calls_hunter(self):
        now = datetime(2099, 1, 5, 12, 0, tzinfo=TORONTO)
        with patch.object(scout_daily, "run_cycle") as run_cycle:
            result = run_daily_research(
                now=now,
                batches=3,
                daily_state_path=self.state,
                daily_report_path=self.report,
                registry_path=self.registry,
            )
        self.assertFalse(result["ran"])
        run_cycle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
