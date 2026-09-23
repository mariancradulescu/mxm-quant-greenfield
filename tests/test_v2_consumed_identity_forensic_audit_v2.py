import json
import unittest
from pathlib import Path

from research_v3.forensic_audit import IDS, build_audit

ROOT=Path(__file__).resolve().parents[1]

class ConsumedIdentityForensicAuditV2Tests(unittest.TestCase):
    def test_automated_audit_covers_exact_current_consumed_identity_set(self):
        audit=build_audit(ROOT)
        self.assertEqual(audit["status"],"COMPLETE_LIVE_EQUIVALENT_CORRECTIONS_REQUIRED")
        self.assertEqual(audit["distinct_consumed_identities"],16)
        self.assertEqual(audit["result_recorded_entries"],17)
        self.assertEqual(set(audit["candidate_ids"]),set(IDS))
        self.assertTrue(all(v=="IMPLEMENTATION_INVALID_SAME_SEMANTICS_CORRECTABLE" for v in audit["classifications"].values()))
        self.assertEqual(audit["attempt_accounting"]["v2_attempts_used"],16)
        self.assertEqual(audit["attempt_accounting"]["v2_search_budget_remaining"],68)
        self.assertFalse(audit["safety"]["protected_evidence_opened"])
        self.assertFalse(audit["safety"]["live_orders_authorized"])
        self.assertFalse(audit["safety"]["competition_start_authorized"])

    def test_committed_authority_matches_automated_accounting_and_classifications(self):
        generated=build_audit(ROOT)
        committed=json.loads((ROOT/"evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V2.json").read_text())
        self.assertEqual(committed["distinct_consumed_identities"],generated["distinct_consumed_identities"])
        self.assertEqual(committed["result_recorded_entries"],generated["result_recorded_entries"])
        self.assertEqual(committed["classifications"],generated["classifications"])
        self.assertEqual(committed["attempt_accounting"],generated["attempt_accounting"])
        self.assertEqual(committed["projection_drift"]["classification"],"PERSISTENCE_ONLY_DEFECT")
        self.assertTrue(committed["projection_drift"]["repaired_by_this_audit"])

    def test_current_state_projects_all_historical_results_but_blocks_live_equivalent_authority(self):
        state=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        self.assertEqual(state["forensic_consumed_identity_audit_authority"],"evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V2.json")
        self.assertEqual(set(state["implementation_invalid_consumed_identities"]),set(IDS))
        self.assertEqual(state["live_equivalent_discovery_survivors"],[])
        self.assertEqual(state["v2_attempts_used"],16)
        self.assertEqual(state["v2_search_budget_remaining"],68)
        self.assertEqual(state["discovery_survivors"],[])
        self.assertEqual(state["current_stage_b_survivor_input_set"],[])
        for cid in ("V2-C006","V2-C012"):
            self.assertEqual(
                state["current_result_authority"][cid]["stage_b_current_config"]["state"],
                "INVALIDATED_DOWNSTREAM_OF_IMPLEMENTATION_INVALID_STAGE_A",
            )
            self.assertEqual(
                state["current_result_authority"][cid]["stage_b_current_config"]["invalidation_ref"],
                "evidence/LIVE_EQUIVALENT_STAGE_B_DOWNSTREAM_INVALIDATION_V1.json",
            )
        for cid in IDS:
            self.assertIn(cid,state["current_result_authority"])
            self.assertIn(f"{cid}_STAGE_A",state["active_result_pointers"])
            self.assertEqual(state["current_result_authority"][cid]["stage_a"]["live_equivalent_replay_state"],"IMPLEMENTATION_INVALID_SAME_SEMANTICS_CORRECTABLE")

if __name__=="__main__":
    unittest.main(verbosity=2)
