"""One-command offline Alpha Vantage JSON -> research report; no network or orders."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from alphavantage_daily_adapter import convert
from run_research_bundle import bundle

def run(input_json, output_json, *, symbol, acquired_on, min_bars=120):
    if not isinstance(symbol,str) or not symbol.strip() or not symbol.strip().isascii() or not all(c.isalnum() or c in ".-" for c in symbol.strip()):
        raise ValueError("INVALID_SYMBOL")
    if not isinstance(acquired_on,str):
        raise ValueError("INVALID_ACQUISITION_DATE")
    from datetime import date
    try:
        if date.fromisoformat(acquired_on).isoformat()!=acquired_on:
            raise ValueError()
    except ValueError as exc:
        raise ValueError("INVALID_ACQUISITION_DATE") from exc
    src=Path(input_json)
    dst=Path(output_json)
    if src.resolve()==dst.resolve():
        raise ValueError("OUTPUT_OVERWRITES_INPUT")
    if dst.exists():
        raise FileExistsError("REPORT_ALREADY_EXISTS")
    source_sha=hashlib.sha256(src.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="project200_research_") as folder:
        csv_path=Path(folder)/"daily.csv"
        conversion=convert(src,csv_path)
        if conversion["rows"]<min_bars:
            raise ValueError("INSUFFICIENT_HISTORY")
        result=bundle(csv_path,source_label=f"Alpha Vantage / {symbol.strip()} / RAW daily / acquired {acquired_on}",min_bars=min_bars)
    if hashlib.sha256(src.read_bytes()).hexdigest()!=source_sha:
        raise ValueError("INPUT_CHANGED_DURING_RESEARCH")
    result["provider_json_sha256"]=source_sha
    result["provider_adapter"]=conversion
    result["instrument_symbol_user_supplied_unverified"]=symbol.strip()
    result["acquired_on_user_supplied_unverified"]=acquired_on
    # The source JSON and transformed CSV remain local; only aggregate research is written.
    # Exclusive creation prevents overwriting a report, including concurrent runs.
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    with dst.open("x",encoding="utf-8") as output:
        output.write(encoded)
    return result

def main():
    parser=argparse.ArgumentParser(description="Offline Alpha Vantage daily research; never sends orders")
    parser.add_argument("provider_json")
    parser.add_argument("output_json")
    parser.add_argument("--symbol",required=True)
    parser.add_argument("--acquired-on",required=True,help="YYYY-MM-DD (user supplied)")
    args=parser.parse_args()
    result=run(args.provider_json,args.output_json,symbol=args.symbol,acquired_on=args.acquired_on)
    print("Research saved:",args.output_json)
    print("Evidence screen passed:",result["evidence_screen"]["screen_passed"])
    print("Live trading approved:",result["evidence_screen"]["live_trading_approved"])

if __name__=="__main__":
    main()
