import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from research_v3.evidence_eligibility import C032_CAPTURE, C032_RESULT, EvidenceIneligible, packet, validate_eligibility
from research_v3.general_ai_implementation_executor import implementation_required
from research_v3.general_ai_autonomy_loop import run
from research_v3.general_ai_director_bridge import AIProposalRejected
from research_v3.general_ai_reasoning_provider import wake

ROOT=Path(__file__).resolve().parents[1]

class EvidenceEligibilityTests(unittest.TestCase):
    def test_consumed_capture_forbidden_as_new_binding(self):
        with self.assertRaisesRegex(EvidenceIneligible, "OUTCOME_EXPOSED"):
            validate_eligibility({"data_bindings":[C032_CAPTURE],"decision":{"method":"screen"}})

    def test_c032_friction_go_no_go_rejected_even_as_source(self):
        proposal={"data_bindings":[],"objective":{"goal":"friction-adjusted go/no-go"},
                  "decision":{"source_evidence_used":[C032_CAPTURE],
                              "method":"subtract transaction cost from observed post-event move"}}
        with self.assertRaises(EvidenceIneligible):
            validate_eligibility(proposal)

    def test_historical_context_is_readable_without_reuse(self):
        p=packet(ROOT,evidence_epoch=21,decision_class="NEW_PROSPECTIVE",
                 refs=[C032_CAPTURE,C032_RESULT],
                 accounting={"v2_attempts_used":20},
                 universe={"status":"OPEN_1578_ELIGIBLE_POST_EXCLUSION_FRONTIER_CANDIDATES"},
                 semantic_question="What next?",delta_refs=[])
        self.assertEqual(len(p["admissible_inputs"]),0)
        self.assertEqual(len(p["historical_context"]),2)
        self.assertEqual(len(p["forbidden_inputs"]),2)
        self.assertNotIn("content",str(p))

    def test_semantic_rejection_makes_exactly_one_call_without_registry_insertion(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            request={"status":"AI_REASONING_REQUIRED","request_id":"reason_semantic_rejection_test",
                     "evidence_epoch_seen":21}
            calls=[]
            def transport(*args,**kwargs):
                calls.append(1)
                return {},{}
            with patch("research_v3.general_ai_reasoning_provider.build_reasoning_request",return_value=request), patch("research_v3.general_ai_reasoning_provider._context_payload",return_value={}), patch("research_v3.general_ai_reasoning_provider._wrap",side_effect=AIProposalRejected("authority outside supplied context")):
                result=wake(root,token="test-token",transport=transport)
            self.assertEqual(result["status"],"REJECTED_BEFORE_REGISTRY_AND_IMPLEMENTATION")
            self.assertEqual(len(calls),1)
            self.assertFalse((root/"research_v3/ai_director/PROPOSAL_REGISTRY_V1.json").exists())

    def test_integrity_gate_makes_zero_provider_calls(self):
        self.assertFalse(implementation_required({"status":"MATERIAL_INTEGRITY_FAILURE",
             "integrity_gate":"C032_CAPTURE_REUSE","next_action":"RUN_UNSAFE_SCREEN"}))
        from research_v3.general_ai_autonomy_loop import load_json as real_load
        blocked={"status":"MATERIAL_INTEGRITY_FAILURE","integrity_gate":"C032_CAPTURE_REUSE",
                 "next_action":"","ai_reasoning_required":False}
        def fixture(path,default=None):
            if str(path).endswith("NEXT_AUTONOMOUS_STATE.json"):
                return blocked
            return real_load(path,default)
        with patch("research_v3.general_ai_autonomy_loop.load_json",side_effect=fixture), patch("research_v3.general_ai_autonomy_loop.reason") as reason, patch("research_v3.general_ai_autonomy_loop.implement") as implement:
            out=run(ROOT,max_cycles=1)
            self.assertEqual(out["status"],"MATERIAL_INTEGRITY_FAILURE")
            reason.assert_not_called()
            implement.assert_not_called()
