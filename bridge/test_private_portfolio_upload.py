import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import private_portfolio_upload as upload
from private_portfolio_upload import (
    PrivatePortfolioUploadError,
    _load_private_env,
    _validate_destination,
    build_mobile_snapshot,
    upload_snapshot,
)


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.value).encode("utf-8")


class PrivatePortfolioUploadTests(unittest.TestCase):
    def test_private_env_loader_only_accepts_expected_keys_and_does_not_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private.env"
            path.write_text(
                "RUNLU_PRIVATE_PORTFOLIO_URL=https://private.example.com/api/private/snapshot\n"
                "RUNLU_PRIVATE_PORTFOLIO_ALLOWED_HOST=private.example.com\n"
                "PRIVATE_SNAPSHOT_UPLOAD_TOKEN=synthetic-token\n"
                "CSU_SNAPSHOT_TOKEN=must-not-load\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"RUNLU_PRIVATE_PORTFOLIO_ALLOWED_HOST": "already-set"}, clear=True):
                _load_private_env(path)
                self.assertEqual(
                    os.environ["RUNLU_PRIVATE_PORTFOLIO_URL"],
                    "https://private.example.com/api/private/snapshot",
                )
                self.assertEqual(os.environ["RUNLU_PRIVATE_PORTFOLIO_ALLOWED_HOST"], "already-set")
                self.assertEqual(os.environ["PRIVATE_SNAPSHOT_UPLOAD_TOKEN"], "synthetic-token")
                self.assertNotIn("CSU_SNAPSHOT_TOKEN", os.environ)

    def test_mobile_snapshot_drops_account_and_transaction_fields(self):
        safe = build_mobile_snapshot({
            "accountId": "DO-NOT-SEND",
            "clientSecret": "DO-NOT-SEND",
            "currency": "CAD",
            "cash": 1000,
            "buyingPower": 900,
            "fetchedAt": "2026-10-13T12:00:00Z",
            "positions": [{
                "symbol": "CSU.TO",
                "quantity": 2,
                "averageCost": 2700,
                "marketValue": 5600,
                "secret": "drop",
            }],
            "openOrders": [{"id": "private-order", "price": 2500}],
            "transactions": [{"id": "private-history"}],
        })
        serialized = json.dumps(safe)
        self.assertNotIn("accountId", serialized)
        self.assertNotIn("clientSecret", serialized)
        self.assertNotIn("transactions", serialized)
        self.assertNotIn("private-order", serialized)
        self.assertNotIn("private-history", serialized)
        self.assertEqual(safe["positions"][0]["symbol"], "CSU.TO")
        self.assertEqual(len(safe["openOrders"]), 1)

    def test_destination_must_be_exact_https_allowlisted_host_and_path(self):
        good = "https://private.example.com/api/private/snapshot"
        self.assertEqual(_validate_destination(good, "private.example.com"), good)
        for bad in [
            "http://private.example.com/api/private/snapshot",
            "https://evil.example.com/api/private/snapshot",
            "https://user:pass@private.example.com/api/private/snapshot",
            "https://private.example.com/api/private/other",
            "https://private.example.com/api/private/snapshot#x",
        ]:
            with self.assertRaises(PrivatePortfolioUploadError):
                _validate_destination(bad, "private.example.com")

    def test_bad_destination_is_rejected_before_upload_token_is_read(self):
        with patch.object(upload, "_upload_headers") as headers,              patch.object(upload.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(PrivatePortfolioUploadError):
                upload_snapshot(
                    {"fetchedAt": "2026-10-13T12:00:00Z"},
                    url="https://evil.example.com/api/private/snapshot",
                    allowed_host="private.example.com",
                )
        headers.assert_not_called()
        urlopen.assert_not_called()

    def test_safe_snapshot_can_upload_with_dedicated_token(self):
        response = {
            "ok": True,
            "storedAt": "2026-10-13T12:01:00Z",
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }
        raw = {
            "currency": "CAD",
            "cash": 1000,
            "buyingPower": 900,
            "fetchedAt": "2026-10-13T12:00:00Z",
            "positions": [],
            "openOrders": [],
        }
        with patch.dict(os.environ, {"PRIVATE_SNAPSHOT_UPLOAD_TOKEN": "synthetic-upload-token"}, clear=True),              patch.object(upload.urllib.request, "urlopen", return_value=FakeResponse(response)) as urlopen:
            result = upload_snapshot(
                raw,
                url="https://private.example.com/api/private/snapshot",
                allowed_host="private.example.com",
            )
        self.assertTrue(result["ok"])
        request = urlopen.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer synthetic-upload-token")
        body = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("accountId", body)
        self.assertNotIn("transactions", body)


if __name__ == "__main__":
    unittest.main()
