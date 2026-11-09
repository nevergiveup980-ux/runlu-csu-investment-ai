"""Convert Twelve Data /time_series JSON to strict daily OHLCV CSV.

No network calls or API keys. Feed the response from an authorized source.
"""
import csv
import io
import json
from datetime import date
from decimal import Decimal, InvalidOperation

FIELDS=("date","open","high","low","close","volume")

def convert(payload, *, expected_symbol=None):
    if isinstance(payload, (str,bytes)):
        payload=json.loads(payload)
    if not isinstance(payload,dict):
        raise ValueError("INVALID_RESPONSE")
    if payload.get("status")=="error" or "values" not in payload:
        raise ValueError("PROVIDER_ERROR_OR_MISSING_VALUES")
    meta=payload.get("meta")
    if not isinstance(meta,dict):
        raise ValueError("MISSING_META")
    symbol=meta.get("symbol")
    if expected_symbol is not None and str(symbol).upper()!=str(expected_symbol).upper():
        raise ValueError("SYMBOL_MISMATCH")
    if meta.get("interval")!="1day":
        raise ValueError("NOT_DAILY_DATA")
    values=payload["values"]
    if not isinstance(values,list) or not values:
        raise ValueError("EMPTY_VALUES")
    rows=[]
    seen=set()
    for value in values:
        if not isinstance(value,dict):
            raise ValueError("INVALID_BAR")
        try:
            day=date.fromisoformat(value["datetime"]).isoformat()
            o,h,l,c,v=(Decimal(str(value[k])) for k in ("open","high","low","close","volume"))
        except (KeyError,TypeError,ValueError,InvalidOperation) as exc:
            raise ValueError("INVALID_BAR") from exc
        if day in seen:
            raise ValueError("DUPLICATE_DATE")
        seen.add(day)
        if not all(x.is_finite() for x in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<0 or h<max(o,l,c) or l>min(o,h,c):
            raise ValueError("INVALID_OHLCV")
        rows.append((day,o,h,l,c,v))
    rows.sort(key=lambda x:x[0])
    output=io.StringIO()
    writer=csv.writer(output,lineterminator="\n")
    writer.writerow(FIELDS)
    writer.writerows(rows)
    return output.getvalue()
