import json
import unittest
from pathlib import Path

from m6.stage_b_current_config_tier1_runner import (
    CurrentConfigExecutionNotAuthorized,
    validate_execution_authorization,
    verify_repository_current_config_authorities,
)

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class StageBCurrentConfigExecutionAuthorizationV2Tests(unittest.TestCase):
    def test_01_v2_is_preserved_as_failed_exact_head_binding_artifact(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V2.json")
        self.assertEqual(a["status"],"AUTHORIZED")
        self.assertTrue(a["single_use"])
        self.assertFalse(a["consumed"])
        self.assertTrue(a["execution_authorized"])
        self.assertTrue(a["independent_audit_pass"])
        self.assertNotIn("current_config_stage_b_outcomes_before_authorization",a)
        with self.assertRaises(CurrentConfigExecutionNotAuthorized):
            validate_execution_authorization(a)

    def test_02_authorization_binds_green_corrected_head(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V2.json")
        ci=a["activation_precondition_ci"]
        self.assertEqual(ci["head"],"551e51ea9debf36d1374665648e83f2c06c13d80")
        self.assertEqual(ci["run_id"],35589599912)
        self.assertEqual(ci["conclusion"],"SUCCESS")
        self.assertEqual(ci["tests_passed"],524)
        self.assertEqual(ci["tests_failed"],0)

    def test_03_attempt_budget_and_discovery_ledger_do_not_change(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V2.json")
        x=a["accounting_semantics"]
        self.assertEqual(x["new_v2_attempts_authorized"],0)
        self.assertEqual(x["new_v2_evaluated_identities_authorized"],0)
        self.assertEqual(x["search_budget_units_authorized"],0)
        self.assertEqual(x["v2_attempts_used_after_execution"],2)
        self.assertEqual(x["v2_evaluated_identities_after_execution"],2)
        self.assertEqual(x["v2_search_budget_remaining_after_execution"],82)
        self.assertEqual(x["current_config_stage_b_outcomes_authorized"],2)
        self.assertEqual(x["economic_outcomes_opened_after_two_scenario_results"],4)
        self.assertEqual(x["discovery_result_recorded_after"],2)
        self.assertEqual(x["discovery_ledger_entries_after"],22)

    def test_04_v2_authorization_history_is_preserved_after_execution(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V2.json")
        s=load("CURRENT_STATE.json")
        t=s["m6"]["stage_b_current_configuration"]
        self.assertEqual(a["status"],"AUTHORIZED")
        self.assertFalse(a["consumed"])
        self.assertTrue(a["execution_authorized"])
        self.assertEqual(t["state"],"EXECUTED_RESULTS_PERSISTED")
        self.assertFalse(t["execution_authorized"])
        self.assertTrue(t["authorization_consumed"])
        self.assertTrue(t["economics_run"])
        self.assertTrue(t["results_created"])
        self.assertEqual(t["stage_b_current_config_outcomes_opened"],2)
        self.assertEqual(s["economic_outcomes_opened"],8)
        self.assertEqual(s["v2_attempts_used"],6)
        self.assertEqual(s["v2_evaluated_identities"],6)
        self.assertEqual(s["v2_search_budget_remaining"],78)
        self.assertFalse(s["protected_evidence_opened"])

    def test_05_historical_margin_is_explicitly_non_blocking_not_resolved(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V2.json")
        self.assertEqual(
            a["historical_margin_authority_state"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertFalse(a["historical_margin_authority_changed"])
        self.assertFalse(a["historical_margin_blocks_this_execution"])
        self.assertEqual(a["result_semantics"]["historical_certification_effect"],"NONE")
        self.assertFalse(a["result_semantics"]["certification_survivor_promotion_authorized"])

if __name__=="__main__":
    unittest.main(verbosity=2)
