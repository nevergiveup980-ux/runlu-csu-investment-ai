from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    buying_power: Decimal
    cash_balance: Decimal
    market_value: Decimal


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    quantity: Decimal
    average_price: Decimal | None = None


def _d(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def normalize_account(account_id: str, payload: dict[str, Any]) -> AccountSnapshot:
    return AccountSnapshot(
        account_id=account_id,
        buying_power=_d(payload.get("buying_power") or payload.get("buyingPower")),
        cash_balance=_d(payload.get("cash_balance") or payload.get("cashBalance") or payload.get("cash")),
        market_value=_d(payload.get("market_value") or payload.get("marketValue")),
    )


def normalize_positions(rows: Iterable[dict[str, Any]]) -> list[PositionSnapshot]:
    out: list[PositionSnapshot] = []
    for row in rows:
        symbol = str(row.get("symbol") or row.get("ticker") or "").strip().upper()
        if not symbol:
            continue
        avg_raw = row.get("average_price") or row.get("averagePrice") or row.get("cost_price") or row.get("costPrice")
        out.append(
            PositionSnapshot(
                symbol=symbol,
                quantity=_d(row.get("quantity") or row.get("qty")),
                average_price=_d(avg_raw) if avg_raw is not None else None,
            )
        )
    return out


def preflight_buy(*, account: AccountSnapshot, estimated_notional: Decimal) -> dict:
    if estimated_notional <= 0:
        return {"approved": False, "reason": "non-positive order notional"}
    if account.buying_power < estimated_notional:
        return {
            "approved": False,
            "reason": "insufficient buying power",
            "buying_power": str(account.buying_power),
            "estimated_notional": str(estimated_notional),
        }
    return {"approved": True, "buying_power": str(account.buying_power)}


def preflight_sell(*, symbol: str, quantity: Decimal, positions: list[PositionSnapshot]) -> dict:
    target = symbol.upper().strip()
    held = sum((p.quantity for p in positions if p.symbol == target), Decimal("0"))
    if quantity <= 0:
        return {"approved": False, "reason": "non-positive sell quantity"}
    if held < quantity:
        return {
            "approved": False,
            "reason": "insufficient position quantity",
            "held_quantity": str(held),
            "requested_quantity": str(quantity),
        }
    return {"approved": True, "held_quantity": str(held)}
