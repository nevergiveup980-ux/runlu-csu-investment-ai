import unittest
from unittest.mock import patch

import review_candidate_handoff


class ReviewCandidateHandoffTests(unittest.TestCase):
    def snapshot(self):
        return {
            "provider": "SnapTrade / Webull Canada",
            "currency": "CAD",
            "cash": 10000,
            "buyingPower": 7000,
            "positions": [{"ticker": "CSU.TO", "units": 1}],
            "orders": [],
            "history": [],
            "fetchedAt": "2099-01-01T00:00:00Z",
        }

    def test_no_proposal_does_not_publish(self):
        fake = {"decision": {"action": "HOLD"}, "reviewPacket": None}
        with patch.object(review_candidate_handoff, "request_review_candidate", return_value=fake),              patch.object(review_candidate_handoff, "publish_review_response") as publish:
            result = review_candidate_handoff.request_and_publish_review(
                self.snapshot(),
                indicative_limit_cad=3000,
                expires_at="2099-01-01T00:05:00Z",
            )
        self.assertFalse(result["published"])
        publish.assert_not_called()

    def test_review_packet_is_forwarded_to_local_panel(self):
        fake = {
            "decision": {"action": "BUY"},
            "reviewPacket": {
                "proposalId": "22222222-2222-4222-8222-222222222222",
                "kind": "CSU_DECISION_REVIEW",
            },
        }
        with patch.object(review_candidate_handoff, "request_review_candidate", return_value=fake),              patch.object(review_candidate_handoff, "publish_review_response", return_value={"proposal": {"state": "PENDING_APPROVAL"}}) as publish:
            result = review_candidate_handoff.request_and_publish_review(
                self.snapshot(),
                indicative_limit_cad=3000,
                expires_at="2099-01-01T00:05:00Z",
            )
        self.assertTrue(result["published"])
        self.assertFalse(result["broker_submission_enabled"])
        publish.assert_called_once_with(fake)


if __name__ == "__main__":
    unittest.main()
