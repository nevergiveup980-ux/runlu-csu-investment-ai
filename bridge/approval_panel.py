"""Loopback-only human approval panel for CSU Bot V2.

This service never submits a brokerage order. It can register an already
preflighted one-share CSU limit-order packet, display it locally, record an
APPROVE/REJECT decision in the private audit ledger, and produce an approved
DRY-RUN envelope.

Bind address is always 127.0.0.1. No CORS. No broker credentials are accepted.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from approval_ledger import (
    DEFAULT_LEDGER,
    ApprovalLedgerError,
    approve_proposal,
    issue_approval_challenge,
    proposal_status,
    reject_proposal,
)
from execution_bridge import (
    ExecutionBridgeError,
    build_approved_dry_run,
    execution_order_digest,
    validate_order_body,
)

HOST = "127.0.0.1"
DEFAULT_PORT = 8775
MAX_BODY = 65536
SESSION_FILE = Path(".csu-private") / "approval-session-token"
SCOUT_DAILY_REPORT = Path(".csu-private") / "scout-daily-top5.json"


class ApprovalPanelError(RuntimeError):
    pass


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApprovalPanelError("Invalid proposal expiry") from exc
    if parsed.tzinfo is None:
        raise ApprovalPanelError("Proposal expiry must include timezone")
    return parsed


def _safe_review(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "role", "reasons", "current_shares", "target_shares",
        "score", "confidence", "quote_as_of", "snapshot_as_of",
    }
    result = {k: value[k] for k in allowed if k in value}
    if "reasons" in result and not isinstance(result["reasons"], list):
        result["reasons"] = [str(result["reasons"])]
    return result


class PanelState:
    def __init__(self, ledger_path: Path = DEFAULT_LEDGER, scout_report_path: Path = SCOUT_DAILY_REPORT):
        self.ledger_path = ledger_path
        self.scout_report_path = Path(scout_report_path)
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._reviews: Dict[str, Dict[str, Any]] = {}

    def register(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(packet, dict) or not isinstance(packet.get("order"), dict):
            raise ApprovalPanelError("Packet must contain an order object")
        order = validate_order_body(packet["order"])
        proposal_id = order["client_order_id"]
        expires_at = str(packet.get("expires_at") or "")
        expiry = _parse_time(expires_at)
        if expiry <= datetime.now(timezone.utc):
            raise ApprovalPanelError("Proposal is already expired")
        review = _safe_review(packet.get("review"))
        challenge = issue_approval_challenge(
            proposal_id,
            expires_at=expires_at,
            proposal_digest=execution_order_digest(order),
            path=self.ledger_path,
        )
        self._pending[proposal_id] = {
            "order": order,
            "expires_at": expires_at,
            "review": review,
            "approval_token": challenge.approval_token,
        }
        return self.card(proposal_id)


    def register_review(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(packet, dict):
            raise ApprovalPanelError("Review packet must be an object")
        if packet.get("kind") != "CSU_DECISION_REVIEW" or packet.get("version") != 1:
            raise ApprovalPanelError("Unsupported review packet")
        if packet.get("symbol") != "CSU.TO" or packet.get("quantity") != 1:
            raise ApprovalPanelError("Only one-share CSU.TO reviews are accepted")
        if packet.get("action") not in ("BUY", "SELL"):
            raise ApprovalPanelError("Review action must be BUY or SELL")
        if packet.get("simulationOnly") is not True or packet.get("brokerSubmitted") is not False:
            raise ApprovalPanelError("Only simulation-only reviews are accepted")

        proposal_id = str(packet.get("proposalId") or "")
        if not proposal_id:
            raise ApprovalPanelError("proposalId is required")
        expires_at = str(packet.get("expiresAt") or "")
        expiry = _parse_time(expires_at)
        if expiry <= datetime.now(timezone.utc):
            raise ApprovalPanelError("Review is already expired")

        current_shares = int(packet.get("currentShares"))
        target_shares = int(packet.get("targetShares"))
        if current_shares < 0 or current_shares > 3 or target_shares < 0 or target_shares > 3:
            raise ApprovalPanelError("Review share counts are outside the 0-3 range")

        sanitized = {
            "kind": "CSU_DECISION_REVIEW",
            "version": 1,
            "proposalId": proposal_id,
            "symbol": "CSU.TO",
            "action": packet["action"],
            "quantity": 1,
            "indicativeLimitCAD": float(packet.get("indicativeLimitCAD")),
            "expiresAt": expires_at,
            "role": str(packet.get("role") or "NONE"),
            "currentShares": current_shares,
            "targetShares": target_shares,
            "score": int(packet.get("score") or 0),
            "confidence": str(packet.get("confidence") or "LOW"),
            "reasons": [str(x) for x in (packet.get("reasons") or [])][:20],
            "simulationOnly": True,
            "brokerSubmitted": False,
        }
        if sanitized["indicativeLimitCAD"] <= 0:
            raise ApprovalPanelError("Indicative limit must be positive")

        digest = hashlib.sha256(
            json.dumps(sanitized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        challenge = issue_approval_challenge(
            proposal_id,
            expires_at=expires_at,
            proposal_digest=digest,
            path=self.ledger_path,
        )
        self._reviews[proposal_id] = {
            "packet": sanitized,
            "approval_token": challenge.approval_token,
        }
        return self.review_card(proposal_id)

    def review_card(self, proposal_id: str) -> Dict[str, Any]:
        item = self._reviews.get(proposal_id)
        if not item:
            raise ApprovalPanelError("Review is not available in this panel session")
        p = item["packet"]
        status = proposal_status(proposal_id, self.ledger_path)
        return {
            "proposal_id": proposal_id,
            "state": status["state"],
            "symbol": "CSU.TO",
            "action": p["action"],
            "quantity": 1,
            "order_type": "REVIEW_ONLY",
            "limit_price_cad": p["indicativeLimitCAD"],
            "expires_at": p["expiresAt"],
            "role": p["role"],
            "current_shares": p["currentShares"],
            "target_shares": p["targetShares"],
            "score": p["score"],
            "confidence": p["confidence"],
            "reasons": p["reasons"],
            "quote_as_of": None,
            "snapshot_as_of": None,
            "broker_submission_enabled": False,
            "simulation_only": True,
        }

    def approve_review(self, proposal_id: str) -> Dict[str, Any]:
        item = self._reviews.get(proposal_id)
        if not item:
            raise ApprovalPanelError("Review is not available in this panel session")
        approve_proposal(
            proposal_id,
            item["approval_token"],
            path=self.ledger_path,
        )
        return {
            "proposal": self.review_card(proposal_id),
            "approved_review": True,
            "broker_submission_enabled": False,
        }

    def reject_review(self, proposal_id: str) -> Dict[str, Any]:
        if proposal_id not in self._reviews:
            raise ApprovalPanelError("Review is not available in this panel session")
        reject_proposal(proposal_id, path=self.ledger_path)
        return self.review_card(proposal_id)

    def card(self, proposal_id: str) -> Dict[str, Any]:
        item = self._pending.get(proposal_id)
        if not item:
            raise ApprovalPanelError("Proposal is not available in this panel session")
        order = item["order"]
        status = proposal_status(proposal_id, self.ledger_path)
        review = item["review"]
        return {
            "proposal_id": proposal_id,
            "state": status["state"],
            "symbol": "CSU.TO",
            "action": order["action"],
            "quantity": 1,
            "order_type": "LIMIT",
            "limit_price_cad": order["price"],
            "expires_at": item["expires_at"],
            "role": review.get("role"),
            "current_shares": review.get("current_shares"),
            "target_shares": review.get("target_shares"),
            "score": review.get("score"),
            "confidence": review.get("confidence"),
            "reasons": review.get("reasons") or [],
            "quote_as_of": review.get("quote_as_of"),
            "snapshot_as_of": review.get("snapshot_as_of"),
            "broker_submission_enabled": False,
        }

    def list_cards(self):
        cards = [self.review_card(pid) for pid in list(self._reviews)]
        cards.extend(self.card(pid) for pid in list(self._pending))
        return cards

    def scout_research_cards(self):
        try:
            raw = json.loads(self.scout_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        cards = raw.get("researchCards") if isinstance(raw, dict) else None
        if not isinstance(cards, list):
            return []

        safe = []
        for card in cards[:5]:
            if not isinstance(card, dict):
                continue
            symbol = str(card.get("symbol") or "").upper()
            if not symbol.endswith(":TSX") or symbol == "CSU:TSX":
                continue
            scout = card.get("scout") if isinstance(card.get("scout"), dict) else {}
            agenda = card.get("researchAgenda") if isinstance(card.get("researchAgenda"), dict) else {}
            authority = card.get("authority") if isinstance(card.get("authority"), dict) else {}
            safe.append({
                "symbol": symbol,
                "score": scout.get("score"),
                "tier": scout.get("tier"),
                "stage": scout.get("stage") or "RESEARCH_REQUIRED",
                "reasons": [str(x) for x in (scout.get("reasons") or [])][:8],
                "risk_flags": [str(x) for x in (scout.get("riskFlags") or [])][:8],
                "questions": [str(x) for x in (agenda.get("questions") or [])][:12],
                "research_required": True,
                "trade_eligible": False,
                "broker_submission_enabled": False,
                "automatic_promotion": False,
                "source_policy": agenda.get("evidenceRequirements") or {},
            })
        return safe

    def approve(self, proposal_id: str) -> Dict[str, Any]:
        item = self._pending.get(proposal_id)
        if not item:
            raise ApprovalPanelError("Proposal is not available in this panel session")
        approve_proposal(
            proposal_id,
            item["approval_token"],
            path=self.ledger_path,
        )
        envelope = build_approved_dry_run(item["order"], ledger_path=self.ledger_path)
        return {
            "proposal": self.card(proposal_id),
            "dry_run": envelope.as_dict(),
        }

    def reject(self, proposal_id: str) -> Dict[str, Any]:
        if proposal_id not in self._pending:
            raise ApprovalPanelError("Proposal is not available in this panel session")
        reject_proposal(proposal_id, path=self.ledger_path)
        return self.card(proposal_id)


def _html(session_token: str) -> str:
    token = json.dumps(session_token)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Cache-Control" content="no-store">
<title>RUNLU CSU Approval</title>
<style>
:root{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#171717;background:#f5f5f2}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:760px;margin:auto;padding:24px}}
h1{{font-size:30px;margin:8px 0}}.muted{{color:#666}}.banner{{padding:12px 14px;border:1px solid #d2d2cb;border-radius:14px;background:#fff;margin:18px 0}}
.card{{background:#fff;border:1px solid #dcdcd5;border-radius:20px;padding:18px;margin:16px 0;box-shadow:0 4px 20px rgba(0,0,0,.03)}}
.action{{font-size:30px;font-weight:750;margin:8px 0}}.price{{font-size:24px;font-weight:650}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}}
.k{{font-size:12px;color:#777;text-transform:uppercase;letter-spacing:.06em}}.v{{font-size:17px;margin-top:3px}}
button{{font:inherit;border-radius:999px;padding:11px 18px;border:1px solid #bbb;background:white;cursor:pointer}}
button.primary{{background:#171717;color:white;border-color:#171717}}button:disabled{{opacity:.45;cursor:not-allowed}}
.row{{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap}}ul{{padding-left:21px}}code{{font-size:12px;word-break:break-all}}
</style></head><body><main>
<div class="muted">RUNLU · LOCALHOST ONLY</div>
<h1>CSU Trade Approval / 交易审批</h1>
<div class="banner"><b>LOCAL REVIEW ONLY</b> · 当前页面不会向券商提交订单。批准只记录本机审核结果；模拟订单卡片仍只生成 dry-run。</div>
<div id="cards"><div class="muted">Waiting for a proposal…</div></div>
<h1 style="font-size:24px;margin-top:34px">Scout Research Queue / 调研候选</h1>
<div class="banner"><b>RESEARCH ONLY</b> · Scout 候选不能在这里获得交易权限，必须先完成咱俩的联合调研。</div>
<div id="research"><div class="muted">No Scout research queue yet.</div></div>
</main><script>
const SESSION={token};
const esc=x=>String(x??"—");
async function api(path,body){{
 const r=await fetch(path,{{method:body?"POST":"GET",headers:{{"X-Approval-Session":SESSION,...(body?{{"content-type":"application/json"}}:{{}})}},body:body?JSON.stringify(body):undefined,cache:"no-store"}});
 const d=await r.json(); if(!r.ok) throw new Error(d.error||"Request failed"); return d;
}}
function cell(k,v){{const d=document.createElement("div");const a=document.createElement("div");a.className="k";a.textContent=k;const b=document.createElement("div");b.className="v";b.textContent=esc(v);d.append(a,b);return d}}
function renderCard(x){{
 const c=document.createElement("div");c.className="card";
 const id=document.createElement("code");id.textContent=x.proposal_id;c.append(id);
 const a=document.createElement("div");a.className="action";a.textContent=x.action+" 1 "+x.symbol;c.append(a);
 const p=document.createElement("div");p.className="price";p.textContent="Limit C$"+Number(x.limit_price_cad).toLocaleString(undefined,{{maximumFractionDigits:2}});c.append(p);
 const g=document.createElement("div");g.className="grid";
 g.append(cell("State",x.state),cell("Role",x.role),cell("Shares",esc(x.current_shares)+" → "+esc(x.target_shares)),cell("Expires",x.expires_at),cell("Score",x.score),cell("Confidence",x.confidence));c.append(g);
 if(x.reasons?.length){{const ul=document.createElement("ul");x.reasons.forEach(r=>{{const li=document.createElement("li");li.textContent=esc(r);ul.append(li)}});c.append(ul)}}
 const row=document.createElement("div");row.className="row";
 const yes=document.createElement("button");yes.className="primary";yes.textContent="APPROVE / 批准";
 const no=document.createElement("button");no.textContent="REJECT / 拒绝";
 const pending=x.state==="PENDING_APPROVAL";yes.disabled=!pending;no.disabled=!pending;
 const reviewOnly=x.order_type==="REVIEW_ONLY";
 yes.onclick=async()=>{{const msg=reviewOnly?"Approve this simulation-only CSU decision review?":"Approve this exact CSU limit-order proposal? No broker order will be sent in this version.";if(!confirm(msg))return;try{{await api(reviewOnly?"/api/approve-review":"/api/approve",{{proposal_id:x.proposal_id}});await load()}}catch(e){{alert(e.message)}}}};
 no.onclick=async()=>{{if(!confirm("Reject this proposal?"))return;try{{await api(reviewOnly?"/api/reject-review":"/api/reject",{{proposal_id:x.proposal_id}});await load()}}catch(e){{alert(e.message)}}}};
 row.append(yes,no);c.append(row);return c
}}
function renderResearch(x){{
 const c=document.createElement("div");c.className="card";
 const title=document.createElement("div");title.className="action";title.textContent=x.symbol+" · "+esc(x.score);c.append(title);
 const g=document.createElement("div");g.className="grid";
 g.append(cell("Tier",x.tier),cell("Stage",x.stage),cell("Trade Eligible","NO"),cell("Auto Promotion","NO"));c.append(g);
 if(x.reasons?.length){{const h=document.createElement("div");h.className="k";h.style.marginTop="14px";h.textContent="Why Scout found it";c.append(h);const ul=document.createElement("ul");x.reasons.forEach(r=>{{const li=document.createElement("li");li.textContent=esc(r);ul.append(li)}});c.append(ul)}}
 if(x.risk_flags?.length){{const h=document.createElement("div");h.className="k";h.textContent="Risk flags";c.append(h);const ul=document.createElement("ul");x.risk_flags.forEach(r=>{{const li=document.createElement("li");li.textContent=esc(r);ul.append(li)}});c.append(ul)}}
 if(x.questions?.length){{const d=document.createElement("details");const s=document.createElement("summary");s.textContent="Research questions / 调研问题";d.append(s);const ul=document.createElement("ul");x.questions.forEach(q=>{{const li=document.createElement("li");li.textContent=esc(q);ul.append(li)}});d.append(ul);c.append(d)}}
 return c
}}
async function load(){{try{{const d=await api("/api/pending");const root=document.getElementById("cards");root.replaceChildren();if(!d.proposals.length){{const m=document.createElement("div");m.className="muted";m.textContent="Waiting for a proposal…";root.append(m)}}else d.proposals.forEach(x=>root.append(renderCard(x)))}}catch(e){{document.getElementById("cards").textContent=e.message}}
 try{{const d=await api("/api/scout/research");const root=document.getElementById("research");root.replaceChildren();if(!d.candidates.length){{const m=document.createElement("div");m.className="muted";m.textContent="No Scout research queue yet.";root.append(m)}}else d.candidates.forEach(x=>root.append(renderResearch(x)))}}catch(e){{document.getElementById("research").textContent=e.message}}
}}
load();setInterval(load,2500);
</script></body></html>"""


