import csv
import tempfile
import unittest
from datetime import date,timedelta
from decimal import Decimal as D
from pathlib import Path
from data_validation import validate_history,walk_forward

class DataTests(unittest.TestCase):
    def test_valid_history(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bars.csv"
            with p.open("w",newline="") as f:
                w=csv.writer(f)
                w.writerow(["date","open","high","low","close","volume"])
                day=date(2026,1,1)
                for i in range(130):
                    w.writerow([(day+timedelta(days=i)).isoformat(),10,11,9,10,100])
            self.assertEqual(len(validate_history(p)),130)
    def test_insufficient(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bars.csv"
            p.write_text("date,open,high,low,close,volume\n2026-01-01,10,11,9,10,100\n")
            with self.assertRaisesRegex(ValueError,"INSUFFICIENT_HISTORY"):
                validate_history(p)
    def test_walk_forward_flat(self):
        bars=[{"date":(date(2026,1,1)+timedelta(days=i)).isoformat(),"open":D(10),"high":D(11),"low":D(9),"close":D(10),"volume":D(100)} for i in range(100)]
        r=walk_forward(bars)
        self.assertEqual(r["test"]["trade_count"],0)
    def test_split_guard(self):
        with self.assertRaisesRegex(ValueError,"INVALID_SPLIT"):
            walk_forward([],train_fraction=D("0.99"))
if __name__=="__main__":unittest.main()
