import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from snaptrade_handoff import _auth_headers, cache_sanitized_snapshot, sanitize_snapshot


class HandoffTests(unittest.TestCase):
    def test_private_endpoint_requires_local_bearer_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                _auth_headers()
        with patch.dict(os.environ, {"CSU_SNAPSHOT_TOKEN": "synthetic-token"}, clear=True):
            headers = _auth_headers()
            self.assertEqual(headers["Authorization"], "Bearer synthetic-token")

    def test_private_snapshot_cache_is_sanitized_and_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest-snapshot.json"
            raw = {
                "provider": "synthetic",
                "currency": "CAD",
                "cash": 10000,
                "buyingPower": 7000,
                "fetchedAt": "2099-01-01T00:00:00Z",
                "clientSecret": "DO-NOT-CACHE",
                "positions": [],
                "orders": [],
                "history": [],
            }
            cache_sanitized_snapshot(raw, path)
            cached = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(cached["currency"], "CAD")
            self.assertNotIn("clientSecret", cached)

    def test_whitelists_account_fields_and_drops_secrets(self):
        raw = {
            "provider": "SnapTrade / Webull Canada",
            "cash": 10000.00,
            "buyingPower": 7000.00,
            "fetchedAt": "2026-10-10T20:00:00Z",
            "clientSecret": "DO-NOT-FORWARD",
            "accessToken": "DO-NOT-FORWARD",
            "positions": [{"ticker": "CSU.TO", "units": 0}],
            "orders": [{"orderId": "x", "ticker": "CSU.TO", "action": "buy", "units": 1, "price": 3000, "status": "OPEN"}],
            "history": [{"ticker": "CSU.TO"}] * 5,
        }
        safe = sanitize_snapshot(raw)
        self.assertEqual(safe["cash"], 10000.00)
        self.assertEqual(safe["buyingPower"], 7000.00)
        self.assertEqual(len(safe["transactions"]), 5)
        self.assertEqual(safe["openOrders"][0]["limitPrice"], 3000)
        self.assertNotIn("clientSecret", safe)
        self.assertNotIn("accessToken", safe)


if __name__ == "__main__":
    unittest.main()
