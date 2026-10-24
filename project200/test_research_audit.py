import unittest
from research_audit import audit

def sample():
    return {'mode':'RESEARCH_ONLY','data':{'sha256':'a'*64,'rows':150},
            'assumptions':{'fee_per_side_usd':'1','spread_bps':'5'},
            'train':{'trades':2,'net_pnl':'5'},'test':{'trades':1,'net_pnl':'-2'},
            'split_date':'2026-01-01'}
class AuditTests(unittest.TestCase):
    def test_valid_metadata(self): self.assertTrue(audit(sample())['audited'])
    def test_missing_fingerprint(self):
        s=sample();s['data']['sha256']='';self.assertIn('MISSING_DATA_FINGERPRINT',audit(s)['failures'])
    def test_nan_profit(self):
        s=sample();s['test']['net_pnl']='NaN';self.assertIn('INVALID_TEST',audit(s)['failures'])
    def test_fake_live_label(self):
        s=sample();s['mode']='LIVE';self.assertIn('NOT_RESEARCH_ONLY',audit(s)['failures'])
    def test_negative_cost(self):
        s=sample();s['assumptions']['spread_bps']='-1';self.assertIn('INVALID_SPREAD_BPS',audit(s)['failures'])
if __name__=='__main__':unittest.main()
