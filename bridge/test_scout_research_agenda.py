import unittest
from datetime import datetime, timezone

from scout_research_agenda import (
    ResearchEvidenceError,
    build_research_agenda,
    validate_evidence_bundle,
)


class ScoutResearchAgendaTests(unittest.TestCase):
    def card(self):
        return {
            "symbol": "AAA:TSX",
            "scout": {
                "score": 82,
                "tier": "PRIORITY_RESEARCH",
                "reasons": ["near support", "MACD improving"],
                "riskFlags": ["news review"],
            },
        }

    def test_agenda_is_research_only_and_contains_challenge_questions(self):
        agenda = build_research_agenda(self.card())
        self.assertEqual(agenda["purpose"], "JOINT_DUE_DILIGENCE")
        self.assertGreaterEqual(len(agenda["questions"]), 10)
        self.assertFalse(agenda["authority"]["tradeEligible"])
        self.assertFalse(agenda["authority"]["brokerSubmissionEnabled"])
        self.assertFalse(agenda["authority"]["automaticPromotion"])

    def test_invalid_symbol_is_rejected(self):
        card = self.card()
        card["symbol"] = "AAA"
        with self.assertRaises(ResearchEvidenceError):
            build_research_agenda(card)

    def test_evidence_requires_primary_independent_and_three_sources(self):
        now = datetime(2099, 1, 31, tzinfo=timezone.utc)
        result = validate_evidence_bundle([
            {
                "type": "COMPANY_IR",
                "title": "Investor presentation",
                "url": "https://example.com/ir",
                "publishedAt": "2099-01-10T00:00:00Z",
                "notes": "Primary source.",
            },
            {
                "type": "NEWS",
                "title": "Independent article",
                "url": "https://news.example.com/a",
                "publishedAt": "2099-01-20T00:00:00Z",
                "notes": "Independent source.",
            },
        ], now=now)
        self.assertFalse(result["complete"])
        self.assertIn("At least three valid research sources are required", result["errors"])
        self.assertFalse(result["tradeEligible"])

    def test_complete_evidence_bundle_still_never_grants_trading(self):
        now = datetime(2099, 1, 31, tzinfo=timezone.utc)
        result = validate_evidence_bundle([
            {
                "type": "REGULATORY_FILING",
                "title": "Annual filing",
                "url": "https://regulator.example.com/filing",
                "publishedAt": "2098-12-31T00:00:00Z",
                "notes": "Revenue, debt, and cash flow evidence.",
            },
            {
                "type": "COMPANY_IR",
                "title": "Investor presentation",
                "url": "https://company.example.com/ir",
                "publishedAt": "2099-01-10T00:00:00Z",
                "notes": "Management strategy and capital allocation.",
            },
            {
                "type": "NEWS",
                "title": "Recent independent coverage",
                "url": "https://news.example.com/story",
                "publishedAt": "2099-01-20T00:00:00Z",
                "notes": "Independent view of catalyst and risks.",
            },
        ], now=now)
        self.assertTrue(result["complete"])
        self.assertEqual(result["primarySourceCount"], 2)
        self.assertEqual(result["independentSourceCount"], 1)
        self.assertEqual(result["recentNewsCount"], 1)
        self.assertFalse(result["tradeEligible"])
        self.assertFalse(result["brokerSubmissionEnabled"])

    def test_duplicate_urls_are_rejected(self):
        now = datetime(2099, 1, 31, tzinfo=timezone.utc)
        result = validate_evidence_bundle([
            {
                "type": "REGULATORY_FILING",
                "title": "A",
                "url": "https://example.com/x",
                "notes": "x",
            },
            {
                "type": "NEWS",
                "title": "B",
                "url": "https://example.com/x",
                "notes": "y",
            },
            {
                "type": "NEWS",
                "title": "C",
                "url": "https://example.com/c",
                "notes": "z",
            },
        ], now=now)
        self.assertFalse(result["complete"])
        self.assertTrue(any("duplicates" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
