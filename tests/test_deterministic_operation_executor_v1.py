import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.deterministic_operation_executor import execute_one

class DeterministicOperationExecutorV1Tests(unittest.TestCase):
    def test_current_deterministic_operation_advances_with_zero_provider_delta_and_preserves_stale_request(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/runtime_v2_acceptance").mkdir(parents=True)
            (root/"research_v3/ai_director").mkdir(parents=True)
            op_rel="research_v3/op.json"
            op={
                "schema":"mxm.greenfield.deterministic-next-operation.v1",
                "status":"AUTHORIZED_DETERMINISTIC_NON_ECONOMIC_OPERATION",
                "evidence_epoch":21,
                "operation_name":"BUILD_READ_ONLY_ALL_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT",
                "execution_policy":{
                    "implementation_ai_required":False,
                    "copilot_reasoning_required":False,
                    "new_semantic_judgment_required":False,
                },
                "accounting_effect":{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0},
                "required_contract_fields":[],
                "prohibitions":[],
            }
            (root/op_rel).write_text(json.dumps(op),encoding="utf-8")
            state={
                "schema":"mxm.greenfield.runtime-v2-next-autonomous-state.v3",
                "status":"READY","current_research_evidence_epoch":21,
                "next_action":op["operation_name"],
                "next_deterministic_operation_ref":op_rel,
                "ai_reasoning_required":False,"research_judgment_required":False,
                "user_action_required":False,"external_data_required":False,
                "accounting":{"v2_attempts_used":20,"v2_search_budget_remaining":64,"economic_outcomes_opened":28},
            }
            (root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").write_text(json.dumps(state),encoding="utf-8")
            stale={"schema":"mxm.greenfield.general-ai-implementation-request.v1","marker":"PRESERVE_ME"}
            req=root/"research_v3/ai_director/IMPLEMENTATION_REQUEST.json"
            req.write_text(json.dumps(stale),encoding="utf-8")
            with patch("research_v3.deterministic_operation_executor.build_capture_contract",return_value={"status":"OK"}), \
                 patch("research_v3.deterministic_operation_executor.project_snapshot",return_value={"v2_attempts_used":20,"economic_outcomes_opened":28}), \
                 patch("research_v3.deterministic_operation_executor._provider_count",side_effect=[4,4]):
                out=execute_one(root)
            self.assertEqual(out["provider_calls_delta"],0)
            self.assertEqual(json.loads(req.read_text()),stale)
            new_state=json.loads((root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
            self.assertEqual(new_state["status"],"DETERMINISTIC_CAPTURE_CONTRACT_COMPLETE")
            self.assertFalse(new_state["implementation_ai_required"])
            repair=json.loads((root/"research_v3/EPOCH21_DETERMINISTIC_ROUTING_REPAIR_V1.json").read_text())
            self.assertEqual(repair["copilot_provider_calls_delta"],0)
            record=json.loads((root/"research_v3/EPOCH21_DETERMINISTIC_OPERATION_EXECUTION_V1.json").read_text())
            self.assertEqual(record["status"],"PASS_ZERO_PROVIDER_ZERO_ECONOMIC_EFFECT")

if __name__=="__main__":
    unittest.main()
