import json
import unittest
from pathlib import Path

from m6.stage_b_current_config_tier1_runner import (
    validate_execution_authorization,
    verify_repository_current_config_authorities,
)

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class StageBCurrentConfigExecutionAuthorizationV4Tests(unittest.TestCase):
    def test_01_v4_is_valid_single_use_authorization(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V4.json")
        self.assertEqual(a["status"],"AUTHORIZED")
        self.assertTrue(a["single_use"])
        self.assertFalse(a["consumed"])
        self.assertTrue(a["execution_authorized"])
        self.assertTrue(a["independent_audit_pass"])
        self.assertEqual(a["current_config_stage_b_outcomes_before_authorization"],0)
        validate_execution_authorization(a)

    def test_02_v4_binds_complete_reporting_stack(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V4.json")
        self.assertEqual(
            a["reporting_policy_ref"],
            "data/M6_STAGE_B_CURRENT_CONFIG_REPORTING_POLICY_V1.json",
        )
        self.assertEqual(a["reporting_policy_git_blob_sha1"],
                         "e0419b33a7d3dfc5b6ee94b0038093fefcf9c599")
        self.assertEqual(a["reporting_module_git_blob_sha1"],
                         "49851e3ce8d82a3d7661639d76625987b6815638")
        ci=a["reporting_stack_precondition_ci"]
        self.assertEqual(ci["head"],"406cb7adeaaeb240ce7e0f138aaddf35119bf87c")
        self.assertEqual(ci["run_id"],35590368467)
        self.assertEqual(ci["tests_passed"],539)
        self.assertEqual(ci["tests_failed"],0)
        self.assertEqual(ci["conclusion"],"SUCCESS")

    def test_03_v4_accounting_is_same_identities_no_new_attempts(self):
        x=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V4.json")["accounting_semantics"]
        self.assertEqual(x["new_v2_attempts_authorized"],0)
        self.assertEqual(x["new_v2_evaluated_identities_authorized"],0)
        self.assertEqual(x["search_budget_units_authorized"],0)
        self.assertEqual(x["v2_attempts_used_after_execution"],2)
        self.assertEqual(x["v2_evaluated_identities_after_execution"],2)
        self.assertEqual(x["v2_search_budget_remaining_after_execution"],82)
        self.assertEqual(x["current_config_stage_b_outcomes_authorized"],2)
        self.assertEqual(x["economic_outcomes_opened_after_two_scenario_results"],4)
        self.assertEqual(x["discovery_ledger_entries_after"],22)
        self.assertEqual(x["discovery_result_recorded_after"],2)

    def test_04_live_state_points_to_v4_history_and_is_closed_post_execution(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V4.json")
        s=load("CURRENT_STATE.json")
        t=s["m6"]["stage_b_current_configuration"]
        self.assertEqual(
            t["execution_authorization_ref"],
            "data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V4.json",
        )
        self.assertEqual(a["status"],"AUTHORIZED")
        self.assertFalse(a["consumed"])
        self.assertTrue(a["execution_authorized"])
        self.assertEqual(t["state"],"EXECUTED_RESULTS_PERSISTED")
        self.assertFalse(t["execution_authorized"])
        self.assertTrue(t["authorization_consumed"])
        self.assertFalse(t["execution_deferred_pending_v4_reporting_binding"])
        self.assertTrue(t["economics_run"])
        self.assertTrue(t["results_created"])
        self.assertEqual(t["stage_b_current_config_outcomes_opened"],2)
        self.assertFalse(s["protected_evidence_opened"])

    def test_05_current_operational_truth_does_not_resolve_history(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V4.json")
        self.assertFalse(a["historical_margin_blocks_this_execution"])
        self.assertFalse(a["historical_margin_authority_changed"])
        self.assertEqual(
            a["historical_margin_authority_state"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertEqual(a["result_semantics"]["historical_certification_effect"],"NONE")

if __name__=="__main__":
    unittest.main(verbosity=2)
