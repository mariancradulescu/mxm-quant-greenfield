import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class StageBCurrentConfigRunnerStateMachineCorrectionTests(unittest.TestCase):
    def test_01_correction_is_infrastructure_only(self):
        c=load("evidence/M6_STAGE_B_CURRENT_CONFIG_RUNNER_STATE_MACHINE_CORRECTION_V1.json")
        self.assertEqual(c["status"],"PASS_PRE_EXECUTION_INFRASTRUCTURE_CORRECTION_NO_ECONOMICS")
        self.assertTrue(all(v is False for v in c["methodology_unchanged"].values()))
        self.assertFalse(c["protected_evidence_opened"])

    def test_02_pre_execution_state_machine_history_is_preserved_after_execution(self):
        s=load("CURRENT_STATE.json")
        t=s["m6"]["stage_b_current_configuration"]
        self.assertEqual(t["state"],"EXECUTED_RESULTS_PERSISTED_PENDING_INDEPENDENT_AUDIT")
        self.assertFalse(t["execution_authorized"])
        self.assertTrue(t["authorization_consumed"])
        self.assertTrue(t["economics_run"])
        self.assertEqual(t["stage_b_current_config_outcomes_opened"],2)

    def test_03_runner_prep_v2_binds_new_runner_and_audit(self):
        p=load("data/M6_STAGE_B_CURRENT_CONFIG_TIER1_RUNNER_PREP_V2.json")
        self.assertEqual(p["status"],"AUDITED_PRE_EXECUTION_RUNNER_CORRECTED_NOT_AUTHORIZED")
        self.assertEqual(p["runner"]["git_blob_sha1"],"eab768456b02ecb3b200d71266b540a446843ed5")
        self.assertTrue(p["independent_audit_pass"])
        self.assertFalse(p["execution_authorized"])
        self.assertEqual(p["current_config_stage_b_outcomes_opened"],0)

    def test_04_historical_unknown_stays_non_blocking(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(
            s["m6"]["stage_b_current_configuration"]["historical_margin_state"],
            "UNRESOLVED_NO_DEFENSIBLE_HISTORICAL_MARGIN_UPPER_BOUND",
        )
        self.assertTrue(
            s["m6"]["stage_b_current_configuration"]["historical_margin_non_blocking_for_current_scenario"]
        )
        self.assertFalse(s["protected_evidence_opened"])

if __name__=="__main__":
    unittest.main(verbosity=2)
