import json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class FrontierInformationGainV1Tests(unittest.TestCase):
    def test_capture_contract_is_read_only_non_economic_and_staged(self):
        c=load("research_v3/BROKER_NATIVE_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT_V1.json")
        self.assertEqual(c["eligible_identity_count"],1578)
        self.assertFalse(c["scope_law"]["economic_panel_selected"])
        self.assertFalse(c["scope_law"]["mechanism_family_selected"])
        self.assertEqual(c["accounting_effect"],{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0})
        tiers=[x["tier"] for x in c["acquisition_tiers"]]
        self.assertIn("SELECTED_EXECUTION_SNAPSHOT",tiers)
        self.assertIn("MECHANISM_LOCAL_TRANSACTION_COST",tiers)

    def test_feature_store_has_full_identity_surface_and_explicit_missingness(self):
        f=load("research_v3/BROKER_NATIVE_FRONTIER_FEATURE_STORE_V1.json")
        self.assertEqual(f["universe_identity_count"],1578)
        self.assertEqual(len(f["identities"]),1578)
        self.assertEqual(f["summary"]["structural_signature_known"],41)
        self.assertEqual(f["summary"]["accepted_13w_identity_data"],40)
        self.assertEqual(f["summary"]["breakout_event_availability_known"],40)
        self.assertEqual(f["summary"]["full_prospective_transaction_local_cost_authority"],0)
        self.assertTrue(f["no_universal_best_symbol_score"])
        self.assertFalse(f["economic_effect"]["returns_or_pnl_computed"])
        self.assertTrue(any(x["structural_signature"] is None for x in f["identities"]))

    def test_opportunity_map_is_mechanism_specific_without_hidden_scalar_rank(self):
        o=load("research_v3/BROKER_NATIVE_FRONTIER_OPPORTUNITY_MAP_V1.json")
        self.assertEqual(len(o["mechanism_layers"]),10)
        self.assertTrue(o["no_scalar_best_symbol_score"])
        self.assertTrue(all(x["economic_pnl_or_outcomes_used"] is False for x in o["mechanism_layers"]))
        self.assertTrue(all(x["universal_symbol_ranking_permitted"] is False for x in o["mechanism_layers"]))

    def test_information_gain_selector_avoids_expensive_full_frontier_cost_capture(self):
        s=load("research_v3/BROKER_NATIVE_FRONTIER_INFORMATION_GAIN_SELECTION_V1.json")
        pick=s["selected_next_acquisition"]
        self.assertEqual(pick["primary"],"RECOVER_HASH_BOUND_ACCEPTED_STRUCTURAL_DERIVATIVE")
        self.assertEqual(pick["fallback_if_not_recoverable"],"RERUN_EXISTING_READ_ONLY_BROKER_UNIVERSE_CAPTURE_V2")
        self.assertEqual(pick["marginal_coverage_gain"],1537)
        self.assertEqual(pick["next_best_alternative"],"STRUCTURAL_REPRESENTATIVE_EXECUTION_SNAPSHOT_41")
        self.assertTrue(s["no_random_ticker_sampling"])
        self.assertTrue(s["no_arbitrary_fixed_top_n"])
        self.assertEqual(s["economic_effect"]["v2_attempts"],0)

    def test_next_capture_reuses_existing_read_only_collector_and_opens_no_outcome(self):
        p=load("research_v3/BROKER_NATIVE_FRONTIER_NEXT_ACQUISITION_PLAN_V1.json")
        cap=p["fallback_read_only_capture"]
        self.assertEqual(cap["collector_package_builder"],"tools/build_competition_broker_universe_capture_package.py")
        self.assertEqual(cap["collector_entrypoint"],"COMPETITION_BROKER_UNIVERSE_CAPTURE_RUN.py")
        self.assertEqual(cap["expected_return_artifact"],"MXM_COMPETITION_BROKER_UNIVERSE_V2.zip")
        self.assertTrue(cap["read_only"])
        self.assertIn("historical_price_series",cap["explicitly_not_requested"])
        self.assertEqual(p["accounting_effect"]["v2_attempts"],0)
        self.assertEqual(p["accounting_effect"]["economic_outcomes"],0)

    def test_final_state_is_external_metadata_gate_not_ai_or_economics(self):
        n=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        self.assertEqual(n["status"],"INFORMATION_GAIN_ACQUISITION_PLAN_READY")
        self.assertFalse(n["research_judgment_required"])
        self.assertFalse(n["ai_reasoning_required"])
        self.assertFalse(n["implementation_ai_required"])
        self.assertTrue(n["external_data_required"])
        self.assertTrue(n["user_action_required"])
        self.assertEqual(n["accounting"],{"v2_attempts_used":20,"v2_search_budget_remaining":64,"economic_outcomes_opened":28})

    def test_provider_and_resource_dimensions_are_not_conflated(self):
        u=load("research_v3/ai_director/PROVIDER_USAGE_V1.json")
        r=load("research_v3/RESOURCE_EFFICIENCY_V1.json")
        self.assertEqual(u["provider_invocations"],4)
        self.assertEqual(u["successful_implementation_invocations"],0)
        dims=r["resource_dimensions"]
        self.assertIn("AI_CREDITS",dims)
        self.assertIn("ACTIONS_RUNNER_MINUTES",dims)
        self.assertIn("V2_ECONOMIC_ATTEMPTS",dims)
        self.assertIsNone(dims["AI_CREDITS"]["actual_account_billed_credits"])
        self.assertIsNone(dims["ACTIONS_RUNNER_MINUTES"]["exact_account_billable_minutes"])

if __name__=="__main__":
    unittest.main()
