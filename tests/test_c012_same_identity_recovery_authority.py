import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.validate_authoritative_promotion import (
    _validate_active_authority_references,
    _validate_current_dependency_semantics,
)
from m6.c012_corrected_stage_a_runner import (
    C012CorrectionInputPaths,
    EVALUATOR_RUNTIME_SHA256,
    EXPECTED_CORRECTED_INTENT_COUNT,
    EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
    EXPECTED_CORRECTED_TRANSACTION_CONTEXTS,
    StageAExecutionNotAuthorized,
    _git_blob_sha_bytes,
    _load_correction_authorization,
    execute_corrected_c012_stage_a_in_memory,
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


    def test_06_authorized_control_path_binds_real_evaluator_and_runner(self):
        auth_path = ROOT / "data/C012_SAME_IDENTITY_STAGE_A_RERUN_AUTHORIZATION_V1.json"
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        runner_path = ROOT / "m6/c012_corrected_stage_a_runner.py"

        self.assertEqual(
            auth["evaluator_runtime_sha256"],
            EVALUATOR_RUNTIME_SHA256,
        )
        self.assertEqual(
            auth["runner_git_blob_sha1"],
            _git_blob_sha_bytes(runner_path.read_bytes()),
        )
        self.assertEqual(auth["candidate_id"], "V2-C012")
        self.assertEqual(
            auth["candidate_spec_hash"],
            "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845",
        )
        self.assertEqual(
            auth["corrected_intent_manifest_sha256"],
            EXPECTED_CORRECTED_INTENT_MANIFEST_SHA256,
        )
        self.assertIn(
            auth["status"],
            {
                "PENDING_EXACT_HEAD_GREEN_AFTER_RUNTIME_BINDING_FIX",
                "AUTHORIZED_AFTER_EXACT_HEAD_GREEN",
            },
        )

        kwargs = {
            "execution_head": auth["execution_gate_head"],
            "execution_ci_run_id": auth["execution_gate_ci_run_id"],
        }
        if auth["status"] == "AUTHORIZED_AFTER_EXACT_HEAD_GREEN":
            loaded = _load_correction_authorization(ROOT, auth_path, **kwargs)
            self.assertEqual(loaded["runner_git_blob_sha1"], auth["runner_git_blob_sha1"])
        else:
            with self.assertRaises(StageAExecutionNotAuthorized):
                _load_correction_authorization(ROOT, auth_path, **kwargs)

    def test_07_real_runner_entry_hits_authorization_gate_before_economics(self):
        auth_path = ROOT / "data/C012_SAME_IDENTITY_STAGE_A_RERUN_AUTHORIZATION_V1.json"
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        missing = ROOT / "tests/fixtures/__c012_control_path_must_not_read__.csv"
        paths = C012CorrectionInputPaths(
            us500_m15=missing,
            nas100_m15=missing,
            eurusd_m15=missing,
            nas100_c012_transaction_local_cost=missing,
        )

        if auth["status"] != "AUTHORIZED_AFTER_EXACT_HEAD_GREEN":
            with self.assertRaises(StageAExecutionNotAuthorized):
                execute_corrected_c012_stage_a_in_memory(
                    ROOT,
                    paths,
                    authorization_path=auth_path,
                    execution_head=auth["execution_gate_head"],
                    execution_ci_run_id=auth["execution_gate_ci_run_id"],
                )
            return

        class ReachedPostAuthorization(RuntimeError):
            pass

        with patch(
            "m6.c012_corrected_stage_a_runner.build_corrected_c012_pre_economic_candidate",
            side_effect=ReachedPostAuthorization("authorization gate passed"),
        ):
            with self.assertRaisesRegex(ReachedPostAuthorization, "authorization gate passed"):
                execute_corrected_c012_stage_a_in_memory(
                    ROOT,
                    paths,
                    authorization_path=auth_path,
                    execution_head=auth["execution_gate_head"],
                    execution_ci_run_id=auth["execution_gate_ci_run_id"],
                )

if __name__ == "__main__":
    unittest.main(verbosity=2)
