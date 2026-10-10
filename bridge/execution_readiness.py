"""Local-only, read-only readiness assessment for a future SnapTrade execution bridge.

This file DOES NOT request trading access or send orders. It consumes the
existing local bridge.py snapshot and checks whether trading is already
authorized. Never commit account snapshots or credentials.
"""

def assess_execution_readiness(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("read_only") is not True:
        return {"ready": False, "state": "INVALID", "blockers": ["Missing read-only snapshot safety flag"]}
    connections = snapshot.get("connections") or []
    accounts = snapshot.get("accounts") or []
    if not accounts:
        return {"ready": False, "state": "NO_ACCOUNT", "blockers": ["No linked account"]}
    trade_connections = [c for c in connections if c.get("type") == "trade" and not c.get("disabled")]
    read_connections = [c for c in connections if c.get("type") == "read" and not c.get("disabled")]
    blockers = []
    if not trade_connections:
        blockers.append("No active trade-enabled SnapTrade authorization was reported")
    if not any((a.get("sections") or {}).get("orders", {}).get("status") == "ok" for a in accounts):
        blockers.append("No accessible account orders section")
    # This bridge intentionally blocks non-read authorizations, so a trade
    # connection requires a NEW, separately secured execution integration.
    blockers.append("Execution bridge not installed; explicit approval and broker order reconciliation required")
    return {
        "ready": False,
        "state": "TRADE_AUTH_VISIBLE" if trade_connections else ("READ_ONLY" if read_connections else "UNKNOWN"),
        "activeReadConnections": len(read_connections),
        "activeTradeConnections": len(trade_connections),
        "blockers": blockers,
        "liveOrderSubmissionEnabled": False,
    }
