from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class OrderFillSnapshot:
    order_id: str
    symbol: str
    side: str
    status: str
    requested_quantity: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal | None

    @property
    def is_terminal(self) -> bool:
        return self.status.upper() in {"FILLED", "CANCELLED", "REJECTED", "EXPIRED"}

    @property
    def is_filled(self) -> bool:
        return self.status.upper() == "FILLED" and self.filled_quantity > 0


def _d(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def normalize_order(payload: dict[str, Any]) -> OrderFillSnapshot:
    avg_raw = (
        payload.get("average_fill_price")
        or payload.get("avg_fill_price")
        or payload.get("avgFilledPrice")
        or payload.get("filledAvgPrice")
    )
    return OrderFillSnapshot(
        order_id=str(payload.get("order_id") or payload.get("orderId") or payload.get("id") or ""),
        symbol=str(payload.get("symbol") or payload.get("ticker") or "").upper(),
        side=str(payload.get("side") or payload.get("action") or "").upper(),
        status=str(payload.get("status") or payload.get("orderStatus") or "UNKNOWN").upper(),
        requested_quantity=_d(payload.get("quantity") or payload.get("qty") or payload.get("totalQuantity")),
        filled_quantity=_d(payload.get("filled_quantity") or payload.get("filledQty") or payload.get("filledQuantity")),
        average_fill_price=_d(avg_raw) if avg_raw is not None else None,
    )


def reconcile(previous: OrderFillSnapshot | None, current: OrderFillSnapshot) -> dict:
    changed = previous is None or (
        previous.status != current.status
        or previous.filled_quantity != current.filled_quantity
        or previous.average_fill_price != current.average_fill_price
    )
    return {
        "changed": changed,
        "order_id": current.order_id,
        "status": current.status,
        "filled_quantity": str(current.filled_quantity),
        "average_fill_price": str(current.average_fill_price) if current.average_fill_price is not None else None,
        "terminal": current.is_terminal,
        "filled": current.is_filled,
    }
