import os
import sys
import unittest

HERE = os.path.dirname(__file__)
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from sell_gate import SellSignals, evaluate_sell
from trade_lot import TradingMode, new_trade_lot


class SellGateTests(unittest.TestCase):
    def setUp(self):
        self.swing = new_trade_lot(
            lot_id="lot-1",
            symbol="AAPL",
            quantity=10,
            entry_price=100,
            mode=TradingMode.SWING,
        )

    def test_blocks_sale_below_profit_floor(self):
        decision = evaluate_sell(self.swing, SellSignals(price=100.50))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.action, "HOLD / REVIEW")
        self.assertGreater(decision.min_sell_price, 100.50)

    def test_allows_sell_candidate_when_profitable_and_technically_weak(self):
        decision = evaluate_sell(
            self.swing,
            SellSignals(
                price=110,
                sma20=112,
                sma50=113,
                rsi14=40,
                macd=-1,
                macd_signal=0,
                volume_ratio=1.8,
                resistance20=111,
            ),
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.action, "SELL CANDIDATE")
        self.assertGreaterEqual(decision.score, 3)

    def test_profitable_but_strong_trend_stays_hold(self):
        decision = evaluate_sell(
            self.swing,
            SellSignals(
                price=110,
                sma20=105,
                sma50=102,
                rsi14=60,
                macd=2,
                macd_signal=1,
                volume_ratio=1.0,
                resistance20=120,
            ),
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.action, "HOLD / TRAIL")

    def test_major_risk_event_can_override_no_loss_rule(self):
        decision = evaluate_sell(
            self.swing,
            SellSignals(price=80, major_risk_event=True),
        )
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.risk_override)
        self.assertEqual(decision.action, "RISK EXIT / REVIEW")

    def test_mode_changes_default_profit_floor(self):
        intraday = new_trade_lot(lot_id="d", symbol="AAPL", quantity=1, entry_price=100, mode=TradingMode.INTRADAY)
        position = new_trade_lot(lot_id="p", symbol="AAPL", quantity=1, entry_price=100, mode=TradingMode.POSITION)
        d = evaluate_sell(intraday, SellSignals(price=101))
        p = evaluate_sell(position, SellSignals(price=101))
        self.assertLess(d.min_sell_price, p.min_sell_price)


if __name__ == "__main__":
    unittest.main()
