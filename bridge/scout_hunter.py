"""RUNLU Scout Hunter V1: rotate through a larger TSX research universe safely.

The hunter discovers metadata from the protected Scout universe endpoint, caches
that catalog locally, scans only a small batch per cycle, and writes candidates
to the private research registry.

It has no brokerage account access and no trading actions.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from local_url import LocalUrlError, require_loopback_http
from scout_registry import DEFAULT_REGISTRY, ranked_candidates, record_scan
from snaptrade_handoff import _auth_headers

UNIVERSE_URL = os.getenv(
    "RUNLU_SCOUT_UNIVERSE_URL",
    "http://127.0.0.1:8787/api/scout/universe",
)
SCAN_URL = os.getenv(
    "RUNLU_SCOUT_SCAN_URL",
    "http://127.0.0.1:8787/api/scout/scan",
)
UNIVERSE_CACHE = Path(".csu-private") / "scout-universe.json"
HUNTER_STATE = Path(".csu-private") / "scout-hunter-state.json"
DEFAULT_BATCH_SIZE = 8
DEFAULT_CACHE_HOURS = 12
PRIMARY_SYMBOL = "CSU:TSX"


class ScoutHunterError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScoutHunterError("Invalid hunter timestamp") from exc
    if parsed.tzinfo is None:
        raise ScoutHunterError("Hunter timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _atomic_json(path: Path, value: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="scout-hunter-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _request_json(url: str, *, payload: Dict[str, Any] | None = None, timeout: int = 30) -> Dict[str, Any]:
    try:
        safe_url = require_loopback_http(url)
    except LocalUrlError as exc:
        raise ScoutHunterError(str(exc)) from exc
    if payload is None:
        request = urllib.request.Request(safe_url, headers=_auth_headers(), method="GET")
    else:
        request = urllib.request.Request(
            safe_url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=_auth_headers(),
            method="POST",
        )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ScoutHunterError(f"Scout service rejected request: HTTP {exc.code}: {detail[:300]}") from exc
    except Exception as exc:
        raise ScoutHunterError("Unable to reach Scout service") from exc
    if not isinstance(result, dict):
        raise ScoutHunterError("Scout service returned invalid JSON")
    return result


def fetch_universe(*, url: str = UNIVERSE_URL) -> Dict[str, Any]:
    result = _request_json(url)
    if result.get("mode") != "RESEARCH_UNIVERSE_ONLY":
        raise ScoutHunterError("Unexpected Scout universe mode")
    universe = result.get("universe")
    if not isinstance(universe, list):
        raise ScoutHunterError("Scout universe is missing")
    safe_rows = []
    for row in universe:
        if not isinstance(row, dict):
            continue
        provider_symbol = str(row.get("providerSymbol") or "").upper()
        if not provider_symbol.endswith(":TSX"):
            continue
        safe_rows.append({
            "symbol": str(row.get("symbol") or "").upper(),
            "providerSymbol": provider_symbol,
            "name": str(row.get("name") or ""),
            "exchange": "TSX",
            "country": str(row.get("country") or "Canada"),
            "type": str(row.get("type") or "Common Stock"),
            "researchOnly": True,
            "tradeEligible": False,
        })
    return {
        "version": 1,
        "fetchedAt": _utc_now().isoformat().replace("+00:00", "Z"),
        "universe": safe_rows,
        "researchOnly": True,
        "tradeEligible": False,
    }


def load_or_refresh_universe(
    *,
    cache_path: Path = UNIVERSE_CACHE,
    max_age_hours: int = DEFAULT_CACHE_HOURS,
    now: datetime | None = None,
) -> Dict[str, Any]:
    current = (now or _utc_now()).astimezone(timezone.utc)
    try:
        cached = json.loads(Path(cache_path).read_text(encoding="utf-8"))
        fetched = _parse_time(cached.get("fetchedAt") or "")
        age = current - fetched
        if age < timedelta(minutes=-5):
            raise ScoutHunterError("Cached Scout universe timestamp is unexpectedly in the future")
        if age <= timedelta(hours=max_age_hours) and isinstance(cached.get("universe"), list):
            return cached
    except (OSError, json.JSONDecodeError, ScoutHunterError):
        pass

    fresh = fetch_universe()
    _atomic_json(cache_path, fresh)
    return fresh


def _read_state(path: Path = HUNTER_STATE) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def choose_next_batch(
    universe_rows: List[Dict[str, Any]],
    *,
    cursor: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Tuple[List[str], int, bool]:
    if batch_size < 1 or batch_size > 8:
        raise ScoutHunterError("Scout Hunter batch size must be 1-8")
    symbols = [
        str(row.get("providerSymbol") or "").upper()
        for row in universe_rows
        if str(row.get("providerSymbol") or "").upper().endswith(":TSX")
        and str(row.get("providerSymbol") or "").upper() != PRIMARY_SYMBOL
    ]
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        raise ScoutHunterError("Scout Hunter has no eligible research symbols")

    start = max(0, int(cursor)) % len(symbols)
    size = min(batch_size, len(symbols))
    batch = [symbols[(start + i) % len(symbols)] for i in range(size)]
    raw_next = start + size
    return batch, raw_next % len(symbols), raw_next >= len(symbols)


def scan_batch(symbols: List[str], *, url: str = SCAN_URL) -> Dict[str, Any]:
    if not symbols or len(symbols) > 8:
        raise ScoutHunterError("Scout scan batch must contain 1-8 symbols")
    result = _request_json(url, payload={"symbols": symbols}, timeout=60)
    if result.get("mode") != "DISCOVERY_RESEARCH_ONLY":
        raise ScoutHunterError("Unexpected Scout scan mode")
    return result


def run_cycle(
    *,
    universe_cache: Path = UNIVERSE_CACHE,
    state_path: Path = HUNTER_STATE,
    registry_path: Path = DEFAULT_REGISTRY,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, Any]:
    catalog = load_or_refresh_universe(cache_path=universe_cache)
    state = _read_state(state_path)
    batch, next_cursor, wrapped = choose_next_batch(
        catalog["universe"],
        cursor=int(state.get("cursor") or 0),
        batch_size=batch_size,
    )
    scan = scan_batch(batch)
    record_scan(scan, registry_path)

    ranked = ranked_candidates(registry_path)
    new_state = {
        "version": 1,
        "cursor": next_cursor,
        "lastBatch": batch,
        "lastRunAt": _utc_now().isoformat().replace("+00:00", "Z"),
        "wrapped": wrapped,
        "cycles": int(state.get("cycles") or 0) + 1,
        "tradeEligible": False,
    }
    _atomic_json(state_path, new_state)

    return {
        "mode": "RESEARCH_DISCOVERY_ONLY",
        "scanned": batch,
        "nextCursor": next_cursor,
        "wrapped": wrapped,
        "topResearchCandidates": [
            {
                "symbol": row.get("symbol"),
                "score": row.get("latestScore"),
                "tier": row.get("tier"),
                "stage": row.get("stage"),
                "tradeEligible": False,
            }
            for row in ranked[:5]
        ],
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }


def main() -> None:
    result = run_cycle()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
