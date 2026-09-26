import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_reasoning_provider import _authority_context, wake

ROOT=Path(__file__).resolve().parents[1]


class Epoch25AdditionalAuthorityRecoveryTests(unittest.TestCase):
    def test_missing_implementation_scope_is_normalized_without_semantic_recall(self):
        from research_v3.general_ai_reasoning_provider import _normalize_candidate_routing, build_reasoning_request
        request=build_reasoning_request(ROOT)
        candidate={
            "proposal_id":"routing-normalization-test",
            "objective":{"class":"NON_ECONOMIC_STRUCTURAL_RESEARCH","goal":"test","information_gain_rationale":"test"},
            "decision":{"selected_mechanism_family":"MEAN_REVERSION","research_choice":"preserve-me"},
            "next_research_state":{
                "status":"IMPLEMENTATION_REQUIRED",
                "next_action":"BUILD_NEW_NON_ECONOMIC_MEAN_REVERSION_SCREEN",
                "research_judgment_required":False,
                "implementation_ai_required":True,
                "selected_family":"MEAN_REVERSION",
            },
            "authority_refs":["research_v3/RESEARCH_CONTRACT_V3.json"],
            "data_policy":{"new_market_data_requested":False},
        }
        normalized=_normalize_candidate_routing(request,candidate)
        self.assertEqual(normalized["decision"]["research_choice"],"preserve-me")
        self.assertTrue(normalized["next_research_state"]["implementation_ai_required"])
        self.assertEqual(
            normalized["decision"]["implementation_scope"]["next_action"],
            "BUILD_NEW_NON_ECONOMIC_MEAN_REVERSION_SCREEN",
        )

    def test_unroutable_deterministic_guess_is_converted_to_bound_implementation(self):
        from research_v3.general_ai_reasoning_provider import _normalize_candidate_routing, build_reasoning_request
        request=build_reasoning_request(ROOT)
        self.assertEqual(request["authorized_deterministic_operations_current_epoch"],[])
        candidate={
            "proposal_id":"deterministic-guess-normalization-test",
            "objective":{"class":"NON_ECONOMIC_STRUCTURAL_RESEARCH","goal":"test","information_gain_rationale":"test"},
            "decision":{"selected_mechanism_family":"MEAN_REVERSION"},
            "next_research_state":{
                "status":"DETERMINISTIC_WORK",
                "next_action":"BUILD_SOMETHING_NEW",
                "research_judgment_required":False,
                "implementation_ai_required":False,
                "selected_family":"MEAN_REVERSION",
                "next_deterministic_operation_ref":"research_v3/EPOCH25_FRONTIER_SELECTION_EXECUTION_AUTHORITY_V1.json",
            },
            "authority_refs":["research_v3/RESEARCH_CONTRACT_V3.json"],
            "data_policy":{"new_market_data_requested":False},
        }
        normalized=_normalize_candidate_routing(request,candidate)
        self.assertNotIn("next_deterministic_operation_ref",normalized["next_research_state"])
        self.assertTrue(normalized["next_research_state"]["implementation_ai_required"])
        self.assertIn("implementation_scope",normalized["decision"])

    def test_current_epoch_has_no_preexisting_deterministic_operation_to_guess(self):
        from research_v3.evidence_epoch import current_evidence_binding
        from research_v3.general_ai_reasoning_provider import build_reasoning_request
        request=build_reasoning_request(ROOT)
        binding=current_evidence_binding(ROOT)
        self.assertEqual(request["evidence_epoch_seen"],binding["evidence_epoch"])
        self.assertEqual(request["authorized_deterministic_operations_current_epoch"],[])

    def test_current_packet_includes_frontier_and_capture_authorities(self):
        state=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        _,refs=_authority_context(ROOT,state)
        for rel in (
            "evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json",
            "research_v3/BROKER_NATIVE_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT_V1.json",
            "research_v3/EPOCH25_FRONTIER_SELECTION_EXECUTION_AUTHORITY_V1.json",
        ):
            self.assertIn(rel,refs)

    def test_all_existing_repository_refs_exposed_by_current_state_are_authorized(self):
        state=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        _,refs=_authority_context(ROOT,state)
        # Regression for the exact Epoch25 rejection: this ref was visible in
        # NEXT_AUTONOMOUS_STATE but omitted from the old manual authority list.
        self.assertIn(
            "evidence/EPOCH23_CARRY_REGIME_STRUCTURAL_FEASIBILITY_GATE_V1.json",
            refs,
        )

        def walk(value,key=None):
            found=[]
            if isinstance(value,dict):
                for k,v in value.items():
                    if k.endswith("_ref") and isinstance(v,str) and v and (ROOT/v).is_file():
                        found.append(v)
                    elif k.endswith("_refs") and isinstance(v,list):
                        found.extend(x for x in v if isinstance(x,str) and x and (ROOT/x).is_file())
                    found.extend(walk(v,k))
            elif isinstance(value,list):
                for v in value:
                    found.extend(walk(v,key))
            return found

        missing=sorted(set(walk(state))-set(refs))
        self.assertEqual(missing,[])

    def test_authority_packet_is_referentially_closed_over_exposed_refs(self):
        state=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        authorities,refs=_authority_context(ROOT,state)
        self.assertIn(
            "evidence/EPOCH23_REGIME_PROPOSAL_SCOPE_SUPERSESSION_V1.json",
            refs,
        )

        def refs_in_doc(value):
            found=[]
            if isinstance(value,dict):
                for k,v in value.items():
                    if k.endswith("_ref") and isinstance(v,str) and v and (ROOT/v).is_file():
                        found.append(v)
                    elif k.endswith("_refs") and isinstance(v,list):
                        found.extend(x for x in v if isinstance(x,str) and x and (ROOT/x).is_file())
                    found.extend(refs_in_doc(v))
            elif isinstance(value,list):
                for v in value:
                    found.extend(refs_in_doc(v))
            return found

        missing=[]
        for item in authorities:
            path=ROOT/item["ref"]
            if path.suffix.lower()!=".json":
                continue
            try:
                doc=json.loads(path.read_text())
            except Exception:
                continue
            for nested in refs_in_doc(doc):
                if nested not in refs:
                    missing.append((item["ref"],nested))
        self.assertEqual(missing,[])

    def test_epoch25_authority_request_is_already_durable_and_resolved(self):
        request=json.loads((ROOT/"research_v3/ai_director/history/ADDITIONAL_AUTHORITY_REQUEST_reason_bbc9d4431461be54a9df89ef6b79cade.json").read_text())
        acceptance=json.loads((ROOT/"research_v3/ai_director/ADDITIONAL_AUTHORITY_ACCEPTANCE_V1.json").read_text())
        self.assertEqual(request["request_id"],"reason_bbc9d4431461be54a9df89ef6b79cade")
        self.assertEqual(request["status"],"ADDITIONAL_AUTHORITY_REQUIRED")
        self.assertEqual(acceptance["status"],"ELIGIBLE_AUTHORITY_ADDED_TO_NEW_PACKET")
        self.assertEqual(acceptance["source_request_id"],request["request_id"])
        self.assertEqual(
            acceptance["requested_ref"],
            "research_v3/EPOCH25_FRONTIER_SELECTION_EXECUTION_AUTHORITY_V1.json",
        )

    def test_future_additional_authority_result_updates_reasoning_response(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"research_v3/ai_director").mkdir(parents=True)
            fake_request={
                "status":"AI_REASONING_REQUIRED",
                "request_id":"reason_test_authority",
                "evidence_epoch_seen":25,
                "authority_refs":[],
            }
            def transport(*args,**kwargs):
                return ({
                    "status":"ADDITIONAL_AUTHORITY_REQUIRED",
                    "requested_authority_or_class":"TEST_AUTHORITY",
                    "rationale":"Need one deterministic authority before selection.",
                },{"model":"auto","provider":"github-copilot-cli"})
            with patch("research_v3.general_ai_reasoning_provider.build_reasoning_request",return_value=fake_request),                  patch("research_v3.general_ai_reasoning_provider._context_payload",return_value={}),                  patch("research_v3.general_ai_reasoning_provider.GitCheckpointSink.checkpoint",return_value=None):
                out=wake(root,token="test",transport=transport)
            self.assertEqual(out["status"],"ADDITIONAL_AUTHORITY_REQUIRED")
            response=json.loads((root/"research_v3/ai_director/AI_REASONING_RESPONSE.json").read_text())
            self.assertEqual(response["status"],"ADDITIONAL_AUTHORITY_REQUIRED")
            self.assertEqual(response["request_id"],"reason_test_authority")


if __name__=="__main__":
    unittest.main()
