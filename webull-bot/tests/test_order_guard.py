import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from order_guard import OrderIntent, OrderRejected, validate_order


class OrderGuardTests(unittest.TestCase):
    def setUp(self):
        os.environ["RUNLU_ALLOWED_SYMBOLS"] = "AAPL,MSFT"
        os.environ["RUNLU_MAX_ORDER_QTY"] = "2"
        os.environ["RUNLU_MAX_ORDER_NOTIONAL"] = "1000"

    def test_allows_small_sandbox_limit_order(self):
        result = validate_order(
            OrderIntent("AAPL", "BUY", Decimal("1"), Decimal("180"))
        )
        self.assertTrue(result["approved"])
        self.assertEqual(result["environment"], "sandbox")

    def test_rejects_live_environment(self):
        with self.assertRaises(OrderRejected):
            validate_order(
                OrderIntent("AAPL", "BUY", Decimal("1"), Decimal("180")),
                environment="production",
            )

    def test_rejects_unapproved_symbol(self):
        with self.assertRaises(OrderRejected):
            validate_order(OrderIntent("NVDA", "BUY", Decimal("1"), Decimal("100")))

    def test_rejects_notional_over_limit(self):
        with self.assertRaises(OrderRejected):
            validate_order(OrderIntent("AAPL", "BUY", Decimal("2"), Decimal("600")))

    def test_rejects_short(self):
        with self.assertRaises(OrderRejected):
            validate_order(OrderIntent("AAPL", "SHORT", Decimal("1"), Decimal("180")))


if __name__ == "__main__":
    unittest.main()
