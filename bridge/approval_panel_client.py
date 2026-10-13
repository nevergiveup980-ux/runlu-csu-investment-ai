"""Local client for feeding a preflighted CSU packet to approval_panel.py.

The destination is loopback-only. No broker credentials are accepted or sent.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict

DEFAULT_URL = "http://127.0.0.1:8775/api/register"
SESSION_FILE = Path(".csu-private") / "approval-session-token"


class ApprovalPanelClientError(RuntimeError):
    pass


def build_request(packet: Dict[str, Any], *, url: str = DEFAULT_URL, token: str):
    if not url.startswith("http://127.0.0.1:") and not url.startswith("http://localhost:"):
        raise ApprovalPanelClientError("Approval panel destination must be loopback-only")
    if not token:
        raise ApprovalPanelClientError("Approval session token is required")
    body = json.dumps(packet, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Approval-Session": token,
        },
    )


def register_packet(
    packet: Dict[str, Any],
    *,
    url: str = DEFAULT_URL,
    session_file: Path = SESSION_FILE,
) -> Dict[str, Any]:
    try:
        token = session_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ApprovalPanelClientError(
            "Approval panel session token is unavailable; start approval_panel.py first"
        ) from exc
    request = build_request(packet, url=url, token=token)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.loads(response.read())
    except Exception as exc:
        raise ApprovalPanelClientError("Unable to reach the local approval panel") from exc
    if not isinstance(data, dict):
        raise ApprovalPanelClientError("Approval panel returned an invalid response")
    return data


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Register a CSU packet with the local approval panel")
    parser.add_argument("packet", help="Path to local JSON approval packet")
    parser.add_argument("--url", default=os.environ.get("CSU_APPROVAL_REGISTER_URL", DEFAULT_URL))
    args = parser.parse_args()

    with open(args.packet, "r", encoding="utf-8") as handle:
        packet = json.load(handle)
    result = register_packet(packet, url=args.url)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
