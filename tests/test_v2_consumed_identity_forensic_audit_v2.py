import json
import unittest
from pathlib import Path
from research_v3.forensic_classifier_v3 import ALL, IMPLEMENTATION_ONLY, SPEC_INVALID, build_audit

ROOT=Path(__file__).resolve().parents[1]

class ConsumedIdentityForensicAuditV3Tests(unittest.TestCase):
    def test_candidate_by_candidate_classification_and_accounting(self):
        generated=build_audit(ROOT)
        self.assertEqual(generated["status"],"COMPLETE_PER_IDENTITY_CLASSIFICATION")
        self.assertEqual(generated["groups"]["implementation_only_same_semantics_correctable"],sorted(IMPLEMENTATION_ONLY))
        self.assertEqual(generated["groups"]["frozen_spec_causally_invalid_requires_new_identity"],sorted(SPEC_INVALID))
        self.assertEqual(generated["attempt_accounting"]["historical_evaluated_identity_count"],16)
        self.assertEqual(generated["attempt_accounting"]["v2_attempts_used"],4)
        self.assertEqual(generated["attempt_accounting"]["v2_search_budget_remaining"],80)
        self.assertEqual(generated["attempt_accounting"]["released_invalid_spec_slot_count"],12)

    def test_committed_authority_matches_generated_classification(self):
        generated=build_audit(ROOT)
        committed=json.loads((ROOT/"evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V3.json").read_text())
        self.assertEqual(committed["classifications"],generated["classifications"])
        for key in ("historical_evaluated_candidate_ids","budget_charged_candidate_ids","v2_attempts_used","v2_search_budget_remaining","released_invalid_spec_candidate_ids"):
            self.assertEqual(committed["attempt_accounting"][key],generated["attempt_accounting"][key])

    def test_current_state_separates_historical_exposure_from_budget_charge(self):
        state=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        self.assertEqual(state["forensic_consumed_identity_audit_authority"],"evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V3.json")
        self.assertEqual(set(state["implementation_invalid_consumed_identities"]),set(IMPLEMENTATION_ONLY))
        self.assertEqual(set(state["frozen_spec_invalid_consumed_identities"]),set(SPEC_INVALID))
        self.assertEqual(state["v2_attempts_used"],4)
        self.assertEqual(state["v2_evaluated_identities"],16)
        self.assertEqual(state["v2_search_budget_remaining"],80)
        self.assertEqual(state["global_attempts_seen"],32)
        self.assertEqual(state["economic_outcomes_opened"],19)
        self.assertEqual(state["discovery_survivors"],[])
        self.assertEqual(state["current_stage_b_survivor_input_set"],[])
        for cid in ALL:
            self.assertIsNone(state["active_result_pointers"][f"{cid}_STAGE_A"])
        for cid in IMPLEMENTATION_ONLY:
            a=state["current_result_authority"][cid]["stage_a"]
            self.assertEqual(a["live_equivalent_replay_state"],"IMPLEMENTATION_ONLY_SAME_SEMANTICS_CORRECTABLE")
            self.assertTrue(a["same_identity_correction_allowed"])
            self.assertFalse(a["new_identity_required"])
        for cid in SPEC_INVALID:
            a=state["current_result_authority"][cid]["stage_a"]
            self.assertEqual(a["live_equivalent_replay_state"],"FROZEN_SPEC_CAUSALLY_INVALID_REQUIRES_NEW_IDENTITY")
            self.assertFalse(a["same_identity_correction_allowed"])
            self.assertTrue(a["new_identity_required"])

    def test_v2_audit_is_preserved_but_superseded(self):
        old=json.loads((ROOT/"evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V2.json").read_text())
        new=json.loads((ROOT/"evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V3.json").read_text())
        self.assertEqual(old["status"],"COMPLETE_LIVE_EQUIVALENT_CORRECTIONS_REQUIRED")
        self.assertEqual(new["supersedes_for_current_classification"],"evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V2.json")

if __name__=="__main__":
    unittest.main(verbosity=2)
