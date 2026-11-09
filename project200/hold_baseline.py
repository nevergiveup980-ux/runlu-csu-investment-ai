"""Held-out buy-and-hold comparison for daily-bar research; no live orders."""
from decimal import Decimal as D, InvalidOperation
from data_validation import validate_history

def baseline(csv_path, *, min_bars=120, train_fraction=D("0.7"),
             starting_cash=D("2000"), reserve=D("200"), fee=D("1"), spread_bps=D("5")):
    bars=validate_history(csv_path,min_bars=min_bars)
    try:
        fraction,cash,hold,commission,spread=(D(str(x)) for x in
            (train_fraction,starting_cash,reserve,fee,spread_bps))
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise ValueError("INVALID_BASELINE_PARAMETERS") from exc
    if (not all(x.is_finite() for x in (fraction,cash,hold,commission,spread))
            or not D("0.5")<=fraction<=D("0.9") or cash<=hold
            or hold<0 or commission<0 or spread<0 or spread>=D("20000")):
        raise ValueError("INVALID_BASELINE_PARAMETERS")
    cut=int(len(bars)*fraction)
    if cut<8 or len(bars)-cut<2:
        raise ValueError("INSUFFICIENT_SPLIT")
    # Same first out-of-sample open as the strategy; liquidate at last available close.
    entry=bars[cut]["open"]*(D("1")+spread/D("20000"))
    exit_price=bars[-1]["close"]*(D("1")-spread/D("20000"))
    qty=int(max(D("0"),(cash-hold-commission)//entry))
    pnl=D("0") if qty==0 else D(qty)*(exit_price-entry)-commission*2
    return {"mode":"RESEARCH_ONLY","baseline":"BUY_AND_HOLD_HELD_OUT",
            "entry_date":bars[cut]["date"],"exit_date":bars[-1]["date"],
            "shares":qty,"net_pnl":str(pnl),
            "ending_equity":str(cash+pnl),
            "limitations":"Assumes fractional-free shares, fixed spread and fee; excludes dividends, FX, tax and corporate actions."}
