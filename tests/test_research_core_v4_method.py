from __future__ import annotations
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class ResearchCoreV4MethodTests(unittest.TestCase):
    def test_v3_is_read_only_and_quote_v2_is_held(self):
        state = load("research_core_v3/state/V3_STATE.json")
        freeze = load("research_core_v3/state/V3_FREEZE_AUTHORITY_V1.json")
        self.assertEqual(state["v3_status"], "READ_ONLY_RESEARCH_HISTORY")
        self.assertEqual(freeze["status"], "READ_ONLY_RESEARCH_HISTORY")
        self.assertFalse(state["quote_revision_sequence_package_execution_authorized"])
        self.assertEqual(state["quote_revision_sequence_research_execution_status"], "HELD_PENDING_V4")
        self.assertTrue(state["quote_revision_sequence_raw_tick_transfer"])
        self.assertEqual(state["quote_revision_sequence_base_side_requests_before_pagination"], 900)
        self.assertTrue(state["quote_revision_sequence_design"].endswith("_V2.json"))
        self.assertTrue(state["quote_revision_sequence_acquisition_plan"].endswith("_V2.json"))
        self.assertTrue(state["quote_revision_sequence_package_authority"].endswith("_V2.json"))
        self.assertFalse(state["protected_forward_opened"])

    def test_v4_contract_and_state_are_preoutcome(self):
        contract = load("research_core_v4/V4_PROJECT_CONTRACT_V1.json")
        state = load("research_core_v4/state/V4_STATE.json")
        self.assertEqual(contract["primary_research_unit"], "INFORMATION_SOURCE_X_CAUSAL_SCALE_STATE_X_PREENTRY_CONTEXT_X_TRIGGER_X_RESPONSE_FUNCTION_X_EXECUTION_STATE")
        self.assertEqual(state["status"], "FIRST_REAL_MARKET_DESIGN_FROZEN_OUTCOMES_UNOPENED")
        self.assertFalse(state["first_wave"]["development_outcomes_opened"])
        self.assertFalse(state["first_wave"]["confirmation_outcomes_opened"])
        self.assertFalse(state["first_wave"]["new_market_acquisition_started"])
        self.assertFalse(state["first_wave"]["evaluator_execution_authorized"])
        self.assertFalse(state["governance"]["protected_forward_opened"])
        self.assertEqual(state["governance"]["candidate_frozen_count"], 0)
        self.assertFalse(state["governance"]["live_trading_started"])

    def test_closure_graph_preserves_v3_and_does_not_auto_reopen(self):
        graph = load("research_core_v4/state/V3_CLOSURE_DEPENDENCY_GRAPH_V1.json")
        self.assertGreaterEqual(graph["node_count"], 40)
        self.assertFalse(graph["invariants"]["old_pvalues_recomputed"])
        self.assertFalse(graph["invariants"]["old_pass_fail_changed"])
        self.assertFalse(graph["invariants"]["every_old_null_reopened"])
        classes = set(graph["classification_vocabulary"])
        for needed in (
            "CARRY_FORWARD_HARD_CLOSURE",
            "METHOD_DEPENDENT_REINTERPRETATION_REQUIRED",
            "AUTHENTIC_FRICTION_CLOSED",
            "DATA_LIMITED_UNTESTED_NOT_NULL",
        ):
            self.assertIn(needed, classes)

    def test_detector_calibration_is_type_i_controlled_and_information_first(self):
        cal = load("research_core_v4/state/DETECTOR_CALIBRATION_RESULT_V2.json")
        fpr = cal["negative_control"]["pooled_local_maxT_false_positive_rate"]
        self.assertGreater(fpr, 0.04)
        self.assertLess(fpr, 0.06)
        self.assertGreater(cal["negative_control"]["prior_v1_any_of_6_local_without_selection_control_fwer"], 0.20)
        self.assertLess(cal["negative_control"]["prior_v1_holm6_global_fwer"], 0.06)
        low = cal["noise_regimes"]["5"]["mde"]
        self.assertLess(low["pooled_local_maxT"]["p50"], low["old_connected_surrogate"]["p50"])
        self.assertFalse(cal["real_market_outcomes_opened"])
        self.assertFalse(cal["broker_contacted"])

    def test_first_wave_is_one_pooled_source_and_confirmation_is_closed(self):
        design = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V1.json")
        select = load("research_core_v4/state/FIRST_WAVE_PREOUTCOME_SELECTION_AUDIT_V1.json")
        dev_ids = {int(x["symbol_id"]) for x in design["development_panel"]}
        conf_ids = {int(x["symbol_id"]) for x in design["confirmation_architecture"]["panel"]}
        self.assertEqual(len(dev_ids), 6)
        self.assertEqual(len(conf_ids), 6)
        self.assertTrue(dev_ids.isdisjoint(conf_ids))
        self.assertEqual(design["multiplicity"]["local_family"], "FOUR_RESPONSE_HORIZONS_FOR_ONE_POOLED_INFORMATION_SOURCE")
        self.assertFalse(design["multiplicity"]["cross_symbol_maxT"])
        self.assertFalse(design["multiplicity"]["free_best_symbol"])
        self.assertFalse(design["multiplicity"]["generic_connected_region_gate"])
        self.assertIsNone(design["development_information_lead_gate"]["economic_bps_hurdle"])
        self.assertFalse(design["confirmation_architecture"]["outcomes_opened_now"])
        self.assertFalse(design["confirmation_architecture"]["data_acquired_now"])
        self.assertTrue(design["confirmation_architecture"]["protected_forward_forbidden"])
        self.assertFalse(design["governance"]["v4_real_market_outcomes_opened"])
        self.assertFalse(select["governance"]["quote_revision_v2_executed"])

    def test_scale_topology_is_true_completed_multiscale(self):
        design = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V1.json")
        topology = design["scale_topology"]
        self.assertIn("H4_context", topology)
        self.assertIn("H1_setup", topology)
        self.assertIn("M15_transition", topology)
        self.assertIn("M5_event_clock", topology)
        self.assertFalse(topology["scale_grid"])
        self.assertFalse(topology["centered_or_two_sided_filters"])
        self.assertFalse(topology["partial_bucket_use"])
        self.assertFalse(topology["forward_fill"])
        self.assertFalse(topology["synthetic_fill"])
        self.assertEqual(design["response_function"]["horizons_completed_contiguous_m5_bars"], [3, 6, 12, 48])


if __name__ == "__main__":
    unittest.main()
