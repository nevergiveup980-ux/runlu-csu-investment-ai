"""Project 200 paper-only risk checks. No brokerage imports or live order path."""
from dataclasses import dataclass
from decimal import Decimal

D = Decimal
START = D("2000")
TRADE_RISK_LIMIT = D("20")
DAILY_LOSS_LIMIT = D("40")
DRAWDOWN_LIMIT = D("200")
MAX_EXPOSURE = D("1800")

@dataclass(frozen=True)
class Portfolio:
    settled_cash: Decimal
    equity: Decimal
    daily_start_equity: Decimal
    exposure: Decimal

@dataclass(frozen=True)
class Proposal:
    symbol: str
    quantity: int
    entry: Decimal
    stop: Decimal
    quote_age_seconds: int

def check_order(portfolio: Portfolio, order: Proposal, *, mode: str = "PAPER"):
    reasons = []
    if mode != "PAPER":
        reasons.append("LIVE_DISABLED")
    if not order.symbol or order.quantity <= 0 or order.entry <= 0 or order.stop <= 0:
        reasons.append("INVALID_ORDER")
        return reasons
    if order.quote_age_seconds > 60 or order.quote_age_seconds < 0:
        reasons.append("STALE_QUOTE")
    if order.stop >= order.entry:
        reasons.append("INVALID_LONG_STOP")
    if order.quantity * max(order.entry - order.stop, D("0")) > TRADE_RISK_LIMIT:
        reasons.append("TRADE_RISK_LIMIT")
    notional = order.quantity * order.entry
    if notional > portfolio.settled_cash:
        reasons.append("INSUFFICIENT_SETTLED_CASH")
    if portfolio.exposure + notional > MAX_EXPOSURE:
        reasons.append("EXPOSURE_LIMIT")
    if portfolio.daily_start_equity - portfolio.equity >= DAILY_LOSS_LIMIT:
        reasons.append("DAILY_HALT")
    if START - portfolio.equity >= DRAWDOWN_LIMIT:
        reasons.append("PORTFOLIO_HALT")
    return reasons
