from __future__ import annotations
import json
import unittest
from pathlib import Path
from research_v3.discovery_governance import active_open_families,classify_parameter_surface,evidence_class_can_close_family,validate_confirmation_freeze,validate_parameter_discovery_plan,validate_proposal_discovery_governance
ROOT=Path(__file__).resolve().parents[1]

class DiscoveryGovernanceV1Tests(unittest.TestCase):
    def test_legacy_local_nulls_cannot_close_or_starve_families(self):
        state=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        families=state["families_exhausted_non_economically"]
        self.assertEqual(len(families),3)
        self.assertIn("NON_AUTHORITATIVE_FOR_FAMILY_CLOSURE_FRONTIER_SELECTION_OR_ANTI_STARVATION",state["families_exhausted_non_economically_semantics"])
        self.assertEqual(active_open_families(state,families),families)
        for family in families:
            self.assertIn(family,active_open_families(state,[family]))
        with self.assertRaisesRegex(ValueError,"modern closure audit"):
            active_open_families({**state,"family_level_closure":{"status":"FAMILY_LEVEL_CLOSED_WITH_EVIDENCE"}},families)

    def test_exact_candidate_null_does_not_close_family(self):
        self.assertFalse(evidence_class_can_close_family("EXACT_SPECIFICATION_NULL",explicit_closure_audit=True,adequate_power=True,parameter_region_coverage=True,meaningful_universe_breadth=True,asset_class_coverage=True,horizon_coverage=True,plausible_unexplored_frontier=False))

    def test_one_parameter_point_cannot_create_family_exhaustion_authority(self):
        with self.assertRaisesRegex(ValueError,"one parameter point"):
            validate_parameter_discovery_plan({"protected_forward_used":False,"ranges_frozen_before_development_surface":True,"record_all_probes":True,"blind_large_cartesian_grid":False,"threshold_spam":False,"parameter_search_breadth":1,"family_exhaustion_claim":True})

    def test_low_power_data_insufficient_and_cost_rejection_cannot_close_family(self):
        for cls in ("LOW_POWER_INCONCLUSIVE","DATA_INSUFFICIENT","COST_OR_REALIZABILITY_REJECTED"):
            self.assertFalse(evidence_class_can_close_family(cls,explicit_closure_audit=True,adequate_power=True,parameter_region_coverage=True,meaningful_universe_breadth=True,asset_class_coverage=True,horizon_coverage=True,plausible_unexplored_frontier=False))

    def test_protected_data_excluded_and_all_probes_required(self):
        base={"ranges_frozen_before_development_surface":True,"record_all_probes":True,"blind_large_cartesian_grid":False,"threshold_spam":False,"parameter_search_breadth":4,"family_exhaustion_claim":False}
        validate_parameter_discovery_plan({**base,"protected_forward_used":False})
        with self.assertRaisesRegex(ValueError,"protected evidence"):
            validate_parameter_discovery_plan({**base,"protected_forward_used":True})
        with self.assertRaisesRegex(ValueError,"record all probes"):
            validate_parameter_discovery_plan({**base,"protected_forward_used":False,"record_all_probes":False})

    def test_isolated_spike_not_promoted_broad_neighborhood_can_be(self):
        self.assertEqual(classify_parameter_surface([{"development_only":True,"effect":1.0,"neighbor_consistent":True}]),"ISOLATED_POINT_NOT_REGION")
        pts=[{"development_only":True,"effect":x,"neighbor_consistent":True} for x in (0.1,0.2,0.15)]
        self.assertEqual(classify_parameter_surface(pts),"ROBUST_PARAMETER_REGION_CANDIDATE")

    def test_confirmatory_parameters_cannot_change_after_outcome(self):
        with self.assertRaisesRegex(ValueError,"cannot change"):
            validate_confirmation_freeze({"lookback":24},{"lookback":25},outcome_observed=True)

    def test_ledger_and_audit_preserve_scope_laws(self):
        audit=json.loads((ROOT/"evidence/RETROSPECTIVE_EVIDENCE_SCOPE_AUDIT_V1.json").read_text())
        ledger=json.loads((ROOT/"research_v3/DISCOVERY_COVERAGE_LEDGER_V1.json").read_text())
        multi=json.loads((ROOT/"research_v3/MULTI_FRONTIER_DISCOVERY_GOVERNOR_V1.json").read_text())
        self.assertEqual(audit["family_exhaustion"]["mechanism_family_closed_count"],0)
        self.assertFalse(audit["preservation"]["historical_outcomes_erased"])
        self.assertTrue(audit["preservation"]["valid_raw_development_data_remains_reusable_with_provenance"])
        self.assertTrue(audit["preservation"]["protected_forward_remains_excluded"])
        self.assertFalse(ledger["source_frontier"]["structural_representatives_default_inferential_authority"])
        self.assertFalse(multi["anti_starvation"]["fixed_quota"])
        self.assertTrue(all(x["mechanism_family_exhaustion_authority"] is False for x in audit["local_parked_frontiers"]["items"]))

    def test_one_asset_class_cannot_burn_another(self):
        p={"proposal_id":"new","decision":{"selected_mechanism_family":"TREND_MOMENTUM","close_asset_class":True,"discovery_governance":{"parameter_governor_ref":"research_v3/PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1.json","coverage_ledger_ref":"research_v3/DISCOVERY_COVERAGE_LEDGER_V1.json","structural_41_default_inferential_authority":False,"local_parked_scope_is_family_exhaustion":False,"alternatives_considered":["FX"]}},"mechanism_family_closure_claims":[]}
        with self.assertRaisesRegex(ValueError,"one asset class"):
            validate_proposal_discovery_governance(ROOT,p)

    def test_existing_exact_negative_result_remains_immutable(self):
        audit=json.loads((ROOT/"evidence/RETROSPECTIVE_EVIDENCE_SCOPE_AUDIT_V1.json").read_text())
        row=next(x for x in audit["records"] if x["candidate_or_epoch_id"]=="V2-C032")
        self.assertEqual(row["exact_result"],"GROSS_EDGE_FAIL")
        self.assertTrue(row["exact_identity_immutable"])
        self.assertFalse(row["family_exhaustion_authority"])

    def test_zero_user_github_operations_is_governance_intent(self):
        multi=json.loads((ROOT/"research_v3/MULTI_FRONTIER_DISCOVERY_GOVERNOR_V1.json").read_text())
        self.assertFalse(multi["selection_contract"]["user_symbol_parameter_mechanism_or_horizon_selection_required"])

if __name__=="__main__":
    unittest.main()
