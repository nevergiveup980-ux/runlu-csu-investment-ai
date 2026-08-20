import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from buy_gate import BuyDecision, BuySnapshot, evaluate_buy_gate, position_size_plan
from trade_lot import TradingMode


class BuyGateTests(unittest.TestCase):
    def test_blocks_chasing_far_above_sma20(self):
        result = evaluate_buy_gate(
            BuySnapshot(price=110, sma20=100, sma50=95, rsi14=58, macd=2, macd_signal=1),
            TradingMode.SWING,
        )
        self.assertEqual(result.decision, BuyDecision.BLOCK)

    def test_swing_candidate_requires_multiple_confirmations(self):
        result = evaluate_buy_gate(
            BuySnapshot(
                price=102,
                sma20=100,
                sma50=98,
                rsi14=48,
                macd=1.2,
                macd_signal=1.0,
                support20=98,
                resistance20=115,
                volume_ratio=1.3,
            ),
            TradingMode.SWING,
        )
        self.assertEqual(result.decision, BuyDecision.BUY_CANDIDATE)
        self.assertGreaterEqual(result.score, result.required_score)

    def test_weak_setup_stays_watch(self):
        result = evaluate_buy_gate(
            BuySnapshot(price=99, sma20=100, sma50=105, rsi14=65, macd=0.5, macd_signal=1.0),
            TradingMode.SWING,
        )
        self.assertEqual(result.decision, BuyDecision.WATCH)

    def test_position_mode_is_more_selective(self):
        snapshot = BuySnapshot(
            price=101,
            sma20=100,
            sma50=99,
            rsi14=50,
            macd=1.1,
            macd_signal=1.0,
        )
        swing = evaluate_buy_gate(snapshot, TradingMode.SWING)
        position = evaluate_buy_gate(snapshot, TradingMode.POSITION)
        self.assertGreaterEqual(position.required_score, swing.required_score)

    def test_position_size_respects_cash_and_quantity_caps(self):
        plan = position_size_plan(
            available_cash=10000,
            limit_price=500,
            max_trade_cash_pct=0.20,
            max_quantity=2,
        )
        self.assertEqual(plan["quantity"], 2)
        self.assertEqual(plan["estimated_notional"], 1000)

    def test_position_size_can_return_zero(self):
        plan = position_size_plan(
            available_cash=1000,
            limit_price=600,
            max_trade_cash_pct=0.20,
            max_quantity=1,
        )
        self.assertEqual(plan["quantity"], 0)


if __name__ == "__main__":
    unittest.main()
