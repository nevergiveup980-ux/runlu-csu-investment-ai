"""RUNLU Scout Watch Monitor.

Monitors only finalized WATCH / APPROVED_UNIVERSE research candidates. It is
research-only: no brokerage snapshot, order payload, or execution route exists.

Quote observations can trigger the material-change recheck engine. News/event
observations use explicit normalized event records; provider ingestion can be
added later without changing the research authority boundary.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
from zoneinfo import ZoneInfo

from scout_registry import DEFAULT_REGISTRY, _read, flag_material_recheck

STATE_FILE = Path(".csu-private") / "scout-watch-state.json"
DEFAULT_POLL_SECONDS = 300
MIN_POLL_SECONDS = 60
MAX_POLL_SECONDS = 300
TORONTO = ZoneInfo("America/Toronto")
MARKET_START = (9, 30)
MARKET_END = (16, 10)


class ScoutWatchError(RuntimeError):
    pass


def bounded_poll_seconds(value: Any) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ScoutWatchError("Scout Watch polling interval must be an integer") from exc
    if seconds < MIN_POLL_SECONDS or seconds > MAX_POLL_SECONDS:
        raise ScoutWatchError("Scout Watch polling interval must be between 60 and 300 seconds")
    return seconds


def market_monitor_window(now: datetime | None = None) -> bool:
    current = (now or datetime.now(TORONTO)).astimezone(TORONTO)
    if current.weekday() >= 5:
        return False
    hm = (current.hour, current.minute)
    return MARKET_START <= hm <= MARKET_END


def watch_symbols(registry_path: Path = DEFAULT_REGISTRY) -> List[str]:
    registry = _read(registry_path)
    out = []
    for symbol, row in registry["candidates"].items():
        if row.get("stage") in {"WATCH", "APPROVED_UNIVERSE"} and row.get("researchStatus") == "FINALIZED":
            out.append(symbol)
    return sorted(out)


def _read_state(path: Path = STATE_FILE) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(value: Dict[str, Any], path: Path = STATE_FILE) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="scout-watch-", suffix=".json", dir=str(path.parent))
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


def process_observation(
    symbol: str,
    *,
    price: float | None = None,
    events: Iterable[Dict[str, Any]] = (),
    registry_path: Path = DEFAULT_REGISTRY,
    state_path: Path = STATE_FILE,
    observed_at: datetime | None = None,
) -> Dict[str, Any]:
    key = str(symbol or "").upper()
    if key not in watch_symbols(registry_path):
        return {
            "symbol": key,
            "recheckRequired": False,
            "reason": "Symbol is not in finalized WATCH/APPROVED_UNIVERSE",
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }

    state = _read_state(state_path)
    symbols = state.setdefault("symbols", {})
    previous = symbols.get(key) if isinstance(symbols.get(key), dict) else {}
    previous_price = previous.get("price")

    row = flag_material_recheck(
        key,
        events=list(events),
        previous_price=previous_price,
        current_price=price,
        path=registry_path,
    )

    current = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    symbols[key] = {
        "price": float(price) if price is not None else previous_price,
        "observedAt": current.isoformat().replace("+00:00", "Z"),
        "tradeEligible": False,
    }
    state["updatedAt"] = current.isoformat().replace("+00:00", "Z")
    state["brokerSubmissionEnabled"] = False
    _write_state(state, state_path)

    recheck = row.get("stage") == "RECHECK_REQUIRED"
    return {
        "symbol": key,
        "recheckRequired": recheck,
        "stage": row.get("stage"),
        "reasons": list((row.get("recheck") or {}).get("reasons") or []) if recheck else [],
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }


def process_observations(
    observations: Iterable[Dict[str, Any]],
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    state_path: Path = STATE_FILE,
) -> List[Dict[str, Any]]:
    results = []
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        results.append(process_observation(
            str(observation.get("symbol") or ""),
            price=observation.get("price"),
            events=observation.get("events") or (),
            registry_path=registry_path,
            state_path=state_path,
        ))
    return results


def run_once(observer, *, now: datetime | None = None) -> Dict[str, Any]:
    if not market_monitor_window(now):
        return {
            "ran": False,
            "reason": "Outside weekday TSX monitoring window",
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
    observations = observer(symbols)
    results = process_observations(observations)
    return {
        "ran": True,
        "symbolsEligible": len(symbols),
        "observationsProcessed": len(results),
        "results": results,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }


def run_forever(observer) -> None:
    poll_seconds = bounded_poll_seconds(os.getenv("RUNLU_SCOUT_WATCH_POLL_SECONDS", DEFAULT_POLL_SECONDS))
    print(f"RUNLU Scout Watch: every {poll_seconds}s during weekday TSX hours")
    print("Broker submission: DISABLED")
    while True:
        try:
            print(json.dumps(run_once(observer), ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"ran": False, "error": str(exc), "brokerSubmissionEnabled": False}, ensure_ascii=False))
        time.sleep(poll_seconds)
