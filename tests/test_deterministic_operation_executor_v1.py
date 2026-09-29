import base64, gzip, hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.deterministic_operation_executor import execute_one, _run_hash_bound_python_json_transform

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

    def test_hash_bound_python_transform_materializes_and_routes_to_fresh_reasoning(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/runtime_v2_inputs").mkdir(parents=True)
            (root/"research_v3/runtime_v2_acceptance").mkdir(parents=True)
            (root/"evidence").mkdir(parents=True)
            implementation=root/"research_v3/transform.py"
            implementation.write_text(
                "def build(payload, expected_count):\n"
                "    assert len(payload['rows']) == expected_count\n"
                "    return {\n"
                "      'schema':'test.index.v1','status':'COMPLETE_NON_ECONOMIC_CANDIDATE_UNIVERSE_INDEX',\n"
                "      'source_universe':{'indexed_identity_count':expected_count},\n"
                "      'coverage':{'cohort_breadth_total':expected_count},\n"
                "      'cohort_policy':{'structural_representatives_used_as_substitutes':False},\n"
                "      'interpretation_boundary':{\n"
                "        'strategy_or_price_outcome_evaluated':False,'returns_or_pnl_computed':False,\n"
                "        'economic_equivalence_claimed':False,'protected_forward_opened':False,\n"
                "        'economic_outcomes_opened':0,'v2_attempts_consumed':0}\n"
                "    }\n",
                encoding="utf-8",
            )
            impl_bytes=implementation.read_bytes()
            impl_blob=hashlib.sha1(
                f"blob {len(impl_bytes)}\0".encode("ascii")+impl_bytes
            ).hexdigest()
            payload=json.dumps({"rows":[1,2]},sort_keys=True,separators=(",",":")).encode()
            decoded_sha=hashlib.sha256(payload).hexdigest()
            encoded=base64.b64encode(gzip.compress(payload))
            first,second=encoded[:len(encoded)//2],encoded[len(encoded)//2:]
            refs=[]
            hashes=[]
            for index,part in enumerate((first,second)):
                rel=f"research_v3/runtime_v2_inputs/p{index}.b64"
                (root/rel).write_bytes(part)
                refs.append(rel); hashes.append(hashlib.sha256(part).hexdigest())
            op={
                "operation_contract":{
                    "kind":"HASH_BOUND_PYTHON_JSON_TRANSFORM_V1",
                    "implementation_ref":"research_v3/transform.py",
                    "implementation_git_blob_sha1":impl_blob,
                    "callable":"build",
                    "call_kwargs":{"expected_count":2},
                    "input_transport":{
                        "encoding":"CONCAT_BASE64_GZIP_JSON",
                        "fragment_refs":refs,
                        "fragment_sha256":hashes,
                        "concatenated_base64_sha256":hashlib.sha256(encoded).hexdigest(),
                        "decoded_json_sha256":decoded_sha,
                    },
                    "output":{
                        "ref":"evidence/index.json",
                        "expected_schema":"test.index.v1",
                        "expected_status":"COMPLETE_NON_ECONOMIC_CANDIDATE_UNIVERSE_INDEX",
                        "expected_indexed_identity_count":2,
                    },
                },
                "post_execution_state":{
                    "status":"FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_TEST_INDEX",
                    "next_action":"AI_INTERPRET_TEST_INDEX",
                    "ai_reasoning_required":True,
                    "research_judgment_required":True,
                },
            }
            state={
                "status":"READY",
                "next_action":"MATERIALIZE_TEST_INDEX",
                "accounting":{"economic_outcomes_opened":28,"v2_attempts_used":20,"v2_search_budget_remaining":64},
            }
            out=_run_hash_bound_python_json_transform(root,state,op)
            self.assertEqual(out["status"],"FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_TEST_INDEX")
            self.assertTrue(out["ai_reasoning_required"])
            self.assertFalse(out["implementation_ai_required"])
            self.assertEqual(out["peer_cohort_index_identity_count"],2)
            self.assertTrue((root/"evidence/index.json").is_file())

            # A byte-level transport mutation must fail closed.
            (root/refs[0]).write_bytes(first+b"A")
            with self.assertRaisesRegex(Exception,"fragment mismatch"):
                _run_hash_bound_python_json_transform(root,state,op)

    def test_generic_structural_result_acceptance_advances_without_provider(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/runtime_v2_acceptance").mkdir(parents=True)
            (root/"research_v3/ai_director").mkdir(parents=True)
            (root/"evidence").mkdir(parents=True)
            result_rel="evidence/result.json"
            result={
                "schema":"test.structural-result.v1",
                "status":"ACCEPTED_NON_ECONOMIC_STRUCTURAL_RESULT",
                "source_evidence_epoch":26,
                "family":"CROSS_SECTIONAL_RANKING",
                "accounting_effect":{"v2_attempts_consumed":0,"economic_outcomes_opened":0,"search_budget_change":0},
                "safety":{"protected_forward_opened":False,"live_orders_authorized":False},
                "interpretation_boundary":{"economic_promotion_authorized":False},
            }
            (root/result_rel).write_text(json.dumps(result),encoding="utf-8")
            op_rel="research_v3/op.json"
            op={
                "schema":"mxm.greenfield.deterministic-next-operation.v1",
                "status":"AUTHORIZED_DETERMINISTIC_NON_ECONOMIC_OPERATION",
                "evidence_epoch":26,
                "operation_name":"ACCEPT_STRUCTURAL_RESULT",
                "materializer":"ACCEPT_EXISTING_NON_ECONOMIC_STRUCTURAL_RESULT",
                "result_ref":result_rel,
                "result_validation":{"schema":"test.structural-result.v1","status":"ACCEPTED_NON_ECONOMIC_STRUCTURAL_RESULT","family":"CROSS_SECTIONAL_RANKING"},
                "execution_policy":{"implementation_ai_required":False,"copilot_reasoning_required":False,"new_semantic_judgment_required":False},
                "accounting_effect":{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0},
                "acceptance_reason":"Accept fixed non-economic structural result.",
                "family_result":"NO_REPRESENTATIVE_PASSED",
                "next_status":"FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_STRUCTURAL_RESULT",
                "next_reasoning_action":"AI_INTERPRET_STRUCTURAL_RESULT",
            }
            (root/op_rel).write_text(json.dumps(op),encoding="utf-8")
            state={
                "schema":"mxm.greenfield.runtime-v2-next-autonomous-state.v3",
                "status":"DETERMINISTIC_RESULT_ACCEPTANCE_REQUIRED",
                "current_research_evidence_epoch":26,"evidence_epoch":26,
                "next_action":"ACCEPT_STRUCTURAL_RESULT",
                "next_deterministic_operation_ref":op_rel,
                "implementation_ai_required":False,
                "ai_reasoning_required":False,"research_judgment_required":False,
                "user_action_required":False,"external_data_required":False,
                "accounting":{"v2_attempts_used":20,"v2_search_budget_remaining":64,"economic_outcomes_opened":28},
            }
            (root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").write_text(json.dumps(state),encoding="utf-8")
            with patch("research_v3.deterministic_operation_executor.project_snapshot",return_value={"v2_attempts_used":20,"economic_outcomes_opened":28}), \
                 patch("research_v3.deterministic_operation_executor._provider_count",side_effect=[73,73]), \
                 patch("research_v3.deterministic_operation_executor.advance_evidence_epoch",return_value={"current_epoch":27}):
                out=execute_one(root)
            self.assertEqual(out["provider_calls_delta"],0)
            new_state=json.loads((root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
            self.assertEqual(new_state["current_research_evidence_epoch"],27)
            self.assertEqual(new_state["status"],"FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_STRUCTURAL_RESULT")
            self.assertEqual(new_state["next_action"],"AI_INTERPRET_STRUCTURAL_RESULT")
            self.assertTrue(new_state["ai_reasoning_required"])
            self.assertTrue(new_state["research_judgment_required"])
            self.assertFalse(new_state["implementation_ai_required"])
            self.assertIsNone(new_state["next_deterministic_operation_ref"])
            self.assertEqual(new_state["completed_family"],"CROSS_SECTIONAL_RANKING")
            self.assertEqual(new_state["completed_structural_report_ref"],result_rel)


    def test_generic_embedded_structural_result_materializes_next_epoch_and_advances_without_provider(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/runtime_v2_acceptance").mkdir(parents=True)
            (root/"research_v3/ai_director").mkdir(parents=True)
            (root/"research_v3/runtime_v2_inputs").mkdir(parents=True)
            (root/"evidence").mkdir(parents=True)
            freeze_rel="research_v3/freeze.json"
            (root/freeze_rel).write_text('{"frozen":true}\n',encoding="utf-8")
            result={
                "schema":"test.structural-result.v2",
                "status":"COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
                "evidence_epoch":29,
                "family":"GENERIC_TEST_FAMILY",
                "freeze_sha256":"PENDING",
                "accounting_effect":{"v2_attempts_consumed":0,"economic_outcomes_opened":0,"search_budget_change":0},
                "safety":{"protected_forward_opened":False,"live_orders_authorized":False},
                "interpretation_boundary":{"economic_promotion_authorized":False},
            }
            payload_rel="research_v3/runtime_v2_inputs/result.b64"
            payload=base64.b64encode(gzip.compress(json.dumps(result,separators=(",",":")).encode())).decode()
            # Base64 transport is canonicalized for insignificant surrounding whitespace.
            (root/payload_rel).write_text(payload+"\n",encoding="ascii")
            op_rel="research_v3/op.json"
            op={
                "schema":"mxm.greenfield.deterministic-next-operation.v1",
                "status":"AUTHORIZED_DETERMINISTIC_NON_ECONOMIC_OPERATION",
                "evidence_epoch":28,
                "operation_name":"MATERIALIZE_AND_ACCEPT_GENERIC_STRUCTURAL_RESULT",
                "materializer":"MATERIALIZE_BASE64_GZIP_NON_ECONOMIC_STRUCTURAL_RESULT",
                "payload_ref":payload_rel,
                "payload_encoding":"BASE64_GZIP_JSON",
                "result_ref":"evidence/result.json",
                "sha256_attestations":{"freeze_sha256":freeze_rel},
                "result_validation":{"schema":"test.structural-result.v2","status":"COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT","family":"GENERIC_TEST_FAMILY","evidence_epoch":29},
                "execution_policy":{"implementation_ai_required":False,"copilot_reasoning_required":False,"new_semantic_judgment_required":False},
                "accounting_effect":{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0},
                "acceptance_reason":"Accept next-epoch prospective non-economic result.",
                "family_result":"NO_SUPPORT",
            }
            import research_v3.runtime_v2_primitives as primitives
            op["payload_sha256"]=hashlib.sha256(payload.encode("ascii")).hexdigest()
            (root/op_rel).write_text(json.dumps(op),encoding="utf-8")
            state={
                "schema":"mxm.greenfield.runtime-v2-next-autonomous-state.v3",
                "status":"READY","current_research_evidence_epoch":28,"evidence_epoch":28,
                "next_action":op["operation_name"],"next_deterministic_operation_ref":op_rel,
                "implementation_ai_required":False,"ai_reasoning_required":False,"research_judgment_required":False,
                "user_action_required":False,"external_data_required":False,
                "accounting":{"v2_attempts_used":20,"v2_search_budget_remaining":64,"economic_outcomes_opened":28},
            }
            (root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").write_text(json.dumps(state),encoding="utf-8")
            with patch("research_v3.deterministic_operation_executor.project_snapshot",return_value={"v2_attempts_used":20,"economic_outcomes_opened":28}), \
                 patch("research_v3.deterministic_operation_executor._provider_count",side_effect=[79,79]), \
                 patch("research_v3.deterministic_operation_executor.advance_evidence_epoch",return_value={"current_epoch":29}):
                out=execute_one(root)
            self.assertEqual(out["provider_calls_delta"],0)
            materialized=json.loads((root/"evidence/result.json").read_text())
            expected_freeze=hashlib.sha256((root/freeze_rel).read_bytes()).hexdigest()
            self.assertEqual(materialized["freeze_sha256"],expected_freeze)
            new_state=json.loads((root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
            self.assertEqual(new_state["current_research_evidence_epoch"],29)
            self.assertTrue(new_state["ai_reasoning_required"])
            self.assertFalse(new_state["implementation_ai_required"])


    def test_authorizing_epoch_45_accepts_epoch46_result_under_epoch47_sequence_label(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/runtime_v2_acceptance").mkdir(parents=True)
            (root/"research_v3/ai_director").mkdir(parents=True)
            (root/"research_v3/runtime_v2_inputs").mkdir(parents=True)
            (root/"evidence").mkdir(parents=True)
            result={
                "schema":"test.sequence-labeled-result.v1",
                "status":"COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
                "evidence_epoch":46,
                "research_sequence_label":"EPOCH47",
                "family":"MEAN_REVERSION",
                "accounting_effect":{"v2_attempts_consumed":0,"economic_outcomes_opened":0,"search_budget_change":0},
                "safety":{"protected_forward_opened":False,"live_orders_authorized":False},
                "interpretation_boundary":{"economic_promotion_authorized":False},
            }
            payload=base64.b64encode(gzip.compress(json.dumps(result,separators=(",",":")).encode())).decode()
            a,b=payload[:len(payload)//2],payload[len(payload)//2:]
            refs=["research_v3/runtime_v2_inputs/a.b64","research_v3/runtime_v2_inputs/b.b64"]
            (root/refs[0]).write_text(a,encoding="ascii")
            (root/refs[1]).write_text(b,encoding="ascii")
            op_rel="research_v3/op.json"
            op={
                "schema":"mxm.greenfield.deterministic-next-operation.v1",
                "status":"AUTHORIZED_DETERMINISTIC_NON_ECONOMIC_OPERATION",
                "evidence_epoch":47,
                "authorizing_evidence_epoch":45,
                "research_sequence_label":"EPOCH47",
                "operation_name":"MATERIALIZE_SEQUENCE_LABELED_RESULT",
                "materializer":"MATERIALIZE_BASE64_GZIP_NON_ECONOMIC_STRUCTURAL_RESULT",
                "payload_refs":refs,
                "payload_encoding":"BASE64_GZIP_JSON",
                "payload_sha256":hashlib.sha256(payload.encode("ascii")).hexdigest(),
                "result_ref":"evidence/result.json",
                "result_validation":{"schema":"test.sequence-labeled-result.v1","status":"COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT","family":"MEAN_REVERSION","evidence_epoch":46},
                "execution_policy":{"implementation_ai_required":False,"copilot_reasoning_required":False,"new_semantic_judgment_required":False},
                "accounting_effect":{"v2_attempts":0,"economic_outcomes":0,"copilot_reasoning_calls":0},
                "acceptance_reason":"Accept material result exactly once.",
            }
            (root/op_rel).write_text(json.dumps(op),encoding="utf-8")
            state={
                "schema":"mxm.greenfield.runtime-v2-next-autonomous-state.v3",
                "status":"READY","current_research_evidence_epoch":45,"evidence_epoch":45,
                "next_action":op["operation_name"],"next_deterministic_operation_ref":op_rel,
                "implementation_ai_required":False,"implementation_satisfied":True,
                "ai_reasoning_required":False,"research_judgment_required":False,
                "user_action_required":False,"external_data_required":False,
                "accounting":{"v2_attempts_used":20,"v2_search_budget_remaining":64,"economic_outcomes_opened":28},
            }
            (root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").write_text(json.dumps(state),encoding="utf-8")
            with patch("research_v3.deterministic_operation_executor.project_snapshot",return_value={"v2_attempts_used":20,"economic_outcomes_opened":28}), \
                 patch("research_v3.deterministic_operation_executor._provider_count",side_effect=[100,100]), \
                 patch("research_v3.deterministic_operation_executor.advance_evidence_epoch",return_value={"current_epoch":46}):
                out=execute_one(root)
            self.assertEqual(out["provider_calls_delta"],0)
            new_state=json.loads((root/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
            self.assertEqual(new_state["current_research_evidence_epoch"],46)
            self.assertTrue(new_state["ai_reasoning_required"])
            self.assertFalse(new_state["implementation_ai_required"])

if __name__=="__main__":
    unittest.main()
