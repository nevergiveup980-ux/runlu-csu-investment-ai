"""Fail-closed audit of a Project 200 research report, not a profit endorsement."""
from decimal import Decimal, InvalidOperation

def audit(report):
    failures = []
    if report.get('mode') != 'RESEARCH_ONLY':
        failures.append('NOT_RESEARCH_ONLY')
    data = report.get('data') or {}
    sha = data.get('sha256', '')
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        failures.append('MISSING_DATA_FINGERPRINT')
    if not isinstance(data.get('rows'), int) or data['rows'] < 120:
        failures.append('INSUFFICIENT_HISTORY')
    assumptions = report.get('assumptions') or {}
    for key in ('fee_per_side_usd', 'spread_bps'):
        try:
            v = Decimal(str(assumptions[key]))
            if not v.is_finite() or v < 0:
                raise ValueError()
        except (KeyError, ValueError, TypeError, InvalidOperation):
            failures.append('INVALID_' + key.upper())
    for segment in ('train', 'test'):
        result = report.get(segment) or {}
        try:
            count = result['trades']
            pnl = Decimal(str(result['net_pnl']))
            if not isinstance(count, int) or count < 0 or not pnl.is_finite():
                raise ValueError()
        except (KeyError, ValueError, TypeError, InvalidOperation):
            failures.append('INVALID_' + segment.upper())
    if not report.get('split_date'):
        failures.append('MISSING_SPLIT_DATE')
    return {'audited': not failures, 'failures': failures,
            'meaning': 'Research data and accounting metadata checks only; not evidence of live profitability'}
