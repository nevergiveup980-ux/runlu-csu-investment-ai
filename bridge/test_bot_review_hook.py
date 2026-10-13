import json
import unittest

from bot_review_hook import ReviewHookError, build_request, extract_review_packet


class BotReviewHookTests(unittest.TestCase):
    def response(self):
        return {
            "proposal": {"private": "not-forwarded"},
            "reviewPacket": {
                "kind": "CSU_DECISION_REVIEW",
                "version": 1,
                "proposalId": "22222222-2222-4222-8222-222222222222",
                "symbol": "CSU.TO",
                "action": "BUY",
                "quantity": 1,
                "indicativeLimitCAD": 3000.0,
                "expiresAt": "2099-01-01T00:00:00Z",
                "role": "SWING",
                "currentShares": 1,
                "targetShares": 2,
                "score": 4,
                "confidence": "MEDIUM",
                "reasons": ["synthetic"],
                "simulationOnly": True,
                "brokerSubmitted": False,
            },
            "snapshot": {"accountId": "never-forward-this"},
        }

    def test_extracts_only_sanitized_review_packet(self):
        packet = extract_review_packet(self.response())
        raw = json.dumps(packet)
        self.assertNotIn("accountId", raw)
        self.assertNotIn("private", raw)
        self.assertTrue(packet["simulationOnly"])
        self.assertFalse(packet["brokerSubmitted"])

    def test_rejects_extra_fields(self):
        value = self.response()
        value["reviewPacket"]["accountId"] = "private"
        with self.assertRaises(ReviewHookError):
            extract_review_packet(value)

    def test_rejects_non_loopback_destination(self):
        packet = extract_review_packet(self.response())
        with self.assertRaises(ReviewHookError):
            build_request(packet, "token", "https://example.com/register")


if __name__ == "__main__":
    unittest.main()
