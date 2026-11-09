"""Convert locally saved Alpha Vantage TIME_SERIES_DAILY JSON to offline OHLCV CSV.

No network requests, credentials, market-data redistribution, or live orders.
"""
import argparse
import csv
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS=("date","open","high","low","close","volume")
SOURCE="Time Series (Daily)"

def convert(input_path, output_path):
    payload=json.loads(Path(input_path).read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise ValueError("INVALID_PROVIDER_RESPONSE")
    for key in ("Error Message","Note","Information"):
        if key in payload:
            raise ValueError("PROVIDER_ERROR_OR_RATE_LIMIT")
    series=payload.get(SOURCE)
    if not isinstance(series,dict) or not series:
        raise ValueError("MISSING_DAILY_SERIES")
    rows=[]
    for day,record in series.items():
        try:
            parsed=date.fromisoformat(day)
            if parsed.isoformat()!=day or not isinstance(record,dict):
                raise ValueError()
            values=[Decimal(str(record[k])) for k in
                    ("1. open","2. high","3. low","4. close","5. volume")]
            op,hi,lo,cl,vol=values
            if not all(v.is_finite() for v in values) or min(op,hi,lo,cl)<=0 or vol<0:
                raise ValueError()
            if lo>min(op,cl) or hi<max(op,cl) or hi<lo:
                raise ValueError()
        except (ValueError,TypeError,KeyError,InvalidOperation) as exc:
            raise ValueError("INVALID_PROVIDER_BAR") from exc
        rows.append((day,*(str(v) for v in values)))
    rows.sort(key=lambda r:r[0])
    destination=Path(output_path)
    if destination.resolve()==Path(input_path).resolve():
        raise ValueError("OUTPUT_OVERWRITES_INPUT")
    with destination.open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(rows)
    return {"rows":len(rows),"first":rows[0][0],"last":rows[-1][0],
            "adjustment":"RAW_AS_TRADED_NOT_CORPORATE_ACTION_ADJUSTED"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("json_file")
    parser.add_argument("csv_file")
    args=parser.parse_args()
    print(json.dumps(convert(args.json_file,args.csv_file),indent=2))

if __name__=="__main__":
    main()
