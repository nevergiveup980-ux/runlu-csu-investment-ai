"""Optional Alpha Vantage daily-data downloader. Research only; never sends orders.

API key comes from ALPHAVANTAGE_API_KEY environment variable. The provider
may require a paid plan for full output. Never commit provider responses.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import date
from decimal import Decimal, InvalidOperation

ENDPOINT="https://www.alphavantage.co/query"

def fetch_daily(symbol, output_path, *, api_key=None, outputsize="full", opener=urlopen):
    if not isinstance(symbol,str) or not symbol or not symbol.isascii() or not all(c.isalnum() or c in ".-" for c in symbol):
        raise ValueError("INVALID_SYMBOL")
    if outputsize not in ("compact","full"):
        raise ValueError("INVALID_OUTPUTSIZE")
    key=api_key if api_key is not None else os.environ.get("ALPHAVANTAGE_API_KEY")
    if not isinstance(key,str) or not key.strip():
        raise ValueError("MISSING_ALPHAVANTAGE_API_KEY")
    destination=Path(output_path)
    if destination.exists():
        raise FileExistsError("OUTPUT_ALREADY_EXISTS")
    url=ENDPOINT+"?"+urlencode({"function":"TIME_SERIES_DAILY","symbol":symbol,
                               "outputsize":outputsize,"apikey":key})
    # Do not print URL or underlying HTTP errors: the URL contains the secret.
    try:
        with opener(url,timeout=30) as response:
            raw=response.read(15_000_001)
    except Exception as exc:
        raise RuntimeError("PROVIDER_REQUEST_FAILED") from None
    if len(raw)>15_000_000:
        raise ValueError("PROVIDER_RESPONSE_TOO_LARGE")
    try:
        payload=json.loads(raw)
    except (ValueError,UnicodeDecodeError):
        raise ValueError("INVALID_PROVIDER_JSON") from None
    if not isinstance(payload,dict) or any(k in payload for k in ("Error Message","Note","Information")):
        raise ValueError("PROVIDER_ERROR_OR_RATE_LIMIT")
    series=payload.get("Time Series (Daily)")
    if not isinstance(series,dict) or not series:
        raise ValueError("MISSING_DAILY_SERIES")
    for day,record in series.items():
        try:
            if date.fromisoformat(day).isoformat()!=day or not isinstance(record,dict):
                raise ValueError()
            values=[Decimal(str(record[key])) for key in
                    ("1. open","2. high","3. low","4. close","5. volume")]
            op,hi,lo,cl,vol=values
            if (not all(v.is_finite() for v in values) or min(op,hi,lo,cl)<=0
                    or vol<0 or lo>min(op,cl) or hi<max(op,cl) or hi<lo):
                raise ValueError()
        except (ValueError,TypeError,KeyError,InvalidOperation) as exc:
            raise ValueError("INVALID_PROVIDER_BAR") from None
    # Exclusive creation prevents silently replacing previous provider evidence.
    with destination.open("x",encoding="utf-8") as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)
        f.write("\n")
    return {"symbol":symbol,"bars_received":len(payload["Time Series (Daily)"]),
            "output_path":str(destination),"provenance_verified":False}

def main():
    parser=argparse.ArgumentParser(description="Research-only market data download; no trading")
    parser.add_argument("symbol")
    parser.add_argument("output_json")
    parser.add_argument("--outputsize",choices=("compact","full"),default="full")
    args=parser.parse_args()
    result=fetch_daily(args.symbol,args.output_json,outputsize=args.outputsize)
    print("Saved:",result["output_path"],"bars:",result["bars_received"])
    if result["bars_received"]<120:
        print("Warning: fewer than 120 bars; Project 200 research will reject this dataset.")

if __name__=="__main__":
    main()
