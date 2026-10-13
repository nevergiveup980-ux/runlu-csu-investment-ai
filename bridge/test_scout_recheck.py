import unittest
from datetime import datetime, timedelta, timezone

from scout_recheck import ScoutRecheckError, build_recheck_packet, evaluate_recheck


class ScoutRecheckTests(unittest.TestCase):
    def candidate(self, stage="WATCH", score=80):
        return {
            "symbol": "AAA:TSX",
            "stage": stage,
            "latestScore": score,
            "research": {
                "completedAt": datetime.now(timezone.utc).isoformat(),
                "researchDigest": "a" * 64,
                "finalDecision": "WATCH",
            },
            "tradeEligible": False,
        }

    def test_small_change_does_not_reopen_research(self):
        result = evaluate_recheck(
            self.candidate(score=82),
            previous_score=80,
            previous_price=100,
            current_price=105,
        )
        self.assertFalse(result["recheckRequired"])
        self.assertFalse(result["tradeEligible"])

    def test_material_score_move_triggers_recheck(self):
        result = evaluate_recheck(self.candidate(score=96), previous_score=80)
        self.assertTrue(result["recheckRequired"])
        self.assertIn("SCOUT_SCORE_MOVE:80->96", result["reasons"])

    def test_material_price_move_triggers_recheck(self):
        result = evaluate_recheck(
            self.candidate(),
            previous_price=100,
            current_price=87,
        )
        self.assertTrue(result["recheckRequired"])
        self.assertTrue(any(x.startswith("PRICE_MOVE_PCT:") for x in result["reasons"]))

    def test_material_event_triggers_recheck(self):
        result = evaluate_recheck(
            self.candidate(),
            events=[
                {
                    "id": "pr-1",
                    "type": "EARNINGS",
                    "title": "Quarterly results",
                    "datetime": "2026-10-12T12:00:00",
                    "sourceType": "OFFICIAL_PRESS_RELEASE",
                },
                {"type": "MATERIAL_NEWS", "title": "Other material update"},
            ],
        )
        self.assertTrue(result["recheckRequired"])
        self.assertIn("EVENT:EARNINGS", result["reasons"])
        self.assertIn("EVENT:MATERIAL_NEWS", result["reasons"])
        self.assertEqual(result["eventDetails"][0]["id"], "pr-1")
        self.assertEqual(result["eventDetails"][0]["title"], "Quarterly results")
        self.assertEqual(result["eventDetails"][0]["sourceType"], "OFFICIAL_PRESS_RELEASE")

    def test_stale_research_triggers_recheck(self):
        candidate = self.candidate()
        candidate["research"]["completedAt"] = (
            datetime.now(timezone.utc) - timedelta(days=121)
        ).isoformat()
        result = evaluate_recheck(candidate)
        self.assertTrue(result["recheckRequired"])
        self.assertTrue(any(x.startswith("RESEARCH_AGE_DAYS:") for x in result["reasons"]))

    def test_non_finalized_candidate_is_not_auto_rechecked(self):
        result = evaluate_recheck(
            self.candidate(stage="RESEARCH_REQUIRED", score=99),
            previous_score=50,
            events=[{"type": "EARNINGS"}],
        )
        self.assertFalse(result["recheckRequired"])

    def test_recheck_packet_is_research_only(self):
        candidate = self.candidate(score=96)
        evaluation = evaluate_recheck(
            candidate,
            previous_score=80,
            events=[{"id": "pr-2", "type": "GUIDANCE", "title": "Guidance update"}],
        )
        packet = build_recheck_packet(candidate, evaluation)
        self.assertEqual(packet["kind"], "RUNLU_SCOUT_RECHECK")
        self.assertEqual(packet["requiredAction"], "JOINT_RESEARCH_RECHECK")
        self.assertEqual(packet["eventDetails"][0]["title"], "Guidance update")
        self.assertFalse(packet["tradeEligible"])
        self.assertFalse(packet["brokerSubmissionEnabled"])

    def test_packet_rejects_no_material_change(self):
        with self.assertRaises(ScoutRecheckError):
            build_recheck_packet(self.candidate(), {"recheckRequired": False})


if __name__ == "__main__":
    unittest.main()
