"""RUNLU independent-news watchman.

Runs the best-effort RSS radar on a slow cadence during weekday company-news
hours. It never changes Scout stage by itself.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from scout_independent_news import run_news_cycle

TORONTO = ZoneInfo("America/Toronto")
DEFAULT_SECONDS = 1800
MIN_SECONDS = 900
MAX_SECONDS = 3600
START = (7, 0)
END = (18, 30)


class IndependentNewsWatchmanError(RuntimeError):
    pass


def bounded_seconds(value) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise IndependentNewsWatchmanError("News watch interval must be an integer") from exc
    if seconds < MIN_SECONDS or seconds > MAX_SECONDS:
        raise IndependentNewsWatchmanError("News watch interval must be between 900 and 3600 seconds")
    return seconds


def news_window(now: datetime | None = None) -> bool:
    current = (now or datetime.now(TORONTO)).astimezone(TORONTO)
    if current.weekday() >= 5:
        return False
    hm = (current.hour, current.minute)
    return START <= hm <= END


def tick_once(*, now: datetime | None = None):
    if not news_window(now):
        return {
            "ran": False,
            "reason": "Outside weekday independent-news window",
            "automaticRecheck": False,
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }
    result = run_news_cycle()
    result["automaticRecheck"] = False
    result["tradeEligible"] = False
    result["brokerSubmissionEnabled"] = False
    return result


def run_forever() -> None:
    seconds = bounded_seconds(os.getenv("RUNLU_SCOUT_NEWS_POLL_SECONDS", DEFAULT_SECONDS))
    print(f"RUNLU Scout Independent News: every {seconds}s during weekday news window")
    print("Automatic recheck: DISABLED")
    print("Broker submission: DISABLED")
    while True:
        try:
            print(json.dumps(tick_once(), ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({
                "ran": False,
                "error": str(exc),
                "automaticRecheck": False,
                "brokerSubmissionEnabled": False,
            }, ensure_ascii=False))
        time.sleep(seconds)


if __name__ == "__main__":
    run_forever()
