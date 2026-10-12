import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import scout_event_provider
from scout_event_provider import (
    ScoutEventProviderError,
    bounded_poll_seconds,
    choose_event_batch,
    event_monitor_window,
    fetch_event_observations,
)


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.value).encode("utf-8")


class ScoutEventProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "event-state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def response(self, ids):
        return {
            "mode": "WATCH_EVENT_RESEARCH_ONLY",
            "observations": [{
                "symbol": "AAA:TSX",
                "events": [
                    {
                        "id": event_id,
                        "type": "EARNINGS",
                        "title": f"Release {event_id}",
                        "datetime": "2026-10-12T12:00:00",
                        "sourceType": "OFFICIAL_PRESS_RELEASE",
                    }
                    for event_id in ids
                ],
            }],
            "policy": {
                "tradeEligible": False,
                "brokerSubmissionEnabled": False,
            },
        }

    def test_poll_interval_is_cost_bounded(self):
        self.assertEqual(bounded_poll_seconds(900), 900)
        self.assertEqual(bounded_poll_seconds(1800), 1800)
        self.assertEqual(bounded_poll_seconds(3600), 3600)
        with self.assertRaises(ScoutEventProviderError):
            bounded_poll_seconds(899)
        with self.assertRaises(ScoutEventProviderError):
            bounded_poll_seconds(3601)

    def test_event_window_includes_pre_and_post_market_weekday(self):
        toronto = ZoneInfo("America/Toronto")
        self.assertTrue(event_monitor_window(datetime(2026, 10, 13, 7, 0, tzinfo=toronto)))
        self.assertTrue(event_monitor_window(datetime(2026, 10, 13, 18, 30, tzinfo=toronto)))
        self.assertFalse(event_monitor_window(datetime(2026, 10, 13, 6, 59, tzinfo=toronto)))
        self.assertFalse(event_monitor_window(datetime(2026, 10, 11, 12, 0, tzinfo=toronto)))

    def test_batch_rotates_at_most_three_and_excludes_csu(self):
        symbols = ["CSU:TSX"] + [f"A{i}:TSX" for i in range(5)]
        first, cursor = choose_event_batch(symbols, cursor=0)
        second, _ = choose_event_batch(symbols, cursor=cursor)
        self.assertEqual(first, ["A0:TSX", "A1:TSX", "A2:TSX"])
        self.assertEqual(second, ["A3:TSX", "A4:TSX", "A0:TSX"])

    def test_remote_url_is_rejected_before_token_access(self):
        with patch.object(scout_event_provider, "_auth_headers") as auth,              patch.object(scout_event_provider.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(ScoutEventProviderError):
                fetch_event_observations(
                    ["AAA:TSX"],
                    url="https://evil.example.com/api/scout/watch-events",
                    state_path=self.state,
                )
        auth.assert_not_called()
        urlopen.assert_not_called()

    def test_first_fetch_establishes_baseline_without_alerting(self):
        with patch.object(scout_event_provider, "_auth_headers", return_value={"Authorization": "Bearer test"}),              patch.object(
                 scout_event_provider.urllib.request,
                 "urlopen",
                 return_value=FakeResponse(self.response(["old-1", "old-2"])),
             ):
            rows = fetch_event_observations(
                ["AAA:TSX"],
                url="http://127.0.0.1:8787/api/scout/watch-events",
                state_path=self.state,
            )
        self.assertEqual(rows, [])
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertIn("old-1", saved["seenBySymbol"]["AAA:TSX"])
        self.assertFalse(saved["tradeEligible"])

    def test_only_unseen_press_release_is_emitted_after_baseline(self):
        self.state.write_text(json.dumps({
            "cursor": 0,
            "seenBySymbol": {"AAA:TSX": ["old-1"]},
            "tradeEligible": False,
        }), encoding="utf-8")
        with patch.object(scout_event_provider, "_auth_headers", return_value={"Authorization": "Bearer test"}),              patch.object(
                 scout_event_provider.urllib.request,
                 "urlopen",
                 return_value=FakeResponse(self.response(["new-2", "old-1"])),
             ):
            rows = fetch_event_observations(
                ["AAA:TSX"],
                url="http://127.0.0.1:8787/api/scout/watch-events",
                state_path=self.state,
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "AAA:TSX")
        self.assertEqual([x["id"] for x in rows[0]["events"]], ["new-2"])
        self.assertEqual(rows[0]["events"][0]["sourceType"], "OFFICIAL_PRESS_RELEASE")


if __name__ == "__main__":
    unittest.main()
