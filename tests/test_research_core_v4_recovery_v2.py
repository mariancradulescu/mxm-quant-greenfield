from __future__ import annotations

import json
import unittest
from pathlib import Path

from research_core_v4.crash_recovery_control_v2 import validate_recovery_v2_prepared

ROOT=Path(__file__).resolve().parents[1]


def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))


class RecoveryV2AuditTests(unittest.TestCase):
    def test_recovery_v2_is_prepared_but_not_armed(self):
        report=validate_recovery_v2_prepared()
        self.assertEqual(report["status"],"PASS_PREPARED_NOT_ARMED_NO_REAL_RESPONSE_EXECUTION")
        self.assertEqual(report["accepted_canonical_result_count"],0)
        self.assertEqual(report["accepted_canonical_result_limit"],1)
        self.assertFalse(report["private_input_staging_satisfied"])
        self.assertFalse(report["arm_present"])
        self.assertFalse(report["real_execution_authorized"])
        self.assertEqual(report["process_attempts_started"],0)
        self.assertTrue(report["scientific_source_unchanged"])
        self.assertTrue(report["historical_locks_unchanged"])

    def test_runtime_audit_corrects_900_second_interpretation(self):
        audit=load("research_core_v4/state/V4_EXECUTION_RUNTIME_PROFILE_AUDIT_V1.json")
        self.assertFalse(audit["timeout_reconciliation"]["verified_elapsed_900_seconds"])
        self.assertEqual(audit["timeout_reconciliation"]["attempt_commit_to_failure_commit_seconds"],213)
        self.assertEqual(audit["timeout_reconciliation"]["recovery_opening_lock_to_failure_commit_seconds_approx"],79)
        self.assertEqual(audit["decision"],"DO_NOT_REFACTOR_SCIENTIFIC_EVALUATOR_FOR_RECOVERY_V2;MOVE_BYTE_IDENTICAL_SOURCE_TO_DURABLE_RUNNER")
        self.assertFalse(audit["real_development_response_values_calculated"])
        self.assertFalse(audit["real_development_response_values_exposed"])

    def test_exact_source_contract_adopts_no_refactor(self):
        x=load("research_core_v4/state/V4_EXACT_SOURCE_EXECUTION_EQUIVALENCE_CONTRACT_V1.json")
        self.assertEqual(x["status"],"EXACT_SOURCE_ONLY_NO_EXECUTION_REFACTOR_ADOPTED")
        self.assertIsNone(x["adopted_optimization"])
        self.assertEqual(x["authoritative_source_head"],"68bdee4b51244ae50acd56fe868468b96106450f")
        self.assertFalse(x["rng_law_changed"])
        self.assertFalse(x["event_membership_changed"])
        self.assertFalse(x["pairing_changed"])
        self.assertFalse(x["diagnostics_output_changed"])

    def test_private_transport_remains_unsatisfied_and_public_raw_is_forbidden(self):
        x=load("research_core_v4/state/V4_PRIVATE_INPUT_TRANSPORT_DECISION_V1.json")
        self.assertEqual(x["status"],"PRIVATE_RUNTIME_SELECTED_INPUT_STAGING_NOT_YET_SATISFIED")
        self.assertTrue(x["public_repo_raw_commit_forbidden"])
        self.assertTrue(x["public_repo_actions_artifact_for_raw_inputs_forbidden"])
        self.assertFalse(x["current_real_execution_authorized"])


if __name__=="__main__":
    unittest.main()
