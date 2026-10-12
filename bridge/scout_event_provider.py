"""Official press-release provider for RUNLU Scout Event Radar.

Polls the protected loopback Worker endpoint on a slow, bounded cadence.
The first successful observation for a symbol establishes a baseline and emits
no historical event. Only subsequently unseen press-release IDs are forwarded
to the Scout recheck engine.

No brokerage data or trading actions exist here.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from local_url import LocalUrlError, require_loopback_http
from snaptrade_handoff import _auth_headers
from scout_watch import process_observations, watch_symbols

EVENTS_URL = os.getenv(
    "RUNLU_SCOUT_WATCH_EVENTS_URL",
    "http://127.0.0.1:8787/api/scout/watch-events",
)
STATE_FILE = Path(".csu-private") / "scout-event-provider-state.json"
TORONTO = ZoneInfo("America/Toronto")
DEFAULT_POLL_SECONDS = 1800
MIN_POLL_SECONDS = 900
MAX_POLL_SECONDS = 3600
DEFAULT_BATCH_SIZE = 3
EVENT_START = (7, 0)
EVENT_END = (18, 30)


class ScoutEventProviderError(RuntimeError):
    pass


def bounded_poll_seconds(value: Any) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ScoutEventProviderError("Event Radar polling interval must be an integer") from exc
    if seconds < MIN_POLL_SECONDS or seconds > MAX_POLL_SECONDS:
        raise ScoutEventProviderError("Event Radar polling interval must be between 900 and 3600 seconds")
    return seconds


def event_monitor_window(now: datetime | None = None) -> bool:
    current = (now or datetime.now(TORONTO)).astimezone(TORONTO)
    if current.weekday() >= 5:
        return False
    hm = (current.hour, current.minute)
    return EVENT_START <= hm <= EVENT_END


def _read_state(path: Path = STATE_FILE) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(value: Dict[str, Any], path: Path = STATE_FILE) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="scout-event-", suffix=".json", dir=str(path.parent))
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


def choose_event_batch(
    symbols: List[str],
    *,
    cursor: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[List[str], int]:
    if batch_size < 1 or batch_size > 3:
        raise ScoutEventProviderError("Event Radar batch size must be 1-3")
    safe: List[str] = []
    for raw in symbols:
        symbol = str(raw or "").upper()
        if symbol.endswith(":TSX") and symbol != "CSU:TSX" and symbol not in safe:
            safe.append(symbol)
    if not safe:
        return [], 0
    start = max(0, int(cursor)) % len(safe)
    size = min(batch_size, len(safe))
    batch = [safe[(start + i) % len(safe)] for i in range(size)]
    return batch, (start + size) % len(safe)


def fetch_event_observations(
    symbols: List[str],
    *,
    url: str = EVENTS_URL,
    state_path: Path = STATE_FILE,
) -> List[Dict[str, Any]]:
    try:
        safe_url = require_loopback_http(url)
    except LocalUrlError as exc:
        raise ScoutEventProviderError(str(exc)) from exc

    state = _read_state(state_path)
    batch, next_cursor = choose_event_batch(
        symbols,
        cursor=int(state.get("cursor") or 0),
    )
    if not batch:
        return []

    payload = json.dumps({"symbols": batch}, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        safe_url,
        data=payload,
        headers=_auth_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ScoutEventProviderError(
            f"Scout Event Radar rejected request: HTTP {exc.code}: {detail[:300]}"
        ) from exc
    except Exception as exc:
        raise ScoutEventProviderError("Unable to reach Scout Event Radar endpoint") from exc

    if not isinstance(result, dict) or result.get("mode") != "WATCH_EVENT_RESEARCH_ONLY":
        raise ScoutEventProviderError("Scout Event Radar returned unexpected mode")

    rows = result.get("observations")
    if not isinstance(rows, list):
        raise ScoutEventProviderError("Scout Event Radar returned invalid observations")

    seen_by_symbol = state.setdefault("seenBySymbol", {})
    output: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper()
        if symbol not in batch:
            continue
        events = row.get("events")
        if not isinstance(events, list):
            continue

        prior = seen_by_symbol.get(symbol)
        prior_ids = set(prior if isinstance(prior, list) else [])
        current_ids: List[str] = []
        normalized: List[Dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or "")
            event_type = str(event.get("type") or "").upper()
            title = str(event.get("title") or "").strip()
            if not event_id or not event_type or not title:
                continue
            current_ids.append(event_id)
            if prior is not None and event_id not in prior_ids:
                normalized.append({
                    "id": event_id,
                    "type": event_type,
                    "title": title[:240],
                    "datetime": event.get("datetime"),
                    "sourceType": "OFFICIAL_PRESS_RELEASE",
                })

        merged = list(dict.fromkeys(current_ids + list(prior_ids)))[:50]
        seen_by_symbol[symbol] = merged
        if normalized:
            output.append({"symbol": symbol, "events": normalized})

    state["version"] = 1
    state["cursor"] = next_cursor
    state["lastBatch"] = batch
    state["tradeEligible"] = False
    state["brokerSubmissionEnabled"] = False
    _write_state(state, state_path)
    return output


def run_event_once(
    *,
    now: datetime | None = None,
    state_path: Path = STATE_FILE,
) -> Dict[str, Any]:
    if not event_monitor_window(now):
        return {
            "ran": False,
            "reason": "Outside weekday Event Radar window",
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }
    symbols = watch_symbols()
    if not symbols:
        return {
            "ran": False,
            "reason": "No finalized WATCH/APPROVED_UNIVERSE symbols",
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }
    observations = fetch_event_observations(symbols, state_path=state_path)
    results = process_observations(observations)
    return {
        "ran": True,
        "symbolsEligible": len(symbols),
        "newEventObservations": len(observations),
        "results": results,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }


def run_forever() -> None:
    poll_seconds = bounded_poll_seconds(
        os.getenv("RUNLU_SCOUT_EVENT_POLL_SECONDS", DEFAULT_POLL_SECONDS)
    )
    print(f"RUNLU Scout Event Radar: every {poll_seconds}s during weekday event window")
    print("Broker submission: DISABLED")
    while True:
        try:
            print(json.dumps(run_event_once(), ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({
                "ran": False,
                "error": str(exc),
                "brokerSubmissionEnabled": False,
            }, ensure_ascii=False))
        time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
