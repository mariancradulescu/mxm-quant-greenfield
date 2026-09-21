import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class StageBHistoricalMarginPublicSourceSearchTests(unittest.TestCase):
    def test_public_search_is_fail_closed(self):
        e=load("evidence/M6_STAGE_B_HISTORICAL_MARGIN_PUBLIC_SOURCE_SEARCH_V1.json")
        self.assertEqual(e["status"],"PUBLIC_OFFICIAL_SEARCH_INSUFFICIENT_BROKER_CONFIRMATION_REQUIRED")
        a=e["search_assessment"]
        self.assertFalse(a["official_public_point_in_time_schedule_found"])
        self.assertFalse(a["broker_specific_us500_historical_upper_bound_found"])
        self.assertFalse(a["broker_specific_nas100_historical_upper_bound_found"])
        self.assertFalse(a["development_wide_upper_bound_found"])
        self.assertFalse(a["public_5_percent_can_be_promoted_to_exact_historical_requirement"])
        self.assertFalse(a["public_5_percent_can_be_promoted_to_historical_upper_bound"])
        self.assertFalse(a["current_margin_or_leverage_backfill_allowed"])

    def test_margin_variability_blocks_public_upper_bound(self):
        e=load("evidence/M6_STAGE_B_HISTORICAL_MARGIN_PUBLIC_SOURCE_SEARCH_V1.json")
        logic=e["logic"]
        self.assertTrue(logic["pepperstone_contract_permits_margin_adjustment"])
        self.assertTrue(logic["public_sources_do_not_state_a_finite_maximum_adjusted_margin"])
        self.assertTrue(logic["therefore_public_sources_cannot_prove_development_wide_conservative_upper_bound"])
        self.assertTrue(logic["historical_margin_gate_must_remain_unresolved"])

    def test_broker_request_rejects_generic_five_percent_answer(self):
        e=load("evidence/M6_STAGE_B_HISTORICAL_MARGIN_PUBLIC_SOURCE_SEARCH_V1.json")
        insufficient=e["required_external_confirmation"]["insufficient_responses"]
        self.assertTrue(any("generic" in x.lower() and "5%" in x for x in insufficient))
        text=(ROOT/"data/M6_STAGE_B_HISTORICAL_MARGIN_BROKER_CONFIRMATION_REQUEST_V1.txt").read_text(encoding="utf-8")
        self.assertIn("MAXIMUM margin percentage",text)
        self.assertIn("exceptional",text.lower())
        self.assertIn("US500",text)
        self.assertIn("NAS100",text)
        self.assertIn("0.1 unit",text)

    def test_state_keeps_historical_broker_confirmation_non_blocking_for_current_scenario(self):
        s=load("CURRENT_STATE.json")
        self.assertFalse(s["user_action_required"])
        self.assertTrue(s["m6"]["stage_b"]["broker_confirmation_required"])
        self.assertFalse(s["m6"]["stage_b"]["broker_confirmation_blocks_current_configuration_scenario"])
        self.assertTrue(s["m6"]["stage_b"]["historical_track_remains_open"])
        self.assertTrue(s["m6"]["stage_b"]["current_configuration_scenario_is_separate"])
        self.assertEqual(
            s["m6"]["stage_b"]["historical_margin_gate"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertFalse(s["m6"]["stage_b"]["historical_margin_authority_frozen"])
        self.assertFalse(s["m6"]["stage_b"]["execution_authorized"])
        self.assertFalse(s["m6"]["stage_b"]["economics_run"])
        self.assertFalse(s["m6"]["stage_b"]["results_created"])
        self.assertEqual(s["m6"]["stage_b"]["stage_b_outcomes_opened"],0)
        self.assertFalse(s["protected_evidence_opened"])

    def test_accounting_is_unchanged(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(s["economic_outcomes_opened"],2)
        self.assertEqual(s["v2_attempts_used"],2)
        self.assertEqual(s["v2_evaluated_identities"],2)
        self.assertEqual(s["v2_search_budget"],84)
        self.assertEqual(s["v2_search_budget_remaining"],82)
        self.assertFalse(s["competition_start_authorized"])
        self.assertFalse(s["live_orders_authorized"])

if __name__=="__main__":
    unittest.main(verbosity=2)
