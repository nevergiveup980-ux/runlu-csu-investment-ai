#!/usr/bin/env python3
"""
Drop-in helper for the local CSU SnapTrade bridge (127.0.0.1:8765).

Import publish_to_csu_bot() in the existing server after it has assembled its
sanitized read-only dashboard payload. This module has no SnapTrade credentials
and no order write/cancel methods.
"""
from snaptrade_handoff import forward_snapshot
from bot_review_hook import publish_review_response


def publish_to_csu_bot(dashboard_payload):
    """Return CSU Bot V2's account-aware paper decision for a dashboard payload."""
    return forward_snapshot(dashboard_payload)


def publish_bot_review_to_local_panel(bot_response):
    """Forward only CSU Bot's sanitized simulation reviewPacket to localhost:8775."""
    return publish_review_response(bot_response)
