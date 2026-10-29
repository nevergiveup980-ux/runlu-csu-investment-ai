import csv
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from run_research_bundle import bundle

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.csv=Path(self.tmp.name)/"flat.csv"
        with self.csv.open("w",newline="") as f:
            w=csv.writer(f)
            w.writerow(("date","open","high","low","close","volume"))
            for i in range(140):
                w.writerow(((date(2025,1,1)+timedelta(days=i)).isoformat(),10,11,9,10,100))
    def test_flat_market_reproducible(self):
        first=bundle(self.csv,source_label="SYNTHETIC TEST DATA")
        second=bundle(self.csv,source_label="SYNTHETIC TEST DATA")
        self.assertEqual(first,second)
        self.assertEqual(first["mode"],"RESEARCH_ONLY")
        self.assertIs(first["provenance_verified"],False)
        self.assertEqual(first["input_sha256"],first["research"]["data"]["sha256"])
        self.assertEqual(first["cost_sensitivity"]["scenario_count"],9)
        self.assertEqual(first["buy_and_hold_baseline"]["baseline"],"BUY_AND_HOLD_HELD_OUT")
        from decimal import Decimal as D
        self.assertEqual(D(first["test_excess_pnl_vs_baseline_usd"]),
                         D(first["research"]["test"]["net_pnl"])-D(first["buy_and_hold_baseline"]["net_pnl"]))
        self.assertFalse(first["evidence_screen"]["screen_passed"])
        self.assertFalse(first["evidence_screen"]["live_trading_approved"])
    def test_source_label_required(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_LABEL_REQUIRED"):
            bundle(self.csv,source_label=" ")
    def test_missing_input_fails(self):
        with self.assertRaises(FileNotFoundError):
            bundle(Path(self.tmp.name)/"missing.csv",source_label="test")
if __name__=="__main__":
    unittest.main()
