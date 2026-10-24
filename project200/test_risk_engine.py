import unittest
from decimal import Decimal as D
from risk_engine import Portfolio, Proposal, check_order

class RiskTests(unittest.TestCase):
    def setUp(self):
        self.p = Portfolio(D("2000"), D("2000"), D("2000"), D("0"))
        self.o = Proposal("SPY", 2, D("500"), D("495"), 2)

    def test_accept_paper(self):
        self.assertEqual(check_order(self.p, self.o), [])

    def test_reject_live(self):
        self.assertIn("LIVE_DISABLED", check_order(self.p, self.o, mode="LIVE"))

    def test_risk_limit(self):
        self.assertIn("TRADE_RISK_LIMIT", check_order(self.p, Proposal("SPY", 5, D("500"), D("495"), 2)))

    def test_daily_halt(self):
        p = Portfolio(D("2000"), D("1959"), D("2000"), D("0"))
        self.assertIn("DAILY_HALT", check_order(p, self.o))

    def test_portfolio_halt(self):
        p = Portfolio(D("2000"), D("1799"), D("2000"), D("0"))
        self.assertIn("PORTFOLIO_HALT", check_order(p, self.o))

    def test_stale(self):
        self.assertIn("STALE_QUOTE", check_order(self.p, Proposal("SPY", 2, D("500"), D("495"), 61)))

if __name__ == "__main__":
    unittest.main()
