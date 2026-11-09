"""Offline fee/spread sensitivity grid; research-only, no market downloads or orders."""
from decimal import Decimal as D, InvalidOperation
from data_validation import validate_history, walk_forward

def _cost(value):
    try:
        n=D(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("INVALID_COST") from exc
    if not n.is_finite() or n<0:
        raise ValueError("INVALID_COST")
    return n

def sensitivity(csv_path, *, fees=("0","1","2"), spreads_bps=("0","5","20"), min_bars=120):
    bars=validate_history(csv_path,min_bars=min_bars)
    if not fees or not spreads_bps:
        raise ValueError("EMPTY_GRID")
    fee_values=[_cost(v) for v in fees]
    spread_values=[_cost(v) for v in spreads_bps]
    if any(v>=D("20000") for v in spread_values):
        raise ValueError("INVALID_SPREAD")
    scenarios=[]
    for fee in fee_values:
        for spread in spread_values:
            split=walk_forward(bars,fee=fee,spread_bps=spread)
            result=split["test"]
            scenarios.append({"fee_per_side_usd":str(fee),"spread_bps":str(spread),
                              "test_trades":result["trade_count"],"test_net_pnl_usd":result["net_pnl"]})
    positive=sum(D(s["test_net_pnl_usd"])>0 for s in scenarios)
    return {"mode":"RESEARCH_ONLY","scenario_count":len(scenarios),
            "positive_test_scenarios":positive,"all_scenarios_positive":positive==len(scenarios),
            "split_date":split["split_date"],"scenarios":scenarios,
            "warning":"Cost sensitivity on daily bars only; not live fills, intraday stops, or future returns."}
