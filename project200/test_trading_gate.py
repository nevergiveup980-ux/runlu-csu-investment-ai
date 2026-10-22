import unittest
from decimal import Decimal as D
from datetime import datetime, timezone
from paper_broker import Quote
from trading_gate import TradingGate

class GateTests(unittest.TestCase):
    def setUp(self):
        self.g = TradingGate()
        self.t = datetime(2026,10,22,tzinfo=timezone.utc)
        self.q = Quote('TEST',D('99'),D('100'),self.t)
    def test_paper_buy(self):
        self.assertEqual(self.g.buy('one',self.q,5,D('98'),self.t),['FILLED_PAPER'])
    def test_risk_reject(self):
        self.assertIn('TRADE_RISK_LIMIT',self.g.buy('one',self.q,5,D('90'),self.t))
    def test_duplicate(self):
        self.g.buy('one',self.q,1,D('98'),self.t)
        self.assertIn('DUPLICATE_ORDER',self.g.buy('one',self.q,1,D('98'),self.t))
    def test_fee_reserve(self):
        self.assertIn('FEE_RESERVE',self.g.buy('one',self.q,18,D('99'),self.t,D('1')))
    def test_no_missing_marks(self):
        self.g.buy('one',self.q,1,D('99'),self.t)
        other=Quote('OTHER',D('10'),D('11'),self.t)
        self.assertIn('MISSING_PORTFOLIO_MARKS',self.g.buy('two',other,1,D('10'),self.t))
if __name__=='__main__': unittest.main()
