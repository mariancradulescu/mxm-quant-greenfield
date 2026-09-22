import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class StageBMarginHistoryCaptureAcceptanceTests(unittest.TestCase):
    def test_capture_is_valid_but_zero_target_history(self):
        a=load("data/M6_STAGE_B_MARGIN_HISTORY_CAPTURE_ACCEPTANCE_V1.json")
        self.assertEqual(a["status"],"PASS_CAPTURE_VALID_MARGIN_AUTHORITY_UNRESOLVED")
        self.assertEqual(a["capture_contract"]["initial_window_count"],56)
        self.assertEqual(a["capture_contract"]["complete_leaf_window_count"],56)
        self.assertEqual(a["capture_contract"]["deal_list_request_count"],56)
        self.assertEqual(a["capture_contract"]["has_more_response_count"],0)
        self.assertTrue(a["privacy_audit"]["pass"])
        self.assertEqual(a["privacy_audit"]["forbidden_identity_or_credential_keys_detected"],[])
        self.assertEqual(
            a["historical_observation_result"]["US500"]["state"],
            "UNRESOLVED_NO_ACCOUNT_NATIVE_HISTORICAL_MARGIN_OBSERVATIONS",
        )
        self.assertEqual(
            a["historical_observation_result"]["NAS100"]["state"],
            "UNRESOLVED_NO_ACCOUNT_NATIVE_HISTORICAL_MARGIN_OBSERVATIONS",
        )
        self.assertEqual(
            a["component_sha256"]["historical_margin_observations.jsonl"],
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_transport_wrapper_is_canonicalized_without_semantic_change(self):
        a=load("data/M6_STAGE_B_MARGIN_HISTORY_CAPTURE_ACCEPTANCE_V1.json")
        self.assertTrue(a["source_uploaded_bundle"]["transport_wrapper_detected"])
        self.assertEqual(
            a["source_uploaded_bundle"]["sha256"],
            "b216c9e6f44defd8c01ad0131a2eced593a100b8f82e92f231e2740f0d8fa523",
        )
        self.assertEqual(
            a["canonical_repack"]["sha256"],
            "e31b053489c04f610635ce1a70064bc3b5f64ffa48d59e497f6d73a1213b1546",
        )
        self.assertFalse(a["canonical_repack"]["semantic_content_changed"])

    def test_public_evidence_does_not_promote_minimum_to_upper_bound(self):
        historical=load("evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V1.json")
        r=load("evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V2.json")
        self.assertFalse(
            historical["reasoning"]["using_5_percent_as_historical_exact_margin_would_be_optimistic"]
        )
        self.assertEqual(
            r["supersedes"]["ref"],
            "evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V1.json",
        )
        self.assertEqual(
            r["supersedes"]["git_blob_sha1"],
            "7d9535f6cd766ebc1c14a90b38b5045b365a1031",
        )
        self.assertEqual(r["status"],"UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND")
        reasoning=r["reasoning"]
        self.assertTrue(reasoning["regulatory_5_percent_is_a_minimum_required_margin_not_a_maximum_required_margin"])
        self.assertTrue(reasoning["using_5_percent_as_historical_exact_margin_would_be_optimistic"])
        self.assertTrue(reasoning["current_margin_or_leverage_backfill_into_2022_2026_forbidden"])
        self.assertTrue(reasoning["broker_could_have_required_more_margin_historically"])
        self.assertTrue(reasoning["therefore_conservative_historical_max_required_margin_eur_not_proven"])
        premises=(
            reasoning["regulatory_5_percent_is_a_minimum_required_margin_not_a_maximum_required_margin"]
            and reasoning["broker_could_have_required_more_margin_historically"]
            and reasoning["using_5_percent_as_historical_exact_margin_would_be_optimistic"]
        )
        self.assertTrue(premises)
        self.assertEqual(
            r["logical_consistency"]["implication"],
            "HISTORICAL_UPPER_BOUND_REMAINS_UNRESOLVED",
        )
        self.assertTrue(r["logical_consistency"]["implication_satisfied"])
        self.assertTrue(reasoning["therefore_conservative_historical_max_required_margin_eur_not_proven"])
        self.assertFalse(r["conclusion"]["historical_margin_authority_frozen"])
        self.assertFalse(r["conclusion"]["stage_b_execution_authorized"])
        self.assertFalse(r["conclusion"]["stage_b_economics_may_run"])
        self.assertFalse(r["conclusion"]["user_recapture_same_package_required"])

    def test_active_authority_is_v2_and_gate_stays_fail_closed(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(
            s["m6_stage_b_historical_margin_authority_resolution"],
            "evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V2.json",
        )
        self.assertEqual(
            s["m6_stage_b_historical_margin_authority_resolution_historical_v1"],
            "evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V1.json",
        )
        self.assertEqual(
            s["m6"]["stage_b"]["historical_margin_authority_resolution_ref"],
            "evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V2.json",
        )
        self.assertEqual(
            s["m6"]["stage_b"]["historical_margin_gate"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertFalse(s["m6"]["stage_b"]["historical_margin_authority_frozen"])
        self.assertFalse(s["m6"]["stage_b"]["execution_authorized"])
        self.assertFalse(s["m6"]["stage_b"]["economics_run"])
        self.assertEqual(s["m6"]["stage_b"]["stage_b_outcomes_opened"],0)

    def test_accounting_includes_current_config_outcomes_and_protected_boundary_is_unchanged(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(s["v2_search_budget"],84)
        self.assertEqual(s["m6"]["stage_b"]["stage_b_outcomes_opened"],0)
        self.assertFalse(s["m6"]["stage_b"]["execution_authorized"])
        self.assertFalse(s["m6"]["stage_b"]["economics_run"])
        self.assertFalse(s["m6"]["stage_b"]["results_created"])
        self.assertFalse(s["protected_evidence_opened"])
        self.assertTrue(s["m6"]["stage_b"].get("broker_confirmation_required"))
        self.assertFalse(s["m6"]["stage_b"]["broker_confirmation_blocks_current_configuration_scenario"])
        self.assertFalse(s["user_action_required"])
        self.assertTrue(
            s["m6"]["stage_b_current_configuration"]["historical_broker_confirmation_optional_non_blocking"]
        )
        self.assertEqual(
            s["m6"]["stage_b"]["historical_margin_gate"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )

if __name__=="__main__":
    unittest.main(verbosity=2)
