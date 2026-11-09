import tempfile, unittest
from decimal import Decimal as D
from pathlib import Path
from backtest import load_bars, backtest

class BacktestTests(unittest.TestCase):
    def bars(self):
        return [{'date':str(i),'open':D('10'),'close':D(10+i),'high':D(20+i),'low':D('9'),'volume':D('100')} for i in range(9)]
    def test_no_lookahead(self):
        a=self.bars()
        changed=[dict(x) for x in a]
        changed[-1]['close']=D('1000')
        self.assertEqual(backtest(a),backtest(changed))
    def test_flat_no_signal(self):
        bars=[{'date':str(i),'open':D('10'),'close':D('10'),'high':D('11'),'low':D('9'),'volume':D('100')} for i in range(9)]
        self.assertEqual(backtest(bars)['trade_count'],0)
    def test_costs_count(self):
        a=self.bars()
        self.assertLess(D(backtest(a,fee=D('2'))['net_pnl']),D(backtest(a,fee=D('0'))['net_pnl']))
    def test_reject_bad_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.csv'
            p.write_text('date,open,high,low,close,volume\n2026-01-01,10,9,8,10,100\n')
            with self.assertRaises(ValueError):load_bars(p)
    def test_nonfinite_assumptions_rejected(self):
        for kwargs in ({'fee':D('NaN')},{'spread_bps':D('Infinity')},
                       {'starting_cash':D('NaN')},{'fee':D('-1')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                backtest(self.bars(),**kwargs)
    def test_excessive_spread_rejected(self):
        with self.assertRaises(ValueError):
            backtest(self.bars(),spread_bps=D('20000'))
    def test_invalid_lookback_rejected(self):
        with self.assertRaises(ValueError):
            backtest(self.bars(),lookback=True)
if __name__=='__main__':unittest.main()
