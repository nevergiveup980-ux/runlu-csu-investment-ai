"""RUNLU Scout Watchman — local after-close research scheduler.

The process may stay running on the user's Mac. It wakes periodically, but the
daily guard only permits one Scout research run per weekday after 16:20
America/Toronto. It contains no broker write path.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

from scout_daily import (
    DEFAULT_BATCHES,
    ScoutDailyError,
    bounded_daily_batches,
    run_daily_research,
)

DEFAULT_WAKE_SECONDS = 1800
MIN_WAKE_SECONDS = 900
MAX_WAKE_SECONDS = 3600


class ScoutWatchmanError(RuntimeError):
    pass


def bounded_wake_seconds(value: Any) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ScoutWatchmanError("Watchman wake interval must be an integer") from exc
    if seconds < MIN_WAKE_SECONDS or seconds > MAX_WAKE_SECONDS:
        raise ScoutWatchmanError("Watchman wake interval must be between 900 and 3600 seconds")
    return seconds


def tick_once(*, batches: int = DEFAULT_BATCHES) -> Dict[str, Any]:
    result = run_daily_research(batches=bounded_daily_batches(batches))
    return {
        **result,
        "scheduler": "RUNLU_SCOUT_WATCHMAN",
        "brokerSubmissionEnabled": False,
    }


def run_forever() -> None:
    wake_seconds = bounded_wake_seconds(
        os.getenv("RUNLU_SCOUT_WATCHMAN_SECONDS", DEFAULT_WAKE_SECONDS)
    )
    batches = bounded_daily_batches(
        os.getenv("RUNLU_SCOUT_DAILY_BATCHES", DEFAULT_BATCHES)
    )
    print(json.dumps({
        "service": "RUNLU Scout Watchman",
        "wakeSeconds": wake_seconds,
        "dailyBatches": batches,
        "brokerSubmissionEnabled": False,
    }, ensure_ascii=False))

    while True:
        try:
            print(json.dumps(tick_once(batches=batches), ensure_ascii=False))
        except (ScoutDailyError, ScoutWatchmanError, RuntimeError) as exc:
            print(json.dumps({
                "ran": False,
                "error": str(exc),
                "brokerSubmissionEnabled": False,
            }, ensure_ascii=False))
        time.sleep(wake_seconds)


if __name__ == "__main__":
    run_forever()
