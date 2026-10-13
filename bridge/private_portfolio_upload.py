"""Upload a minimized read-only portfolio snapshot to RUNLU Private Portfolio.

This is the only component allowed to send portfolio display data off the Mac.
It never sends account IDs, transactions, credentials, tokens, or order detail.

The upload token is dedicated to this endpoint and is NOT CSU_SNAPSHOT_TOKEN.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

SNAPSHOT_CACHE = Path(".csu-private") / "latest-snapshot.json"
PRIVATE_ENV_FILE = Path(".csu-private") / "private-portfolio.env"


def _load_private_env(path: Path = PRIVATE_ENV_FILE) -> None:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, raw = value.split("=", 1)
        key = key.strip()
        if key in {
            "RUNLU_PRIVATE_PORTFOLIO_URL",
            "RUNLU_PRIVATE_PORTFOLIO_ALLOWED_HOST",
            "PRIVATE_SNAPSHOT_UPLOAD_TOKEN",
        } and key not in os.environ:
            os.environ[key] = raw.strip()


_load_private_env()
PRIVATE_URL = os.getenv("RUNLU_PRIVATE_PORTFOLIO_URL", "").strip()
ALLOWED_HOST = os.getenv("RUNLU_PRIVATE_PORTFOLIO_ALLOWED_HOST", "").strip()


class PrivatePortfolioUploadError(RuntimeError):
    pass


def build_mobile_snapshot(raw: Dict[str, Any]) -> Dict[str, Any]:
    positions = []
    for item in (raw.get("positions") or [])[:100]:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or item.get("ticker") or "").strip().upper()
        if not symbol:
            continue
        positions.append({
            "symbol": symbol,
            "quantity": item.get("quantity") if item.get("quantity") is not None else item.get("units", 0),
            "averageCost": item.get("averageCost") if item.get("averageCost") is not None else item.get("average_cost"),
            "marketValue": item.get("marketValue") if item.get("marketValue") is not None else item.get("market_value"),
        })
    return {
        "currency": raw.get("currency") or "CAD",
        "cash": raw.get("cash"),
        "buyingPower": raw.get("buyingPower") if raw.get("buyingPower") is not None else raw.get("buying_power"),
        "positions": positions,
        "openOrders": [{} for _ in (raw.get("openOrders") or raw.get("orders") or [])[:1000]],
        "fetchedAt": raw.get("fetchedAt") or raw.get("fetched_at"),
    }


def _validate_destination(url: str, allowed_host: str) -> str:
    parsed = urlparse(str(url or ""))
    if parsed.scheme != "https":
        raise PrivatePortfolioUploadError("Private portfolio upload requires HTTPS")
    if parsed.username or parsed.password or parsed.fragment:
        raise PrivatePortfolioUploadError("Private portfolio URL must not contain userinfo or fragments")
    if not allowed_host or parsed.hostname != allowed_host:
        raise PrivatePortfolioUploadError("Private portfolio host is not explicitly allowlisted")
    if parsed.path != "/api/private/snapshot":
        raise PrivatePortfolioUploadError("Private portfolio upload path must be /api/private/snapshot")
    return url


def _upload_headers() -> Dict[str, str]:
    token = os.getenv("PRIVATE_SNAPSHOT_UPLOAD_TOKEN", "").strip()
    if not token:
        raise PrivatePortfolioUploadError("PRIVATE_SNAPSHOT_UPLOAD_TOKEN is required")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def upload_snapshot(
    raw: Dict[str, Any],
    *,
    url: str = PRIVATE_URL,
    allowed_host: str = ALLOWED_HOST,
    timeout: int = 15,
) -> Dict[str, Any]:
    safe_url = _validate_destination(url, allowed_host)
    payload = json.dumps(build_mobile_snapshot(raw), separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        safe_url,
        data=payload,
        headers=_upload_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PrivatePortfolioUploadError(
            f"Private portfolio rejected snapshot: HTTP {exc.code}: {detail[:300]}"
        ) from exc
    except Exception as exc:
        raise PrivatePortfolioUploadError("Unable to upload private portfolio snapshot") from exc
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise PrivatePortfolioUploadError("Private portfolio returned an unexpected response")
    return result


def upload_cached_snapshot(path: Path = SNAPSHOT_CACHE) -> Dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PrivatePortfolioUploadError("Latest sanitized local snapshot is unavailable") from exc
    if not isinstance(raw, dict):
        raise PrivatePortfolioUploadError("Latest sanitized local snapshot is invalid")
    return upload_snapshot(raw)


if __name__ == "__main__":
    print(json.dumps(upload_cached_snapshot(), indent=2))
