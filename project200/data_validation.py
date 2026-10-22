"""Fail-closed daily OHLCV quality gates for research CSVs."""
from datetime import date
from decimal import Decimal as D
from backtest import load_bars

def validate_history(path, *, min_bars=120, max_gap_days=7):
    bars=load_bars(path)
    if len(bars)<min_bars:
        raise ValueError("INSUFFICIENT_HISTORY")
    dates=[]
    for row in bars:
        try:
            day=date.fromisoformat(row["date"])
        except ValueError as exc:
            raise ValueError("INVALID_DATE") from exc
        dates.append(day)
        if row["high"]<row["low"] or row["volume"]<0:
            raise ValueError("INVALID_OHLCV")
    if any((b-a).days>max_gap_days for a,b in zip(dates,dates[1:])):
        raise ValueError("DATA_GAP")
    return bars

def walk_forward(bars, *, train_fraction=D("0.7"), fee=D("1"), spread_bps=D("5")):
    from backtest import backtest
    if not D("0.5")<=train_fraction<=D("0.9"):
        raise ValueError("INVALID_SPLIT")
    cut=int(len(bars)*train_fraction)
    if cut<8 or len(bars)-cut<8:
        raise ValueError("INSUFFICIENT_SPLIT")
    train=backtest(bars[:cut],fee=fee,spread_bps=spread_bps)
    # Supply only the prior lookback context, but signals are evaluated on
    # out-of-sample dates by filtering the trade entry date.
    context=4
    test_bars=bars[cut-context:]
    test=backtest(test_bars,fee=fee,spread_bps=spread_bps)
    test_trades=[t for t in test["trades"] if t["entry_date"]>=bars[cut]["date"]]
    net=sum((D(t["net_pnl"]) for t in test_trades),D("0"))
    return {"train":train,"test":{"trade_count":len(test_trades),"net_pnl":str(net),"trades":test_trades},"split_date":bars[cut]["date"]}
