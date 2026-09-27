import json
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.deterministic_operation_executor import _pending_exact_head

ROOT = Path(__file__).resolve().parents[1]
OPERATION = ROOT / "research_v3/EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_DETERMINISTIC_OPERATION_V1.json"


class Epoch34DeterministicOperationTests(unittest.TestCase):
    def test_exact_head_prerequisite_returns_machine_owned_pending_without_state_checkpoint(self):
        operation = json.loads(OPERATION.read_text(encoding="utf-8"))
        state = {"status":"DETERMINISTIC_OPERATION_READY_AFTER_IMPLEMENTATION_GREEN","next_action":operation["operation_name"]}
        proof={"green":False,"head":"a"*40,"predecessor_head":"b"*40,"predecessor_conclusion":"success","predecessor_run_id":123}
        with patch("research_v3.deterministic_operation_executor.exact_head_green",return_value=proof):
            pending=_pending_exact_head(ROOT,state,operation)
        self.assertEqual(pending["status"],"PENDING_EXACT_HEAD_GREEN")
        self.assertEqual(pending["operation_name"],operation["operation_name"])
        self.assertFalse(pending["state_persisted"])
        self.assertEqual(pending["provider_calls_delta"],0)
        self.assertEqual(pending["exact_head"]["head"],"a"*40)

    def test_matching_green_exact_head_releases_same_frozen_operation(self):
        operation = json.loads(OPERATION.read_text(encoding="utf-8"))
        with patch("research_v3.deterministic_operation_executor.exact_head_green",
                   return_value={"green":True,"head":"a"*40,"predecessor_head":"a"*40,"predecessor_conclusion":"success","predecessor_run_id":456}):
            self.assertIsNone(_pending_exact_head(ROOT,{},operation))
        self.assertEqual(operation["materializer"],"MATERIALIZE_BASE64_GZIP_NON_ECONOMIC_STRUCTURAL_RESULT")
        payload=ROOT/operation["payload_ref"]
        self.assertTrue(payload.is_file())
        self.assertEqual(operation["payload_sha256"],"e38ddde73212a74851c95538ec99411bf5bd82eaf2262cea872a3d686d3ccc80")


if __name__ == "__main__":
    unittest.main()
