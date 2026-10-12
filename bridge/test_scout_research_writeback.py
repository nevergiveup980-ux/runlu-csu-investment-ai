import tempfile
import unittest
from pathlib import Path

from scout_research_writeback import (
    ResearchWritebackError,
    archive_research_result,
    build_result_template,
    validate_research_result,
)


class ScoutResearchWritebackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.archive = Path(self.tmp.name) / "archive.json"

    def tearDown(self):
        self.tmp.cleanup()

    def candidate(self):
        return {
            "symbol": "AAA:TSX",
            "latestScore": 82,
            "tier": "PRIORITY_RESEARCH",
            "stage": "RESEARCH_REQUIRED",
            "reasons": ["near support"],
            "riskFlags": ["news review"],
            "marketDataAsOf": "2026-10-10",
        }

    def complete_packet(self):
        packet = build_result_template(self.candidate())
        packet["assistantResearchComplete"] = True
        r = packet["research"]
        r.update({
            "business_model": "Synthetic business model.",
            "financial_quality": "Synthetic financial review.",
            "valuation": "Synthetic valuation review.",
            "industry_and_competition": "Synthetic industry review.",
            "management_and_governance": "Synthetic management review.",
            "recent_news_and_catalysts": "Synthetic catalyst review.",
            "bull_case": "Synthetic bull case.",
            "bear_case": "Synthetic bear case.",
            "key_risks": ["Synthetic risk."],
            "what_could_make_us_wrong": "Synthetic disconfirming evidence.",
            "invalidation_condition": "Synthetic invalidation condition.",
            "sources": [
                {
                    "type": "REGULATORY_FILING",
                    "title": "Annual filing",
                    "url": "https://regulator.example.com/aaa",
                    "publishedAt": "2026-01-01T00:00:00Z",
                    "notes": "Primary financial evidence.",
                },
                {
                    "type": "COMPANY_IR",
                    "title": "Investor relations update",
                    "url": "https://company.example.com/aaa",
                    "publishedAt": "2026-02-01T00:00:00Z",
                    "notes": "Primary management evidence.",
                },
                {
                    "type": "NEWS",
                    "title": "Independent coverage",
                    "url": "https://news.example.com/aaa",
                    "publishedAt": "2026-03-01T00:00:00Z",
                    "notes": "Independent risk evidence.",
                },
            ],
        })
        return packet

    def test_template_cannot_claim_user_confirmation(self):
        packet = build_result_template(self.candidate())
        self.assertFalse(packet["assistantResearchComplete"])
        self.assertFalse(packet["userConfirmed"])
        self.assertIsNone(packet["finalDecision"])
        self.assertFalse(packet["authority"]["tradeEligible"])

    def test_complete_result_is_valid_but_still_non_tradeable(self):
        result = validate_research_result(self.complete_packet(), self.candidate())
        self.assertTrue(result["assistantResearchComplete"])
        self.assertFalse(result["userConfirmed"])
        self.assertFalse(result["tradeEligible"])
        self.assertFalse(result["brokerSubmissionEnabled"])
        self.assertEqual(result["evidence"]["sourceCount"], 3)
        self.assertEqual(len(result["digest"]), 64)

    def test_assistant_writeback_cannot_fake_user_confirmation(self):
        packet = self.complete_packet()
        packet["userConfirmed"] = True
        with self.assertRaises(ResearchWritebackError):
            validate_research_result(packet, self.candidate())

    def test_assistant_writeback_cannot_make_final_decision(self):
        packet = self.complete_packet()
        packet["finalDecision"] = "APPROVED"
        with self.assertRaises(ResearchWritebackError):
            validate_research_result(packet, self.candidate())

    def test_incomplete_research_is_rejected(self):
        packet = self.complete_packet()
        packet["research"]["bear_case"] = ""
        with self.assertRaises(ResearchWritebackError):
            validate_research_result(packet, self.candidate())

    def test_archive_versions_research_and_rejects_duplicate_digest(self):
        validated = validate_research_result(self.complete_packet(), self.candidate())
        first = archive_research_result(validated, self.archive)
        self.assertEqual(first["version"], 1)
        self.assertFalse(first["tradeEligible"])
        with self.assertRaises(ResearchWritebackError):
            archive_research_result(validated, self.archive)


if __name__ == "__main__":
    unittest.main()
