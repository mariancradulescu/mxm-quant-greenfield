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

class StageBCurrentConfigExecutionAuthorizationV3Tests(unittest.TestCase):
    def test_01_v3_satisfies_exact_validator_contract(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V3.json")
        self.assertEqual(a["status"],"AUTHORIZED")
        self.assertTrue(a["single_use"])
        self.assertFalse(a["consumed"])
        self.assertTrue(a["execution_authorized"])
        self.assertTrue(a["independent_audit_pass"])
        self.assertEqual(a["current_config_stage_b_outcomes_before_authorization"],0)
        validate_execution_authorization(a)

    def test_02_v3_preserves_current_operational_truth_and_historical_separation(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V3.json")
        self.assertFalse(a["historical_margin_blocks_this_execution"])
        self.assertFalse(a["historical_margin_authority_changed"])
        self.assertEqual(
            a["historical_margin_authority_state"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertEqual(a["result_semantics"]["required_label"],
                         "STAGE_B_CURRENT_CONFIGURATION_SCENARIO")
        self.assertEqual(a["result_semantics"]["historical_certification_effect"],"NONE")

    def test_03_v3_authorizes_no_new_search_attempt(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V3.json")
        x=a["accounting_semantics"]
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

    def test_04_v3_was_green_and_unconsumed_before_reporting_v4(self):
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V3.json")
        e=load("evidence/M6_STAGE_B_CURRENT_CONFIG_REPORTING_COMPLETENESS_V1.json")
        self.assertEqual(a["status"],"AUTHORIZED")
        self.assertFalse(a["consumed"])
        self.assertFalse(e["resolution"]["authorization_v3_consumed"])
        self.assertEqual(e["last_green_authorization"]["head"],
                         "41f7ca14b22c1a06c5d0d3bab320dd38d31821b2")
        self.assertEqual(e["last_green_authorization"]["ci_run"],35589983786)
        self.assertEqual(e["last_green_authorization"]["conclusion"],"SUCCESS")

    def test_05_failed_v2_binding_is_explicitly_superseded(self):
        c=load("evidence/M6_STAGE_B_CURRENT_CONFIG_AUTHORIZATION_BINDING_CORRECTION_V1.json")
        a=load("data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V3.json")
        self.assertEqual(
            c["failed_activation"]["head"],
            "035b5c39a39e81ded0944320f3e4512d83021470",
        )
        self.assertEqual(c["failed_activation"]["ci_run"],35589787219)
        self.assertEqual(a["supersedes"]["ref"],
                         "data/M6_STAGE_B_CURRENT_CONFIG_EXECUTION_AUTHORIZATION_V2.json")
        self.assertFalse(c["correction"]["economic_semantics_changed"])
        self.assertFalse(c["correction"]["authorization_semantics_changed"])

if __name__=="__main__":
    unittest.main(verbosity=2)
