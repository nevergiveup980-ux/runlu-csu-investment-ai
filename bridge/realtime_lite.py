"""CSU Realtime Lite: 1-5 minute human-review scanner.

This local service is deliberately non-trading. It reuses a recently cached,
sanitized read-only broker snapshot, asks the protected bot endpoint for a
1-minute or 5-minute candidate, and pushes only new BUY/SELL review episodes to
the localhost approval panel.

No brokerage write endpoint exists here.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from bot_review_hook import publish_review_response
from local_url import LocalUrlError, require_loopback_http
from snaptrade_handoff import SNAPSHOT_CACHE, _auth_headers

REALTIME_URL = os.getenv(
    "CSU_REALTIME_PROPOSAL_URL",
    "http://127.0.0.1:8787/api/bot/realtime-proposal",
)
STATE_FILE = Path(".csu-private") / "realtime-lite-state.json"
DEFAULT_POLL_SECONDS = 180
DEFAULT_RENOTIFY_SECONDS = 900
MAX_SNAPSHOT_AGE_SECONDS = 15 * 60


class RealtimeLiteError(RuntimeError):
    pass


def bounded_poll_seconds(value: Any) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise RealtimeLiteError("Polling interval must be an integer") from exc
    if seconds < 60 or seconds > 300:
        raise RealtimeLiteError("Polling interval must be between 60 and 300 seconds")
    return seconds


def _parse_iso(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise RealtimeLiteError("Invalid timestamp") from exc
    if dt.tzinfo is None:
        raise RealtimeLiteError("Timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def load_cached_snapshot(
    path: Path = SNAPSHOT_CACHE,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: int = MAX_SNAPSHOT_AGE_SECONDS,
) -> Dict[str, Any]:
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RealtimeLiteError("No cached broker snapshot; refresh the read-only bridge first") from exc
    except json.JSONDecodeError as exc:
        raise RealtimeLiteError("Cached broker snapshot is corrupt") from exc
    if not isinstance(value, dict):
        raise RealtimeLiteError("Cached broker snapshot must be an object")
    fetched = _parse_iso(str(value.get("fetchedAt") or ""))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = (current - fetched).total_seconds()
    if age < -300:
        raise RealtimeLiteError("Cached broker snapshot is unexpectedly in the future")
    if age > max_age_seconds:
        raise RealtimeLiteError("Cached broker snapshot is stale; refresh the read-only bridge")
    return value


def request_realtime_candidate(
    snapshot: Dict[str, Any],
    *,
    expires_at: str,
    interval: str = "1min",
    url: str = REALTIME_URL,
) -> Dict[str, Any]:
    if interval not in {"1min", "5min"}:
        raise RealtimeLiteError("Market interval must be 1min or 5min")
    body = json.dumps({
        "snapshot": snapshot,
        "expiresAt": expires_at,
        "interval": interval,
    }, separators=(",", ":")).encode("utf-8")
    try:
        safe_url = require_loopback_http(url)
    except LocalUrlError as exc:
        raise RealtimeLiteError(str(exc)) from exc
    req = urllib.request.Request(
        safe_url,
        data=body,
        headers=_auth_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RealtimeLiteError(
            f"Realtime bot rejected scan: HTTP {exc.code}: {detail[:300]}"
        ) from exc
    except Exception as exc:
        raise RealtimeLiteError("Unable to reach realtime bot endpoint") from exc
    if not isinstance(result, dict):
        raise RealtimeLiteError("Realtime bot returned invalid JSON")
    return result


def review_fingerprint(packet: Dict[str, Any]) -> str:
    stable = {
        "symbol": packet.get("symbol"),
        "action": packet.get("action"),
        "quantity": packet.get("quantity"),
        "role": packet.get("role"),
        "currentShares": packet.get("currentShares"),
        "targetShares": packet.get("targetShares"),
    }
    raw = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
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
    fd, tmp_name = tempfile.mkstemp(prefix="realtime-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, separators=(",", ":"), ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def process_scan_result(
    result: Dict[str, Any],
    *,
    state_path: Path = STATE_FILE,
    now: Optional[datetime] = None,
    renotify_seconds: int = DEFAULT_RENOTIFY_SECONDS,
) -> Dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    state = _read_state(state_path)
    market_as_of = result.get("marketDataAsOf")
    if market_as_of and state.get("marketDataAsOf") == market_as_of:
        return {"published": False, "reason": "No new market bar", "decision": (result.get("decision") or {}).get("action")}

    packet = result.get("reviewPacket")
    decision = (result.get("decision") or {}).get("action") or "HOLD"
    if not isinstance(packet, dict):
        _write_state({
            "marketDataAsOf": market_as_of,
            "decision": decision,
            "fingerprint": None,
            "lastPublishedAt": state.get("lastPublishedAt"),
            "brokerSubmissionEnabled": False,
        }, state_path)
        return {"published": False, "reason": "No reviewable BUY/SELL proposal", "decision": decision}

    fingerprint = review_fingerprint(packet)
    last_at_text = state.get("lastPublishedAt")
    last_at = None
    if last_at_text:
        try:
            last_at = _parse_iso(last_at_text)
        except RealtimeLiteError:
            last_at = None
    same_episode = state.get("fingerprint") == fingerprint
    within_cooldown = bool(last_at and (current - last_at).total_seconds() < renotify_seconds)
    if same_episode and within_cooldown:
        _write_state({
            **state,
            "marketDataAsOf": market_as_of,
            "decision": decision,
            "brokerSubmissionEnabled": False,
        }, state_path)
        return {"published": False, "reason": "Same signal episode already reviewed recently", "decision": decision}

    panel = publish_review_response(result)
    now_text = current.isoformat().replace("+00:00", "Z")
    _write_state({
        "marketDataAsOf": market_as_of,
        "decision": decision,
        "fingerprint": fingerprint,
        "lastPublishedAt": now_text,
        "proposalId": packet.get("proposalId"),
        "brokerSubmissionEnabled": False,
    }, state_path)
    return {
        "published": True,
        "decision": decision,
        "proposal_id": packet.get("proposalId"),
        "panel": panel,
        "broker_submission_enabled": False,
    }


def scan_once(
    *,
    snapshot_path: Path = SNAPSHOT_CACHE,
    interval: str = "1min",
    state_path: Path = STATE_FILE,
    ttl_seconds: int = 300,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    snapshot = load_cached_snapshot(snapshot_path, now=now)
    expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat().replace("+00:00", "Z")
    result = request_realtime_candidate(
        snapshot,
        expires_at=expires_at,
        interval=interval,
    )
    return process_scan_result(result, state_path=state_path, now=now)


def run_forever() -> None:
    poll_seconds = bounded_poll_seconds(os.getenv("CSU_REALTIME_POLL_SECONDS", DEFAULT_POLL_SECONDS))
    interval = os.getenv("CSU_REALTIME_MARKET_INTERVAL", "1min")
    if interval not in {"1min", "5min"}:
        raise RealtimeLiteError("CSU_REALTIME_MARKET_INTERVAL must be 1min or 5min")
    print(f"CSU Realtime Lite: every {poll_seconds}s using {interval} bars")
    print("Broker submission: DISABLED")
    while True:
        try:
            outcome = scan_once(interval=interval)
            print(json.dumps(outcome, ensure_ascii=False))
        except RealtimeLiteError as exc:
            print(json.dumps({"published": False, "error": str(exc)}, ensure_ascii=False))
        time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
