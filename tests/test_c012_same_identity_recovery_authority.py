import json
import unittest
from pathlib import Path

from tools.validate_authoritative_promotion import (
    _validate_active_authority_references,
    _validate_current_dependency_semantics,
)
from m6.c012_corrected_stage_a_runner import (
    EXPECTED_CORRECTED_INTENT_COUNT,
    EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
    EXPECTED_CORRECTED_TRANSACTION_CONTEXTS,
)

ROOT = Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

class C012SameIdentityRecoveryAuthorityTests(unittest.TestCase):
    def test_01_corrected_pre_economic_identity_is_frozen_without_pnl(self):
        a = load("evidence/C012_SAME_IDENTITY_CORRECTED_STAGE_A_PRE_ECONOMIC_MATERIALIZATION_V1.json")
        self.assertEqual(a["status"], "PASS_CORRECTED_SAME_IDENTITY_PRE_ECONOMIC_NO_PNL")
        self.assertTrue(a["same_identity"])
        self.assertFalse(a["semantic_change"])
        self.assertEqual(EXPECTED_CORRECTED_INTENT_COUNT, 34)
        self.assertEqual(EXPECTED_CORRECTED_TRANSACTION_CONTEXTS, 68)
        self.assertEqual(
            a["corrected_replay_materialization"]["full_intent_manifest_sha256"],
            EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
        )
        self.assertEqual(a["corrected_replay_materialization"]["unresolved_transaction_cost_contexts"], 0)
        self.assertEqual(a["corrected_replay_materialization"]["causal_eurusd_conversion_gaps"], 0)
        self.assertFalse(a["forbidden_during_materialization"]["candidate_pnl_computed"])

    def test_02_old_stage_b_is_explicitly_invalidated_but_preserved(self):
        a = load("evidence/C012_STAGE_B_DOWNSTREAM_INVALIDATION_V1.json")
        self.assertEqual(a["status"], "CURRENT_AUTHORITY_INVALIDATED_HISTORICAL_BYTES_PRESERVED")
        self.assertFalse(a["current_effect"]["allocator_input_permitted"])
        self.assertFalse(a["current_effect"]["portfolio_comparison_input_permitted"])
        self.assertFalse(a["historical_bytes_deleted"])
        self.assertFalse(a["historical_bytes_overwritten"])
        self.assertTrue((ROOT / a["invalidated_downstream"]["stage_b_result_ref"]).is_file())
        self.assertTrue((ROOT / a["invalidated_downstream"]["run_record_ref"]).is_file())

    def test_03_current_state_excludes_invalid_c012(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(state["authoritative_branch"], "competition-performance-v1-20260921")
        self.assertNotIn("V2-C012", state["discovery_survivors"])
        self.assertNotIn("V2-C012", state["current_stage_b_survivor_input_set"])
        self.assertIn("V2-C012", state["implementation_invalid_consumed_identities"])
        self.assertEqual(
            state["current_result_authority"]["V2-C012"]["stage_b_current_config"]["state"],
            "INVALIDATED_DOWNSTREAM_OF_IMPLEMENTATION_INVALID_STAGE_A",
        )

    def test_04_active_refs_and_dependency_semantics_fail_closed(self):
        state = load("CURRENT_STATE.json")
        _validate_active_authority_references(state)
        _validate_current_dependency_semantics(state)

    def test_05_no_attempt_or_budget_is_consumed_by_correction_preparation(self):
        state = load("CURRENT_STATE.json")
        c = state["c012_same_identity_corrected_rerun"]
        self.assertFalse(c["new_v2_attempt_consumed"])
        self.assertEqual(c["search_budget_decrement"], 0)
        self.assertEqual(state["v2_attempts_used"], 9)
        self.assertEqual(state["v2_search_budget_remaining"], 75)

if __name__ == "__main__":
    unittest.main(verbosity=2)
