"""RUNLU Scout Daily Research — after-close candidate discovery.

Runs a small number of Scout Hunter batches after the TSX session, writes a
private Top-5 research queue, and never grants trading authority.

This module is orchestration only. It does not place, modify, or cancel orders.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from scout_hunter import run_cycle
from scout_registry import DEFAULT_REGISTRY, ranked_candidates
from scout_research_card import build_cards

TORONTO = ZoneInfo("America/Toronto")
DAILY_STATE = Path(".csu-private") / "scout-daily-state.json"
DAILY_REPORT = Path(".csu-private") / "scout-daily-top5.json"
DEFAULT_BATCHES = 3
MIN_BATCHES = 1
MAX_BATCHES = 6
AFTER_CLOSE_HOUR = 16
AFTER_CLOSE_MINUTE = 20


class ScoutDailyError(RuntimeError):
    pass


def bounded_daily_batches(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ScoutDailyError("Daily Scout batch count must be an integer") from exc
    if n < MIN_BATCHES or n > MAX_BATCHES:
        raise ScoutDailyError("Daily Scout batch count must be between 1 and 6")
    return n


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _atomic_json(path: Path, value: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="scout-daily-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def tsx_after_close(now: datetime | None = None) -> bool:
    current = (now or datetime.now(TORONTO)).astimezone(TORONTO)
    if current.weekday() >= 5:
        return False
    return (current.hour, current.minute) >= (AFTER_CLOSE_HOUR, AFTER_CLOSE_MINUTE)


def research_queue(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("stage") == "PASS":
            continue
        out.append({
            "symbol": row.get("symbol"),
            "score": row.get("latestScore"),
            "tier": row.get("tier"),
            "stage": row.get("stage"),
            "reasons": list(row.get("reasons") or [])[:6],
            "riskFlags": list(row.get("riskFlags") or [])[:6],
            "marketDataAsOf": row.get("marketDataAsOf"),
            "researchRequired": True,
            "tradeEligible": False,
        })
        if len(out) >= limit:
            break
    return out


def run_daily_research(
    *,
    now: datetime | None = None,
    batches: int = DEFAULT_BATCHES,
    daily_state_path: Path = DAILY_STATE,
    daily_report_path: Path = DAILY_REPORT,
    registry_path: Path = DEFAULT_REGISTRY,
) -> Dict[str, Any]:
    batches = bounded_daily_batches(batches)
    current = (now or datetime.now(TORONTO)).astimezone(TORONTO)

    if not tsx_after_close(current):
        return {
            "ran": False,
            "reason": "Outside weekday after-close research window",
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }

    trading_date = current.date().isoformat()
    state = _read_json(daily_state_path)
    if state.get("lastCompletedDate") == trading_date:
        return {
            "ran": False,
            "reason": "Daily Scout research already completed",
            "date": trading_date,
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }

    cycles: List[Dict[str, Any]] = []
    for _ in range(batches):
        cycles.append(run_cycle(registry_path=registry_path))

    ranked = ranked_candidates(registry_path)
    queue = research_queue(ranked, 5)
    cards = build_cards(ranked, 5)
    generated_at = current.isoformat()

    report = {
        "product": "RUNLU Scout Daily Research",
        "mode": "RESEARCH_QUEUE_ONLY",
        "date": trading_date,
        "generatedAt": generated_at,
        "batches": batches,
        "symbolsScanned": [symbol for cycle in cycles for symbol in cycle.get("scanned", [])],
        "top5": queue,
        "researchCards": cards,
        "policy": {
            "csuPrimary": True,
            "jointResearchRequired": True,
            "explicitUserConfirmationRequired": True,
            "automaticTrading": False,
            "tradeEligible": False,
        },
    }
    _atomic_json(daily_report_path, report)
    _atomic_json(daily_state_path, {
        "lastCompletedDate": trading_date,
        "lastCompletedAt": generated_at,
        "batches": batches,
        "tradeEligible": False,
    })

    return {
        "ran": True,
        "date": trading_date,
        "batches": batches,
        "symbolsScanned": len(report["symbolsScanned"]),
        "top5": queue,
        "reportPath": str(daily_report_path),
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }


def main() -> None:
    batches = bounded_daily_batches(os.getenv("RUNLU_SCOUT_DAILY_BATCHES", DEFAULT_BATCHES))
    print(json.dumps(run_daily_research(batches=batches), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
