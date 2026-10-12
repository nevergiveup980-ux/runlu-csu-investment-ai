import unittest
from unittest.mock import patch

import scout_watchman
from scout_watchman import ScoutWatchmanError, bounded_wake_seconds, tick_once


class ScoutWatchmanTests(unittest.TestCase):
    def test_wake_interval_is_bounded(self):
        self.assertEqual(bounded_wake_seconds(900), 900)
        self.assertEqual(bounded_wake_seconds(1800), 1800)
        self.assertEqual(bounded_wake_seconds(3600), 3600)
        with self.assertRaises(ScoutWatchmanError):
            bounded_wake_seconds(899)
        with self.assertRaises(ScoutWatchmanError):
            bounded_wake_seconds(3601)

    def test_tick_never_enables_broker_submission(self):
        with patch.object(
            scout_watchman,
            "run_daily_research",
            return_value={"ran": False, "reason": "Outside weekday after-close research window"},
        ) as run:
            result = tick_once(batches=3)
        run.assert_called_once_with(batches=3)
        self.assertEqual(result["scheduler"], "RUNLU_SCOUT_WATCHMAN")
        self.assertFalse(result["brokerSubmissionEnabled"])

    def test_tick_preserves_success_but_forces_no_broker_submission(self):
        with patch.object(
            scout_watchman,
            "run_daily_research",
            return_value={
                "ran": True,
                "brokerSubmissionEnabled": True,
                "top5": [],
            },
        ):
            result = tick_once(batches=1)
        self.assertTrue(result["ran"])
        self.assertFalse(result["brokerSubmissionEnabled"])


if __name__ == "__main__":
    unittest.main()
