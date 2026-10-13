import unittest
import local_bridge_hook


class LocalBridgeHookTests(unittest.TestCase):
    def test_review_hook_delegates_sanitized_bot_response(self):
        seen = {}
        original = local_bridge_hook.publish_review_response
        try:
            def fake(value):
                seen["value"] = value
                return {"ok": True}
            local_bridge_hook.publish_review_response = fake
            payload = {"reviewPacket": {"kind": "CSU_DECISION_REVIEW"}}
            result = local_bridge_hook.publish_bot_review_to_local_panel(payload)
            self.assertEqual(result, {"ok": True})
            self.assertIs(seen["value"], payload)
        finally:
            local_bridge_hook.publish_review_response = original


if __name__ == "__main__":
    unittest.main()
