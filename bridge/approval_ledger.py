"""Local append-only approval + audit ledger for CSU Bot V2.

No broker network calls live here. The ledger stores only proposal metadata,
approval events, and hashes. Raw brokerage account IDs, balances, credentials,
tokens, and full snapshots must never be written here.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_LEDGER = Path(".csu-private") / "approval-ledger.jsonl"


class ApprovalLedgerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovalChallenge:
    proposal_id: str
    approval_token: str
    token_hash: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash_entry(entry_without_hash: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(entry_without_hash)).hexdigest()


def _safe_public_details(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not details:
        return {}
    forbidden = {
        "account_id", "accountid", "cash", "buyingpower", "buying_power",
        "consumer_key", "consumerkey", "client_id", "clientid", "secret",
        "token", "authorization", "cookie", "snapshot",
    }
    out: Dict[str, Any] = {}
    for key, value in details.items():
        normalized = str(key).lower().replace("-", "_")
        if normalized in forbidden or any(x in normalized for x in ("secret", "token", "password", "cookie")):
            continue
        out[str(key)] = value
    return out


def read_ledger(path: Path = DEFAULT_LEDGER) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ApprovalLedgerError(f"Ledger JSON corrupt at line {line_no}") from exc
            rows.append(row)
    return rows


def verify_ledger(path: Path = DEFAULT_LEDGER) -> Dict[str, Any]:
    rows = read_ledger(path)
    previous = "GENESIS"
    seen_hashes = set()
    for index, row in enumerate(rows, 1):
        entry_hash = row.get("entry_hash")
        if not isinstance(entry_hash, str) or not entry_hash:
            raise ApprovalLedgerError(f"Missing entry hash at line {index}")
        if entry_hash in seen_hashes:
            raise ApprovalLedgerError(f"Duplicate ledger hash at line {index}")
        if row.get("prev_hash") != previous:
            raise ApprovalLedgerError(f"Broken ledger chain at line {index}")
        payload = dict(row)
        payload.pop("entry_hash", None)
        expected = _hash_entry(payload)
        if not hmac.compare_digest(expected, entry_hash):
            raise ApprovalLedgerError(f"Ledger tamper detected at line {index}")
        seen_hashes.add(entry_hash)
        previous = entry_hash
    return {"valid": True, "entries": len(rows), "head_hash": previous}


def append_event(
    proposal_id: str,
    event: str,
    details: Optional[Dict[str, Any]] = None,
    *,
    path: Path = DEFAULT_LEDGER,
    at: Optional[str] = None,
) -> Dict[str, Any]:
    if not proposal_id:
        raise ApprovalLedgerError("proposal_id is required")
    if event not in {
        "PROPOSAL_CREATED", "APPROVED", "REJECTED", "EXPIRED",
        "SUBMISSION_STARTED", "BROKER_ACK", "BROKER_STATUS", "HALTED",
    }:
        raise ApprovalLedgerError("Unsupported audit event")

    path.parent.mkdir(parents=True, exist_ok=True)
    state = verify_ledger(path)
    base = {
        "version": 1,
        "proposal_id": proposal_id,
        "event": event,
        "at": at or _utc_now(),
        "details": _safe_public_details(details),
        "prev_hash": state["head_hash"],
    }
    row = dict(base)
    row["entry_hash"] = _hash_entry(base)

    encoded = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, encoded.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)

    verify_ledger(path)
    return row


def issue_approval_challenge(
    proposal_id: str,
    *,
    expires_at: str,
    proposal_digest: str,
    path: Path = DEFAULT_LEDGER,
) -> ApprovalChallenge:
    rows = read_ledger(path)
    if any(r.get("proposal_id") == proposal_id for r in rows):
        raise ApprovalLedgerError("Proposal already exists in audit ledger")
    token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    append_event(
        proposal_id,
        "PROPOSAL_CREATED",
        {
            "expires_at": expires_at,
            "proposal_digest": proposal_digest,
            "approval_token_hash": token_hash,
        },
        path=path,
    )
    return ApprovalChallenge(proposal_id, token, token_hash)


def _proposal_events(proposal_id: str, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in rows if r.get("proposal_id") == proposal_id]


def approve_proposal(
    proposal_id: str,
    approval_token: str,
    *,
    path: Path = DEFAULT_LEDGER,
    at: Optional[str] = None,
) -> Dict[str, Any]:
    verify_ledger(path)
    events = _proposal_events(proposal_id, read_ledger(path))
    if not events or events[0].get("event") != "PROPOSAL_CREATED":
        raise ApprovalLedgerError("Unknown proposal")
    if any(e.get("event") in {"APPROVED", "REJECTED", "EXPIRED", "SUBMISSION_STARTED", "HALTED"} for e in events):
        raise ApprovalLedgerError("Proposal is no longer approval-pending")

    details = events[0].get("details") or {}
    expected_hash = details.get("approval_token_hash")
    if not isinstance(expected_hash, str):
        raise ApprovalLedgerError("Approval challenge is missing")
    actual_hash = hashlib.sha256(approval_token.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(expected_hash, actual_hash):
        raise ApprovalLedgerError("Approval token does not match")

    expires_at = details.get("expires_at")
    now_text = at or _utc_now()
    try:
        now = datetime.fromisoformat(now_text.replace("Z", "+00:00"))
        expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApprovalLedgerError("Invalid approval timestamp") from exc
    if now >= expiry:
        append_event(proposal_id, "EXPIRED", {"reason": "approval_after_expiry"}, path=path, at=now_text)
        raise ApprovalLedgerError("Proposal expired before approval")

    return append_event(proposal_id, "APPROVED", {"human_approved": True}, path=path, at=now_text)


def proposal_status(proposal_id: str, path: Path = DEFAULT_LEDGER) -> Dict[str, Any]:
    verify_ledger(path)
    events = _proposal_events(proposal_id, read_ledger(path))
    if not events:
        return {"proposal_id": proposal_id, "state": "UNKNOWN", "events": 0}
    last = events[-1]["event"]
    state_map = {
        "PROPOSAL_CREATED": "PENDING_APPROVAL",
        "APPROVED": "APPROVED",
        "REJECTED": "REJECTED",
        "EXPIRED": "EXPIRED",
        "SUBMISSION_STARTED": "SUBMISSION_UNKNOWN",
        "BROKER_ACK": "BROKER_ACCEPTED",
        "BROKER_STATUS": "BROKER_STATUS",
        "HALTED": "HALTED",
    }
    state = state_map[last]
    if last == "BROKER_STATUS":
        broker_state = str((events[-1].get("details") or {}).get("status") or "").upper()
        state = {
            "OPEN": "BROKER_ACCEPTED",
            "PARTIAL": "PARTIALLY_FILLED",
            "FILLED": "FILLED",
            "CANCELLED": "CANCELLED",
            "CANCELED": "CANCELLED",
            "REJECTED": "BROKER_REJECTED",
        }.get(broker_state, "BROKER_STATUS")
    return {
        "proposal_id": proposal_id,
        "state": state,
        "events": len(events),
        "ledger_head": verify_ledger(path)["head_hash"],
    }


def mark_submission_started(
    proposal_id: str,
    *,
    path: Path = DEFAULT_LEDGER,
    at: Optional[str] = None,
) -> Dict[str, Any]:
    status = proposal_status(proposal_id, path)
    if status["state"] != "APPROVED":
        raise ApprovalLedgerError("Only an approved proposal may start submission")
    return append_event(proposal_id, "SUBMISSION_STARTED", {"network_result": "unknown"}, path=path, at=at)


def record_broker_ack(
    proposal_id: str,
    broker_order_id: str,
    *,
    path: Path = DEFAULT_LEDGER,
    at: Optional[str] = None,
) -> Dict[str, Any]:
    status = proposal_status(proposal_id, path)
    if status["state"] != "SUBMISSION_UNKNOWN":
        raise ApprovalLedgerError("Broker acknowledgement is not expected")
    if not broker_order_id:
        raise ApprovalLedgerError("broker_order_id is required")
    broker_ref_hash = hashlib.sha256(str(broker_order_id).encode("utf-8")).hexdigest()
    return append_event(
        proposal_id,
        "BROKER_ACK",
        {"broker_order_id_hash": broker_ref_hash},
        path=path,
        at=at,
    )


def record_broker_status(
    proposal_id: str,
    broker_status: str,
    filled_quantity: int,
    *,
    path: Path = DEFAULT_LEDGER,
    at: Optional[str] = None,
) -> Dict[str, Any]:
    current = proposal_status(proposal_id, path)
    if current["state"] not in {"SUBMISSION_UNKNOWN", "BROKER_ACCEPTED", "BROKER_STATUS"}:
        raise ApprovalLedgerError("Broker status is not expected")
    normalized = str(broker_status).upper()
    if normalized not in {"OPEN", "PARTIAL", "FILLED", "CANCELLED", "CANCELED", "REJECTED"}:
        raise ApprovalLedgerError("Unsupported broker status")
    if filled_quantity not in (0, 1):
        raise ApprovalLedgerError("Filled quantity must be zero or one")
    if normalized == "FILLED" and filled_quantity != 1:
        raise ApprovalLedgerError("Filled status requires one filled share")
    return append_event(
        proposal_id,
        "BROKER_STATUS",
        {"status": normalized, "filled_quantity": filled_quantity},
        path=path,
        at=at,
    )


def halt_proposal(
    proposal_id: str,
    reason: str,
    *,
    path: Path = DEFAULT_LEDGER,
    at: Optional[str] = None,
) -> Dict[str, Any]:
    current = proposal_status(proposal_id, path)
    if current["state"] in {"REJECTED", "EXPIRED", "HALTED"}:
        raise ApprovalLedgerError("Proposal is already terminal")
    return append_event(proposal_id, "HALTED", {"reason": reason}, path=path, at=at)
