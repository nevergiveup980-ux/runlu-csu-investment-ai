import unittest
from evidence_gate import assess

def report(trades=30,pnl="50"):
    return {"mode":"RESEARCH_ONLY","audit":{"audited":True},
            "test":{"trades":trades,"net_pnl":pnl},"split_date":"2026-05-01"}

def costs(pnl="5"):
    return {"mode":"RESEARCH_ONLY","split_date":"2026-05-01",
            "scenario_count":2,"positive_test_scenarios":2,"all_scenarios_positive":True,
            "scenarios":[{"fee_per_side_usd":"0","spread_bps":"0","test_trades":30,"test_net_pnl_usd":pnl},
                         {"fee_per_side_usd":"1","spread_bps":"5","test_trades":30,"test_net_pnl_usd":"2"}]}

class EvidenceGateTests(unittest.TestCase):
    def test_pass_is_not_live_approval(self):
        r=assess(report(),costs())
        self.assertTrue(r["screen_passed"])
        self.assertFalse(r["live_trading_approved"])
    def test_too_few_trades(self):
        self.assertIn("INSUFFICIENT_TEST_TRADES",assess(report(trades=2),costs())["failures"])
    def test_loss_in_held_out(self):
        self.assertIn("NO_POSITIVE_HELD_OUT_PNL",assess(report(pnl="-1"),costs())["failures"])
    def test_cost_loss(self):
        self.assertIn("COST_SCENARIO_NOT_PROFITABLE",assess(report(),costs(pnl="-1"))["failures"])
    def test_duplicate_costs(self):
        s=costs();s["scenarios"][1]=dict(s["scenarios"][0])
        self.assertIn("DUPLICATE_COST_SCENARIO",assess(report(),s)["failures"])
    def test_mismatched_split(self):
        s=costs();s["split_date"]="2026-06-01"
        self.assertIn("INVALID_SENSITIVITY",assess(report(),s)["failures"])
    def test_unverified_report(self):
        r=report();r["audit"]["audited"]=False
        self.assertIn("UNVERIFIED_RESEARCH_REPORT",assess(r,costs())["failures"])
    def test_nan_cost(self):
        s=costs();s["scenarios"][0]["test_net_pnl_usd"]="NaN"
        self.assertIn("INVALID_SENSITIVITY",assess(report(),s)["failures"])
    def test_false_positive_summary_rejected(self):
        s=costs();s["positive_test_scenarios"]=1
        self.assertIn("INCONSISTENT_SENSITIVITY_SUMMARY",assess(report(),s)["failures"])
    def test_false_all_positive_rejected(self):
        s=costs();s["all_scenarios_positive"]=False
        self.assertIn("INCONSISTENT_SENSITIVITY_SUMMARY",assess(report(),s)["failures"])
    def test_invalid_minimum(self):
        with self.assertRaisesRegex(ValueError,"INVALID_MIN_TEST_TRADES"):
            assess(report(),costs(),min_test_trades=True)
if __name__=="__main__":
    unittest.main()
