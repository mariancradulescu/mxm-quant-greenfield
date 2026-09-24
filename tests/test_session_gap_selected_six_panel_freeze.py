import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SelectedSixPanelFreezeTests(unittest.TestCase):
    def test_panel_and_data_scope_are_fixed_before_outcomes(self):
        document = json.loads(
            (ROOT / "research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json").read_text()
        )
        self.assertEqual(
            document["status"], "FROZEN_PROSPECTIVE_NON_ECONOMIC_METHODOLOGY_PENDING_INDEPENDENT_OUTER_DATA"
        )
        self.assertEqual(
            document["panel"]["symbols"],
            ["MXNJPY", "USDCAD", "EURUSD", "IWM.US", "TLT.US", "NVDA.US-24"],
        )
        self.assertEqual(document["data_scope"]["resolution"], "M5")
        self.assertTrue(document["data_scope"]["no_new_market_data_required_for_methodology_compilation"])
        self.assertTrue(document["independent_outer_contract"]["required"])
        self.assertFalse(document["independent_outer_contract"]["source_wave01_canonical_capture_may_be_outer"])
        self.assertTrue(document["independent_outer_contract"]["outer_dataset_must_be_disjoint_from_source_capture"])
        self.assertEqual(document["analysis_discipline"]["confirmatory_outer_testing"]["familywise_correction"], "HOLM_BONFERRONI")
        self.assertTrue(document["panel"]["selection_rule"].startswith("Fixed before"))

    def test_causal_controls_and_multiple_testing_discipline_are_explicit(self):
        document = json.loads(
            (ROOT / "research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json").read_text()
        )
        causal = document["causal_methodology"]
        self.assertEqual(causal["prior_scale_window_exact_m5_returns"], 288)
        self.assertEqual(causal["measurement_horizon_minutes"], 60)
        self.assertIn("only rows observed before", causal["admission"])
        self.assertIn("descriptive structural tests", document["analysis_discipline"]["multiple_testing"])
        self.assertEqual(
            document["analysis_discipline"]["minimum_coverage"]["maximum_unresolved_chronology_conflicts"],
            0,
        )

    def test_economic_and_safety_boundaries_remain_closed(self):
        boundary = json.loads(
            (ROOT / "research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json").read_text()
        )["economic_boundary"]
        self.assertFalse(boundary["cost_hurdle_applied"])
        self.assertFalse(boundary["notional_pnl_computed"])
        self.assertFalse(boundary["economic_candidate_identity_created"])
        self.assertEqual(boundary["economic_outcomes_opened"], 0)
        self.assertEqual(boundary["v2_attempts_consumed"], 0)
        self.assertFalse(boundary["protected_forward_opened"])
        self.assertFalse(boundary["live_orders_authorized"])
        self.assertFalse(boundary["competition_start_authorized"])


if __name__ == "__main__":
    unittest.main()
