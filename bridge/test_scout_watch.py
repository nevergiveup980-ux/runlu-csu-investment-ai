import json
import tempfile
import unittest
from pathlib import Path

from scout_watch import ScoutWatchError, bounded_poll_seconds, process_observation, watch_symbols


class ScoutWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.registry = root / "registry.json"
        self.state = root / "watch-state.json"
        self.registry.write_text(json.dumps({
            "version": 1,
            "candidates": {
                "AAA:TSX": {
                    "symbol": "AAA:TSX",
                    "stage": "WATCH",
                    "researchStatus": "FINALIZED",
                    "latestScore": 80,
                    "research": {"researchDigest": "a" * 64, "finalDecision": "WATCH"},
                    "tradeEligible": False,
                },
                "BBB:TSX": {
                    "symbol": "BBB:TSX",
                    "stage": "APPROVED_UNIVERSE",
                    "researchStatus": "FINALIZED",
                    "latestScore": 85,
                    "research": {"researchDigest": "b" * 64, "finalDecision": "APPROVED"},
                    "tradeEligible": False,
                },
                "CCC:TSX": {
                    "symbol": "CCC:TSX",
                    "stage": "RESEARCH_REQUIRED",
                    "researchStatus": "PENDING",
                    "latestScore": 70,
                    "tradeEligible": False,
                },
            },
        }), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_poll_bounds(self):
        self.assertEqual(bounded_poll_seconds(60), 60)
        self.assertEqual(bounded_poll_seconds(300), 300)
        with self.assertRaises(ScoutWatchError):
            bounded_poll_seconds(30)
        with self.assertRaises(ScoutWatchError):
            bounded_poll_seconds(301)

    def test_only_finalized_watch_and_approved_are_monitored(self):
        self.assertEqual(watch_symbols(self.registry), ["AAA:TSX", "BBB:TSX"])

    def test_first_price_is_baseline_only(self):
        result = process_observation(
            "AAA:TSX", price=100, registry_path=self.registry, state_path=self.state
        )
        self.assertFalse(result["recheckRequired"])
        self.assertFalse(result["tradeEligible"])

    def test_material_price_move_reopens_research(self):
        process_observation(
            "AAA:TSX", price=100, registry_path=self.registry, state_path=self.state
        )
        result = process_observation(
            "AAA:TSX", price=87, registry_path=self.registry, state_path=self.state
        )
        self.assertTrue(result["recheckRequired"])
        self.assertEqual(result["stage"], "RECHECK_REQUIRED")
        self.assertTrue(any(x.startswith("PRICE_MOVE_PCT:") for x in result["reasons"]))
        self.assertFalse(result["brokerSubmissionEnabled"])

    def test_material_event_reopens_research(self):
        result = process_observation(
            "BBB:TSX",
            price=50,
            events=[{"type": "GUIDANCE"}],
            registry_path=self.registry,
            state_path=self.state,
        )
        self.assertTrue(result["recheckRequired"])
        self.assertIn("EVENT:GUIDANCE", result["reasons"])
        self.assertFalse(result["tradeEligible"])

    def test_non_watch_symbol_is_ignored(self):
        result = process_observation(
            "CCC:TSX", price=10, registry_path=self.registry, state_path=self.state
        )
        self.assertFalse(result["recheckRequired"])
        self.assertFalse(result["tradeEligible"])


if __name__ == "__main__":
    unittest.main()
