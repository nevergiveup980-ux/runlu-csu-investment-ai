import unittest
from import_market_csv import normalize_csv
class ImportTests(unittest.TestCase):
    def test_normalize_and_sort(self):
        raw=b"Date,Open,High,Low,Close,Volume\n2026-01-03,10,11,9,10,100\n2026-01-02,10,11,9,10,100\n"
        r=normalize_csv(raw)
        self.assertEqual(r["rows"],2)
        self.assertEqual(r["first"],"2026-01-02")
    def test_html_refusal(self):
        with self.assertRaisesRegex(ValueError,"NOT_MARKET_CSV"):
            normalize_csv(b"<html>blocked</html>")
    def test_duplicate(self):
        raw=b"Date,Open,High,Low,Close,Volume\n2026-01-02,10,11,9,10,100\n2026-01-02,10,11,9,10,100\n"
        with self.assertRaisesRegex(ValueError,"EMPTY_OR_DUPLICATE_DATES"):
            normalize_csv(raw)
    def test_bad_ohlc(self):
        raw=b"Date,Open,High,Low,Close,Volume\n2026-01-02,10,9,8,10,100\n"
        with self.assertRaisesRegex(ValueError,"INVALID_OHLC"):
            normalize_csv(raw)
    def test_nan(self):
        raw=b"Date,Open,High,Low,Close,Volume\n2026-01-02,NaN,11,9,10,100\n"
        with self.assertRaisesRegex(ValueError,"INVALID_NUMERIC_VALUE"):
            normalize_csv(raw)
if __name__=="__main__":unittest.main()
