import json
import tempfile
import unittest
from pathlib import Path

from approval_ledger import (
    ApprovalLedgerError,
    approve_proposal,
    issue_approval_challenge,
    proposal_status,
    read_ledger,
    verify_ledger,
)


class ApprovalLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "approval-ledger.jsonl"
        self.proposal_id = "11111111-1111-4111-8111-111111111111"

    def tearDown(self):
        self.tmp.cleanup()

    def issue(self):
        return issue_approval_challenge(
            self.proposal_id,
            expires_at="2099-01-01T00:00:00Z",
            proposal_digest="synthetic-digest",
            path=self.path,
        )

    def test_valid_token_approves_and_token_is_not_stored_raw(self):
        challenge = self.issue()
        approve_proposal(
            self.proposal_id,
            challenge.approval_token,
            path=self.path,
            at="2098-12-31T23:59:00Z",
        )
        status = proposal_status(self.proposal_id, self.path)
        self.assertEqual(status["state"], "APPROVED")
        raw = self.path.read_text(encoding="utf-8")
        self.assertNotIn(challenge.approval_token, raw)
        self.assertTrue(verify_ledger(self.path)["valid"])

    def test_wrong_token_is_rejected(self):
        self.issue()
        with self.assertRaises(ApprovalLedgerError):
            approve_proposal(
                self.proposal_id,
                "wrong-token",
                path=self.path,
                at="2098-12-31T23:59:00Z",
            )
        self.assertEqual(proposal_status(self.proposal_id, self.path)["state"], "PENDING_APPROVAL")

    def test_duplicate_proposal_id_is_rejected(self):
        self.issue()
        with self.assertRaises(ApprovalLedgerError):
            self.issue()

    def test_expired_approval_fails_closed(self):
        challenge = issue_approval_challenge(
            self.proposal_id,
            expires_at="2020-01-01T00:00:00Z",
            proposal_digest="synthetic-digest",
            path=self.path,
        )
        with self.assertRaises(ApprovalLedgerError):
            approve_proposal(
                self.proposal_id,
                challenge.approval_token,
                path=self.path,
                at="2020-01-02T00:00:00Z",
            )
        self.assertEqual(proposal_status(self.proposal_id, self.path)["state"], "EXPIRED")

    def test_tampering_breaks_hash_chain(self):
        self.issue()
        rows = read_ledger(self.path)
        rows[0]["details"]["proposal_digest"] = "tampered"
        self.path.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
        with self.assertRaises(ApprovalLedgerError):
            verify_ledger(self.path)

    def test_private_fields_are_not_persisted(self):
        from approval_ledger import append_event

        append_event(
            self.proposal_id,
            "PROPOSAL_CREATED",
            {
                "account_id": "PRIVATE",
                "cash": 9999,
                "access_token": "SECRET",
                "proposal_digest": "safe",
            },
            path=self.path,
        )
        row = read_ledger(self.path)[0]
        details = row["details"]
        self.assertNotIn("account_id", details)
        self.assertNotIn("cash", details)
        self.assertNotIn("access_token", details)
        self.assertEqual(details["proposal_digest"], "safe")


if __name__ == "__main__":
    unittest.main()
