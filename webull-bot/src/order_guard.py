from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os


class OrderRejected(ValueError):
    pass


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    quantity: Decimal
    limit_price: Decimal
    market: str = "US"
    instrument_type: str = "EQUITY"
    order_type: str = "LIMIT"
    time_in_force: str = "DAY"
    trading_session: str = "CORE"

    @property
    def estimated_notional(self) -> Decimal:
        return self.quantity * self.limit_price


def _decimal_env(name: str, default: str) -> Decimal:
    raw = os.getenv(name, default).strip()
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise OrderRejected(f"Invalid {name}: {raw}") from exc
    if value <= 0:
        raise OrderRejected(f"{name} must be positive")
    return value


def allowed_symbols() -> set[str]:
    raw = os.getenv("RUNLU_ALLOWED_SYMBOLS", "").strip()
    return {s.strip().upper() for s in raw.split(",") if s.strip()}


def validate_order(intent: OrderIntent, *, environment: str = "sandbox") -> dict:
    """Validate a proposed order before any broker call.

    V2 deliberately supports only US equity LIMIT orders in Webull Sandbox.
    Live trading, short selling, market orders, extended-hours orders, and
    unapproved symbols are rejected here before credentials are used.
    """
    env = environment.strip().lower()
    if env != "sandbox":
        raise OrderRejected("Live trading is disabled in RUNLU Webull Bot V2")

    symbol = intent.symbol.strip().upper()
    side = intent.side.strip().upper()

    if intent.market != "US":
        raise OrderRejected("Only US market orders are allowed")
    if intent.instrument_type != "EQUITY":
        raise OrderRejected("Only equity orders are allowed")
    if side not in {"BUY", "SELL"}:
        raise OrderRejected("Only BUY and SELL are allowed; SHORT is disabled")
    if intent.order_type != "LIMIT":
        raise OrderRejected("Only LIMIT orders are allowed in V2")
    if intent.time_in_force != "DAY":
        raise OrderRejected("Only DAY time-in-force is allowed in V2")
    if intent.trading_session != "CORE":
        raise OrderRejected("Only regular-hours CORE trading is allowed in V2")
    if intent.quantity <= 0:
        raise OrderRejected("Quantity must be positive")
    if intent.limit_price <= 0:
        raise OrderRejected("Limit price must be positive")

    symbols = allowed_symbols()
    if not symbols:
        raise OrderRejected("RUNLU_ALLOWED_SYMBOLS is empty; no symbol is authorized")
    if symbol not in symbols:
        raise OrderRejected(f"{symbol} is not in RUNLU_ALLOWED_SYMBOLS")

    max_qty = _decimal_env("RUNLU_MAX_ORDER_QTY", "1")
    max_notional = _decimal_env("RUNLU_MAX_ORDER_NOTIONAL", "1000")
    if intent.quantity > max_qty:
        raise OrderRejected(f"Quantity {intent.quantity} exceeds max {max_qty}")
    if intent.estimated_notional > max_notional:
        raise OrderRejected(
            f"Estimated notional {intent.estimated_notional} exceeds max {max_notional}"
        )

    return {
        "approved": True,
        "environment": "sandbox",
        "symbol": symbol,
        "side": side,
        "quantity": str(intent.quantity),
        "limit_price": str(intent.limit_price),
        "estimated_notional": str(intent.estimated_notional),
        "market": "US",
        "instrument_type": "EQUITY",
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "support_trading_session": "CORE",
        "max_order_qty": str(max_qty),
        "max_order_notional": str(max_notional),
    }
