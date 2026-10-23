import csv
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from run_research import research

class ResearchTests(unittest.TestCase):
    def test_pipeline_flat_market(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"flat.csv"
            with p.open("w",newline="") as f:
                w=csv.writer(f)
                w.writerow(("date","open","high","low","close","volume"))
                day=date(2025,1,1)
                for i in range(140):
                    w.writerow(((day+timedelta(days=i)).isoformat(),10,11,9,10,100))
            report=research(p)
            self.assertEqual(report["mode"],"RESEARCH_ONLY")
            self.assertEqual(report["test"]["trades"],0)
            self.assertEqual(report["test"]["net_pnl"],"0")
            self.assertEqual(report["data"]["rows"],140)
    def test_no_missing_file_silence(self):
        with self.assertRaises(FileNotFoundError):
            research("/nonexistent/project200.csv")
if __name__=="__main__":
    unittest.main()
