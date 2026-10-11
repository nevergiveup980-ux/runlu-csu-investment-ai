"""Local command-line interface for human CSU proposal approval.

No network calls. Intended for the private Mac bridge folder only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from approval_ledger import (
    DEFAULT_LEDGER,
    approve_proposal,
    issue_approval_challenge,
    proposal_status,
    verify_ledger,
)


def _ledger_path() -> Path:
    raw = os.environ.get("CSU_PRIVATE_LEDGER")
    return Path(raw).expanduser() if raw else DEFAULT_LEDGER


def _proposal_digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _proposal_id(value) -> str:
    proposal_id = value.get("proposalId") or value.get("proposal_id") or value.get("client_order_id")
    if not proposal_id:
        raise SystemExit("Proposal JSON is missing proposalId/client_order_id")
    return str(proposal_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="CSU Bot local approval ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("issue")
    issue.add_argument("--proposal", required=True, help="Local proposal/order JSON file")
    issue.add_argument("--expires-at", required=True, help="ISO-8601 expiry timestamp")

    approve = sub.add_parser("approve")
    approve.add_argument("--proposal-id", required=True)
    approve.add_argument("--token", required=True)

    status = sub.add_parser("status")
    status.add_argument("--proposal-id", required=True)

    sub.add_parser("verify")
    args = parser.parse_args()
    ledger = _ledger_path()

    if args.command == "issue":
        with open(args.proposal, "r", encoding="utf-8") as handle:
            proposal = json.load(handle)
        challenge = issue_approval_challenge(
            _proposal_id(proposal),
            expires_at=args.expires_at,
            proposal_digest=_proposal_digest(proposal),
            path=ledger,
        )
        print(json.dumps({
            "proposal_id": challenge.proposal_id,
            "approval_token": challenge.approval_token,
            "warning": "This one-time token is shown only to the local operator. Do not commit it.",
        }, indent=2))
        return

    if args.command == "approve":
        row = approve_proposal(args.proposal_id, args.token, path=ledger)
        print(json.dumps({
            "proposal_id": row["proposal_id"],
            "state": "APPROVED",
            "at": row["at"],
            "ledger_head": row["entry_hash"],
        }, indent=2))
        return

    if args.command == "status":
        print(json.dumps(proposal_status(args.proposal_id, ledger), indent=2))
        return

    if args.command == "verify":
        print(json.dumps(verify_ledger(ledger), indent=2))


if __name__ == "__main__":
    main()
