from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from typing import Any
from urllib import request


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "value"):
        return value.value
    return value


def journal_event(*, event_type: str, symbol: str, payload: dict[str, Any], dry_run: bool = True) -> dict:
    row = {
        "event_type": event_type,
        "symbol": symbol.upper().strip(),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": _jsonable(payload),
    }
    if dry_run:
        return {"written": False, "dry_run": True, "row": row}

    base = _required("SUPABASE_URL").rstrip("/")
    key = _required("SUPABASE_SERVICE_ROLE_KEY")
    table = os.getenv("RUNLU_TRADE_JOURNAL_TABLE", "trade_journal").strip() or "trade_journal"
    req = request.Request(
        f"{base}/rest/v1/{table}",
        data=json.dumps(row).encode("utf-8"),
        method="POST",
        headers={
            "apikey": key,
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
            "prefer": "return=representation",
        },
    )
    with request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
    return {"written": True, "row": row, "response": json.loads(body or "[]")}
