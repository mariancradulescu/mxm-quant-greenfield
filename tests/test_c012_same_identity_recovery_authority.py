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

    def test_03_current_state_tracks_c012_correction_lifecycle(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(state["authoritative_branch"], "competition-performance-v1-20260921")
        self.assertIn("V2-C012", state["implementation_invalid_consumed_identities"])
        correction = state["c012_same_identity_corrected_rerun"]
        stage_a = state["current_result_authority"]["V2-C012"]["stage_a"]
        stage_b = state["current_result_authority"]["V2-C012"]["stage_b_current_config"]
        replay_invalid = stage_a.get("live_equivalent_replay_state") in {
            "IMPLEMENTATION_INVALID_SAME_SEMANTICS_CORRECTABLE",
            "IMPLEMENTATION_ONLY_SAME_SEMANTICS_CORRECTABLE",
        }
        if correction["status"] == "CORRECTED_STAGE_A_RECORDED_SURVIVOR":
            # Historical C012 correction facts remain immutable, but later
            # forensic findings may invalidate its current live-equivalent
            # authority without rewriting that successful correction history.
            self.assertEqual(stage_a["state"], "VALID_CORRECTED_SUCCESSOR")
            self.assertEqual(
                stage_a["corrected_successor_ref"],
                "discovery/results/V2-C012_STAGE_A_V2.json",
            )
            corrected_stage_b = correction.get("corrected_stage_b", {})
            if replay_invalid:
                self.assertNotIn("V2-C012", state["discovery_survivors"])
                self.assertNotIn("V2-C012", state["current_stage_b_survivor_input_set"])
                self.assertEqual(
                    stage_b["state"],
                    "INVALIDATED_DOWNSTREAM_OF_IMPLEMENTATION_INVALID_STAGE_A",
                )
                self.assertEqual(
                    stage_b["invalidation_ref"],
                    "evidence/LIVE_EQUIVALENT_STAGE_B_DOWNSTREAM_INVALIDATION_V1.json",
                )
            elif corrected_stage_b.get("economics_run") is True:
                self.assertIn("V2-C012", state["discovery_survivors"])
                self.assertIn("V2-C012", state["current_stage_b_survivor_input_set"])
                self.assertEqual(stage_b["state"], "VALID_CORRECTED_SUCCESSOR")
                self.assertEqual(
                    stage_b["corrected_successor_ref"],
                    "m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V2.json",
                )
                self.assertEqual(
                    stage_b["corrected_successor_hash"],
                    corrected_stage_b["corrected_stage_b_result_hash"],
                )
            else:
                self.assertIn("PENDING_CORRECTED_SUCCESSOR", stage_b["state"])
        else:
            self.assertNotIn("V2-C012", state["discovery_survivors"])
            self.assertNotIn("V2-C012", state["current_stage_b_survivor_input_set"])
            self.assertEqual(
                stage_b["state"],
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
        self.assertFalse(c["protected_evidence_opened"])
        self.assertEqual(state["v2_evaluated_identities"], state["v2_attempts_used"])
        self.assertEqual(state["v2_search_budget_remaining"], 84 - state["v2_attempts_used"])
        self.assertEqual(state["global_attempts_seen"], state["legacy_prior_attempts"] + state["v2_attempts_used"])


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

    def test_08_corrected_stage_a_successor_is_canonical_and_same_identity(self):
        state = load("CURRENT_STATE.json")
        correction = state["c012_same_identity_corrected_rerun"]
        if correction["status"] != "CORRECTED_STAGE_A_RECORDED_SURVIVOR":
            self.skipTest("corrected successor not persisted yet")
        from discovery.canonical import compute_result_hash
        from discovery.schema import validate_result
        result = load("discovery/results/V2-C012_STAGE_A_V2.json")
        self.assertTrue(validate_result(result))
        self.assertEqual(result["candidate_id"], "V2-C012")
        self.assertEqual(result["spec_hash"], "3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845")
        self.assertEqual(result["metrics"]["event_count"], 34)
        self.assertEqual(result["result_hash"], compute_result_hash(result))
        self.assertEqual(result["result_hash"], correction["corrected_stage_a_result_hash"])
        self.assertFalse(correction["new_v2_attempt_consumed"])
        self.assertEqual(correction["search_budget_decrement"], 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
