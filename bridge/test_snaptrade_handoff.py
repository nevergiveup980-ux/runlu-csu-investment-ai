import unittest
from snaptrade_handoff import sanitize_snapshot


class HandoffTests(unittest.TestCase):
    def test_whitelists_account_fields_and_drops_secrets(self):
        raw = {
            "provider": "SnapTrade / Webull Canada",
            "cash": 9895.53,
            "buyingPower": 7045.53,
            "fetchedAt": "2026-10-10T20:00:00Z",
            "clientSecret": "DO-NOT-FORWARD",
            "accessToken": "DO-NOT-FORWARD",
            "positions": [{"ticker": "CSU.TO", "units": 0}],
            "orders": [{"orderId": "x", "ticker": "CSU.TO", "action": "buy", "units": 1, "price": 2850, "status": "OPEN"}],
            "history": [{"ticker": "CSU.TO"}] * 33,
        }
        safe = sanitize_snapshot(raw)
        self.assertEqual(safe["cash"], 9895.53)
        self.assertEqual(safe["buyingPower"], 7045.53)
        self.assertEqual(len(safe["transactions"]), 33)
        self.assertEqual(safe["openOrders"][0]["limitPrice"], 2850)
        self.assertNotIn("clientSecret", safe)
        self.assertNotIn("accessToken", safe)


if __name__ == "__main__":
    unittest.main()
