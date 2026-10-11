import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import realtime_lite
from realtime_lite import (
    RealtimeLiteError,
    bounded_poll_seconds,
    load_cached_snapshot,
    process_scan_result,
)


class RealtimeLiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.snapshot = Path(self.tmp.name) / "snapshot.json"
        self.state = Path(self.tmp.name) / "state.json"
        self.now = datetime(2099, 1, 1, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def write_snapshot(self, fetched_at):
        self.snapshot.write_text(json.dumps({
            "provider": "synthetic",
            "currency": "CAD",
            "cash": 10000,
            "buyingPower": 7000,
            "positions": [],
            "openOrders": [],
            "transactions": [],
            "fetchedAt": fetched_at,
        }), encoding="utf-8")

    def result(self, market_as_of="2099-01-01 11:59:00", action="BUY"):
        return {
            "marketDataAsOf": market_as_of,
            "decision": {"action": action},
            "reviewPacket": {
                "kind": "CSU_DECISION_REVIEW",
                "version": 1,
                "proposalId": "22222222-2222-4222-8222-222222222222",
                "symbol": "CSU.TO",
                "action": action,
                "quantity": 1,
                "indicativeLimitCAD": 3000.0,
                "expiresAt": "2099-01-01T12:05:00Z",
                "role": "SWING",
                "currentShares": 1,
                "targetShares": 2,
                "score": 4,
                "confidence": "MEDIUM",
                "reasons": ["synthetic"],
                "simulationOnly": True,
                "brokerSubmitted": False,
            },
        }

    def test_poll_interval_is_limited_to_one_to_five_minutes(self):
        self.assertEqual(bounded_poll_seconds(60), 60)
        self.assertEqual(bounded_poll_seconds(180), 180)
        self.assertEqual(bounded_poll_seconds(300), 300)
        with self.assertRaises(RealtimeLiteError):
            bounded_poll_seconds(59)
        with self.assertRaises(RealtimeLiteError):
            bounded_poll_seconds(301)

    def test_stale_cached_snapshot_fails_closed(self):
        stale = (self.now - timedelta(minutes=16)).isoformat().replace("+00:00", "Z")
        self.write_snapshot(stale)
        with self.assertRaises(RealtimeLiteError):
            load_cached_snapshot(self.snapshot, now=self.now)

    def test_fresh_cached_snapshot_is_accepted(self):
        fresh = (self.now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        self.write_snapshot(fresh)
        value = load_cached_snapshot(self.snapshot, now=self.now)
        self.assertEqual(value["currency"], "CAD")

    def test_first_signal_episode_publishes_to_local_panel(self):
        with patch.object(realtime_lite, "publish_review_response", return_value={"ok": True}) as publish:
            out = process_scan_result(self.result(), state_path=self.state, now=self.now)
        self.assertTrue(out["published"])
        self.assertFalse(out["broker_submission_enabled"])
        publish.assert_called_once()

    def test_same_signal_episode_is_suppressed_during_cooldown(self):
        with patch.object(realtime_lite, "publish_review_response", return_value={"ok": True}) as publish:
            first = process_scan_result(self.result(), state_path=self.state, now=self.now)
            second = process_scan_result(
                self.result("2099-01-01 12:02:00"),
                state_path=self.state,
                now=self.now + timedelta(minutes=2),
            )
        self.assertTrue(first["published"])
        self.assertFalse(second["published"])
        self.assertEqual(publish.call_count, 1)

    def test_same_market_bar_is_not_reprocessed(self):
        with patch.object(realtime_lite, "publish_review_response", return_value={"ok": True}) as publish:
            process_scan_result(self.result(), state_path=self.state, now=self.now)
            second = process_scan_result(
                self.result(),
                state_path=self.state,
                now=self.now + timedelta(minutes=3),
            )
        self.assertFalse(second["published"])
        self.assertEqual(second["reason"], "No new market bar")
        self.assertEqual(publish.call_count, 1)

    def test_hold_resets_signal_episode(self):
        with patch.object(realtime_lite, "publish_review_response", return_value={"ok": True}) as publish:
            process_scan_result(self.result(), state_path=self.state, now=self.now)
            hold = self.result("2099-01-01 12:02:00", "HOLD")
            hold["reviewPacket"] = None
            process_scan_result(hold, state_path=self.state, now=self.now + timedelta(minutes=2))
            again = process_scan_result(
                self.result("2099-01-01 12:04:00"),
                state_path=self.state,
                now=self.now + timedelta(minutes=4),
            )
        self.assertTrue(again["published"])
        self.assertEqual(publish.call_count, 2)


if __name__ == "__main__":
    unittest.main()
