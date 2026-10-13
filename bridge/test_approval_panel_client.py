import unittest

from approval_panel_client import ApprovalPanelClientError, build_request


class ApprovalPanelClientTests(unittest.TestCase):
    def test_builds_loopback_registration_request(self):
        request = build_request({"order": {}}, token="synthetic-token")
        self.assertEqual(request.full_url, "http://127.0.0.1:8775/api/register")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers.get("X-approval-session"), "synthetic-token")

    def test_rejects_non_loopback_destination(self):
        with self.assertRaises(ApprovalPanelClientError):
            build_request(
                {"order": {}},
                url="https://example.com/api/register",
                token="synthetic-token",
            )


if __name__ == "__main__":
    unittest.main()
