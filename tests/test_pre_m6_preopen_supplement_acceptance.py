import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class PreM6PreopenSupplementAcceptanceTests(unittest.TestCase):
    def test_01_uploaded_compact_bundle_is_checksum_verified_and_zero_economics(self):
        a=load("data/TIER1_PREOPEN_0930_SUPPLEMENT_ACCEPTANCE_V1.json")
        self.assertEqual(a["status"],"ACCEPTED_COMPACT_BUNDLE_CHECKSUM_VERIFIED_RAW_COMMITMENT_BOUND")
        self.assertEqual(a["source_uploaded_bundle"]["sha256"],"8171ce2d68fef0ac0241b88e914725c16a301e36ae836f766efff4da8aabe798")
        self.assertEqual(a["source_uploaded_bundle"]["checksum_failures"],0)
        self.assertFalse(a["provenance"]["economics"])
        self.assertEqual(a["research_state"]["economic_outcomes_opened"],0)
        self.assertEqual(a["research_state"]["v2_attempts_used"],0)
        self.assertFalse(a["research_state"]["protected_evidence_opened"])

    def test_02_preopen_commitment_is_not_misreported_as_external_raw_byte_recomputation(self):
        a=load("data/TIER1_PREOPEN_0930_SUPPLEMENT_ACCEPTANCE_V1.json")["raw_preopen_commitment"]
        self.assertEqual(a["chunk_count"],4912)
        self.assertEqual(a["total_rows"],6951290)
        self.assertTrue(a["raw_bytes_retained_locally"])
        self.assertFalse(a["raw_bytes_transferred"])
        self.assertFalse(a["raw_bytes_independently_recomputed_by_external_verifier"])
        self.assertTrue(a["local_retention_required"])
        self.assertFalse(a["deletion_authorized"])

    def test_03_0930_state_is_complete_on_all_real_reference_sessions(self):
        x=load("data/TIER1_PREOPEN_0930_SUPPLEMENT_ACCEPTANCE_V1.json")["derived_evidence"]["preopen_0930_causal_state"]
        self.assertEqual(x["real_reference_sessions"],1180)
        self.assertEqual(x["US500_real_sessions_two_sided"],"1180/1180")
        self.assertEqual(x["NAS100_real_sessions_two_sided"],"1180/1180")

    def test_04_c012_generic_support_is_candidate_independent_and_two_rows_fail_closed(self):
        a=load("data/TIER1_PREOPEN_0930_SUPPLEMENT_ACCEPTANCE_V1.json")
        x=a["derived_evidence"]["nas100_c012_generic_bound_support"]
        self.assertEqual(x["rows"],27032)
        self.assertEqual(x["valid_rows"],27030)
        self.assertEqual(x["missing_causal_rows"],0)
        self.assertEqual(x["missing_bilateral_refresh_rows"],2)
        self.assertEqual(x["max_causal_spread_points"],12.5)
        self.assertEqual(x["max_absolute_mid_displacement_to_first_bilateral_refresh_points"],82.8)
        self.assertEqual(x["componentwise_constant_transaction_envelope_points"],95.3)
        unresolved=a["derived_evidence"]["unresolved_generic_boundaries"]
        self.assertEqual([(x["session_date"],x["boundary_local_et"]) for x in unresolved],[("2024-12-31","15:00"),("2025-12-31","15:00")])

    def test_05_c012_cost_gate_is_frozen_before_signals_and_never_imputes_unsupported_contexts(self):
        g=load("evidence/C012_DISCOVERY_COST_APPLICABILITY_GATE_V1.json")
        self.assertEqual(g["status"],"FROZEN_PRE_OUTCOME_FAIL_CLOSED")
        self.assertEqual(g["rule"]["transaction_cost_envelope_points"],95.3)
        self.assertEqual(g["rule"]["nominal_round_trip_two_transaction_envelope_points"],190.6)
        self.assertTrue(g["rule"]["candidate_direction_independent"])
        self.assertTrue(g["rule"]["candidate_pnl_independent"])
        self.assertTrue(g["rule"]["candidate_signal_independent_at_freeze"])
        self.assertFalse(any(g["forbidden_inputs_used"].values()))
        joined="\n".join(g["fail_closed_application"])
        self.assertIn("COST_UNRESOLVED",joined)
        self.assertIn("outside the supported domain",joined)
        self.assertIn("late-session exit",joined)

    def test_06_calibration_v3_marks_both_tier1_candidates_preoutcome_ready_without_fill_truth_claim(self):
        c=load("evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V3.json")
        self.assertEqual(c["selected_state"],"CONSERVATIVE_BOUND")
        self.assertEqual(c["products"]["US500"]["readiness"],"READY_PRE_OUTCOME")
        self.assertEqual(c["products"]["NAS100"]["readiness"],"READY_PRE_OUTCOME_WITH_FAIL_CLOSED_COST_APPLICABILITY_GATE")
        self.assertFalse(c["products"]["US500"]["certification_fill_truth"])
        self.assertFalse(c["products"]["NAS100"]["certification_fill_truth"])
        self.assertFalse(any(c["candidate_inputs_used"].values()))

    def test_07_readiness_v6_requires_no_more_user_capture_and_keeps_other_blockers_explicit(self):
        r=load("data/PRIMARY_WAVE_02_PRE_M6_READINESS_V6.json")
        self.assertEqual(r["ready_for_first_clean_stage_a"],["V2-C006","V2-C012"])
        self.assertEqual(set(r["still_preoutcome_blocked"]),{"V2-C007","V2-C008","V2-C009","V2-C010","V2-C011"})
        self.assertFalse(r["user_action_required"])
        self.assertFalse(r["global_full_wave_complete"])

    def test_08_current_state_points_to_v7_v4_and_keeps_research_invariants_zero(self):
        state = load("CURRENT_STATE.json")
        auth = load("data/M6_STAGE_A_EXECUTION_AUTHORIZATION_V1.json")
        self.assertEqual(state["pre_m6_readiness_authority"], "data/PRIMARY_WAVE_02_PRE_M6_READINESS_V7.json")
        self.assertEqual(state["tier1_discovery_execution_cost_calibration_result_authority"], "evidence/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_RESULT_V4.json")
        self.assertEqual(state["tier1_preopen_0930_supplement_acceptance_authority"], "data/TIER1_PREOPEN_0930_SUPPLEMENT_ACCEPTANCE_V1.json")
        self.assertEqual(state["c012_discovery_cost_applicability_gate_authority"], "evidence/C012_DISCOVERY_COST_APPLICABILITY_GATE_V1.json")
        self.assertFalse(state["user_action_required"])
        self.assertEqual(auth["preconditions"]["economic_outcomes_opened"], 0)
        self.assertEqual(auth["preconditions"]["v2_attempts_used"], 0)
        self.assertEqual(auth["preconditions"]["v2_evaluated_identities"], 0)
        self.assertFalse(state["protected_evidence_opened"])
if __name__=="__main__":
    unittest.main(verbosity=2)
