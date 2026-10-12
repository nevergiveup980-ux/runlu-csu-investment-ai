import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import scout_independent_news_watchman as watchman
from scout_independent_news_watchman import (
    IndependentNewsWatchmanError,
    bounded_seconds,
    news_window,
    tick_once,
)


class IndependentNewsWatchmanTests(unittest.TestCase):
    def test_poll_bounds(self):
        self.assertEqual(bounded_seconds(900), 900)
        self.assertEqual(bounded_seconds(1800), 1800)
        self.assertEqual(bounded_seconds(3600), 3600)
        with self.assertRaises(IndependentNewsWatchmanError):
            bounded_seconds(899)
        with self.assertRaises(IndependentNewsWatchmanError):
            bounded_seconds(3601)

    def test_weekday_news_window(self):
        toronto = ZoneInfo("America/Toronto")
        self.assertTrue(news_window(datetime(2026, 10, 13, 7, 0, tzinfo=toronto)))
        self.assertTrue(news_window(datetime(2026, 10, 13, 18, 30, tzinfo=toronto)))
        self.assertFalse(news_window(datetime(2026, 10, 13, 6, 59, tzinfo=toronto)))
        self.assertFalse(news_window(datetime(2026, 10, 11, 12, 0, tzinfo=toronto)))

    def test_tick_outside_window_does_not_fetch(self):
        toronto = ZoneInfo("America/Toronto")
        with patch.object(watchman, "run_news_cycle") as run:
            result = tick_once(now=datetime(2026, 10, 13, 6, 0, tzinfo=toronto))
        run.assert_not_called()
        self.assertFalse(result["ran"])
        self.assertFalse(result["automaticRecheck"])
        self.assertFalse(result["tradeEligible"])

    def test_tick_forces_research_only_even_if_underlying_result_is_wrong(self):
        toronto = ZoneInfo("America/Toronto")
        with patch.object(watchman, "run_news_cycle", return_value={
            "ran": True,
            "automaticRecheck": True,
            "tradeEligible": True,
            "brokerSubmissionEnabled": True,
        }):
            result = tick_once(now=datetime(2026, 10, 13, 12, 0, tzinfo=toronto))
        self.assertTrue(result["ran"])
        self.assertFalse(result["automaticRecheck"])
        self.assertFalse(result["tradeEligible"])
        self.assertFalse(result["brokerSubmissionEnabled"])


if __name__ == "__main__":
    unittest.main()
