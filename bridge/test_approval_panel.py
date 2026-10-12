import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from approval_panel import ApprovalPanelError, PanelState, _html
from scout_registry import record_scan
from scout_research_writeback import build_result_template


class ApprovalPanelStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "approval-ledger.jsonl"
        self.scout_report = Path(self.tmp.name) / "scout-daily-top5.json"
        self.state = PanelState(self.ledger, self.scout_report)

    def tearDown(self):
        self.tmp.cleanup()

    def packet(self, proposal_id="11111111-1111-4111-8111-111111111111"):
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        return {
            "expires_at": expiry,
            "order": {
                "account_id": "private-runtime-account",
                "action": "BUY",
                "universal_symbol_id": None,
                "symbol": "CSU.TO",
                "order_type": "Limit",
                "time_in_force": "Day",
                "trading_session": "REGULAR",
                "price": 3000.0,
                "stop": None,
                "units": 1,
                "notional_value": None,
                "client_order_id": proposal_id,
            },
            "review": {
                "role": "SWING",
                "current_shares": 1,
                "target_shares": 2,
                "score": 4,
                "confidence": "MEDIUM",
                "reasons": ["synthetic test"],
                "account_id": "must-not-surface",
                "cash": 9999,
            },
        }


    def review_packet(self, proposal_id="22222222-2222-4222-8222-222222222222"):
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        return {
            "kind": "CSU_DECISION_REVIEW",
            "version": 1,
            "proposalId": proposal_id,
            "symbol": "CSU.TO",
            "action": "BUY",
            "quantity": 1,
            "indicativeLimitCAD": 3000.0,
            "expiresAt": expiry,
            "role": "SWING",
            "currentShares": 1,
            "targetShares": 2,
            "score": 4,
            "confidence": "MEDIUM",
            "reasons": ["synthetic review"],
            "simulationOnly": True,
            "brokerSubmitted": False,
        }

    def test_review_packet_can_be_approved_without_execution_envelope(self):
        card = self.state.register_review(self.review_packet())
        self.assertEqual(card["order_type"], "REVIEW_ONLY")
        self.assertTrue(card["simulation_only"])
        result = self.state.approve_review(card["proposal_id"])
        self.assertTrue(result["approved_review"])
        self.assertFalse(result["broker_submission_enabled"])
        self.assertNotIn("dry_run", result)

    def test_review_packet_rejects_non_simulation_mode(self):
        packet = self.review_packet()
        packet["simulationOnly"] = False
        with self.assertRaises(ApprovalPanelError):
            self.state.register_review(packet)

    def test_review_rejection_is_durable(self):
        card = self.state.register_review(self.review_packet())
        rejected = self.state.reject_review(card["proposal_id"])
        self.assertEqual(rejected["state"], "REJECTED")
        with self.assertRaises(Exception):
            self.state.approve_review(card["proposal_id"])

    def test_html_routes_review_cards_to_review_only_endpoints(self):
        page = _html("synthetic-session")
        self.assertIn("/api/approve-review", page)
        self.assertIn("/api/reject-review", page)
        self.assertIn("LOCAL REVIEW ONLY", page)

    def test_html_includes_read_only_scout_research_queue(self):
        page = _html("synthetic-session")
        self.assertIn("/api/scout/research", page)
        self.assertIn("Scout Research Queue", page)
        self.assertIn("RESEARCH ONLY", page)
        self.assertIn("COPY RESEARCH PACKET", page)
        self.assertIn("RUNLU_SCOUT_RESEARCH_PACKET", page)

    def test_scout_research_cards_are_sanitized_and_never_tradeable(self):
        self.scout_report.write_text(json.dumps({
            "researchCards": [{
                "symbol": "AAA:TSX",
                "scout": {
                    "score": 81,
                    "tier": "PRIORITY_RESEARCH",
                    "stage": "RESEARCH_REQUIRED",
                    "reasons": ["near support"],
                    "riskFlags": ["news review"],
                },
                "researchAgenda": {
                    "questions": ["What could make us wrong?"],
                    "evidenceRequirements": {"minimumSources": 3},
                },
                "authority": {
                    "tradeEligible": True,
                    "brokerSubmissionEnabled": True,
                },
                "account_id": "must-not-surface",
                "cash": 9999,
            }]
        }), encoding="utf-8")
        cards = self.state.scout_research_cards()
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["symbol"], "AAA:TSX")
        self.assertFalse(card["trade_eligible"])
        self.assertFalse(card["broker_submission_enabled"])
        self.assertFalse(card["automatic_promotion"])
        self.assertNotIn("account_id", card)
        self.assertNotIn("cash", card)

    def test_scout_research_writeback_records_assistant_work_but_not_user_approval(self):
        registry = Path(self.tmp.name) / "scout-registry.json"
        archive = Path(self.tmp.name) / "scout-research-archive.json"
        state = PanelState(self.ledger, self.scout_report, registry, archive)
        candidate = record_scan({
            "mode": "DISCOVERY_RESEARCH_ONLY",
            "candidates": [{
                "symbol": "AAA:TSX",
                "score": 80,
                "tier": "PRIORITY_RESEARCH",
                "reasons": ["synthetic"],
                "riskFlags": ["synthetic risk"],
                "marketDataAsOf": "2026-10-10",
            }],
        }, registry)["candidates"]["AAA:TSX"]
        packet = build_result_template(candidate)
        packet["assistantResearchComplete"] = True
        packet["research"].update({
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
        })
        result = state.writeback_scout_research(packet)
        self.assertEqual(result["research_status"], "ASSISTANT_COMPLETE_AWAITING_USER")
        self.assertTrue(result["assistant_research_complete"])
        self.assertFalse(result["user_confirmed"])
        self.assertFalse(result["trade_eligible"])
        self.assertFalse(result["broker_submission_enabled"])

    def test_register_card_never_surfaces_private_account_data(self):
        card = self.state.register(self.packet())
        self.assertEqual(card["state"], "PENDING_APPROVAL")
        self.assertEqual(card["action"], "BUY")
        self.assertEqual(card["limit_price_cad"], 3000.0)
        self.assertFalse(card["broker_submission_enabled"])
        self.assertNotIn("account_id", card)
        self.assertNotIn("cash", card)

    def test_approve_records_ledger_and_returns_dry_run_only(self):
        card = self.state.register(self.packet())
        result = self.state.approve(card["proposal_id"])
        self.assertEqual(result["proposal"]["state"], "APPROVED")
        self.assertEqual(result["dry_run"]["mode"], "DRY_RUN_ONLY")
        self.assertFalse(result["dry_run"]["network_sent"])
        self.assertEqual(result["dry_run"]["body"]["account_id"], "[PRIVATE_RUNTIME_ACCOUNT]")

    def test_reject_disables_future_approval(self):
        card = self.state.register(self.packet())
        rejected = self.state.reject(card["proposal_id"])
        self.assertEqual(rejected["state"], "REJECTED")
        with self.assertRaises(Exception):
            self.state.approve(card["proposal_id"])

    def test_duplicate_proposal_id_is_rejected(self):
        packet = self.packet()
        self.state.register(packet)
        with self.assertRaises(Exception):
            self.state.register(packet)

    def test_expired_packet_is_rejected_before_ledger_issue(self):
        packet = self.packet()
        packet["expires_at"] = "2020-01-01T00:00:00Z"
        with self.assertRaises(ApprovalPanelError):
            self.state.register(packet)


if __name__ == "__main__":
    unittest.main()
