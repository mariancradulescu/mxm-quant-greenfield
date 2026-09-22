import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class StageBCurrentConfigPreExecutionAuditTests(unittest.TestCase):
    def test_01_audit_passes_only_current_configuration_track(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_PRE_EXECUTION_AUDIT_V1.json")
        self.assertEqual(a["status"],"PASS_CURRENT_CONFIGURATION_TRACK_READY_FOR_SEPARATE_AUTHORIZATION")
        self.assertTrue(a["semantic_audit"]["current_configuration_is_operational_authority_for_this_track"])
        self.assertFalse(a["semantic_audit"]["historical_uncertainty_blocks_current_scenario"])
        self.assertFalse(a["semantic_audit"]["historical_invariance_claimed"])
        self.assertTrue(a["semantic_audit"]["current_evaluator_has_no_historical_margin_gate_dependency"])

    def test_02_exact_head_and_execution_inputs_are_bound(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_PRE_EXECUTION_AUDIT_V1.json")
        self.assertEqual(a["audited_head"],"cd55ffdc4f4b8876dc59013eb21bec44211fbdb4")
        self.assertEqual(a["exact_head_ci"]["run_id"],35578736226)
        self.assertEqual(a["exact_head_ci"]["conclusion"],"SUCCESS")
        self.assertEqual(a["exact_head_ci"]["tests_passed"],515)
        self.assertEqual(a["exact_head_ci"]["tests_failed"],0)
        self.assertTrue(a["execution_input_reconciliation"]["all_five_frozen_execution_inputs_match"])
        self.assertFalse(a["execution_input_reconciliation"]["new_capture_required"])

    def test_03_historical_track_remains_unresolved_and_separate(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_PRE_EXECUTION_AUDIT_V1.json")
        h=load("evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V2.json")
        self.assertEqual(h["status"],"UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND")
        self.assertEqual(
            a["semantic_audit"]["historical_point_in_time_margin_state"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertFalse(a["semantic_audit"]["historical_uncertainty_blocks_current_scenario"])

    def test_04_audit_does_not_open_economics_or_authorize_execution(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_PRE_EXECUTION_AUDIT_V1.json")
        s=load("CURRENT_STATE.json")
        auth=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V1.json")
        self.assertFalse(a["audit_opened_economic_outcome"])
        self.assertEqual(a["accounting_at_audit"]["economic_outcomes_opened"],2)
        self.assertEqual(a["accounting_at_audit"]["current_config_stage_b_outcomes_opened"],0)
        self.assertEqual(auth["status"],"FROZEN_SINGLE_USE_PENDING_INDEPENDENT_AUDIT")
        self.assertFalse(auth["execution_authorized"])
        self.assertFalse(auth["consumed"])
        self.assertTrue(s["m6"]["stage_b_current_configuration"]["independent_audit_pass"])
        self.assertEqual(
            s["m6"]["stage_b_current_configuration"]["state"],
            "EXECUTED_RESULTS_PERSISTED",
        )
        self.assertTrue(s["m6"]["stage_b_current_configuration"]["economics_run"])
        self.assertFalse(s["protected_evidence_opened"])

    def test_05_attempt_and_search_accounting_is_unchanged(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(s["economic_outcomes_opened"],10)
        self.assertEqual(s["v2_attempts_used"],8)
        self.assertEqual(s["v2_evaluated_identities"],8)
        self.assertEqual(s["v2_search_budget"],84)
        self.assertEqual(s["v2_search_budget_remaining"],76)
        self.assertFalse(s["m6"]["stage_b_current_configuration"]["historical_margin_non_blocking_for_current_scenario"] is False)

if __name__=="__main__":
    unittest.main(verbosity=2)
