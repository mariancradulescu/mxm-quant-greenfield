import json, tempfile, unittest
from pathlib import Path

from research_v3.execution_router import (
    classify_execution, deterministic_operation_required, implementation_required,
    liveness_fingerprint,
)
from research_v3.lightweight_dispatcher import classify as classify_dispatch

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

    def test_exact_head_transport_prefix_routes_only_after_implementation_is_satisfied(self):
        td,root,state=self._root_with_op()
        try:
            state["next_action"]="RUN_EXACT_HEAD_CI_THEN_DO_DETERMINISTIC_THING"
            state["implementation_satisfied"]=True
            state["implementation_ai_required"]=False
            self.assertTrue(deterministic_operation_required(root,state))
            self.assertEqual(classify_execution(root,state)["execution_class"],"DETERMINISTIC_OPERATION")
            state["implementation_satisfied"]=False
            route=classify_execution(root,state)
            self.assertEqual(route["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
            self.assertIn("next_action mismatch",route["detail"])
        finally:
            td.cleanup()

    def test_nonempty_action_alone_is_not_ai_authority(self):
        state={"status":"READY","next_action":"UNBOUND_ACTION","user_action_required":False}
        self.assertFalse(implementation_required(ROOT,state))
        route=classify_execution(ROOT,state)
        self.assertEqual(route["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
        self.assertEqual(route["reason"],"UNROUTED_NONEMPTY_ACTION_FAIL_CLOSED")

    def test_explicit_false_blocks_legacy_proposal_binding_from_becoming_ai_authority(self):
        state={
            "status":"READY",
            "next_action":"VALIDATE_STRUCTURAL_GATE",
            "implementation_ai_required":False,
            "source_ai_proposal_id":"p1",
            "source_ai_proposal_hash":"a"*64,
            "source_runtime_operation_id":"op1",
            "user_action_required":False,
            "external_data_required":False,
        }
        self.assertFalse(implementation_required(ROOT,state))
        route=classify_execution(ROOT,state)
        self.assertEqual(route["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
        self.assertEqual(route["reason"],"UNROUTED_NONEMPTY_ACTION_FAIL_CLOSED")

    def test_explicit_novel_ai_implementation_still_routes_to_ai(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            registry=root/"research_v3/ai_director/PROPOSAL_REGISTRY_V1.json"
            registry.parent.mkdir(parents=True)
            registry.write_text(json.dumps({"accepted":[{"proposal_id":"accepted-p1","proposal_hash":"a"*64}]}))
            state={"status":"READY","next_action":"IMPLEMENT_NEW_VALIDATED_COLLECTOR",
                   "implementation_ai_required":True,"source_ai_proposal_id":"accepted-p1",
                   "source_ai_proposal_hash":"a"*64}
            self.assertTrue(implementation_required(root,state))
            self.assertEqual(classify_execution(root,state)["execution_class"],"NOVEL_AI_IMPLEMENTATION")
            state["source_ai_proposal_id"]="rejected-p2"
            self.assertFalse(implementation_required(root,state))

    def test_fresh_semantic_requirement_precedes_implementation(self):
        state={"status":"READY","next_action":"AI_REASSESS","ai_reasoning_required":True,"implementation_ai_required":True}
        self.assertEqual(classify_execution(ROOT,state)["execution_class"],"SEMANTIC_REASONING")
        self.assertFalse(implementation_required(ROOT,state))

    def test_external_and_integrity_gates_fail_closed(self):
        self.assertEqual(classify_execution(ROOT,{"status":"MATERIAL_INTEGRITY_FAILURE","next_action":"X"})["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
        self.assertEqual(classify_execution(ROOT,{"status":"WAIT","next_action":"X","external_data_required":True})["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
        self.assertEqual(classify_execution(ROOT,{"status":"WAIT","next_action":"X","user_action_required":True})["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")

    def test_completed_dedup_does_not_suppress_new_frontier_action(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/runtime_v2_acceptance").mkdir(parents=True)
            state={
                "status":"FRESH_GENERAL_AI_REASONING_REQUIRED",
                "next_action":"AI_INTERPRET_NEW_RESULT",
                "current_research_evidence_epoch":27,
                "evidence_epoch":27,
                "ai_reasoning_required":True,
                "research_judgment_required":True,
                "implementation_ai_required":False,
                "user_action_required":False,
                "external_data_required":False,
            }
            state_path=root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json"
            state_path.write_text(json.dumps(state),encoding="utf-8")
            fp=liveness_fingerprint(root,state)
            (root/"research_v3/LIVENESS_DEDUP_V1.json").write_text(json.dumps({
                "last_completed_fingerprint":fp,
                "last_completed_operation":"ACCEPT_PREVIOUS_STRUCTURAL_RESULT",
            }),encoding="utf-8")
            out=classify_dispatch(root)
            self.assertFalse(out["duplicate_completed_fingerprint"])
            self.assertTrue(out["dispatch_required"])
            self.assertEqual(out["execution_class"],"SEMANTIC_REASONING")

    def test_current_peer_cohort_lifecycle_routes_consistently(self):
        state=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        route=classify_execution(ROOT,state)
        self.assertEqual(
            state.get("peer_cohort_index_ref"),
            "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json",
        )
        self.assertTrue((ROOT/state["peer_cohort_index_ref"]).is_file())
        if state["next_action"]=="MATERIALIZE_HASH_BOUND_CURRENT_FRONTIER_AND_BUILD_PEER_COHORT_INDEX":
            self.assertEqual(route["execution_class"],"DETERMINISTIC_OPERATION")
            self.assertEqual(
                route["operation_name"],
                "MATERIALIZE_HASH_BOUND_CURRENT_FRONTIER_AND_BUILD_PEER_COHORT_INDEX",
            )
            self.assertFalse(implementation_required(ROOT,state))
        elif state["status"]=="FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_PEER_COHORT_INDEX":
            self.assertEqual(
                state["next_action"],
                "AI_SELECT_PROSPECTIVE_CROSS_SECTIONAL_ESTIMAND_AND_ALIGNED_HISTORY_SCOPE_FROM_PEER_COHORT_INDEX",
            )
            self.assertEqual(route["execution_class"],"SEMANTIC_REASONING")
            self.assertFalse(implementation_required(ROOT,state))
        elif route["execution_class"]=="NOVEL_AI_IMPLEMENTATION":
            self.assertEqual(route["execution_class"],"NOVEL_AI_IMPLEMENTATION")
            self.assertTrue(implementation_required(ROOT,state))
        elif state["status"]=="IMPLEMENTATION_PENDING_EXACT_HEAD_GREEN":
            self.assertEqual(
                state["next_action"],
                "RUN_AUTHORIZED_DETERMINISTIC_OPERATION_AFTER_EXACT_HEAD_GREEN",
            )
            self.assertEqual(route["execution_class"],"DETERMINISTIC_OPERATION")
            self.assertEqual(
                route["operation_ref"],
                "research_v3/EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_ACQUISITION_READINESS_OPERATION_V1.json",
            )
            self.assertFalse(implementation_required(ROOT,state))
        elif route["execution_class"]=="SEMANTIC_REASONING":
            self.assertEqual(route["execution_class"],"SEMANTIC_REASONING")
            self.assertTrue(state["ai_reasoning_required"])
            self.assertFalse(state["implementation_ai_required"])
            self.assertFalse(implementation_required(ROOT,state))
            self.assertIsNone(state.get("next_deterministic_operation_ref"))
            self.assertIsNone(state.get("deterministic_next_operation"))
            if state.get("status")=="FRESH_GENERAL_AI_REASONING_REQUIRED_FOR_DISJOINT_MEAN_REVERSION_DATA_SCOPE":
                audit_ref=state["accepted_capture_scope_audit_ref"]
                audit=json.loads((ROOT/audit_ref).read_text())
                self.assertEqual(audit["scope_count"],10)
                self.assertEqual(audit["disjoint_accepted_exact_identities"],["NETH25"])
                self.assertEqual(state["accounting"],{
                    "economic_outcomes_opened":28,
                    "v2_attempts_used":20,
                    "v2_search_budget_remaining":64,
                })
            self.assertEqual(state.get("authorizing_evidence_epoch"),state.get("current_research_evidence_epoch"))
            if state["next_action"].startswith("AI_SELECT_HIGHEST_INFORMATION_"):
                self.assertTrue((ROOT/state["epoch38_alignment_readiness_ref"]).is_file())
            if state.get("local_data_park_ref"):
                park=json.loads((ROOT/state["local_data_park_ref"]).read_text())
                self.assertFalse(park["items"][0]["mechanism_family_closed"])
            self.assertTrue(state["broader_universe_remains_open"])
            self.assertEqual(state["accounting"],{
                "economic_outcomes_opened":28,
                "v2_attempts_used":20,
                "v2_search_budget_remaining":64,
            })
        elif route["execution_class"]=="DETERMINISTIC_OPERATION":
            # The canonical repository state may legitimately advance beyond the
            # historical peer-cohort lifecycle. Any newer explicitly authorized
            # deterministic operation must still route deterministically and must
            # never fall through to the AI implementation provider.
            expected_action=route["operation_name"]
            if (state.get("implementation_satisfied") is True
                    and state.get("implementation_ai_required") is False
                    and "PENDING_EXACT_HEAD_GREEN" in str(state.get("status") or "")):
                expected_action=f"RUN_EXACT_HEAD_CI_THEN_{expected_action}"
            self.assertEqual(expected_action,state["next_action"])
            self.assertEqual(route["operation_ref"],state["next_deterministic_operation_ref"])
            self.assertFalse(state["ai_reasoning_required"])
            self.assertFalse(state["implementation_ai_required"])
            self.assertFalse(implementation_required(ROOT,state))
            self.assertEqual(state["accounting"],{
                "economic_outcomes_opened":28,
                "v2_attempts_used":20,
                "v2_search_budget_remaining":64,
            })
        elif state.get("status")=="FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_EPOCH46_OUTCOME_BLIND_WAVE_01":
            self.assertEqual(route["execution_class"],"SEMANTIC_REASONING")
            self.assertTrue(state["ai_reasoning_required"])
            self.assertTrue(state["research_judgment_required"])
            self.assertFalse(state["user_action_required"])
            self.assertFalse(state["external_data_required"])
            self.assertFalse(state["implementation_ai_required"])
            self.assertIsNone(state.get("next_deterministic_operation_ref"))
            self.assertTrue((ROOT/state["accepted_epoch46_wave01_capture_ref"]).is_file())
            self.assertTrue((ROOT/state["epoch46_wave01_data_sufficiency_ref"]).is_file())
            acceptance=json.loads((ROOT/state["accepted_epoch46_wave01_capture_ref"]).read_text())
            self.assertEqual(acceptance["integrity_validation"]["nonempty_series"],33)
            self.assertEqual(acceptance["integrity_validation"]["zero_history_series"],1)
            self.assertEqual(acceptance["integrity_validation"]["total_m5_rows"],305938)
            suff=json.loads((ROOT/state["epoch46_wave01_data_sufficiency_ref"]).read_text())
            self.assertFalse(suff["acquisition_decision"]["immediate_wave02_required"])
            self.assertFalse(suff["allowed_next_step"]["economic_response_evaluation_authorized_now"])
            self.assertTrue(suff["allowed_next_step"]["prospective_freeze_required_before_any_response_statistic"])
            self.assertTrue(state["broader_universe_remains_open"])
            self.assertEqual(state["accounting"],{
                "economic_outcomes_opened":28,
                "v2_attempts_used":20,
                "v2_search_budget_remaining":64,
            })
        elif state.get("status")=="OUTCOME_BLIND_PEPPERSTONE_M5_WAVE_01_CAPTURE_REQUIRED":
            self.assertEqual(route["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
            self.assertNotEqual(route["execution_class"],"NO_WORK")
            self.assertEqual(state.get("next_action"),"COLLECT_EPOCH46_OUTCOME_BLIND_PEPPERSTONE_M5_WAVE_01")
            self.assertFalse(implementation_required(ROOT,state))
            local=json.loads((ROOT/state["mean_reversion_disjoint_scope_decision_ref"]).read_text())
            self.assertFalse(local["broader_research"]["mean_reversion_family_closed"])
            global_decision=json.loads((ROOT/state["global_information_gain_decision_ref"]).read_text())
            self.assertEqual(global_decision["status"],"GLOBAL_AUTONOMOUS_DISCOVERY_RESTORED_OUTCOME_BLIND_ACQUISITION_SELECTED")
            wave=json.loads((ROOT/state["next_acquisition_plan_ref"]).read_text())
            self.assertEqual(len(wave["symbols"]),34)
            self.assertFalse(wave["selection_authority"]["outcomes_used"])
            self.assertEqual(state["accounting"],{
                "economic_outcomes_opened":28,
                "v2_attempts_used":20,
                "v2_search_budget_remaining":64,
            })
        else:
            self.fail(f"unexpected peer-cohort lifecycle state: {state.get('status')} / {state.get('next_action')}")

    def test_unknown_deterministic_schema_and_contract_kind_fail_closed(self):
        td,root,state=self._root_with_op()
        try:
            op_path=root/"research_v3/op.json"
            op=json.loads(op_path.read_text())
            op["schema"]="mxm.greenfield.unknown-operation.v1"
            op_path.write_text(json.dumps(op))
            route=classify_execution(root,state)
            self.assertEqual(route["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
            self.assertEqual(route["reason"],"DETERMINISTIC_AUTHORITY_INVALID")
            self.assertIn("unsupported deterministic operation schema",route["detail"])

            op["schema"]="mxm.greenfield.deterministic-next-operation.v1"
            op["operation_contract"]={"kind":"UNKNOWN_KIND"}
            op_path.write_text(json.dumps(op))
            route=classify_execution(root,state)
            self.assertEqual(route["execution_class"],"MATERIAL_INTEGRITY_OR_EXTERNAL_GATE")
            self.assertIn("unsupported deterministic operation contract kind",route["detail"])
        finally:
            td.cleanup()

    def test_liveness_fingerprint_is_deterministic(self):
        td,root,state=self._root_with_op()
        try:
            a=liveness_fingerprint(root,state); b=liveness_fingerprint(root,dict(state))
            self.assertEqual(a,b); self.assertEqual(len(a),64)
        finally:
            td.cleanup()

if __name__=="__main__":
    unittest.main()
