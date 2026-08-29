import sys
import unittest
from decimal import Decimal
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from account_preflight import AccountSnapshot, PositionSnapshot, preflight_buy, preflight_sell
from order_reconcile import normalize_order, reconcile


class PreflightTests(unittest.TestCase):
    def test_buy_rejects_insufficient_buying_power(self):
        account = AccountSnapshot("a1", Decimal("500"), Decimal("500"), Decimal("0"))
        result = preflight_buy(account=account, estimated_notional=Decimal("750"))
        self.assertFalse(result["approved"])

    def test_sell_rejects_more_than_held(self):
        positions = [PositionSnapshot("AAPL", Decimal("1"), Decimal("180"))]
        result = preflight_sell(symbol="AAPL", quantity=Decimal("2"), positions=positions)
        self.assertFalse(result["approved"])

    def test_sell_allows_held_quantity(self):
        positions = [PositionSnapshot("AAPL", Decimal("2"), Decimal("180"))]
        result = preflight_sell(symbol="AAPL", quantity=Decimal("1"), positions=positions)
        self.assertTrue(result["approved"])


class ReconcileTests(unittest.TestCase):
    def test_fill_transition_is_detected(self):
        previous = normalize_order({"orderId": "o1", "symbol": "AAPL", "side": "BUY", "status": "WORKING", "quantity": 1, "filledQty": 0})
        current = normalize_order({"orderId": "o1", "symbol": "AAPL", "side": "BUY", "status": "FILLED", "quantity": 1, "filledQty": 1, "avgFilledPrice": 181.25})
        result = reconcile(previous, current)
        self.assertTrue(result["changed"])
        self.assertTrue(result["filled"])
        self.assertTrue(result["terminal"])


if __name__ == "__main__":
    unittest.main()
