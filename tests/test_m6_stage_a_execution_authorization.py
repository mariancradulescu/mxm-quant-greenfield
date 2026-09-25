import json
import unittest
from pathlib import Path

from m6.stage_a_tier1_runner import (
    StageAExecutionNotAuthorized,
    _load_execution_authorization,
)

ROOT=Path(__file__).resolve().parents[1]
AUTH=ROOT/"data/M6_STAGE_A_EXECUTION_AUTHORIZATION_V1.json"
RUNNER_SHA="84a4e588300053fe8583ff36dde3db885d77727f811212d161bdac770c5919df"


class StageAExecutionAuthorizationTests(unittest.TestCase):
    def test_01_frozen_authorization_matches_runner_gates(self):
        a=_load_execution_authorization(
            AUTH,
            runner_source_sha256=RUNNER_SHA,
        )
        self.assertEqual(a["status"],"AUTHORIZED")
        self.assertEqual(a["stage"],"A")
        self.assertEqual(a["candidates"],["V2-C006","V2-C012"])
        self.assertFalse(a["protected_evidence_opened"])
        self.assertFalse(a["protected_evidence_authorized"])
        self.assertEqual(a["attempt_accounting"]["authorized_new_attempts"],2)

    def test_02_authorization_does_not_itself_open_outcomes(self):
        state = json.loads((ROOT / "CURRENT_STATE.json").read_text(encoding="utf-8"))
        auth = json.loads((ROOT / "data/M6_STAGE_A_EXECUTION_AUTHORIZATION_V1.json").read_text(encoding="utf-8"))
        self.assertEqual(state["m6_stage_a_execution_authorization_authority"], "data/M6_STAGE_A_EXECUTION_AUTHORIZATION_V1.json")
        self.assertTrue(state["m6"]["first_stage_a_runner"]["execution_authorization_frozen"])
        self.assertEqual(auth["preconditions"]["economic_outcomes_opened"], 0)
        self.assertEqual(auth["preconditions"]["v2_attempts_used"], 0)
        self.assertEqual(auth["preconditions"]["v2_evaluated_identities"], 0)
        self.assertEqual(auth["preconditions"]["result_recorded"], 0)
        self.assertEqual(auth["preconditions"]["ledger_entries"], 20)
        self.assertFalse(auth["protected_evidence_opened"])
        self.assertTrue(state["m6"]["first_stage_a_runner"]["authorization_consumed"])
        self.assertFalse(state["protected_evidence_opened"])
if __name__=="__main__":
    unittest.main(verbosity=2)
