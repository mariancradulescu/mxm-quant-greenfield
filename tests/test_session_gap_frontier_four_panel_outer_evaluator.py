import json, math, unittest
from pathlib import Path
from research_v3.session_gap_frontier_four_panel_outer_evaluator_v1 import CAPTURE_SHA256, PLAN_SHA256, SYMBOLS, _binom_upper
ROOT=Path(__file__).resolve().parents[1]
class FourPanelOuterEvaluatorTests(unittest.TestCase):
    def test_result_is_bound_to_frozen_capture_and_plan(self):
        r=json.loads((ROOT/"evidence/SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_CONFIRMATORY_RESULT_V1.json").read_text())
        self.assertEqual(r["source_capture_sha256"],CAPTURE_SHA256)
        self.assertEqual(r["source_plan_sha256"],PLAN_SHA256)
        self.assertEqual(r["fixed_symbols"],list(SYMBOLS))
        self.assertEqual(r["economic_effect"],{"economic_outcomes_opened":0,"v2_attempts_consumed":0})
    def test_frozen_binomial_and_holm_facts(self):
        r=json.loads((ROOT/"evidence/SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_CONFIRMATORY_RESULT_V1.json").read_text())
        for s in SYMBOLS:
            row=r["per_symbol"][s]
            self.assertAlmostEqual(row["one_sided_exact_binomial_p"],_binom_upper(row["positive"],row["confirmatory_nonzero_n"]))
        self.assertTrue(r["per_symbol"]["XPDUSD"]["holm_reject_null"])
        self.assertEqual(sum(r["per_symbol"][s]["holm_reject_null"] for s in SYMBOLS),1)
        self.assertFalse(r["interpretation_boundary"]["mechanism_family_closed"])
    def test_friction_blocks_only_confirmed_member_from_promotion(self):
        a=json.loads((ROOT/"evidence/SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_CAPTURE_ACCEPTANCE_V1.json").read_text())
        i=json.loads((ROOT/"evidence/SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_INTERPRETATION_V1.json").read_text())
        self.assertEqual(a["friction_authority"]["per_symbol"]["XPDUSD"]["friction_state"],"FRICTION_FAIL")
        self.assertEqual(a["friction_authority"]["per_symbol"]["NETH25"]["friction_state"],"FRICTION_PASS")
        self.assertFalse(i["decision"]["economic_promotion_now"])
        self.assertFalse(i["decision"]["mechanism_family_closed"])
if __name__=="__main__": unittest.main()
