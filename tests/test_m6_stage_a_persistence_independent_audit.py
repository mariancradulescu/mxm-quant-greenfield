import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

class StageAPersistenceIndependentAuditTests(unittest.TestCase):
    def test_audit_accepts_exact_corrected_head_without_new_economics(self):
        a=load("data/M6_STAGE_A_POST_OUTCOME_PERSISTENCE_INTEGRITY_AUDIT_V1.json")
        self.assertEqual(a["status"], "PASS_INDEPENDENT_AUDIT")
        self.assertEqual(a["audited_head"], "4d24ffeba9311e333ed1c391c4ede913dca5408d")
        self.assertTrue(a["independent_byte_recomputation"]["c006_result_hash"]["pass"])
        self.assertTrue(a["independent_byte_recomputation"]["c012_result_hash"]["pass"])
        self.assertTrue(a["independent_byte_recomputation"]["ledger_sequence_21"]["pass"])
        self.assertTrue(a["independent_byte_recomputation"]["ledger_sequence_22"]["pass"])
        self.assertTrue(a["independent_byte_recomputation"]["ledger_entries_1_20"]["byte_identical_to_current_prefix"])
        self.assertEqual(a["exact_head_ci"]["run_id"], 35506538404)
        self.assertEqual(a["exact_head_ci"]["tests_passed"], 460)
        self.assertEqual(a["exact_head_ci"]["tests_failed"], 0)
        self.assertFalse(a["conclusion"]["economic_re_evaluation_performed"])
        self.assertFalse(a["conclusion"]["new_attempt_consumed"])
        self.assertTrue(a["conclusion"]["stage_b_preparation_may_begin"])
        self.assertFalse(a["conclusion"]["stage_b_economic_execution_authorized_by_this_audit"])

    def test_live_state_preserves_two_attempts_and_records_post_stage_b_total(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(s["economic_outcomes_opened"], 10)
        self.assertEqual(s["v2_attempts_used"], 8)
        self.assertEqual(s["v2_evaluated_identities"], 8)
        self.assertEqual(s["v2_search_budget_remaining"], 76)
        self.assertEqual(s["discovery_survivors"], ["V2-C006", "V2-C012"])
        self.assertEqual(s["certification_survivors"], [])
        self.assertFalse(s["protected_evidence_opened"])
        self.assertTrue(s["m6"]["tier1_stage_a"]["stage_b_preparation_allowed"])
        self.assertFalse(s["m6"]["tier1_stage_a"]["stage_b_authorized"])
        self.assertFalse(s["m6"]["tier1_stage_a"]["stage_b_run"])
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
