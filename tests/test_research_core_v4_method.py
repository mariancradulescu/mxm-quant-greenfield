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
        self.assertFalse(state["protected_forward_opened"])

    def test_v1_is_immutable_preoutcome_history_and_v2_is_successor(self):
        v1 = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V1.json")
        sup = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V1_SUPERSESSION_V1.json")
        v2 = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json")
        self.assertFalse(v1["governance"]["v4_real_market_outcomes_opened"])
        self.assertEqual(sup["status"], "SUPERSEDED_BEFORE_ANY_V4_MARKET_OUTCOME")
        self.assertFalse(sup["outcomes_opened_under_v1"])
        self.assertEqual(v2["status"], "FROZEN_PREOUTCOME_STOP_BEFORE_ANY_FIRST_WAVE_V4_RESPONSE_OPENING")
        self.assertEqual(v2["supersedes"], "research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V1.json")

    def test_final_detector_calibration_covers_heterogeneity_and_context(self):
        cal = load("research_core_v4/state/DETECTOR_CALIBRATION_RESULT_V3.json")
        self.assertTrue(cal["acceptance"]["type_I_error_control_verified"])
        self.assertTrue(cal["acceptance"]["heterogeneous_effect_power_reported"])
        self.assertTrue(cal["acceptance"]["context_specific_effect_power_reported"])
        self.assertTrue(cal["acceptance"]["high_low_context_selection_calibrated"])
        self.assertLess(cal["negative_control"]["baseline_global_false_positive_rate"], 0.06)
        for fpr in cal["negative_control"]["stressed_false_positive_rates"].values():
            self.assertLess(fpr, 0.06)
        self.assertGreater(
            cal["power_by_effect_prevalence"]["4_OF_6_POSITIVE"]["mde50_bps"],
            cal["power_by_effect_prevalence"]["6_OF_6_POSITIVE"]["mde50_bps"],
        )
        self.assertGreater(
            cal["power_by_context_concentration"]["EFFECT_PRESENT_HIGH_VOL_ONLY"]["mde50_bps"],
            cal["power_by_context_concentration"]["EFFECT_PRESENT_BOTH_VOL_STATES"]["mde50_bps"],
        )
        self.assertFalse(cal["real_market_outcomes_opened"])
        self.assertFalse(cal["broker_contacted"])

    def test_v2_hierarchy_has_no_free_symbol_context_state_or_horizon_selection(self):
        d = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json")
        h = d["hierarchical_inference"]
        self.assertEqual(len(d["structural_contexts"]), 3)
        self.assertEqual(h["leaves_per_structural_context"], 8)
        self.assertEqual(h["local_multiplicity"], "MAXT_ACROSS_8_LEAVES_WITH_SHARED_BLOCK_RESAMPLING")
        self.assertIn("HOLM", h["higher_selection_control"])
        self.assertFalse(h["free_best_symbol"])
        self.assertFalse(h["free_best_context"])
        self.assertFalse(h["free_best_volatility_state"])
        self.assertFalse(h["free_best_horizon"])
        self.assertFalse(h["universal_cross_asset_pooling"])

    def test_volatility_context_is_sibling_not_universality_gate(self):
        d = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json")
        v = d["causal_preentry_volatility_context"]
        self.assertEqual(v["role"], "PREDECLARED_SIBLING_CONTEXT_HYPOTHESES")
        self.assertFalse(v["universality_required"])
        self.assertFalse(v["postoutcome_high_low_selection"])

    def test_incremental_cross_scale_attribution_is_primary(self):
        d = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json")
        a = d["trigger_and_attribution"]
        self.assertTrue(a["same_information_boundary"])
        self.assertFalse(a["baseline_is_not_a_development_candidate"] is False)
        self.assertIn("ADDS_DIRECTIONAL_RESPONSE_INFORMATION", a["primary_attribution_claim"])
        self.assertIn("FULL_ARM_MEAN_MINUS_BASELINE_ARM_MEAN", d["paired_incremental_estimator"]["paired_unit_contrast"])

    def test_sign_only_is_explicitly_resolved_without_threshold_grid(self):
        d = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json")
        s = d["scale_topology"]["sign_only_state_rule"]
        self.assertTrue(s["retained"])
        self.assertIsNone(s["deadband"])
        self.assertFalse(d["scale_topology"]["scale_grid"])
        self.assertFalse(d["scale_topology"]["centered_or_two_sided_filters"])

    def test_development_and_confirmation_are_context_matched_and_disjoint(self):
        d = load("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json")
        dev=set()
        conf=set()
        for c in d["structural_contexts"]:
            self.assertEqual(len(c["development_symbols"]), 6)
            self.assertEqual(len(c["confirmation_symbols"]), 4)
            dev |= {int(x[1]) for x in c["development_symbols"]}
            conf |= {int(x[1]) for x in c["confirmation_symbols"]}
        self.assertTrue(dev.isdisjoint(conf))
        ca=d["confirmation_architecture"]
        self.assertTrue(ca["matched_by_structural_context"])
        self.assertTrue(ca["identity_disjoint"])
        self.assertTrue(ca["time_disjoint"])
        self.assertFalse(ca["data_acquired_now"])
        self.assertFalse(ca["outcomes_opened_now"])
        self.assertTrue(ca["protected_forward_forbidden"])

    def test_v4_canonical_state_is_valid_under_recovery_control_plane(self):
        from tests.test_research_core_v4_control_state_history import validate_historical_v3_and_current_transport

        state=load("research_core_v4/state/V4_STATE.json")
        authority=load("research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_EXECUTION_AUTHORITY_V3.json")
        recovery=load("research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V3.json")
        report=validate_historical_v3_and_current_transport()
        self.assertEqual(report["status"],"PASS_GREENFIELD_RECOVERY_V3_FAIL_CLOSED_PRE_ARM_BLOCKED_NO_REAL_RESPONSE_EXECUTION")
        self.assertEqual(report["accepted_canonical_result_count"],0)
        self.assertFalse(report["real_execution_authorized"])
        self.assertEqual(authority["status"],"AUTHORIZED_READY_NOT_EXECUTED")
        self.assertTrue(authority["real_development_response_execution_authorized"])
        self.assertFalse(authority["confirmation_response_execution_authorized"])
        self.assertFalse(authority["broker_acquisition_authorized"])
        self.assertFalse(authority["quote_revision_v2_execution_authorized"])
        self.assertFalse(authority["protected_forward_opened"])
        self.assertFalse(authority["candidate_promotion_authorized"])
        self.assertEqual(authority["schema"],"mxm.research-core-v4.first-development-response-execution-authority.v3")
        self.assertEqual(len(authority["bindings"]["development_series"]),18)
        self.assertTrue(state["first_wave"]["development_outcomes_opened"])
        self.assertFalse(state["first_wave"]["evaluator_execution_authorized"])
        self.assertFalse(state["first_wave"]["deterministic_crash_recovery_authorized"])
        self.assertEqual(state["first_wave"]["deterministic_crash_recovery_attempt_limit"],1)
        self.assertFalse(state["first_wave"]["confirmation_execution_authorized"])
        self.assertFalse(state["first_wave"]["confirmation_outcomes_opened"])
        self.assertFalse(state["first_wave"]["new_market_acquisition_started"])
        self.assertEqual(recovery["classification"],"GREENFIELD_ONLY_DETERMINISTIC_INFRASTRUCTURE_RECOVERY_V3")
        self.assertFalse(recovery["real_development_response_execution_authorized"])
        self.assertFalse(recovery["arm_authorized"])
        self.assertFalse(recovery["automatic_retry"])
        self.assertTrue(recovery["frozen_reference"]["execution_is_byte_identical_to_reference"])
        audit=load("research_core_v4/state/FRESH_INDEPENDENT_PREOUTCOME_AUDIT_V2.json")
        self.assertEqual(audit["unresolved_findings_gate"]["classification"],"NO_MATERIAL_PREOUTCOME_FINDINGS_REMAIN")



if __name__ == "__main__":
    unittest.main()
