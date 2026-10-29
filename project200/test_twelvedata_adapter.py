import csv
import io
import unittest
from twelvedata_adapter import convert

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.data={"meta":{"symbol":"SPY","interval":"1day"},"values":[
            {"datetime":"2026-10-21","open":"10","high":"11","low":"9","close":"10","volume":"100"},
            {"datetime":"2026-10-20","open":"9","high":"10","low":"8","close":"9","volume":"90"}]}
    def test_valid_and_sorted(self):
        rows=list(csv.DictReader(io.StringIO(convert(self.data,expected_symbol="SPY"))))
        self.assertEqual(rows[0]["date"],"2026-10-20")
    def test_provider_error(self):
        with self.assertRaisesRegex(ValueError,"PROVIDER_ERROR"):
            convert({"status":"error","message":"credits exhausted"})
    def test_wrong_symbol(self):
        with self.assertRaisesRegex(ValueError,"SYMBOL_MISMATCH"):
            convert(self.data,expected_symbol="QQQ")
    def test_wrong_interval(self):
        self.data["meta"]["interval"]="5min"
        with self.assertRaisesRegex(ValueError,"NOT_DAILY_DATA"):
            convert(self.data)
    def test_duplicate_date(self):
        self.data["values"].append(dict(self.data["values"][0]))
        with self.assertRaisesRegex(ValueError,"DUPLICATE_DATE"):
            convert(self.data)
    def test_missing_volume(self):
        del self.data["values"][0]["volume"]
        with self.assertRaisesRegex(ValueError,"INVALID_BAR"):
            convert(self.data)
    def test_nan(self):
        self.data["values"][0]["close"]="NaN"
        with self.assertRaisesRegex(ValueError,"INVALID_OHLCV"):
            convert(self.data)
if __name__=="__main__":
    unittest.main()
