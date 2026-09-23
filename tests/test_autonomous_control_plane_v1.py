import json,tempfile,unittest
from pathlib import Path
from research_v3.autonomous_control_plane import (
    inspect_repository_state,targeted_test_modules,validate_repository_state,write_checkpoint,
)

ROOT=Path(__file__).resolve().parents[1]

class AutonomousControlPlaneV1Tests(unittest.TestCase):
    def test_current_repository_self_diagnoses_without_chat_memory(self):
        report=validate_repository_state(ROOT)
        self.assertEqual(report["next_action"],"REVALIDATE_STAGE_B")
        self.assertEqual(report["material_issues"],[])
        self.assertEqual(report["recoverable_conditions"],[])
        self.assertEqual(report["accounting"]["v2_attempts_used"],16)
        self.assertEqual(report["accounting"]["v2_search_budget_remaining"],68)
        self.assertEqual(report["accounting"]["economic_outcomes_opened"],23)
        self.assertEqual(report["lifecycle"]["distinct_identity_outcomes_opened"],16)
        self.assertEqual(report["lifecycle"]["stage_a_result_recorded_entries"],21)
        self.assertEqual(report["lifecycle"]["same_identity_successor_result_entries"],5)
        self.assertEqual(report["stage_b_revalidation_required_candidate_ids"],["V2-C006","V2-C012"])
        self.assertEqual(
            report["current_live_equivalent_authoritative_candidate_ids"],
            ["V2-C006","V2-C012","V2-C023","V2-C025"],
        )
        self.assertTrue(any(x["wave_key"]=="wave04" for x in report["blocked_historical_waves"]))
        self.assertFalse(any(report["safety"].values()))

    def test_targeted_validation_is_selected_from_lifecycle(self):
        report=inspect_repository_state(ROOT)
        modules=targeted_test_modules(report)
        self.assertIn("tests.test_research_v3_lifecycle",modules)
        self.assertIn("tests.test_same_identity_persistence_v1",modules)
        self.assertIn("tests.test_c012_corrected_stage_b_recovery",modules)

    def test_checkpoint_is_repository_serializable(self):
        report=inspect_repository_state(ROOT)
        with tempfile.TemporaryDirectory() as td:
            path=write_checkpoint(td,report,status="VALIDATED")
            checkpoint=json.loads(path.read_text())
            self.assertEqual(checkpoint["next_action"],"REVALIDATE_STAGE_B")
            self.assertEqual(checkpoint["accounting"]["v2_attempts_used"],16)
            self.assertEqual(checkpoint["accounting"]["economic_outcomes_opened"],23)
            self.assertEqual(checkpoint["ledger_tail_entry_hash"],report["lifecycle"]["ledger_tail_entry_hash"])

if __name__=="__main__":
    unittest.main(verbosity=2)
