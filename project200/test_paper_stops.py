import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from paper_broker import Quote
from trading_gate import TradingGate
from paper_stops import evaluate_stops

class StopTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 23, tzinfo=timezone.utc)
        self.gate = TradingGate()
        q = Quote("TEST", D("99"), D("100"), self.now)
        self.assertEqual(self.gate.buy("entry", q, 2, D("95"), self.now), ["FILLED_PAPER"])
    def test_no_trigger(self):
        q = Quote("TEST", D("96"), D("97"), self.now)
        self.assertEqual(evaluate_stops(self.gate, {"TEST": q}, self.now)["status"], "NO_STOP_TRIGGER")
        self.assertEqual(self.gate.broker.positions["TEST"], 2)
    def test_trigger(self):
        q = Quote("TEST", D("95"), D("96"), self.now)
        result = evaluate_stops(self.gate, {"TEST": q}, self.now)
        self.assertEqual(result["status"], "STOP_FILLED_PAPER")
        self.assertEqual(self.gate.broker.positions["TEST"], 0)
        self.assertEqual(self.gate.broker.cash, D("1990"))
    def test_gap_fill_at_bid_not_stop(self):
        q = Quote("TEST", D("80"), D("81"), self.now)
        result = evaluate_stops(self.gate, {"TEST": q}, self.now)
        self.assertEqual(result["fills"][0]["fill_bid"], "80")
        self.assertEqual(self.gate.broker.cash, D("1960"))
    def test_stale_quote(self):
        q = Quote("TEST", D("90"), D("91"), self.now-timedelta(seconds=61))
        self.assertEqual(evaluate_stops(self.gate, {"TEST": q}, self.now)["status"], "STALE_QUOTE")
        self.assertEqual(self.gate.broker.positions["TEST"], 2)
    def test_missing_quote(self):
        self.assertEqual(evaluate_stops(self.gate, {}, self.now)["status"], "INVALID_OR_MISSING_QUOTE")
    def test_idempotent_after_liquidation(self):
        q = Quote("TEST", D("90"), D("91"), self.now)
        evaluate_stops(self.gate, {"TEST": q}, self.now)
        self.assertEqual(evaluate_stops(self.gate, {"TEST": q}, self.now)["status"], "NO_POSITIONS")
    def test_no_automatic_background_execution(self):
        q = Quote("TEST", D("90"), D("91"), self.now)
        self.assertEqual(self.gate.broker.positions["TEST"], 2)
        self.assertEqual(self.gate.broker.events[-1]["side"], "BUY")
if __name__ == "__main__":
    unittest.main()
