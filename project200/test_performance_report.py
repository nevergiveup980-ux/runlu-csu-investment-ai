import unittest
from decimal import Decimal as D
from performance_report import summarize

def trade(date,pnl):
    return {"entry_date":date,"exit_date":date,"net_pnl":str(pnl)}

class ReportTests(unittest.TestCase):
    def test_no_trades(self):
        r=summarize({"trades":[]})
        self.assertEqual(r["net_pnl"],"0")
        self.assertIsNone(r["win_rate_pct"])
    def test_win_loss_and_drawdown(self):
        r=summarize({"trades":[trade("2026-01-01",20),trade("2026-01-02",-30),trade("2026-01-03",5)]})
        self.assertEqual(r["net_pnl"],"-5")
        self.assertEqual(r["max_closed_trade_drawdown"],"30")
        self.assertEqual(r["wins"],2)
    def test_reject_nan(self):
        with self.assertRaisesRegex(ValueError,"INVALID_TRADE"):
            summarize({"trades":[trade("2026-01-01","NaN")]})
    def test_reject_out_of_order(self):
        with self.assertRaisesRegex(ValueError,"OUT_OF_ORDER_TRADES"):
            summarize({"trades":[trade("2026-01-03",1),trade("2026-01-01",2)]})
    def test_no_losses_profit_factor_undefined(self):
        self.assertIsNone(summarize({"trades":[trade("2026-01-01",10)]})["profit_factor"])
    def test_reject_nonfinite_starting_cash(self):
        for value in (D("NaN"),D("Infinity"),D("-1")):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,"INVALID_STARTING_CASH"):
                summarize({"trades":[]},starting_cash=value)
    def test_reject_invalid_calendar_date(self):
        with self.assertRaisesRegex(ValueError,"INVALID_TRADE"):
            summarize({"trades":[trade("2026-02-30",5)]})
    def test_reject_malformed_result(self):
        with self.assertRaisesRegex(ValueError,"MISSING_TRADES"):
            summarize(None)
    def test_reconcile_matching_ledger(self):
        r=summarize({"trades":[trade("2026-01-01",20)],"trade_count":1,
                     "net_pnl":"20.00","ending_equity":"2020"})
        self.assertEqual(r["net_pnl"],"20")
    def test_reject_incorrect_count(self):
        with self.assertRaisesRegex(ValueError,"INCONSISTENT_TRADE_COUNT"):
            summarize({"trades":[trade("2026-01-01",20)],"trade_count":2})
    def test_reject_incorrect_total(self):
        with self.assertRaisesRegex(ValueError,"INCONSISTENT_NET_PNL"):
            summarize({"trades":[trade("2026-01-01",20)],"net_pnl":"200"})
    def test_reject_incorrect_ending_equity(self):
        with self.assertRaisesRegex(ValueError,"INCONSISTENT_ENDING_EQUITY"):
            summarize({"trades":[trade("2026-01-01",20)],"ending_equity":"2200"})
if __name__=="__main__":unittest.main()
