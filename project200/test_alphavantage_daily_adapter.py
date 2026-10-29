import csv
import json
import tempfile
import unittest
from pathlib import Path
from alphavantage_daily_adapter import convert

class AlphaVantageDailyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src=Path(self.tmp.name)/"input.json"
        self.dst=Path(self.tmp.name)/"out.csv"
    def write(self,body):
        self.src.write_text(json.dumps(body),encoding="utf-8")
    def test_sorts_and_normalizes(self):
        self.write({"Time Series (Daily)":{
            "2026-10-23":{"1. open":"12","2. high":"13","3. low":"11","4. close":"12.5","5. volume":"1200"},
            "2026-10-22":{"1. open":"10","2. high":"12","3. low":"9","4. close":"11","5. volume":"1000"}}})
        result=convert(self.src,self.dst)
        self.assertEqual(result["rows"],2)
        with self.dst.open(newline="") as f:
            rows=list(csv.DictReader(f))
        self.assertEqual([r["date"] for r in rows],["2026-10-22","2026-10-23"])
        self.assertEqual(rows[0]["close"],"11")
        self.assertEqual(rows[0]["volume"],"1000")
    def test_provider_rate_limit_rejected(self):
        self.write({"Note":"API limit"})
        with self.assertRaisesRegex(ValueError,"PROVIDER_ERROR"):
            convert(self.src,self.dst)
    def test_nonfinite_rejected(self):
        self.write({"Time Series (Daily)":{"2026-10-22":{
            "1. open":"10","2. high":"11","3. low":"9","4. close":"NaN","5. volume":"100"}}})
        with self.assertRaisesRegex(ValueError,"INVALID_PROVIDER_BAR"):
            convert(self.src,self.dst)
    def test_impossible_bar_rejected(self):
        self.write({"Time Series (Daily)":{"2026-10-22":{
            "1. open":"10","2. high":"9","3. low":"8","4. close":"10","5. volume":"100"}}})
        with self.assertRaisesRegex(ValueError,"INVALID_PROVIDER_BAR"):
            convert(self.src,self.dst)
    def test_no_input_overwrite(self):
        self.write({"Time Series (Daily)":{"2026-10-22":{
            "1. open":"10","2. high":"11","3. low":"9","4. close":"10","5. volume":"100"}}})
        with self.assertRaisesRegex(ValueError,"OUTPUT_OVERWRITES_INPUT"):
            convert(self.src,self.src)
if __name__=="__main__":
    unittest.main()
