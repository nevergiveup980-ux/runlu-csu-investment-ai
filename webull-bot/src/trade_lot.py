from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class TradingMode(str, Enum):
    POSITION = "POSITION"
    SWING = "SWING"
    INTRADAY = "INTRADAY"


@dataclass(frozen=True)
class TradeLot:
    lot_id: str
    symbol: str
    quantity: float
    entry_price: float
    entry_time: str
    mode: TradingMode = TradingMode.SWING
    entry_fees: float = 0.0
    notes: str = ""

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.entry_price + self.entry_fees

    @property
    def break_even_price(self) -> float:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        return self.cost_basis / self.quantity

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        payload["break_even_price"] = self.break_even_price
        payload["cost_basis"] = self.cost_basis
        return payload


def new_trade_lot(
    *,
    lot_id: str,
    symbol: str,
    quantity: float,
    entry_price: float,
    mode: TradingMode = TradingMode.SWING,
    entry_fees: float = 0.0,
    notes: str = "",
    entry_time: Optional[str] = None,
) -> TradeLot:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if entry_fees < 0:
        raise ValueError("entry_fees cannot be negative")

    return TradeLot(
        lot_id=lot_id,
        symbol=symbol.upper().strip(),
        quantity=quantity,
        entry_price=entry_price,
        entry_time=entry_time or datetime.now(timezone.utc).isoformat(),
        mode=mode,
        entry_fees=entry_fees,
        notes=notes,
    )
