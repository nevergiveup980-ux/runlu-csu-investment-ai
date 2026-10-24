"""Offline, fail-closed normalization of legitimately obtained daily OHLCV CSV."""
import csv
import hashlib
import io
from pathlib import Path
from datetime import date
from decimal import Decimal, InvalidOperation

EXPECTED = ("date", "open", "high", "low", "close", "volume")
MAX_BYTES = 10_000_000

def normalize_csv(raw: bytes):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("INVALID_FILE_SIZE")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("INVALID_ENCODING") from exc
    if "<html" in content[:512].lower() or "exceeded" in content[:512].lower():
        raise ValueError("NOT_MARKET_CSV")
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None or tuple(x.strip().lower() for x in reader.fieldnames) != EXPECTED:
        raise ValueError("INVALID_COLUMNS")
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("MALFORMED_ROW")
        try:
            day = date.fromisoformat(row[reader.fieldnames[0]].strip())
            o,h,l,c,v = [Decimal(row[k].strip()) for k in reader.fieldnames[1:]]
        except (ValueError, InvalidOperation, TypeError) as exc:
            raise ValueError("INVALID_ROW_VALUE") from exc
        if any(not x.is_finite() for x in (o,h,l,c,v)) or min(o,h,l,c) <= 0 or v < 0:
            raise ValueError("INVALID_NUMERIC_VALUE")
        if h < max(o,c,l) or l > min(o,c,h):
            raise ValueError("INVALID_OHLC")
        rows.append((day.isoformat(), o,h,l,c,v))
    if not rows or len({r[0] for r in rows}) != len(rows):
        raise ValueError("EMPTY_OR_DUPLICATE_DATES")
    rows.sort(key=lambda r:r[0])
    output = io.StringIO()
    writer = csv.writer(output,lineterminator="\n")
    writer.writerow(EXPECTED)
    writer.writerows(rows)
    return {"csv":output.getvalue(),"source_sha256":hashlib.sha256(raw).hexdigest(),"rows":len(rows),"first":rows[0][0],"last":rows[-1][0]}

def import_file(source, destination):
    result=normalize_csv(Path(source).read_bytes())
    Path(destination).write_text(result["csv"],encoding="utf-8")
    return {k:v for k,v in result.items() if k != "csv"}
