"""Local handoff from CSU Bot proposal response to localhost approval panel.

This module forwards only the sanitized simulation-only reviewPacket. It never
forwards brokerage snapshots, balances, account identifiers, credentials, or
executable order payloads.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Dict

SESSION_FILE = Path(".csu-private") / "approval-session-token"
REGISTER_URL = "http://127.0.0.1:8775/api/register-review"


class ReviewHookError(RuntimeError):
    pass


def extract_review_packet(bot_response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(bot_response, dict):
        raise ReviewHookError("Bot response must be an object")
    packet = bot_response.get("reviewPacket")
    if not isinstance(packet, dict):
        raise ReviewHookError("Bot response has no reviewPacket")
    if packet.get("kind") != "CSU_DECISION_REVIEW":
        raise ReviewHookError("Unexpected review packet kind")
    if packet.get("simulationOnly") is not True or packet.get("brokerSubmitted") is not False:
        raise ReviewHookError("Only simulation-only review packets are allowed")
    allowed = {
        "kind", "version", "proposalId", "symbol", "action", "quantity",
        "indicativeLimitCAD", "expiresAt", "role", "currentShares",
        "targetShares", "score", "confidence", "reasons",
        "simulationOnly", "brokerSubmitted",
    }
    extras = set(packet) - allowed
    if extras:
        raise ReviewHookError("Review packet contains unexpected fields")
    return {key: packet[key] for key in allowed if key in packet}


def build_request(packet: Dict[str, Any], token: str, url: str = REGISTER_URL):
    if not (url.startswith("http://127.0.0.1:") or url.startswith("http://localhost:")):
        raise ReviewHookError("Review handoff destination must be loopback-only")
    if not token:
        raise ReviewHookError("Approval session token is required")
    data = json.dumps(packet, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Approval-Session": token,
        },
    )


def publish_review_response(
    bot_response: Dict[str, Any],
    *,
    session_file: Path = SESSION_FILE,
    url: str = REGISTER_URL,
) -> Dict[str, Any]:
    packet = extract_review_packet(bot_response)
    try:
        token = session_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ReviewHookError("Approval panel session is unavailable") from exc
    request = build_request(packet, token, url)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            result = json.loads(response.read())
    except Exception as exc:
        raise ReviewHookError("Unable to publish review to localhost panel") from exc
    if not isinstance(result, dict):
        raise ReviewHookError("Approval panel returned invalid JSON")
    return result
