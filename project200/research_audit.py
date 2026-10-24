"""Fail-closed audit of research metadata, never evidence of profitability."""
from datetime import date
from decimal import Decimal, InvalidOperation

def _number(value):
    try:
        n=Decimal(str(value))
        return n if n.is_finite() else None
    except (TypeError, ValueError, InvalidOperation):
        return None

def audit(report):
    failures=[]
    if not isinstance(report,dict):
        return {'audited':False,'failures':['INVALID_REPORT'],
                'meaning':'Research metadata checks only; not evidence of live profitability'}
    if report.get('mode')!='RESEARCH_ONLY':
        failures.append('NOT_RESEARCH_ONLY')
    data=report.get('data')
    if not isinstance(data,dict):
        data={}
        failures.append('INVALID_DATA')
    sha=data.get('sha256','')
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
        failures.append('MISSING_DATA_FINGERPRINT')
    if type(data.get('rows')) is not int or data['rows']<120:
        failures.append('INSUFFICIENT_HISTORY')
    assumptions=report.get('assumptions')
    if not isinstance(assumptions,dict):
        assumptions={}
        failures.append('INVALID_ASSUMPTIONS')
    for key in ('fee_per_side_usd','spread_bps'):
        n=_number(assumptions.get(key))
        if n is None or n<0 or (key=='spread_bps' and n>=20000):
            failures.append('INVALID_'+key.upper())
    capital=_number(assumptions.get('starting_cash_usd'))
    if capital is None or capital<=0:
        failures.append('INVALID_STARTING_CASH')
    for segment in ('train','test'):
        result=report.get(segment)
        if not isinstance(result,dict):
            failures.append('INVALID_'+segment.upper())
            continue
        count=result.get('trades')
        pnl=_number(result.get('net_pnl'))
        if type(count) is not int or count<0 or pnl is None:
            failures.append('INVALID_'+segment.upper())
    try:
        split=date.fromisoformat(report.get('split_date'))
    except (TypeError, ValueError):
        failures.append('MISSING_SPLIT_DATE')
        split=None
    try:
        first=date.fromisoformat(data.get('first'))
        last=date.fromisoformat(data.get('last'))
        if first>=last or (split is not None and not first<split<=last):
            raise ValueError()
    except (TypeError, ValueError):
        failures.append('INVALID_DATA_DATE_RANGE')
    return {'audited':not failures,'failures':failures,
            'meaning':'Research metadata checks only; not evidence of live profitability'}
