"""Performance accounting for completed, chronological paper backtest trades."""
from datetime import date
from decimal import Decimal as D, InvalidOperation

def summarize(result, *, starting_cash=D("2000")):
    try:
        starting_cash=D(str(starting_cash))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("INVALID_STARTING_CASH") from exc
    if not starting_cash.is_finite() or starting_cash <= 0:
        raise ValueError("INVALID_STARTING_CASH")
    if not isinstance(result,dict):
        raise ValueError("MISSING_TRADES")
    trades=result.get("trades")
    if not isinstance(trades,list):
        raise ValueError("MISSING_TRADES")
    equity=starting_cash
    peak=equity
    max_drawdown=D("0")
    wins=losses=breakeven=0
    gross_wins=gross_losses=D("0")
    last_exit=None
    for trade in trades:
        try:
            pnl=D(str(trade["net_pnl"]))
            entry=date.fromisoformat(trade["entry_date"])
            exit_date=date.fromisoformat(trade["exit_date"])
        except (KeyError, InvalidOperation, ValueError, TypeError, AttributeError) as exc:
            raise ValueError("INVALID_TRADE") from exc
        if not pnl.is_finite() or entry>exit_date:
            raise ValueError("INVALID_TRADE")
        if last_exit is not None and entry<last_exit:
            raise ValueError("OUT_OF_ORDER_TRADES")
        last_exit=exit_date
        equity+=pnl
        if pnl>0:
            wins+=1
            gross_wins+=pnl
        elif pnl<0:
            losses+=1
            gross_losses-=pnl
        else:
            breakeven+=1
        peak=max(peak,equity)
        max_drawdown=max(max_drawdown,peak-equity)
    n=len(trades)
    return {
        "trades":n,
        "wins":wins,
        "losses":losses,
        "breakeven":breakeven,
        "win_rate_pct":str(D(wins)*100/D(n)) if n else None,
        "net_pnl":str(equity-starting_cash),
        "ending_equity":str(equity),
        "max_closed_trade_drawdown":str(max_drawdown),
        "profit_factor":str(gross_wins/gross_losses) if gross_losses else None,
        "return_pct":str((equity/starting_cash-D("1"))*100)
    }
