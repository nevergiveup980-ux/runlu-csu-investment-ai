import json
import tempfile
import unittest
from pathlib import Path
from fetch_alphavantage_daily import fetch_daily

class FakeResponse:
    def __init__(self,payload):
        self.payload=json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def read(self,size):
        return self.payload[:size]

class FetchDailyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dst=Path(self.tmp.name)/"provider.json"
    def test_success_and_secret_not_in_result(self):
        calls=[]
        def opener(url,timeout):
            calls.append(url)
            return FakeResponse({"Time Series (Daily)":{"2026-10-28":{"1. open":"10","2. high":"11","3. low":"9","4. close":"10","5. volume":"100"}}})
        result=fetch_daily("SPY",self.dst,api_key="SECRET123",opener=opener)
        self.assertEqual(result["bars_received"],1)
        self.assertNotIn("SECRET123",str(result))
        self.assertIn("outputsize=full",calls[0])
        self.assertTrue(self.dst.exists())
    def test_reject_provider_limit_without_file(self):
        with self.assertRaisesRegex(ValueError,"PROVIDER_ERROR_OR_RATE_LIMIT"):
            fetch_daily("SPY",self.dst,api_key="SECRET",
                opener=lambda url,timeout:FakeResponse({"Note":"limit"}))
        self.assertFalse(self.dst.exists())
    def test_reject_malformed_price_before_saving(self):
        invalid={"Time Series (Daily)":{"2026-10-28":{
            "1. open":"10","2. high":"9","3. low":"8","4. close":"10","5. volume":"100"}}}
        with self.assertRaisesRegex(ValueError,"INVALID_PROVIDER_BAR"):
            fetch_daily("SPY",self.dst,api_key="SECRET",
                opener=lambda url,timeout:FakeResponse(invalid))
        self.assertFalse(self.dst.exists())
    def test_existing_file_is_preserved(self):
        self.dst.write_text("existing")
        with self.assertRaisesRegex(FileExistsError,"OUTPUT_ALREADY_EXISTS"):
            fetch_daily("SPY",self.dst,api_key="SECRET")
        self.assertEqual(self.dst.read_text(),"existing")
    def test_request_error_does_not_leak_secret(self):
        def fail(url,timeout):
            raise RuntimeError(url)
        with self.assertRaisesRegex(RuntimeError,"PROVIDER_REQUEST_FAILED") as caught:
            fetch_daily("SPY",self.dst,api_key="SECRET123",opener=fail)
        self.assertNotIn("SECRET123",str(caught.exception))
        self.assertFalse(self.dst.exists())

if __name__=="__main__":
    unittest.main()
