import json
import unittest
from pathlib import Path
from unittest.mock import patch

from m6.c012_corrected_stage_a_runner import C012CorrectionInputPaths
from discovery.canonical import compute_result_hash
from m6.c012_corrected_stage_b_runner import (
    AUTHORIZATION_REF,
    RESULT_SCHEMA_V2,
    CORRECTED_STAGE_A_RESULT_HASH,
    CORRECTED_STAGE_B_REF,
    HISTORICAL_STAGE_B_GIT_BLOB,
    HISTORICAL_STAGE_B_REF,
    _load_correction_authorization,
    execute_corrected_c012_stage_b_in_memory,
    git_blob_sha1,
    project_current_state_after_successor,
    validate_corrected_c012_stage_b_result,
    verify_corrected_c012_stage_b_pre_economic,
)
from m6.stage_b_current_config_tier1_runner import CurrentConfigExecutionNotAuthorized

ROOT = Path(__file__).resolve().parents[1]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class C012CorrectedStageBRecoveryTests(unittest.TestCase):
    def test_01_pre_economic_authorities_bind_corrected_successor_without_pnl(self):
        state = load("CURRENT_STATE.json")
        correction = state["c012_same_identity_corrected_rerun"]
        self.assertEqual(correction["corrected_stage_a_result_hash"], CORRECTED_STAGE_A_RESULT_HASH)
        self.assertEqual(correction["corrected_intent_count"], 34)
        self.assertFalse(correction["new_v2_attempt_consumed"])
        self.assertEqual(correction["search_budget_decrement"], 0)
        self.assertFalse(correction["protected_evidence_opened"])
        self.assertFalse(correction["corrected_stage_b"]["economic_rerun_performed"])
        self.assertEqual(
            correction["corrected_stage_b"]["persistence_recovery"]["additional_v2_attempts_consumed"],
            0,
        )

    def test_02_historical_stage_b_v1_is_byte_preserved(self):
        self.assertEqual(git_blob_sha1(ROOT / HISTORICAL_STAGE_B_REF), HISTORICAL_STAGE_B_GIT_BLOB)
        old = load(HISTORICAL_STAGE_B_REF)
        self.assertEqual(old["economic_summary"]["executed_trades"], 35)
        self.assertEqual(old["result_sha256"], "51edfcc76693425a07c24962f7b3c060fa2e7bb127385233f28f4fc1233edcaa")

    def test_03_authorization_binds_real_runner_and_exact_gate(self):
        auth_path = ROOT / AUTHORIZATION_REF
        auth = load(AUTHORIZATION_REF)
        self.assertEqual(auth["runner_git_blob_sha1"], git_blob_sha1(ROOT / auth["runner_ref"]))
        self.assertEqual(auth["corrected_stage_a_result_hash"], CORRECTED_STAGE_A_RESULT_HASH)
        self.assertEqual(auth["corrected_intent_count"], 34)
        self.assertFalse(auth["new_v2_attempt_consumed"])
        self.assertEqual(auth["search_budget_decrement"], 0)
        state = load("CURRENT_STATE.json")
        if auth["status"] == "AUTHORIZED_AFTER_EXACT_HEAD_GREEN" and state["v2_attempts_used"] == 9:
            loaded = _load_correction_authorization(
                ROOT,
                auth_path,
                execution_head=auth["execution_gate_head"],
                execution_ci_run_id=auth["execution_gate_ci_run_id"],
            )
            self.assertEqual(loaded["runner_git_blob_sha1"], auth["runner_git_blob_sha1"])
        elif auth["status"] == "AUTHORIZED_AFTER_EXACT_HEAD_GREEN":
            correction = state["c012_same_identity_corrected_rerun"]
            self.assertEqual(correction["corrected_stage_b"]["authorization_ref"], AUTHORIZATION_REF)
            self.assertTrue(auth["execution_gate_head"])
            self.assertGreater(int(auth["execution_gate_ci_run_id"]), 0)
            self.assertFalse(auth["new_v2_attempt_consumed"])
            self.assertEqual(auth["search_budget_decrement"], 0)
            self.assertFalse(correction["corrected_stage_b"]["economic_rerun_performed"])
            self.assertEqual(correction["corrected_stage_b"]["persistence_recovery"]["additional_v2_attempts_consumed"], 0)
        else:
            self.assertEqual(auth["status"], "PENDING_EXACT_HEAD_GREEN")
            with self.assertRaises(CurrentConfigExecutionNotAuthorized):
                _load_correction_authorization(
                    ROOT,
                    auth_path,
                    execution_head="not-authorized",
                    execution_ci_run_id=0,
                )

    def test_04_real_execution_entry_reaches_authorization_before_economics(self):
        auth = load(AUTHORIZATION_REF)
        auth_path = ROOT / AUTHORIZATION_REF
        missing = ROOT / "tests/fixtures/__c012_corrected_stage_b_must_not_read__.csv"
        paths = C012CorrectionInputPaths(
            us500_m15=missing,
            nas100_m15=missing,
            eurusd_m15=missing,
            nas100_c012_transaction_local_cost=missing,
        )
        state = load("CURRENT_STATE.json")
        if auth["status"] != "AUTHORIZED_AFTER_EXACT_HEAD_GREEN":
            names = (
                "build_corrected_c012_pre_economic_candidate",
                "realize_current_configuration_capital",
                "summarize_current_config_realization",
                "_augment_economic_detail",
            )
            ps = [
                patch(
                    f"m6.c012_corrected_stage_b_runner.{name}",
                    side_effect=AssertionError(f"{name} must not be reached"),
                )
                for name in names
            ]
            mocks = [p.start() for p in ps]
            try:
                with self.assertRaises(CurrentConfigExecutionNotAuthorized):
                    execute_corrected_c012_stage_b_in_memory(
                        ROOT,
                        paths,
                        authorization_path=auth_path,
                        execution_head="not-authorized",
                        execution_ci_run_id=0,
                    )
                for m in mocks:
                    m.assert_not_called()
            finally:
                for p in reversed(ps):
                    p.stop()
            return

        if state["v2_attempts_used"] == 9:
            class ReachedPostAuthorization(RuntimeError):
                pass

            with patch(
                "m6.c012_corrected_stage_b_runner.build_corrected_c012_pre_economic_candidate",
                side_effect=ReachedPostAuthorization("corrected Stage-B gate passed"),
            ):
                with self.assertRaisesRegex(ReachedPostAuthorization, "gate passed"):
                    execute_corrected_c012_stage_b_in_memory(
                        ROOT,
                        paths,
                        authorization_path=auth_path,
                        execution_head=auth["execution_gate_head"],
                        execution_ci_run_id=auth["execution_gate_ci_run_id"],
                    )
        else:
            # The historical C012 gate is intentionally bound to its 9/75 lifecycle snapshot.
            # Later valid identities must not make us rerun C012 merely to retest that old path.
            correction = state["c012_same_identity_corrected_rerun"]
            self.assertFalse(correction["corrected_stage_b"]["economic_rerun_performed"])
            self.assertEqual(correction["corrected_stage_b"]["persistence_recovery"]["additional_v2_attempts_consumed"], 0)

    def test_05_corrected_successor_lifecycle_is_append_only(self):
        target = ROOT / CORRECTED_STAGE_B_REF
        state = load("CURRENT_STATE.json")
        downstream = state["current_result_authority"]["V2-C012"]["stage_b_current_config"]
        if not target.exists():
            self.assertIsNone(downstream.get("corrected_successor_ref"))
            return
        result = load(CORRECTED_STAGE_B_REF)
        self.assertEqual(result["candidate_id"], "V2-C012")
        self.assertEqual(result["execution_provenance"]["corrected_intent_count"], 34)
        self.assertEqual(result["result_hash"], compute_result_hash(result))
        self.assertTrue(validate_corrected_c012_stage_b_result(result))
        self.assertEqual(downstream.get("corrected_successor_ref"), CORRECTED_STAGE_B_REF)
        self.assertEqual(downstream.get("corrected_successor_hash"), result["result_hash"])
        self.assertEqual(git_blob_sha1(ROOT / HISTORICAL_STAGE_B_REF), HISTORICAL_STAGE_B_GIT_BLOB)

    def test_06_canonical_result_schema_and_state_projection_rehearsal(self):
        fixture = {
            "schema": RESULT_SCHEMA_V2,
            "label": "STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
            "candidate_id": "V2-C012",
            "execution_provenance": {
                "corrected_intent_count": 34,
                "protected_evidence_opened": False,
            },
            "scenario_boundary": {
                "current_configuration_applied_to_development": True,
                "historical_point_in_time_margin_certification": False,
            },
            "economic_summary": {
                "starting_equity_eur": 200.0,
                "final_equity_eur": 201.0,
            },
            "frozen_reporting": {},
            "performance_metrics": {
                "starting_equity_eur": 200.0,
                "terminal_equity_eur": 201.0,
                "executed_entries": 34,
                "margin_rejected_entries": 0,
            },
        }
        fixture["result_hash"] = compute_result_hash(fixture)
        self.assertTrue(validate_corrected_c012_stage_b_result(fixture))
        self.assertEqual(fixture["result_hash"], compute_result_hash(fixture))
        projected = project_current_state_after_successor(load("CURRENT_STATE.json"), fixture)
        downstream = projected["current_result_authority"]["V2-C012"]["stage_b_current_config"]
        self.assertEqual(downstream["state"], "VALID_CORRECTED_SUCCESSOR")
        self.assertEqual(downstream["corrected_successor_ref"], CORRECTED_STAGE_B_REF)
        self.assertEqual(downstream["corrected_successor_hash"], fixture["result_hash"])
        self.assertEqual(
            projected["active_result_pointers"]["V2-C012_STAGE_B_CURRENT_CONFIG"],
            CORRECTED_STAGE_B_REF,
        )
        self.assertEqual(projected["v2_attempts_used"], 13)
        self.assertEqual(projected["v2_search_budget_remaining"], 71)

    def test_07_accounting_is_same_identity_no_attempt_or_budget_delta(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(state["v2_attempts_used"], 13)
        self.assertEqual(state["v2_evaluated_identities"], 13)
        self.assertEqual(state["v2_search_budget_remaining"], 71)
        self.assertEqual(state["performance_research_v3"]["v2_attempts_used_before_wave01"], 9)
        self.assertEqual(state["performance_research_v3"]["v2_search_budget_remaining_before_wave01"], 75)
        self.assertFalse(state["protected_evidence_opened"])
        correction = state["c012_same_identity_corrected_rerun"]
        self.assertFalse(correction["new_v2_attempt_consumed"])
        self.assertEqual(correction["search_budget_decrement"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
