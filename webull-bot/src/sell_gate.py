from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Optional

from trade_lot import TradeLot, TradingMode


@dataclass(frozen=True)
class SellSignals:
    price: float
    sma20: Optional[float] = None
    sma50: Optional[float] = None
    rsi14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    volume_ratio: Optional[float] = None
    resistance20: Optional[float] = None
    atr14: Optional[float] = None
    major_risk_event: bool = False


@dataclass(frozen=True)
class SellDecision:
    allowed: bool
    action: str
    score: int
    min_sell_price: float
    unrealized_pct: float
    reasons: tuple[str, ...]
    risk_override: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _profit_floor_for_mode(mode: TradingMode) -> float:
    return {
        TradingMode.INTRADAY: 0.003,
        TradingMode.SWING: 0.015,
        TradingMode.POSITION: 0.03,
    }[mode]


def evaluate_sell(
    lot: TradeLot,
    signals: SellSignals,
    *,
    minimum_profit_pct: Optional[float] = None,
    exit_fee_buffer: float = 0.0,
) -> SellDecision:
    if signals.price <= 0:
        raise ValueError("price must be positive")
    if exit_fee_buffer < 0:
        raise ValueError("exit_fee_buffer cannot be negative")

    floor = _profit_floor_for_mode(lot.mode) if minimum_profit_pct is None else minimum_profit_pct
    if floor < 0:
        raise ValueError("minimum_profit_pct cannot be negative")

    break_even = lot.break_even_price
    min_sell_price = break_even * (1 + floor) + (exit_fee_buffer / lot.quantity)
    unrealized_pct = (signals.price / break_even - 1) * 100
    reasons: list[str] = []

    # Emergency override: do not let the no-loss rule turn into an unlimited-loss rule.
    if signals.major_risk_event:
        reasons.append("Major risk event detected; capital-preservation override enabled")
        return SellDecision(
            allowed=True,
            action="RISK EXIT / REVIEW",
            score=-99,
            min_sell_price=min_sell_price,
            unrealized_pct=unrealized_pct,
            reasons=tuple(reasons),
            risk_override=True,
        )

    # Normal discipline: never propose a routine sale below the configured profit floor.
    if signals.price < min_sell_price:
        reasons.append(
            f"Current price {signals.price:.2f} is below protected sell floor {min_sell_price:.2f}"
        )
        reasons.append("Routine SELL blocked; continue HOLD / REVIEW unless risk override is triggered")
        return SellDecision(
            allowed=False,
            action="HOLD / REVIEW",
            score=0,
            min_sell_price=min_sell_price,
            unrealized_pct=unrealized_pct,
            reasons=tuple(reasons),
        )

    score = 0
    if signals.sma20 is not None:
        if signals.price < signals.sma20:
            score += 1
            reasons.append("Price is below SMA20")
        else:
            reasons.append("Price remains above SMA20")

    if signals.sma20 is not None and signals.sma50 is not None:
        if signals.sma20 < signals.sma50:
            score += 1
            reasons.append("SMA20 is below SMA50")

    if signals.rsi14 is not None:
        if signals.rsi14 >= 72:
            score += 1
            reasons.append("RSI is elevated")
        elif signals.rsi14 <= 45:
            score += 1
            reasons.append("RSI has weakened")

    if signals.macd is not None and signals.macd_signal is not None and signals.macd < signals.macd_signal:
        score += 1
        reasons.append("MACD is below signal")

    if signals.volume_ratio is not None and signals.volume_ratio >= 1.5:
        score += 1
        reasons.append("Relative volume is elevated")

    if signals.resistance20 is not None and signals.price >= signals.resistance20 * 0.99:
        score += 1
        reasons.append("Price is near 20-period resistance")

    threshold = {
        TradingMode.INTRADAY: 2,
        TradingMode.SWING: 3,
        TradingMode.POSITION: 4,
    }[lot.mode]

    if score >= threshold:
        action = "SELL CANDIDATE"
        allowed = True
    else:
        action = "HOLD / TRAIL"
        allowed = False
        reasons.append(f"Technical sell score {score} is below {lot.mode.value} threshold {threshold}")

    return SellDecision(
        allowed=allowed,
        action=action,
        score=score,
        min_sell_price=min_sell_price,
        unrealized_pct=unrealized_pct,
        reasons=tuple(reasons),
    )
