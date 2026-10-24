import unittest
from research_audit import audit

def sample():
    return {'mode':'RESEARCH_ONLY',
            'data':{'sha256':'a'*64,'rows':150,'first':'2026-01-01','last':'2026-08-31'},
            'assumptions':{'fee_per_side_usd':'1','spread_bps':'5','starting_cash_usd':'2000'},
            'train':{'trades':2,'net_pnl':'5'},'test':{'trades':1,'net_pnl':'-2'},
            'split_date':'2026-05-01'}

class AuditTests(unittest.TestCase):
    def test_valid_metadata(self):
        self.assertTrue(audit(sample())['audited'])
    def test_missing_fingerprint(self):
        s=sample();s['data']['sha256']=''
        self.assertIn('MISSING_DATA_FINGERPRINT',audit(s)['failures'])
    def test_nan_profit(self):
        s=sample();s['test']['net_pnl']='NaN'
        self.assertIn('INVALID_TEST',audit(s)['failures'])
    def test_fake_live_label(self):
        s=sample();s['mode']='LIVE'
        self.assertIn('NOT_RESEARCH_ONLY',audit(s)['failures'])
    def test_negative_cost(self):
        s=sample();s['assumptions']['spread_bps']='-1'
        self.assertIn('INVALID_SPREAD_BPS',audit(s)['failures'])
    def test_malformed_root(self):
        self.assertIn('INVALID_REPORT',audit(None)['failures'])
    def test_malformed_nested(self):
        s=sample();s['data']=['unexpected'];s['train']='bad'
        result=audit(s)
        self.assertFalse(result['audited'])
        self.assertIn('INVALID_DATA',result['failures'])
        self.assertIn('INVALID_TRAIN',result['failures'])
    def test_invalid_calendar_split(self):
        s=sample();s['split_date']='2026-02-30'
        self.assertIn('MISSING_SPLIT_DATE',audit(s)['failures'])
    def test_split_outside_data(self):
        s=sample();s['split_date']='2025-12-01'
        self.assertIn('INVALID_DATA_DATE_RANGE',audit(s)['failures'])
    def test_missing_starting_cash(self):
        s=sample();del s['assumptions']['starting_cash_usd']
        self.assertIn('INVALID_STARTING_CASH',audit(s)['failures'])
    def test_boolean_trade_count(self):
        s=sample();s['test']['trades']=True
        self.assertIn('INVALID_TEST',audit(s)['failures'])
if __name__=='__main__':unittest.main()
