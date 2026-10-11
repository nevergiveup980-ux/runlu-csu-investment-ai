import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from approval_panel import ApprovalPanelError, PanelState


class ApprovalPanelStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "approval-ledger.jsonl"
        self.state = PanelState(self.ledger)

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
