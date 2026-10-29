import unittest
from decimal import Decimal as D
from datetime import datetime, timezone, timedelta
from paper_broker import PaperBroker, Quote

class Tests(unittest.TestCase):
    def setUp(self):
        self.t = datetime(2026,10,22,tzinfo=timezone.utc)
        self.b = PaperBroker()
        self.q = Quote("TEST",D("99"),D("100"),self.t)
    def test_roundtrip_spread(self):
        self.assertEqual(self.b.buy("a",self.q,10,self.t),"FILLED_PAPER")
        self.assertEqual(self.b.sell("b",self.q,10,self.t),"FILLED_PAPER")
        self.assertEqual(self.b.cash,D("1990"))
    def test_duplicate(self):
        self.b.buy("a",self.q,1,self.t)
        self.assertEqual(self.b.buy("a",self.q,1,self.t),"DUPLICATE_ORDER")
    def test_stale(self):
        self.assertEqual(self.b.buy("a",self.q,1,self.t+timedelta(seconds=61)),"STALE_QUOTE")
    def test_reserve(self):
        self.assertEqual(self.b.buy("a",self.q,19,self.t),"CASH_RESERVE")
    def test_no_short(self):
        self.assertEqual(self.b.sell("a",self.q,1,self.t),"INSUFFICIENT_POSITION")
    def test_fee(self):
        self.b.buy("a",self.q,1,self.t,D("1"))
        self.assertEqual(self.b.cash,D("1899"))
    def test_equity(self):
        self.b.buy("a",self.q,1,self.t)
        self.assertEqual(self.b.equity({"TEST":"99"}),D("1999"))
    def test_future_quote(self):
        q=Quote("TEST",D("99"),D("100"),self.t+timedelta(seconds=5))
        self.assertEqual(self.b.buy("a",q,1,self.t),"STALE_QUOTE")

if __name__=="__main__":
    unittest.main()
