"""Project 200 paper-only risk checks. No brokerage imports or live order path."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

D = Decimal
START = D("2000")
TRADE_RISK_LIMIT = D("20")
DAILY_LOSS_LIMIT = D("40")
DRAWDOWN_LIMIT = D("200")
MAX_EXPOSURE = D("1800")
MIN_CASH_RESERVE = D("200")

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

def _finite(value):
    try:
        result = D(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None

def check_order(portfolio: Portfolio, order: Proposal, *, mode: str = "PAPER"):
    reasons = []
    if mode != "PAPER":
        reasons.append("LIVE_DISABLED")
    if (not isinstance(order.symbol, str) or not order.symbol.strip()
            or type(order.quantity) is not int or order.quantity <= 0):
        reasons.append("INVALID_ORDER")
        return reasons
    entry, stop = _finite(order.entry), _finite(order.stop)
    if entry is None or stop is None or entry <= 0 or stop <= 0:
        reasons.append("INVALID_ORDER")
        return reasons
    if (type(order.quote_age_seconds) is not int or order.quote_age_seconds < 0
            or order.quote_age_seconds > 60):
        reasons.append("STALE_QUOTE")
    cash = _finite(portfolio.settled_cash)
    equity = _finite(portfolio.equity)
    daily = _finite(portfolio.daily_start_equity)
    exposure = _finite(portfolio.exposure)
    if any(x is None for x in (cash, equity, daily, exposure)) or cash < 0 or equity < 0 or daily < 0 or exposure < 0:
        reasons.append("INVALID_PORTFOLIO")
        return reasons
    if stop >= entry:
        reasons.append("INVALID_LONG_STOP")
    if order.quantity * max(entry - stop, D("0")) > TRADE_RISK_LIMIT:
        reasons.append("TRADE_RISK_LIMIT")
    notional = order.quantity * entry
    if notional > cash:
        reasons.append("INSUFFICIENT_SETTLED_CASH")
    if cash - notional < MIN_CASH_RESERVE:
        reasons.append("CASH_RESERVE")
    if exposure + notional > MAX_EXPOSURE:
        reasons.append("EXPOSURE_LIMIT")
    if daily - equity >= DAILY_LOSS_LIMIT:
        reasons.append("DAILY_HALT")
    if START - equity >= DRAWDOWN_LIMIT:
        reasons.append("PORTFOLIO_HALT")
    return reasons
