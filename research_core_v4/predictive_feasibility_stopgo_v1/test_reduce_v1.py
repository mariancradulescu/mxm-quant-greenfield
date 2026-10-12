import unittest
from .reduce_v1 import ratio,stats,consecutive,summarize
class EvidenceSemantics(unittest.TestCase):
    def test_unknown_is_not_zero(self):
        self.assertIsNone(ratio(1,None));self.assertIsNone(ratio(1,0));self.assertEqual(stats([None])['n'],0)
    def test_alternate_weeks_not_consecutive(self):
        self.assertFalse(consecutive(['2026-W12','2026-W14']));self.assertTrue(consecutive(['2025-W52','2026-W01']))
    def test_both_sides_required(self):
        r={'state':'RISK_OR_MARGIN','sid':1,'prior_M5_range_bps':10,'prior_M5_range_eur':1,'cost_eur':.2,'hurdles':{'S2_F010':[{'break_even_bps':1,'flat_cost_eur':.1},None]}}
        s=summarize([r]);self.assertEqual(s['both_side_worst_hurdle_over_causal_range']['n'],0);self.assertEqual(s['range_risk_witnesses'],0)
    def test_worst_side_and_reserve(self):
        r={'state':'ECONOMIC_RANGE_WITNESS_NOT_DIRECTIONAL_EDGE','sid':1,'margin_eur':70,'stressed_risk_eur':1.8,'prior_M5_range_bps':10,'prior_M5_range_eur':1,'cost_eur':.2,'hurdles':{'S2_F010':[{'break_even_bps':1,'flat_cost_eur':.1},{'break_even_bps':3,'flat_cost_eur':.2}]}}
        s=summarize([r]);self.assertAlmostEqual(s['both_side_worst_hurdle_over_causal_range']['median'],.3);self.assertEqual(s['witness_reference_reserve_eur']['median'],130)
if __name__=='__main__':unittest.main()
