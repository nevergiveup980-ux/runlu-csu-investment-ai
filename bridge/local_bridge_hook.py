#!/usr/bin/env python3
"""
Drop-in helper for the local CSU SnapTrade bridge (127.0.0.1:8765).

Import publish_to_csu_bot() in the existing server after it has assembled its
sanitized read-only dashboard payload. This module has no SnapTrade credentials
and no order write/cancel methods.
"""
from snaptrade_handoff import cache_sanitized_snapshot, forward_snapshot
from bot_review_hook import publish_review_response
from review_candidate_handoff import request_and_publish_review
from private_portfolio_upload import upload_snapshot as upload_private_portfolio_snapshot


def publish_to_csu_bot(dashboard_payload):
    """Cache the sanitized read-only snapshot, then ask CSU Bot V2 for its paper decision."""
    cache_sanitized_snapshot(dashboard_payload)
    return forward_snapshot(dashboard_payload)


def publish_bot_review_to_local_panel(bot_response):
    """Forward only CSU Bot's sanitized simulation reviewPacket to localhost:8775."""
    return publish_review_response(bot_response)


def publish_review_candidate_to_local_panel(dashboard_payload, indicative_limit_cad, expires_at):
    """Cache the latest sanitized snapshot, ask CSU Bot, then push only its safe review packet locally."""
    cache_sanitized_snapshot(dashboard_payload)
    return request_and_publish_review(
        dashboard_payload,
        indicative_limit_cad=indicative_limit_cad,
        expires_at=expires_at,
    )


def publish_private_portfolio_to_phone(dashboard_payload):
    """Upload only the minimized read-only portfolio view to the private phone API."""
    return upload_private_portfolio_snapshot(dashboard_payload)
