"""Conservative interpretation of offline research evidence, never trade approval."""
from decimal import Decimal as D, InvalidOperation

def _finite(value):
    try:
        v=D(str(value))
        return v if v.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None

def assess(report, sensitivity_report, *, min_test_trades=20):
    failures=[]
    if not isinstance(report,dict) or report.get("mode")!="RESEARCH_ONLY" or not isinstance(report.get("audit"),dict) or report["audit"].get("audited") is not True:
        failures.append("UNVERIFIED_RESEARCH_REPORT")
    test=report.get("test") if isinstance(report,dict) else None
    if not isinstance(test,dict):
        test={}
    trades=test.get("trades")
    pnl=_finite(test.get("net_pnl"))
    if type(trades) is not int or trades<min_test_trades:
        failures.append("INSUFFICIENT_TEST_TRADES")
    if pnl is None or pnl<=0:
        failures.append("NO_POSITIVE_HELD_OUT_PNL")
    if not isinstance(sensitivity_report,dict) or sensitivity_report.get("mode")!="RESEARCH_ONLY":
        failures.append("INVALID_SENSITIVITY")
    else:
        scenarios=sensitivity_report.get("scenarios")
        count=sensitivity_report.get("scenario_count")
        if (not isinstance(scenarios,list) or not scenarios or type(count) is not int
                or count!=len(scenarios) or sensitivity_report.get("split_date")!=report.get("split_date")):
            failures.append("INVALID_SENSITIVITY")
        else:
            seen=set()
            for s in scenarios:
                if not isinstance(s,dict):
                    failures.append("INVALID_SENSITIVITY")
                    break
                fee=_finite(s.get("fee_per_side_usd"))
                spread=_finite(s.get("spread_bps"))
                value=_finite(s.get("test_net_pnl_usd"))
                n=s.get("test_trades")
                if (fee is None or fee<0 or spread is None or spread<0 or spread>=D("20000")
                        or value is None or type(n) is not int or n<0):
                    failures.append("INVALID_SENSITIVITY")
                    break
                key=(fee,spread)
                if key in seen:
                    failures.append("DUPLICATE_COST_SCENARIO")
                    break
                seen.add(key)
                if value<=0:
                    failures.append("COST_SCENARIO_NOT_PROFITABLE")
            if sensitivity_report.get("all_scenarios_positive") is not True:
                failures.append("COST_SCENARIO_NOT_PROFITABLE")
    return {"mode":"RESEARCH_ONLY","screen_passed":not failures,
            "failures":list(dict.fromkeys(failures)),
            "live_trading_approved":False,
            "meaning":"Screening only: does not prove profitability or authorize live trading."}
