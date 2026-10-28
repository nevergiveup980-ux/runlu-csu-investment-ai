import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from run_alphavantage_research import run

class OfflineProviderResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src=Path(self.tmp.name)/"daily.json"
        self.dst=Path(self.tmp.name)/"research.json"
    def write(self,count):
        bars={}
        for i in range(count):
            day=(date(2025,1,1)+timedelta(days=i)).isoformat()
            bars[day]={"1. open":"10","2. high":"11","3. low":"9","4. close":"10","5. volume":"1000"}
        self.src.write_text(json.dumps({"Time Series (Daily)":bars}),encoding="utf-8")
    def test_full_offline_pipeline(self):
        self.write(140)
        result=run(self.src,self.dst,symbol="SPY",acquired_on="2026-10-28")
        self.assertEqual(result["provider_adapter"]["rows"],140)
        self.assertFalse(result["provenance_verified"])
        self.assertFalse(result["evidence_screen"]["live_trading_approved"])
        self.assertEqual(json.loads(self.dst.read_text())["provider_json_sha256"],result["provider_json_sha256"])
    def test_compact_100_rows_fails_without_report(self):
        self.write(100)
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_HISTORY"):
            run(self.src,self.dst,symbol="SPY",acquired_on="2026-10-28")
        self.assertFalse(self.dst.exists())
    def test_reject_output_overwrite(self):
        self.write(140)
        with self.assertRaisesRegex(ValueError,"OUTPUT_OVERWRITES_INPUT"):
            run(self.src,self.src,symbol="SPY",acquired_on="2026-10-28")
    def test_reject_bad_symbol(self):
        self.write(140)
        with self.assertRaisesRegex(ValueError,"INVALID_SYMBOL"):
            run(self.src,self.dst,symbol="../SPY",acquired_on="2026-10-28")

if __name__=="__main__":
    unittest.main()
