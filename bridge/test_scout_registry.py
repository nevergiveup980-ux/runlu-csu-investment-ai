import tempfile
import unittest
from pathlib import Path

from scout_registry import (
    ScoutRegistryError,
    apply_joint_review,
    execution_eligible_symbols,
    ranked_candidates,
    record_scan,
)


class ScoutRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "scout-registry.json"

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self):
        return {
            "mode": "DISCOVERY_RESEARCH_ONLY",
            "candidates": [
                {
                    "symbol": "SYNTH:TSX",
                    "score": 81,
                    "tier": "PRIORITY_RESEARCH",
                    "reasons": ["synthetic reason"],
                    "riskFlags": ["synthetic risk"],
                    "marketDataAsOf": "2099-01-01",
                }
            ],
        }

    def test_discovery_never_grants_trading_authority(self):
        registry = record_scan(self.scan(), self.path)
        row = registry["candidates"]["SYNTH:TSX"]
        self.assertEqual(row["stage"], "RESEARCH_REQUIRED")
        self.assertFalse(row["tradeEligible"])
        self.assertEqual(execution_eligible_symbols(self.path), [])

    def test_user_confirmation_is_mandatory(self):
        record_scan(self.scan(), self.path)
        with self.assertRaises(ScoutRegistryError):
            apply_joint_review(
                "SYNTH:TSX",
                {
                    "research_complete": True,
                    "assistant_research_complete": True,
                    "user_confirmed": False,
                    "final_decision": "APPROVED",
                    "thesis": "Synthetic thesis",
                    "bear_case": "Synthetic bear case",
                    "key_risks": ["Synthetic risk"],
                    "invalidation": "Synthetic invalidation",
                },
                self.path,
            )

    def test_joint_approval_allows_realtime_watch_but_not_execution(self):
        record_scan(self.scan(), self.path)
        row = apply_joint_review(
            "SYNTH:TSX",
            {
                "research_complete": True,
                "assistant_research_complete": True,
                "user_confirmed": True,
                "final_decision": "APPROVED",
                "thesis": "Synthetic thesis",
                "bear_case": "Synthetic bear case",
                "key_risks": ["Synthetic risk"],
                "invalidation": "Synthetic invalidation",
            },
            self.path,
        )
        self.assertEqual(row["stage"], "APPROVED_UNIVERSE")
        self.assertTrue(row["realtimeEligible"])
        self.assertFalse(row["tradeEligible"])
        self.assertEqual(execution_eligible_symbols(self.path), [])

    def test_ranked_candidates_orders_by_latest_score(self):
        scan = self.scan()
        scan["candidates"].append({
            "symbol": "LOWER:TSX",
            "score": 55,
            "tier": "RESEARCH",
            "reasons": [],
            "riskFlags": [],
            "marketDataAsOf": "2099-01-01",
        })
        record_scan(scan, self.path)
        ranked = ranked_candidates(self.path)
        self.assertEqual(ranked[0]["symbol"], "SYNTH:TSX")


if __name__ == "__main__":
    unittest.main()
