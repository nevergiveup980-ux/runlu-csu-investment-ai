"""Fail-closed daily OHLCV quality gates for research CSVs."""
from datetime import date
from decimal import Decimal as D, InvalidOperation
from backtest import load_bars

def validate_history(path, *, min_bars=120, max_gap_days=7):
    if type(min_bars) is not int or min_bars<8:
        raise ValueError("INVALID_MIN_BARS")
    if type(max_gap_days) is not int or max_gap_days<1:
        raise ValueError("INVALID_MAX_GAP")
    bars=load_bars(path)
    if len(bars)<min_bars:
        raise ValueError("INSUFFICIENT_HISTORY")
    dates=[]
    for row in bars:
        try:
            day=date.fromisoformat(row["date"])
        except (ValueError,TypeError) as exc:
            raise ValueError("INVALID_DATE") from exc
        dates.append(day)
        if row["high"]<row["low"] or row["volume"]<0:
            raise ValueError("INVALID_OHLCV")
    gaps=[(b-a).days for a,b in zip(dates,dates[1:])]
    if any(g<=0 for g in gaps):
        raise ValueError("NON_INCREASING_DATES")
    if any(g>max_gap_days for g in gaps):
        raise ValueError("DATA_GAP")
    return bars

def walk_forward(bars, *, train_fraction=D("0.7"), fee=D("1"), spread_bps=D("5")):
    from backtest import backtest
    try:
        train_fraction=D(str(train_fraction))
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise ValueError("INVALID_SPLIT") from exc
    if not train_fraction.is_finite() or not D("0.5")<=train_fraction<=D("0.9"):
        raise ValueError("INVALID_SPLIT")
    cut=int(len(bars)*train_fraction)
    if cut<8 or len(bars)-cut<8:
        raise ValueError("INSUFFICIENT_SPLIT")
    train=backtest(bars[:cut],fee=fee,spread_bps=spread_bps)
    # Supply only prior lookback context. Test trades are filtered by entry date.
    context=4
    test_bars=bars[cut-context:]
    test=backtest(test_bars,fee=fee,spread_bps=spread_bps)
    test_trades=[t for t in test["trades"] if t["entry_date"]>=bars[cut]["date"]]
    net=sum((D(t["net_pnl"]) for t in test_trades),D("0"))
    return {"train":train,"test":{"trade_count":len(test_trades),"net_pnl":str(net),"trades":test_trades},"split_date":bars[cut]["date"]}
