"""Local Twelve Data quote provider for RUNLU Scout Watch.

Calls only the protected loopback Worker endpoint. The private bearer token is
never sent to a remote URL. Each cycle rotates through at most five research
symbols to keep API usage bounded.

No brokerage data is read or written.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from local_url import LocalUrlError, require_loopback_http
from snaptrade_handoff import _auth_headers

WATCH_QUOTES_URL = os.getenv(
    "RUNLU_SCOUT_WATCH_QUOTES_URL",
    "http://127.0.0.1:8787/api/scout/watch-quotes",
)
PROVIDER_STATE = Path(".csu-private") / "scout-watch-provider-state.json"
DEFAULT_BATCH_SIZE = 5


class ScoutWatchProviderError(RuntimeError):
    pass


def _read_state(path: Path = PROVIDER_STATE) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(value: Dict[str, Any], path: Path = PROVIDER_STATE) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="scout-watch-provider-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def choose_watch_batch(
    symbols: List[str],
    *,
    cursor: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[List[str], int]:
    if batch_size < 1 or batch_size > 5:
        raise ScoutWatchProviderError("Scout Watch provider batch size must be 1-5")
    safe = []
    for raw in symbols:
        symbol = str(raw or "").upper()
        if not symbol.endswith(":TSX") or symbol == "CSU:TSX":
            continue
        if symbol not in safe:
            safe.append(symbol)
    if not safe:
        return [], 0
    start = max(0, int(cursor)) % len(safe)
    size = min(batch_size, len(safe))
    batch = [safe[(start + i) % len(safe)] for i in range(size)]
    return batch, (start + size) % len(safe)


def fetch_quote_observations(
    symbols: List[str],
    *,
    interval: str = "5min",
    url: str = WATCH_QUOTES_URL,
    state_path: Path = PROVIDER_STATE,
) -> List[Dict[str, Any]]:
    if interval not in {"1min", "5min"}:
        raise ScoutWatchProviderError("Scout Watch interval must be 1min or 5min")
    try:
        safe_url = require_loopback_http(url)
    except LocalUrlError as exc:
        raise ScoutWatchProviderError(str(exc)) from exc

    state = _read_state(state_path)
    batch, next_cursor = choose_watch_batch(
        symbols,
        cursor=int(state.get("cursor") or 0),
        batch_size=DEFAULT_BATCH_SIZE,
    )
    if not batch:
        return []

    payload = json.dumps(
        {"symbols": batch, "interval": interval},
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        safe_url,
        data=payload,
        headers=_auth_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ScoutWatchProviderError(
            f"Scout Watch quote endpoint rejected request: HTTP {exc.code}: {detail[:300]}"
        ) from exc
    except Exception as exc:
        raise ScoutWatchProviderError("Unable to reach Scout Watch quote endpoint") from exc

    if not isinstance(result, dict) or result.get("mode") != "WATCH_OBSERVATION_RESEARCH_ONLY":
        raise ScoutWatchProviderError("Scout Watch quote endpoint returned unexpected mode")
    observations = result.get("observations")
    if not isinstance(observations, list):
        raise ScoutWatchProviderError("Scout Watch quote endpoint returned invalid observations")

    safe_observations: List[Dict[str, Any]] = []
    for row in observations:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper()
        price = row.get("price")
        if symbol not in batch:
            continue
        try:
            numeric_price = float(price)
        except (TypeError, ValueError):
            continue
        if numeric_price <= 0:
            continue
        safe_observations.append({
            "symbol": symbol,
            "price": numeric_price,
            "events": [],
            "marketDataAsOf": row.get("marketDataAsOf"),
        })

    _write_state({
        "version": 1,
        "cursor": next_cursor,
        "lastBatch": batch,
        "interval": interval,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }, state_path)
    return safe_observations


def main() -> None:
    from scout_watch import run_forever

    interval = os.getenv("RUNLU_SCOUT_WATCH_INTERVAL", "5min")
    run_forever(lambda symbols: fetch_quote_observations(symbols, interval=interval))


if __name__ == "__main__":
    main()
