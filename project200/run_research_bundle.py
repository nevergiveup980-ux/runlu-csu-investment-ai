"""Offline reproducible research bundle: no downloads, API calls or orders."""
import argparse
import hashlib
import json
from pathlib import Path
from run_research import research
from cost_sensitivity import sensitivity
from evidence_gate import assess
from hold_baseline import baseline

def bundle(csv_path, *, source_label, min_bars=120):
    if not isinstance(source_label,str) or not source_label.strip():
        raise ValueError("SOURCE_LABEL_REQUIRED")
    path=Path(csv_path)
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    report=research(path,min_bars=min_bars)
    stress=sensitivity(path,min_bars=min_bars)
    after=hashlib.sha256(path.read_bytes()).hexdigest()
    if before!=after or before!=report["data"]["sha256"]:
        raise ValueError("INPUT_CHANGED_DURING_RESEARCH")
    benchmark=baseline(path,min_bars=min_bars)
    verdict=assess(report,stress)
    return {
        "mode":"RESEARCH_ONLY",
        "source_label_user_supplied_unverified":source_label.strip(),
        "input_sha256":before,
        "research":report,
        "cost_sensitivity":stress,
        "buy_and_hold_baseline":benchmark,
        "test_excess_pnl_vs_baseline_usd":str(__import__("decimal").Decimal(report["test"]["net_pnl"])-__import__("decimal").Decimal(benchmark["net_pnl"])),
        "evidence_screen":verdict,
        "limitations":[
            "Source label is user supplied and is not proof of data provenance or license",
            "Daily bars cannot verify intraday fills, stops, liquidity or slippage",
            "No corporate action adjustment verification",
            "A passing screen is not evidence of future profitability",
            "Live trading is not authorized"
        ]
    }

def main():
    parser=argparse.ArgumentParser(description="Offline paper-only research bundle")
    parser.add_argument("csv",help="Licensed local OHLCV CSV")
    parser.add_argument("--source-label",required=True,help="Provider and instrument (not independently verified)")
    parser.add_argument("--output",default="project200_bundle.json")
    args=parser.parse_args()
    result=bundle(args.csv,source_label=args.source_label)
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Saved research bundle:",args.output)
    print("Evidence screen passed:",result["evidence_screen"]["screen_passed"])
    print("Live trading approved:",result["evidence_screen"]["live_trading_approved"])

if __name__=="__main__":
    main()
