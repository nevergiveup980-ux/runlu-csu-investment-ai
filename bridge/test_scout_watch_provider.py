import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scout_watch_provider
from scout_watch_provider import (
    ScoutWatchProviderError,
    choose_watch_batch,
    fetch_quote_observations,
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


class ScoutWatchProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "provider-state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_batch_is_capped_at_five_and_rotates(self):
        symbols = [f"A{i}:TSX" for i in range(7)]
        first, cursor = choose_watch_batch(symbols, cursor=0)
        second, cursor2 = choose_watch_batch(symbols, cursor=cursor)
        self.assertEqual(len(first), 5)
        self.assertEqual(first, ["A0:TSX", "A1:TSX", "A2:TSX", "A3:TSX", "A4:TSX"])
        self.assertEqual(second, ["A5:TSX", "A6:TSX", "A0:TSX", "A1:TSX", "A2:TSX"])
        self.assertEqual(cursor2, 3)

    def test_csu_is_excluded_from_scout_watch_batch(self):
        batch, _ = choose_watch_batch(["CSU:TSX", "AAA:TSX"], cursor=0)
        self.assertEqual(batch, ["AAA:TSX"])

    def test_remote_url_is_rejected_before_token_access(self):
        with patch.object(scout_watch_provider, "_auth_headers") as auth,              patch.object(scout_watch_provider.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(ScoutWatchProviderError):
                fetch_quote_observations(
                    ["AAA:TSX"],
                    url="https://evil.example.com/api/scout/watch-quotes",
                    state_path=self.state,
                )
        auth.assert_not_called()
        urlopen.assert_not_called()

    def test_loopback_quote_feed_is_sanitized_and_research_only(self):
        response = {
            "mode": "WATCH_OBSERVATION_RESEARCH_ONLY",
            "observations": [
                {"symbol": "AAA:TSX", "price": 25.5, "marketDataAsOf": "2026-10-12 12:30:00"},
                {"symbol": "EVIL:TSX", "price": 99, "marketDataAsOf": "2026-10-12 12:30:00"},
            ],
            "policy": {"tradeEligible": False, "brokerSubmissionEnabled": False},
        }
        with patch.object(scout_watch_provider, "_auth_headers", return_value={"Authorization": "Bearer test"}),              patch.object(scout_watch_provider.urllib.request, "urlopen", return_value=FakeResponse(response)):
            rows = fetch_quote_observations(
                ["AAA:TSX"],
                url="http://127.0.0.1:8787/api/scout/watch-quotes",
                state_path=self.state,
            )
        self.assertEqual(rows, [{
            "symbol": "AAA:TSX",
            "price": 25.5,
            "events": [],
            "marketDataAsOf": "2026-10-12 12:30:00",
        }])
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertFalse(state["tradeEligible"])
        self.assertFalse(state["brokerSubmissionEnabled"])

    def test_invalid_interval_fails_closed(self):
        with self.assertRaises(ScoutWatchProviderError):
            fetch_quote_observations(
                ["AAA:TSX"],
                interval="30sec",
                state_path=self.state,
            )


if __name__ == "__main__":
    unittest.main()
