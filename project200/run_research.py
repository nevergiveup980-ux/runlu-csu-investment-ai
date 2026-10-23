"""Offline reproducible research runner; never sends orders or network requests."""
import argparse
import hashlib
import json
from pathlib import Path
from decimal import Decimal as D
from data_validation import validate_history, walk_forward
from backtest import backtest
from performance_report import summarize

def research(csv_path, *, min_bars=120, fee=D("1"), spread_bps=D("5")):
    path=Path(csv_path)
    raw=path.read_bytes()
    bars=validate_history(path,min_bars=min_bars)
    result=backtest(bars,fee=fee,spread_bps=spread_bps)
    split=walk_forward(bars,fee=fee,spread_bps=spread_bps)
    return {
        "mode":"RESEARCH_ONLY",
        "data":{"sha256":hashlib.sha256(raw).hexdigest(),"rows":len(bars),"first":bars[0]["date"],"last":bars[-1]["date"]},
        "assumptions":{"fee_per_side_usd":str(fee),"spread_bps":str(spread_bps),"starting_cash_usd":"2000","strategy":"5-close breakout, next-open entry, following-open exit"},
        "all_sample":summarize(result),
        "train":summarize(split["train"]),
        "test":summarize(split["test"]),
        "split_date":split["split_date"],
        "limitations":["No intraday stops","No partial fills or borrow costs","No corporate-action verification","Closed-trade drawdown only","Sample results are not live profits"]
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("csv",help="Locally obtained, licensed daily OHLCV CSV")
    parser.add_argument("--output",default="project200_research_report.json")
    args=parser.parse_args()
    result=research(args.csv)
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Wrote",args.output,"| out-of-sample net P&L:",result["test"]["net_pnl"])

if __name__=="__main__":
    main()
