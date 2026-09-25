import json, tempfile, unittest
from pathlib import Path

from research_v3.execution_router import (
    classify_execution, deterministic_operation_required, implementation_required,
    liveness_fingerprint,
)

ROOT=Path(__file__).resolve().parents[1]

class ExecutionRouterV1Tests(unittest.TestCase):
    def _root_with_op(self,policy=None):
        td=tempfile.TemporaryDirectory(); root=Path(td.name)
        (root/"research_v3").mkdir(parents=True)
        op={
            "schema":"mxm.greenfield.deterministic-next-operation.v1",
            "status":"AUTHORIZED_DETERMINISTIC_NON_ECONOMIC_OPERATION",
            "evidence_epoch":21,
            "operation_name":"DO_DETERMINISTIC_THING",
            "execution_policy":{
                "implementation_ai_required":False,
                "copilot_reasoning_required":False,
                "new_semantic_judgment_required":False,
                **(policy or {}),
            },
            "accounting_effect":{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0},
        }
        (root/"research_v3/op.json").write_text(json.dumps(op),encoding="utf-8")
        state={
            "status":"READY","current_research_evidence_epoch":21,
            "next_action":"DO_DETERMINISTIC_THING",
            "next_deterministic_operation_ref":"research_v3/op.json",
            "user_action_required":False,"external_data_required":False,
            "ai_reasoning_required":False,"research_judgment_required":False,
        }
        return td,root,state

    def test_deterministic_operation_never_routes_to_ai_implementation(self):
        td,root,state=self._root_with_op()
        try:
            self.assertTrue(deterministic_operation_required(root,state))
            self.assertFalse(implementation_required(root,state))
            self.assertEqual(classify_execution(root,state)["execution_class"],"DETERMINISTIC_OPERATION")
        finally:
            td.cleanup()

    def test_nonempty_action_alone_is_not_ai_authority(self):
        state={"status":"READY","next_action":"UNBOUND_ACTION","user_action_required":False}
        self.assertFalse(implementation_required(ROOT,state))
        route=classify_execution(ROOT,state)
        self.assertEqual(route["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
        self.assertEqual(route["reason"],"UNROUTED_NONEMPTY_ACTION_FAIL_CLOSED")

    def test_explicit_novel_ai_implementation_still_routes_to_ai(self):
        state={"status":"READY","next_action":"IMPLEMENT_NEW_VALIDATED_COLLECTOR","implementation_ai_required":True}
        self.assertTrue(implementation_required(ROOT,state))
        self.assertEqual(classify_execution(ROOT,state)["execution_class"],"NOVEL_AI_IMPLEMENTATION")

    def test_fresh_semantic_requirement_precedes_implementation(self):
        state={"status":"READY","next_action":"AI_REASSESS","ai_reasoning_required":True,"implementation_ai_required":True}
        self.assertEqual(classify_execution(ROOT,state)["execution_class"],"SEMANTIC_REASONING")
        self.assertFalse(implementation_required(ROOT,state))

    def test_external_and_integrity_gates_fail_closed(self):
        self.assertEqual(classify_execution(ROOT,{"status":"MATERIAL_INTEGRITY_FAILURE","next_action":"X"})["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
        self.assertEqual(classify_execution(ROOT,{"status":"WAIT","next_action":"X","external_data_required":True})["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
        self.assertEqual(classify_execution(ROOT,{"status":"WAIT","next_action":"X","user_action_required":True})["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")

    def test_liveness_fingerprint_is_deterministic(self):
        td,root,state=self._root_with_op()
        try:
            a=liveness_fingerprint(root,state); b=liveness_fingerprint(root,dict(state))
            self.assertEqual(a,b); self.assertEqual(len(a),64)
        finally:
            td.cleanup()

if __name__=="__main__":
    unittest.main()