def make_handler(state: PanelState, session_token: str, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "RUNLU-CSU-Approval/1"

        def log_message(self, fmt, *args):
            return

        def _local(self) -> bool:
            if self.headers.get("Host") not in allowed_hosts:
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin in allowed_origins

        def _api_auth(self) -> bool:
            return self._local() and secrets.compare_digest(
                self.headers.get("X-Approval-Session") or "", session_token
            )

        def _headers(self, status: int, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()

        def _json(self, value: Dict[str, Any], status: int = 200):
            self._headers(status, "application/json; charset=utf-8")
            self.wfile.write(json.dumps(value).encode("utf-8"))

        def _body(self) -> Dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError as exc:
                raise ApprovalPanelError("Invalid content length") from exc
            if length <= 0 or length > MAX_BODY:
                raise ApprovalPanelError("Invalid request size")
            try:
                value = json.loads(self.rfile.read(length))
            except Exception as exc:
                raise ApprovalPanelError("Invalid JSON") from exc
            if not isinstance(value, dict):
                raise ApprovalPanelError("JSON object required")
            return value

        def do_GET(self):
            path = urlparse(self.path).path
            if not self._local():
                self._json({"error": "Local requests only"}, 403)
                return
            if path == "/":
                body = _html(session_token).encode("utf-8")
                self._headers(200, "text/html; charset=utf-8")
                self.wfile.write(body)
                return
            if path == "/api/pending":
                if not self._api_auth():
                    self._json({"error": "Forbidden"}, 403)
                    return
                self._json({"proposals": state.list_cards(), "broker_submission_enabled": False})
                return
            if path == "/api/scout/research":
                if not self._api_auth():
                    self._json({"error": "Forbidden"}, 403)
                    return
                self._json({
                    "candidates": state.scout_research_cards(),
                    "research_only": True,
                    "trade_eligible": False,
                    "broker_submission_enabled": False,
                })
                return
            self._json({"error": "Not found"}, 404)

        def do_POST(self):
            if not self._api_auth():
                self._json({"error": "Forbidden"}, 403)
                return
            path = urlparse(self.path).path
            try:
                body = self._body()
                if path == "/api/register-review":
                    self._json({"proposal": state.register_review(body)})
                elif path == "/api/approve-review":
                    self._json(state.approve_review(str(body.get("proposal_id") or "")))
                elif path == "/api/reject-review":
                    self._json({"proposal": state.reject_review(str(body.get("proposal_id") or ""))})
                elif path == "/api/register":
                    self._json({"proposal": state.register(body)})
                elif path == "/api/approve":
                    self._json(state.approve(str(body.get("proposal_id") or "")))
                elif path == "/api/reject":
                    self._json({"proposal": state.reject(str(body.get("proposal_id") or ""))})
                else:
                    self._json({"error": "Not found"}, 404)
            except (ApprovalPanelError, ApprovalLedgerError, ExecutionBridgeError) as exc:
                self._json({"error": str(exc)}, 409)

        def do_PUT(self):
            self._json({"error": "Method blocked"}, 405)

        do_PATCH = do_PUT
        do_DELETE = do_PUT
        do_OPTIONS = do_PUT

    return Handler


def main() -> None:
    port = int(os.environ.get("CSU_APPROVAL_PORT", str(DEFAULT_PORT)))
    ledger = Path(os.environ.get("CSU_PRIVATE_LEDGER", str(DEFAULT_LEDGER))).expanduser()
    session_token = secrets.token_urlsafe(32)
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(session_token, encoding="utf-8")
    os.chmod(SESSION_FILE, 0o600)
    state = PanelState(ledger)
    server = ThreadingHTTPServer((HOST, port), make_handler(state, session_token, port))
    print(f"CSU local approval panel: http://127.0.0.1:{port}")
    print("Live brokerage submission: DISABLED")
    try:
        server.serve_forever()
    finally:
        try:
            SESSION_FILE.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
