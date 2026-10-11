import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import scout_hunter
from scout_hunter import ScoutHunterError, choose_next_batch, load_or_refresh_universe, run_cycle


class ScoutHunterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cache = root / "universe.json"
        self.state = root / "state.json"
        self.registry = root / "registry.json"

    def tearDown(self):
        self.tmp.cleanup()

    def catalog(self):
        return {
            "version": 1,
            "fetchedAt": "2099-01-01T12:00:00Z",
            "researchOnly": True,
            "tradeEligible": False,
            "universe": [
                {"providerSymbol": "CSU:TSX"},
                {"providerSymbol": "AAA:TSX"},
                {"providerSymbol": "BBB:TSX"},
                {"providerSymbol": "CCC:TSX"},
            ],
        }

    def scan(self, symbols):
        return {
            "mode": "DISCOVERY_RESEARCH_ONLY",
            "candidates": [
                {
                    "symbol": symbol,
                    "score": 70 - i,
                    "tier": "RESEARCH",
                    "reasons": ["synthetic"],
                    "riskFlags": [],
                    "marketDataAsOf": "2099-01-01",
                }
                for i, symbol in enumerate(symbols)
            ],
        }

    def test_batch_excludes_primary_csu_and_wraps(self):
        batch, next_cursor, wrapped = choose_next_batch(
            self.catalog()["universe"],
            cursor=2,
            batch_size=2,
        )
        self.assertEqual(batch, ["CCC:TSX", "AAA:TSX"])
        self.assertEqual(next_cursor, 1)
        self.assertTrue(wrapped)
        self.assertNotIn("CSU:TSX", batch)

    def test_batch_size_above_eight_fails(self):
        with self.assertRaises(ScoutHunterError):
            choose_next_batch(self.catalog()["universe"], cursor=0, batch_size=9)

    def test_fresh_catalog_cache_avoids_remote_refresh(self):
        self.cache.write_text(json.dumps(self.catalog()), encoding="utf-8")
        now = datetime(2099, 1, 1, 13, 0, tzinfo=timezone.utc)
        with patch.object(scout_hunter, "fetch_universe") as fetch:
            value = load_or_refresh_universe(cache_path=self.cache, now=now)
        self.assertEqual(len(value["universe"]), 4)
        fetch.assert_not_called()

    def test_cycle_scans_small_batch_and_never_grants_trading(self):
        catalog = self.catalog()
        with patch.object(scout_hunter, "load_or_refresh_universe", return_value=catalog),              patch.object(scout_hunter, "scan_batch", side_effect=lambda symbols: self.scan(symbols)):
            result = run_cycle(
                universe_cache=self.cache,
                state_path=self.state,
                registry_path=self.registry,
                batch_size=2,
            )

        self.assertEqual(result["scanned"], ["AAA:TSX", "BBB:TSX"])
        self.assertFalse(result["tradeEligible"])
        self.assertFalse(result["brokerSubmissionEnabled"])
        self.assertTrue(self.registry.exists())

        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(state["cycles"], 1)
        self.assertFalse(state["tradeEligible"])

    def test_second_cycle_advances_cursor(self):
        catalog = self.catalog()
        with patch.object(scout_hunter, "load_or_refresh_universe", return_value=catalog),              patch.object(scout_hunter, "scan_batch", side_effect=lambda symbols: self.scan(symbols)):
            first = run_cycle(
                universe_cache=self.cache,
                state_path=self.state,
                registry_path=self.registry,
                batch_size=2,
            )
            second = run_cycle(
                universe_cache=self.cache,
                state_path=self.state,
                registry_path=self.registry,
                batch_size=2,
            )
        self.assertEqual(first["scanned"], ["AAA:TSX", "BBB:TSX"])
        self.assertEqual(second["scanned"], ["CCC:TSX", "AAA:TSX"])


if __name__ == "__main__":
    unittest.main()
