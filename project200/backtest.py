"""Research-only daily bar backtest: close signal, next open entry, following open exit."""
import csv
from decimal import Decimal as D

def load_bars(path):
    with open(path, newline='', encoding='utf-8') as f:
        bars=list(csv.DictReader(f))
    required={'date','open','high','low','close','volume'}
    if not bars or not required.issubset(bars[0]):
        raise ValueError('missing bars or columns')
    if len({r['date'] for r in bars}) != len(bars) or [r['date'] for r in bars] != sorted(r['date'] for r in bars):
        raise ValueError('dates must be unique and sorted')
    for r in bars:
        for k in ('open','high','low','close'):
            r[k]=D(r[k])
            if not r[k].is_finite() or r[k] <= 0:
                raise ValueError('invalid price')
        r['volume']=D(r['volume'])
        if not r['volume'].is_finite() or r['volume'] < 0 or r['high'] < max(r['open'],r['close']) or r['low'] > min(r['open'],r['close']):
            raise ValueError('invalid OHLCV')
    return bars

def backtest(bars, *, starting_cash=D('2000'), fee=D('1'), spread_bps=D('5'), lookback=5):
    if lookback < 2 or starting_cash <= 0 or fee < 0 or spread_bps < 0:
        raise ValueError('invalid parameters')
    cash=D(starting_cash)
    trades=[]
    next_free_entry=0
    for t in range(lookback-1,len(bars)-2):
        if t+1 < next_free_entry:
            continue
        window=bars[t-lookback+1:t+1]
        if bars[t]['close'] <= max(x['close'] for x in window[:-1]):
            continue
        entry=bars[t+1]['open']*(D('1')+spread_bps/D('20000'))
        exit_price=bars[t+2]['open']*(D('1')-spread_bps/D('20000'))
        qty=int(max(D('0'),(cash-D('200')-fee)//entry))
        if qty < 1:
            continue
        pnl=qty*(exit_price-entry)-fee*2
        cash+=pnl
        next_free_entry=t+2
        trades.append({'signal_date':bars[t]['date'],'entry_date':bars[t+1]['date'],'exit_date':bars[t+2]['date'],'qty':qty,'net_pnl':str(pnl)})
    return {'trades':trades,'trade_count':len(trades),'net_pnl':str(cash-starting_cash),'ending_equity':str(cash)}
