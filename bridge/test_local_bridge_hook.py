import unittest
import local_bridge_hook


class LocalBridgeHookTests(unittest.TestCase):
    def test_publish_to_csu_bot_caches_snapshot_before_forwarding(self):
        calls = []
        original_cache = local_bridge_hook.cache_sanitized_snapshot
        original_forward = local_bridge_hook.forward_snapshot
        try:
            def fake_cache(value):
                calls.append(("cache", value))
                return value
            def fake_forward(value):
                calls.append(("forward", value))
                return {"mode": "READ_ONLY_SIMULATION"}
            local_bridge_hook.cache_sanitized_snapshot = fake_cache
            local_bridge_hook.forward_snapshot = fake_forward
            payload = {"fetchedAt": "2026-10-13T12:00:00Z", "positions": []}
            result = local_bridge_hook.publish_to_csu_bot(payload)
            self.assertEqual(result["mode"], "READ_ONLY_SIMULATION")
            self.assertEqual([x[0] for x in calls], ["cache", "forward"])
        finally:
            local_bridge_hook.cache_sanitized_snapshot = original_cache
            local_bridge_hook.forward_snapshot = original_forward

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
