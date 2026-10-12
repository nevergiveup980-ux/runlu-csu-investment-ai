import unittest

from scout_research_card import build_cards, build_research_card, card_completion


class ScoutResearchCardTests(unittest.TestCase):
    def candidate(self):
        return {
            "symbol": "AAA:TSX",
            "latestScore": 82,
            "tier": "PRIORITY_RESEARCH",
            "stage": "RESEARCH_REQUIRED",
            "reasons": ["near support"],
            "riskFlags": ["news review"],
            "marketDataAsOf": "2099-01-01",
        }

    def test_card_starts_incomplete_and_non_tradeable(self):
        card = build_research_card(self.candidate())
        self.assertFalse(card["decision"]["assistantResearchComplete"])
        self.assertFalse(card["decision"]["userConfirmed"])
        self.assertFalse(card["authority"]["tradeEligible"])
        self.assertFalse(card["authority"]["brokerSubmissionEnabled"])
        self.assertEqual(card["researchAgenda"]["purpose"], "JOINT_DUE_DILIGENCE")

        status = card_completion(card)
        self.assertFalse(status["complete"])
        self.assertIn("bull_case", status["missing"])
        self.assertIn("bear_case", status["missing"])
        self.assertFalse(status["tradeEligible"])
        self.assertFalse(status["brokerSubmissionEnabled"])

    def test_completion_requires_research_sections_and_sources(self):
        card = build_research_card(self.candidate())
        for key in (
            "business_model",
            "financial_quality",
            "valuation",
            "industry_and_competition",
            "management_and_governance",
            "recent_news_and_catalysts",
            "bull_case",
            "bear_case",
            "what_could_make_us_wrong",
            "invalidation_condition",
        ):
            card["research"][key] = "Synthetic research"
        card["research"]["key_risks"] = ["Synthetic risk"]
        card["research"]["sources"] = [
            {
                "type": "REGULATORY_FILING",
                "title": "Synthetic filing",
                "url": "https://example.com/filing",
                "publishedAt": "2026-01-01T00:00:00Z",
                "notes": "Primary evidence",
            },
            {
                "type": "COMPANY_IR",
                "title": "Synthetic IR",
                "url": "https://example.com/ir",
                "publishedAt": "2026-01-02T00:00:00Z",
                "notes": "Management evidence",
            },
            {
                "type": "NEWS",
                "title": "Synthetic news",
                "url": "https://example.com/news",
                "publishedAt": "2026-01-03T00:00:00Z",
                "notes": "Independent evidence",
            },
        ]

        status = card_completion(card)
        self.assertTrue(status["complete"])
        self.assertEqual(status["missing"], [])
        self.assertFalse(status["tradeEligible"])

    def test_card_hydrates_archived_assistant_research_without_user_confirmation(self):
        candidate = self.candidate()
        candidate["researchStatus"] = "ASSISTANT_COMPLETE_AWAITING_USER"
        candidate["researchDraft"] = {
            "digest": "a" * 64,
            "archiveVersion": 2,
            "completedAt": "2026-10-12T12:00:00Z",
            "assistantResearchComplete": True,
            "userConfirmed": False,
            "finalDecision": None,
            "evidence": {"sourceCount": 3},
            "research": {
                "business_model": "Business",
                "financial_quality": "Financials",
                "valuation": "Valuation",
                "industry_and_competition": "Industry",
                "management_and_governance": "Management",
                "recent_news_and_catalysts": "News",
                "bull_case": "Bull",
                "bear_case": "Bear",
                "key_risks": ["Risk"],
                "what_could_make_us_wrong": "Wrong",
                "invalidation_condition": "Invalidation",
                "sources": [
                    {"type": "REGULATORY_FILING", "title": "Filing", "url": "https://example.com/f", "publishedAt": "2026-01-01T00:00:00Z", "notes": "Primary"},
                    {"type": "COMPANY_IR", "title": "IR", "url": "https://example.com/i", "publishedAt": "2026-01-02T00:00:00Z", "notes": "Primary"},
                    {"type": "NEWS", "title": "News", "url": "https://example.com/n", "publishedAt": "2026-01-03T00:00:00Z", "notes": "Independent"},
                ],
            },
        }
        card = build_research_card(candidate)
        self.assertTrue(card["decision"]["assistantResearchComplete"])
        self.assertFalse(card["decision"]["userConfirmed"])
        self.assertEqual(card["researchWriteback"]["status"], "ASSISTANT_COMPLETE_AWAITING_USER")
        self.assertEqual(card["researchWriteback"]["archiveVersion"], 2)
        self.assertFalse(card["authority"]["tradeEligible"])

    def test_pass_candidates_are_omitted_from_card_batch(self):
        passed = self.candidate()
        passed["stage"] = "PASS"
        cards = build_cards([passed, self.candidate()])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["symbol"], "AAA:TSX")

    def test_card_batch_is_capped_at_five(self):
        candidates = []
        for i in range(7):
            row = self.candidate()
            row["symbol"] = f"A{i}:TSX"
            candidates.append(row)
        cards = build_cards(candidates)
        self.assertEqual(len(cards), 5)


if __name__ == "__main__":
    unittest.main()
