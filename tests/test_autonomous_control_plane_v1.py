import json,tempfile,unittest
from pathlib import Path
from research_v3.autonomous_control_plane import (
    inspect_repository_state,targeted_test_modules,validate_repository_state,write_checkpoint,
)

ROOT=Path(__file__).resolve().parents[1]

class AutonomousControlPlaneV1Tests(unittest.TestCase):
    def test_current_repository_self_diagnoses_without_chat_memory(self):
        report=validate_repository_state(ROOT)
        self.assertEqual(report["material_issues"],[])
        a=report["accounting"]; l=report["lifecycle"]
        self.assertEqual(a["v2_attempts_used"],l["distinct_identity_outcomes_opened"])
        self.assertEqual(a["v2_search_budget_remaining"],a["v2_search_budget"]-a["v2_attempts_used"])
        self.assertEqual(a["economic_outcomes_opened"],l["stage_a_result_recorded_entries"]+a["stage_b_current_config_economic_observations"])
        self.assertFalse(any(report["safety"].values()))
        classes={x["class"] for x in report["recoverable_conditions"]}
        if "OPENED_WAVE_PENDING_EXACT_HEAD_GREEN_RECONCILIATION" in classes:
            self.assertEqual(report["next_action"],"RECONCILE_EXISTING_EXACT_HEAD_GREEN_AND_CLOSE_WAVE")
        elif "AUTHORIZED_WAVE_UNOPENED" in classes:
            self.assertEqual(report["next_action"],"EXECUTE_AUTHORIZED_WAVE")
        elif "FROZEN_WAVE_PENDING_AUTHORIZATION" in classes:
            self.assertEqual(report["next_action"],"REQUIRE_EXACT_HEAD_GREEN_AND_BIND_AUTHORIZATION")
        elif "RESEARCH_SCOPE_GOVERNANCE_MISSING" in classes:
            self.assertEqual(report["next_action"],"IMPLEMENT_RESEARCH_SCOPE_UNIVERSE_GOVERNANCE")
        elif "RESEARCH_SCOPE_GOVERNANCE_PENDING_EXACT_HEAD_GREEN" in classes:
            self.assertEqual(report["next_action"],"REQUIRE_SCOPE_GOVERNANCE_EXACT_HEAD_GREEN")
        elif report["stage_b_revalidation_required_candidate_ids"]:
            self.assertEqual(report["next_action"],"REVALIDATE_STAGE_B")
        else:
            self.assertEqual(report["next_action"],"FREEZE_NEXT_HIGH_INFORMATION_WAVE")
        self.assertTrue(any(x["wave_key"]=="wave04" for x in report["blocked_historical_waves"]))

    def test_targeted_validation_is_selected_from_lifecycle(self):
        report=inspect_repository_state(ROOT)
        modules=targeted_test_modules(report)
        self.assertIn("tests.test_research_v3_lifecycle",modules)
        self.assertIn("tests.test_same_identity_persistence_v1",modules)
        self.assertNotIn("tests.test_c012_corrected_stage_b_recovery",modules)

    def test_checkpoint_is_repository_serializable(self):
        report=inspect_repository_state(ROOT)
        with tempfile.TemporaryDirectory() as td:
            path=write_checkpoint(td,report,status="VALIDATED")
            checkpoint=json.loads(path.read_text())
            self.assertEqual(checkpoint["next_action"],report["next_action"])
            self.assertEqual(checkpoint["accounting"]["v2_attempts_used"],report["accounting"]["v2_attempts_used"])
            self.assertEqual(checkpoint["accounting"]["economic_outcomes_opened"],report["accounting"]["economic_outcomes_opened"])
            self.assertEqual(checkpoint["ledger_tail_entry_hash"],report["lifecycle"]["ledger_tail_entry_hash"])

if __name__=="__main__":
    unittest.main(verbosity=2)
