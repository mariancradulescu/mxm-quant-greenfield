import json
import unittest
from pathlib import Path

from m6.stage_b_current_config_tier1_runner import verify_repository_current_config_authorities

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class StageBCurrentConfigRunnerStateMachineCorrectionTests(unittest.TestCase):
    def test_01_correction_is_infrastructure_only(self):
        c=load("evidence/M6_STAGE_B_CURRENT_CONFIG_RUNNER_STATE_MACHINE_CORRECTION_V1.json")
        self.assertEqual(c["status"],"PASS_PRE_EXECUTION_INFRASTRUCTURE_CORRECTION_NO_ECONOMICS")
        self.assertTrue(all(v is False for v in c["methodology_unchanged"].values()))
        self.assertFalse(c["protected_evidence_opened"])

    def test_02_audited_pre_authorization_state_is_now_valid(self):
        s=load("CURRENT_STATE.json")
        self.assertEqual(
            s["m6"]["stage_b_current_configuration"]["state"],
            "AUDITED_PENDING_SINGLE_USE_AUTHORIZATION",
        )
        result=verify_repository_current_config_authorities(ROOT)
        self.assertEqual(result["current_config_outcomes_opened"],0)
        self.assertFalse(s["m6"]["stage_b_current_configuration"]["execution_authorized"])
        self.assertFalse(s["m6"]["stage_b_current_configuration"]["economics_run"])

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
