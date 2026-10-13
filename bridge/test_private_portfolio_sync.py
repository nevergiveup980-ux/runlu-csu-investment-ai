import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import private_portfolio_sync as sync
from private_portfolio_sync import (
    PrivatePortfolioSyncError,
    bounded_poll_seconds,
    sync_once,
)


class PrivatePortfolioSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.snapshot = root / "snapshot.json"
        self.state = root / "state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write_snapshot(self, fetched_at):
        self.snapshot.write_text(json.dumps({
            "currency": "CAD",
            "cash": 1000,
            "buyingPower": 900,
            "positions": [{"symbol": "CSU.TO", "quantity": 1, "averageCost": 2700, "marketValue": 2800}],
            "openOrders": [],
            "transactions": [],
            "fetchedAt": fetched_at,
        }), encoding="utf-8")

    def test_poll_bounds(self):
        self.assertEqual(bounded_poll_seconds(60), 60)
        self.assertEqual(bounded_poll_seconds(180), 180)
        self.assertEqual(bounded_poll_seconds(300), 300)
        with self.assertRaises(PrivatePortfolioSyncError):
            bounded_poll_seconds(59)
        with self.assertRaises(PrivatePortfolioSyncError):
            bounded_poll_seconds(301)

    def test_fresh_snapshot_uploads_once_then_dedupes(self):
        now = datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc)
        self.write_snapshot((now - timedelta(minutes=2)).isoformat())
        with patch.object(sync, "upload_cached_snapshot", return_value={
            "ok": True,
            "storedAt": "2026-10-13T13:00:01Z",
            "fetchedAt": "2026-10-13T12:58:00Z",
            "positions": 1,
        }) as upload:
            first = sync_once(snapshot_path=self.snapshot, state_path=self.state, now=now)
            second = sync_once(snapshot_path=self.snapshot, state_path=self.state, now=now)
        self.assertTrue(first["uploaded"])
        self.assertFalse(second["uploaded"])
        self.assertEqual(second["reason"], "Snapshot already uploaded")
        upload.assert_called_once_with(self.snapshot)
        self.assertFalse(first["tradeEligible"])
        self.assertFalse(first["brokerSubmissionEnabled"])

    def test_stale_snapshot_does_not_upload(self):
        now = datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc)
        self.write_snapshot((now - timedelta(minutes=31)).isoformat())
        with patch.object(sync, "upload_cached_snapshot") as upload:
            result = sync_once(snapshot_path=self.snapshot, state_path=self.state, now=now)
        self.assertFalse(result["uploaded"])
        self.assertEqual(result["reason"], "Cached broker snapshot is stale")
        upload.assert_not_called()

    def test_far_future_snapshot_fails_closed(self):
        now = datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc)
        self.write_snapshot((now + timedelta(minutes=6)).isoformat())
        with self.assertRaises(PrivatePortfolioSyncError):
            sync_once(snapshot_path=self.snapshot, state_path=self.state, now=now)

    def test_upload_failure_is_recorded_without_trade_authority(self):
        now = datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc)
        self.write_snapshot((now - timedelta(minutes=1)).isoformat())
        with patch.object(
            sync,
            "upload_cached_snapshot",
            side_effect=sync.PrivatePortfolioUploadError("synthetic upload failure"),
        ):
            with self.assertRaises(PrivatePortfolioSyncError):
                sync_once(snapshot_path=self.snapshot, state_path=self.state, now=now)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertIn("synthetic upload failure", state["lastError"])
        self.assertFalse(state["tradeEligible"])
        self.assertFalse(state["brokerSubmissionEnabled"])


if __name__ == "__main__":
    unittest.main()
