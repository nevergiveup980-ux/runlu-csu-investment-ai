import tempfile
import unittest
from pathlib import Path

from scout_registry import (
    ScoutRegistryError,
    apply_joint_review,
    execution_eligible_symbols,
    ranked_candidates,
    record_assistant_research,
    record_scan,
)
from scout_research_writeback import build_result_template


class ScoutRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.path = root / "scout-registry.json"
        self.archive = root / "scout-research-archive.json"

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
                    "marketDataAsOf": "2026-10-10",
                }
            ],
        }

    def research_packet(self):
        candidate = record_scan(self.scan(), self.path)["candidates"]["SYNTH:TSX"]
        packet = build_result_template(candidate)
        packet["assistantResearchComplete"] = True
        packet["research"].update({
            "business_model": "Synthetic business model.",
            "financial_quality": "Synthetic financial review.",
            "valuation": "Synthetic valuation review.",
            "industry_and_competition": "Synthetic industry review.",
            "management_and_governance": "Synthetic management review.",
            "recent_news_and_catalysts": "Synthetic catalyst review.",
            "bull_case": "Synthetic thesis",
            "bear_case": "Synthetic bear case",
            "key_risks": ["Synthetic risk"],
            "what_could_make_us_wrong": "Synthetic disconfirming evidence.",
            "invalidation_condition": "Synthetic invalidation",
            "sources": [
                {
                    "type": "REGULATORY_FILING",
                    "title": "Synthetic filing",
                    "url": "https://regulator.example.com/synth",
                    "publishedAt": "2026-01-01T00:00:00Z",
                    "notes": "Primary evidence.",
                },
                {
                    "type": "COMPANY_IR",
                    "title": "Synthetic IR",
                    "url": "https://company.example.com/synth",
                    "publishedAt": "2026-02-01T00:00:00Z",
                    "notes": "Management evidence.",
                },
                {
                    "type": "NEWS",
                    "title": "Synthetic independent coverage",
                    "url": "https://news.example.com/synth",
                    "publishedAt": "2026-03-01T00:00:00Z",
                    "notes": "Independent evidence.",
                },
            ],
        })
        return packet

    def seed_completed_research(self):
        packet = self.research_packet()
        return record_assistant_research(
            "SYNTH:TSX",
            packet,
            self.path,
            self.archive,
        )

    def test_discovery_never_grants_trading_authority(self):
        registry = record_scan(self.scan(), self.path)
        row = registry["candidates"]["SYNTH:TSX"]
        self.assertEqual(row["stage"], "RESEARCH_REQUIRED")
        self.assertEqual(row["researchStatus"], "PENDING")
        self.assertFalse(row["tradeEligible"])
        self.assertEqual(execution_eligible_symbols(self.path), [])

    def test_joint_review_is_blocked_before_archived_assistant_research(self):
        record_scan(self.scan(), self.path)
        with self.assertRaises(ScoutRegistryError):
            apply_joint_review(
                "SYNTH:TSX",
                {
                    "user_confirmed": True,
                    "final_decision": "APPROVED",
                },
                self.path,
            )

    def test_assistant_research_writeback_waits_for_user_and_stays_non_tradeable(self):
        row = self.seed_completed_research()
        self.assertEqual(row["stage"], "RESEARCH_REQUIRED")
        self.assertEqual(row["researchStatus"], "ASSISTANT_COMPLETE_AWAITING_USER")
        self.assertFalse(row["realtimeEligible"])
        self.assertFalse(row["tradeEligible"])
        self.assertTrue(row["researchDraft"]["assistantResearchComplete"])
        self.assertFalse(row["researchDraft"]["userConfirmed"])

    def test_user_confirmation_is_mandatory_after_research(self):
        self.seed_completed_research()
        with self.assertRaises(ScoutRegistryError):
            apply_joint_review(
                "SYNTH:TSX",
                {
                    "user_confirmed": False,
                    "final_decision": "APPROVED",
                },
                self.path,
            )

    def test_wrong_research_digest_is_rejected(self):
        row = self.seed_completed_research()
        with self.assertRaises(ScoutRegistryError):
            apply_joint_review(
                "SYNTH:TSX",
                {
                    "user_confirmed": True,
                    "final_decision": "APPROVED",
                    "research_digest": "0" * 64,
                },
                self.path,
            )
        self.assertNotEqual(row["researchDraft"]["digest"], "0" * 64)

    def test_joint_approval_allows_realtime_watch_but_not_execution(self):
        draft = self.seed_completed_research()["researchDraft"]
        row = apply_joint_review(
            "SYNTH:TSX",
            {
                "user_confirmed": True,
                "final_decision": "APPROVED",
                "research_digest": draft["digest"],
            },
            self.path,
        )
        self.assertEqual(row["stage"], "APPROVED_UNIVERSE")
        self.assertEqual(row["researchStatus"], "FINALIZED")
        self.assertTrue(row["realtimeEligible"])
        self.assertFalse(row["tradeEligible"])
        self.assertEqual(row["research"]["researchDigest"], draft["digest"])
        self.assertEqual(execution_eligible_symbols(self.path), [])

    def test_ranked_candidates_orders_by_latest_score(self):
        scan = self.scan()
        scan["candidates"].append({
            "symbol": "LOWER:TSX",
            "score": 55,
            "tier": "RESEARCH",
            "reasons": [],
            "riskFlags": [],
            "marketDataAsOf": "2026-10-10",
        })
        record_scan(scan, self.path)
        ranked = ranked_candidates(self.path)
        self.assertEqual(ranked[0]["symbol"], "SYNTH:TSX")


if __name__ == "__main__":
    unittest.main()
