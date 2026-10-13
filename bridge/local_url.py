"""Strict URL guard for local services carrying private bearer tokens."""

from __future__ import annotations

from urllib.parse import urlparse


class LocalUrlError(RuntimeError):
    pass


def require_loopback_http(url: str) -> str:
    parsed = urlparse(str(url or ""))
    if parsed.scheme != "http":
        raise LocalUrlError("Private local service URL must use http")
    if parsed.username or parsed.password:
        raise LocalUrlError("Private local service URL must not contain userinfo")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise LocalUrlError("Private bearer token may only be sent to loopback")
    if not parsed.port:
        raise LocalUrlError("Private local service URL must include an explicit port")
    return url
