import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_reasoning_provider import _authority_context, wake

ROOT=Path(__file__).resolve().parents[1]


class Epoch25AdditionalAuthorityRecoveryTests(unittest.TestCase):
    def test_current_packet_includes_frontier_and_capture_authorities(self):
        state=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        _,refs=_authority_context(ROOT,state)
        for rel in (
            "evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json",
            "research_v3/BROKER_NATIVE_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT_V1.json",
            "research_v3/EPOCH25_FRONTIER_SELECTION_EXECUTION_AUTHORITY_V1.json",
        ):
            self.assertIn(rel,refs)

    def test_epoch25_authority_request_is_already_durable_and_resolved(self):
        request=json.loads((ROOT/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json").read_text())
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
