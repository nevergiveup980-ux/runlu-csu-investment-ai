from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import floor

from trade_lot import TradingMode


class BuyDecision(str, Enum):
    BUY_CANDIDATE = "BUY CANDIDATE"
    WATCH = "WATCH"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class BuySnapshot:
    price: float
    sma20: float | None = None
    sma50: float | None = None
    rsi14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    atr14: float | None = None
    support20: float | None = None
    resistance20: float | None = None
    volume_ratio: float | None = None


@dataclass(frozen=True)
class BuyGateResult:
    decision: BuyDecision
    score: int
    required_score: int
    reasons: tuple[str, ...]
    limit_price_ceiling: float


MODE_REQUIRED_SCORE = {
    TradingMode.INTRADAY: 4,
    TradingMode.SWING: 4,
    TradingMode.POSITION: 5,
}

# Do not chase far above SMA20. Position mode is intentionally stricter.
MODE_MAX_SMA20_PREMIUM = {
    TradingMode.INTRADAY: 0.05,
    TradingMode.SWING: 0.06,
    TradingMode.POSITION: 0.04,
}


def evaluate_buy_gate(snapshot: BuySnapshot, mode: TradingMode = TradingMode.SWING) -> BuyGateResult:
    if snapshot.price <= 0:
        raise ValueError("price must be positive")

    score = 0
    reasons: list[str] = []
    max_premium = MODE_MAX_SMA20_PREMIUM[mode]

    # Hard anti-chase gate.
    if snapshot.sma20 and snapshot.sma20 > 0:
        premium = snapshot.price / snapshot.sma20 - 1
        if premium > max_premium:
            return BuyGateResult(
                decision=BuyDecision.BLOCK,
                score=-99,
                required_score=MODE_REQUIRED_SCORE[mode],
                reasons=(f"Price is {premium:.1%} above SMA20; anti-chase gate triggered",),
                limit_price_ceiling=snapshot.sma20 * (1 + max_premium),
            )
        if snapshot.price >= snapshot.sma20:
            score += 1
            reasons.append("Price is at/above SMA20 without excessive extension")
        else:
            score += 1
            reasons.append("Price is below SMA20, offering a less extended entry")

    if snapshot.sma20 and snapshot.sma50:
        if snapshot.sma20 >= snapshot.sma50:
            score += 1
            reasons.append("SMA20 is at/above SMA50")
        elif mode == TradingMode.POSITION:
            reasons.append("Longer trend confirmation is not yet present")

    if snapshot.rsi14 is not None:
        if 35 <= snapshot.rsi14 <= 60:
            score += 1
            reasons.append("RSI is in a constructive entry range")
        elif snapshot.rsi14 < 35:
            score += 1
            reasons.append("RSI is oversold; reversal confirmation is still required")
        elif snapshot.rsi14 >= 70:
            score -= 2
            reasons.append("RSI is overbought")
        else:
            reasons.append("RSI is neutral-to-elevated")

    if snapshot.macd is not None and snapshot.macd_signal is not None:
        if snapshot.macd >= snapshot.macd_signal:
            score += 1
            reasons.append("MACD is at/above signal")
        else:
            reasons.append("MACD has not confirmed upward momentum")

    if snapshot.support20 and snapshot.support20 > 0:
        distance = snapshot.price / snapshot.support20 - 1
        if 0 <= distance <= 0.05:
            score += 2
            reasons.append("Price is within 5% of 20-period support")
        elif distance <= 0.10:
            score += 1
            reasons.append("Price is within 10% of 20-period support")

    if snapshot.resistance20 and snapshot.resistance20 > snapshot.price:
        room = snapshot.resistance20 / snapshot.price - 1
        if room >= 0.08:
            score += 1
            reasons.append("At least 8% room remains to recent resistance")
        elif room < 0.03:
            score -= 1
            reasons.append("Price is too close to recent resistance")

    if snapshot.volume_ratio is not None and 1.0 <= snapshot.volume_ratio <= 2.5:
        score += 1
        reasons.append("Volume participation is supportive without being extreme")

    required = MODE_REQUIRED_SCORE[mode]
    decision = BuyDecision.BUY_CANDIDATE if score >= required else BuyDecision.WATCH

    # A candidate ceiling gives the later order layer a conservative LIMIT reference.
    ceiling = snapshot.price
    if snapshot.sma20 and snapshot.sma20 > 0:
        ceiling = min(ceiling, snapshot.sma20 * (1 + max_premium))

    return BuyGateResult(
        decision=decision,
        score=score,
        required_score=required,
        reasons=tuple(reasons),
        limit_price_ceiling=round(ceiling, 4),
    )


def position_size_plan(
    *,
    available_cash: float,
    limit_price: float,
    max_trade_cash_pct: float = 0.20,
    max_quantity: int = 1,
) -> dict:
    """Return a conservative sizing plan; this function never places an order."""
    if available_cash < 0:
        raise ValueError("available_cash cannot be negative")
    if limit_price <= 0:
        raise ValueError("limit_price must be positive")
    if not 0 < max_trade_cash_pct <= 1:
        raise ValueError("max_trade_cash_pct must be in (0, 1]")
    if max_quantity <= 0:
        raise ValueError("max_quantity must be positive")

    cash_cap = available_cash * max_trade_cash_pct
    affordable = floor(cash_cap / limit_price)
    qty = max(0, min(affordable, max_quantity))
    return {
        "quantity": qty,
        "cash_cap": round(cash_cap, 2),
        "estimated_notional": round(qty * limit_price, 2),
        "reason": "NO CAPACITY" if qty == 0 else "WITHIN CASH AND QUANTITY CAPS",
    }
