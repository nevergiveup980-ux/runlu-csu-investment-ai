import tempfile
import unittest
from pathlib import Path

from execution_bridge import (
    ExecutionBridgeError,
    build_approved_dry_run,
    build_dry_run,
    submit_live,
)
from approval_ledger import approve_proposal, issue_approval_challenge


class ExecutionBridgeTests(unittest.TestCase):
    def order(self):
        return {
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
            "client_order_id": "11111111-1111-4111-8111-111111111111",
        }

    def test_builds_redacted_dry_run_without_network(self):
        result = build_dry_run(self.order()).as_dict()
        self.assertEqual(result["mode"], "DRY_RUN_ONLY")
        self.assertFalse(result["network_sent"])
        self.assertEqual(result["method"], "POST")
        self.assertEqual(result["body"]["account_id"], "[PRIVATE_RUNTIME_ACCOUNT]")
        self.assertEqual(result["body"]["symbol"], "CSU.TO")
        self.assertEqual(result["body"]["units"], 1)

    def test_rejects_more_than_one_share(self):
        order = self.order()
        order["units"] = 2
        with self.assertRaises(ExecutionBridgeError):
            build_dry_run(order)

    def test_rejects_market_order(self):
        order = self.order()
        order["order_type"] = "Market"
        with self.assertRaises(ExecutionBridgeError):
            build_dry_run(order)

    def test_rejects_wrong_symbol(self):
        order = self.order()
        order["symbol"] = "AAPL"
        with self.assertRaises(ExecutionBridgeError):
            build_dry_run(order)

    def test_approved_dry_run_requires_matching_local_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "approval-ledger.jsonl"
            with self.assertRaises(ExecutionBridgeError):
                build_approved_dry_run(self.order(), ledger_path=ledger)

            challenge = issue_approval_challenge(
                self.order()["client_order_id"],
                expires_at="2099-01-01T00:00:00Z",
                proposal_digest="synthetic-digest",
                path=ledger,
            )
            approve_proposal(
                self.order()["client_order_id"],
                challenge.approval_token,
                path=ledger,
                at="2098-12-31T23:59:00Z",
            )
            result = build_approved_dry_run(self.order(), ledger_path=ledger).as_dict()
            self.assertEqual(result["mode"], "DRY_RUN_ONLY")
            self.assertFalse(result["network_sent"])

    def test_live_submission_is_impossible(self):
        with self.assertRaises(RuntimeError):
            submit_live(self.order())


if __name__ == "__main__":
    unittest.main()
