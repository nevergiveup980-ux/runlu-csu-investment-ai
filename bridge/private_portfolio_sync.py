"""RUNLU Private Portfolio sync watcher.

Reads the already-sanitized local broker snapshot cache and uploads only when a
new snapshot appears. The mobile uploader performs a second minimization pass.

No brokerage write capability exists here.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from private_portfolio_upload import (
    SNAPSHOT_CACHE,
    PrivatePortfolioUploadError,
    upload_cached_snapshot,
)

STATE_FILE = Path(".csu-private") / "private-portfolio-sync-state.json"
DEFAULT_POLL_SECONDS = 180
MIN_POLL_SECONDS = 60
MAX_POLL_SECONDS = 300
MAX_SNAPSHOT_AGE_SECONDS = 30 * 60


class PrivatePortfolioSyncError(RuntimeError):
    pass


def bounded_poll_seconds(value: Any) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise PrivatePortfolioSyncError("Private portfolio sync interval must be an integer") from exc
    if seconds < MIN_POLL_SECONDS or seconds > MAX_POLL_SECONDS:
        raise PrivatePortfolioSyncError("Private portfolio sync interval must be between 60 and 300 seconds")
    return seconds


def _parse_time(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PrivatePortfolioSyncError("Cached portfolio snapshot timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise PrivatePortfolioSyncError("Cached portfolio snapshot timestamp needs timezone")
    return parsed.astimezone(timezone.utc)


def _read_snapshot(path: Path = SNAPSHOT_CACHE) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise PrivatePortfolioSyncError("No cached read-only broker snapshot is available") from exc
    except json.JSONDecodeError as exc:
        raise PrivatePortfolioSyncError("Cached read-only broker snapshot is invalid JSON") from exc
    if not isinstance(value, dict):
        raise PrivatePortfolioSyncError("Cached read-only broker snapshot must be an object")
    return value


def _snapshot_digest(value: Dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_state(path: Path = STATE_FILE) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(value: Dict[str, Any], path: Path = STATE_FILE) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="private-sync-", suffix=".json", dir=str(path.parent))
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


def sync_once(
    *,
    snapshot_path: Path = SNAPSHOT_CACHE,
    state_path: Path = STATE_FILE,
    now: datetime | None = None,
) -> Dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    snapshot = _read_snapshot(snapshot_path)
    fetched = _parse_time(snapshot.get("fetchedAt") or snapshot.get("fetched_at"))
    age = (current - fetched).total_seconds()
    if age < -300:
        raise PrivatePortfolioSyncError("Cached broker snapshot is unexpectedly in the future")
    if age > MAX_SNAPSHOT_AGE_SECONDS:
        return {
            "uploaded": False,
            "reason": "Cached broker snapshot is stale",
            "snapshotAgeSeconds": int(age),
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }

    digest = _snapshot_digest(snapshot)
    state = _read_state(state_path)
    if state.get("lastUploadedDigest") == digest:
        return {
            "uploaded": False,
            "reason": "Snapshot already uploaded",
            "fetchedAt": fetched.isoformat().replace("+00:00", "Z"),
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }

    try:
        result = upload_cached_snapshot(snapshot_path)
    except PrivatePortfolioUploadError as exc:
        _write_state({
            **state,
            "lastAttemptAt": current.isoformat().replace("+00:00", "Z"),
            "lastError": str(exc),
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }, state_path)
        raise PrivatePortfolioSyncError(str(exc)) from exc

    _write_state({
        "version": 1,
        "lastUploadedDigest": digest,
        "lastUploadedAt": current.isoformat().replace("+00:00", "Z"),
        "lastSnapshotFetchedAt": fetched.isoformat().replace("+00:00", "Z"),
        "lastError": None,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }, state_path)
    return {
        "uploaded": True,
        "storedAt": result.get("storedAt"),
        "fetchedAt": result.get("fetchedAt"),
        "positions": result.get("positions"),
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }


def run_forever() -> None:
    seconds = bounded_poll_seconds(os.getenv("RUNLU_PRIVATE_PORTFOLIO_POLL_SECONDS", DEFAULT_POLL_SECONDS))
    print(f"RUNLU Private Portfolio sync: every {seconds}s")
    print("Broker submission: DISABLED")
    while True:
        try:
            print(json.dumps(sync_once(), ensure_ascii=False))
        except PrivatePortfolioSyncError as exc:
            print(json.dumps({
                "uploaded": False,
                "error": str(exc),
                "brokerSubmissionEnabled": False,
            }, ensure_ascii=False))
        time.sleep(seconds)


if __name__ == "__main__":
    run_forever()
