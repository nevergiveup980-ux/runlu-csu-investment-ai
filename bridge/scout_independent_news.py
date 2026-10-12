"""RUNLU Scout independent-news radar.

Uses Google News RSS as a best-effort, no-secret external discovery source for
finalized WATCH / APPROVED_UNIVERSE candidates. Independent news is never
trusted enough to reopen research automatically: new items become
NEWS_REVIEW_REQUIRED alerts for user + assistant review.

No brokerage data, bearer token, or order authority exists here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from scout_watch import watch_symbols

STATE_FILE = Path(".csu-private") / "scout-independent-news-state.json"
ALERT_FILE = Path(".csu-private") / "scout-news-alerts.json"
NEWS_HOST = "news.google.com"
NEWS_PATH = "/rss/search"
DEFAULT_MAX_ITEMS = 8
DEFAULT_BATCH_SIZE = 3

MATERIAL_PATTERNS = {
    "EARNINGS": [r"\bearnings\b", r"\bfinancial results?\b", r"\bquarterly results?\b"],
    "GUIDANCE": [r"\bguidance\b", r"\boutlook\b", r"\bforecast\b"],
    "M_AND_A": [r"\bacquisition\b", r"\bacquire[sd]?\b", r"\bmerger\b", r"\btakeover\b"],
    "MANAGEMENT_CHANGE": [r"\bceo\b", r"\bcfo\b", r"\bchief executive\b", r"\bchief financial\b", r"\bresign"],
    "REGULATORY": [r"\bregulator", r"\bcompetition bureau\b", r"\bsecurities commission\b", r"\binvestigation\b"],
    "CAPITAL_RAISE": [r"\boffering\b", r"\bfinancing\b", r"\bprivate placement\b"],
    "CREDIT_EVENT": [r"\bdowngrade\b", r"\bdefault\b", r"\bcredit rating\b", r"\bdebt covenant\b"],
    "LITIGATION": [r"\blawsuit\b", r"\blitigation\b", r"\bclass action\b"],
}


class IndependentNewsError(RuntimeError):
    pass


def _atomic_json(path: Path, value: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="scout-news-", suffix=".json", dir=str(path.parent))
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


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def choose_news_batch(symbols: List[str], *, cursor: int, batch_size: int = DEFAULT_BATCH_SIZE):
    if batch_size < 1 or batch_size > 3:
        raise IndependentNewsError("Independent-news batch size must be 1-3")
    safe = []
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


def classify_headline(title: str) -> str:
    value = str(title or "")
    for category, patterns in MATERIAL_PATTERNS.items():
        if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns):
            return category
    return "INDEPENDENT_NEWS"


def build_google_news_url(symbol: str) -> str:
    ticker = str(symbol or "").upper().split(":", 1)[0]
    if not ticker or not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
        raise IndependentNewsError("Invalid TSX ticker for independent-news query")
    query = urllib.parse.quote_plus(f'"{ticker}" TSX stock')
    return (
        f"https://{NEWS_HOST}{NEWS_PATH}?q={query}"
        "&hl=en-CA&gl=CA&ceid=CA:en"
    )


def _item_id(link: str, title: str) -> str:
    return hashlib.sha256(f"{link}\n{title}".encode("utf-8")).hexdigest()


def parse_google_news_rss(xml_bytes: bytes, symbol: str, *, max_items: int = DEFAULT_MAX_ITEMS):
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise IndependentNewsError("Independent-news RSS is invalid XML") from exc

    rows = []
    for item in root.findall(".//item")[:max_items]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None and source_el.text else ""
        if not title or not link:
            continue
        rows.append({
            "id": _item_id(link, title),
            "symbol": symbol,
            "category": classify_headline(title),
            "title": title[:300],
            "link": link,
            "publishedAt": published or None,
            "publisher": source[:120] or None,
            "sourceType": "INDEPENDENT_NEWS_RSS",
            "reviewRequired": True,
            "tradeEligible": False,
        })
    return rows


def fetch_symbol_news(symbol: str, *, timeout: int = 15) -> List[Dict[str, Any]]:
    url = build_google_news_url(symbol)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != NEWS_HOST or parsed.path != NEWS_PATH:
        raise IndependentNewsError("Independent-news destination is not allowed")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "RUNLU-Scout-News-Radar/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except Exception as exc:
        raise IndependentNewsError("Unable to fetch independent-news RSS") from exc
    return parse_google_news_rss(body, symbol)


def mark_alert_escalated(
    alert_id: str,
    *,
    alert_path: Path = ALERT_FILE,
) -> Dict[str, Any]:
    data = _read_json(alert_path)
    alerts = data.get("alerts")
    if not isinstance(alerts, list):
        raise IndependentNewsError("Independent-news alert archive is unavailable")

    target = None
    for alert in alerts:
        if isinstance(alert, dict) and str(alert.get("id") or "") == str(alert_id or ""):
            target = alert
            break
    if target is None:
        raise IndependentNewsError("Independent-news alert was not found")
    if target.get("status") == "ESCALATED_TO_RECHECK":
        return target

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    target["status"] = "ESCALATED_TO_RECHECK"
    target["userConfirmedMaterial"] = True
    target["escalatedAt"] = now
    target["tradeEligible"] = False
    target["brokerSubmissionEnabled"] = False
    data["updatedAt"] = now
    data["tradeEligible"] = False
    data["brokerSubmissionEnabled"] = False
    _atomic_json(alert_path, data)
    return target


def run_news_cycle(
    *,
    state_path: Path = STATE_FILE,
    alert_path: Path = ALERT_FILE,
) -> Dict[str, Any]:
    symbols = watch_symbols()
    state = _read_json(state_path)
    batch, next_cursor = choose_news_batch(
        symbols,
        cursor=int(state.get("cursor") or 0),
    )
    if not batch:
        return {
            "ran": False,
            "reason": "No finalized WATCH/APPROVED_UNIVERSE symbols",
            "alerts": 0,
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }

    seen = state.setdefault("seenBySymbol", {})
    alerts_file = _read_json(alert_path)
    existing_alerts = alerts_file.get("alerts")
    if not isinstance(existing_alerts, list):
        existing_alerts = []

    emitted = []
    errors = []
    for symbol in batch:
        try:
            items = fetch_symbol_news(symbol)
        except IndependentNewsError as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
            continue

        prior = seen.get(symbol)
        prior_ids = set(prior if isinstance(prior, list) else [])
        current_ids = [str(item.get("id") or "") for item in items if item.get("id")]
        if prior is not None:
            for item in items:
                if item["id"] not in prior_ids:
                    emitted.append(item)

        seen[symbol] = list(dict.fromkeys(current_ids + list(prior_ids)))[:100]

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if emitted:
        existing_ids = {str(x.get("id") or "") for x in existing_alerts if isinstance(x, dict)}
        for item in emitted:
            if item["id"] not in existing_ids:
                existing_alerts.append({
                    **item,
                    "status": "NEWS_REVIEW_REQUIRED",
                    "detectedAt": now,
                    "userConfirmedMaterial": False,
                    "tradeEligible": False,
                    "brokerSubmissionEnabled": False,
                })
        existing_alerts = existing_alerts[-100:]
        _atomic_json(alert_path, {
            "version": 1,
            "updatedAt": now,
            "alerts": existing_alerts,
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        })

    _atomic_json(state_path, {
        "version": 1,
        "cursor": next_cursor,
        "lastBatch": batch,
        "seenBySymbol": seen,
        "updatedAt": now,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    })

    return {
        "ran": True,
        "scanned": batch,
        "alerts": len(emitted),
        "errors": errors,
        "researchOnly": True,
        "automaticRecheck": False,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_news_cycle(), indent=2, ensure_ascii=False))
