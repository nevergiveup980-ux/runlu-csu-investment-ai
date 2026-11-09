import csv
import tempfile
import unittest
from datetime import date,timedelta
from decimal import Decimal as D
from pathlib import Path
from cost_sensitivity import sensitivity

class CostSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"bars.csv"
        with self.path.open("w",newline="") as f:
            w=csv.writer(f)
            w.writerow(("date","open","high","low","close","volume"))
            day=date(2025,1,1)
            for i in range(140):
                w.writerow(((day+timedelta(days=i)).isoformat(),10,11,9,10,100))
    def test_flat_market_grid(self):
        r=sensitivity(self.path)
        self.assertEqual(r["mode"],"RESEARCH_ONLY")
        self.assertEqual(r["scenario_count"],9)
        self.assertEqual(r["positive_test_scenarios"],0)
        self.assertFalse(r["all_scenarios_positive"])
        self.assertTrue(all(D(s["test_net_pnl_usd"])==0 for s in r["scenarios"]))
    def test_bad_cost_fails_closed(self):
        for value in ("NaN","Infinity","-1"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                sensitivity(self.path,fees=[value])
    def test_excessive_spread_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_SPREAD"):
            sensitivity(self.path,spreads_bps=["20000"])
    def test_empty_grid_rejected(self):
        with self.assertRaisesRegex(ValueError,"EMPTY_GRID"):
            sensitivity(self.path,fees=[])
if __name__=="__main__":
    unittest.main()
