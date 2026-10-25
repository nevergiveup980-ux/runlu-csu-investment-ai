import csv
import tempfile
import unittest
from datetime import date,timedelta
from decimal import Decimal as D
from pathlib import Path
from data_validation import validate_history,walk_forward

class DataTests(unittest.TestCase):
    def make_csv(self, rows=130):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p=Path(tmp.name)/"bars.csv"
        with p.open("w",newline="") as f:
            w=csv.writer(f)
            w.writerow(["date","open","high","low","close","volume"])
            day=date(2026,1,1)
            for i in range(rows):
                w.writerow([(day+timedelta(days=i)).isoformat(),10,11,9,10,100])
        return p
    def test_valid_history(self):
        self.assertEqual(len(validate_history(self.make_csv())),130)
    def test_insufficient(self):
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_HISTORY"):
            validate_history(self.make_csv(rows=1))
    def test_walk_forward_flat(self):
        bars=[{"date":(date(2026,1,1)+timedelta(days=i)).isoformat(),"open":D(10),"high":D(11),"low":D(9),"close":D(10),"volume":D(100)} for i in range(100)]
        r=walk_forward(bars)
        self.assertEqual(r["test"]["trade_count"],0)
    def test_split_guard(self):
        with self.assertRaisesRegex(ValueError,"INVALID_SPLIT"):
            walk_forward([],train_fraction=D("0.99"))
    def test_nonfinite_split(self):
        for value in ("NaN","Infinity","bad"):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,"INVALID_SPLIT"):
                walk_forward([],train_fraction=value)
    def test_invalid_validation_limits(self):
        p=self.make_csv()
        with self.assertRaisesRegex(ValueError,"INVALID_MIN_BARS"):
            validate_history(p,min_bars=True)
        with self.assertRaisesRegex(ValueError,"INVALID_MAX_GAP"):
            validate_history(p,max_gap_days=0)
if __name__=="__main__":
    unittest.main()
