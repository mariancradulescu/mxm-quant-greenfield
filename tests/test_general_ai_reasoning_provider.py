import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_reasoning_provider import DEFAULT_MODELS, build_reasoning_request, reasoning_required, wake

class GeneralAIReasoningProviderTests(unittest.TestCase):
    def test_current_pending_c031_state_requires_general_reasoning(self):
        req=build_reasoning_request(".")
        self.assertEqual(req["status"],"AI_REASONING_REQUIRED")
        self.assertEqual(req["project_snapshot"]["v2_attempts_used"],19)
        self.assertEqual(req["project_snapshot"]["v2_search_budget_remaining"],65)
        self.assertEqual(req["project_snapshot"]["economic_outcomes_opened"],27)
        self.assertIn("m6/results/V2-C031_STAGE_B_CURRENT_CONFIG_V1.json",req["authority_refs"])

    def test_wake_detector_is_generic_not_finite_action_map(self):
        self.assertTrue(reasoning_required({"next_action":"AI_SOMETHING_NEVER_SEEN_BEFORE","user_action_required":False}))
        self.assertTrue(reasoning_required({"status":"ANY_PENDING_AI_INTERPRETATION_STATE","user_action_required":False}))
        self.assertFalse(reasoning_required({"next_action":"IMPLEMENT_SOMETHING","user_action_required":False}))
        self.assertFalse(reasoning_required({"ai_reasoning_required":True,"user_action_required":True}))

    def test_default_provider_prefers_frontier_reasoning_model(self):
        self.assertEqual(DEFAULT_MODELS[0],"openai/gpt-5.6-sol")

    def test_missing_token_creates_explicit_gate_without_secret(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch("research_v3.general_ai_reasoning_provider.build_reasoning_request",return_value={"status":"AI_REASONING_REQUIRED","request_id":"reason_test","next_state":{}}), patch.dict(os.environ,{},clear=True):
                out=wake(root,token=None)
            self.assertEqual(out["status"],"EXTERNAL_AUTHORIZATION_REQUIRED")
            raw=(root/"research_v3/ai_director/AI_REASONING_EXTERNAL_GATE.json").read_text()
            self.assertNotIn("Bearer",raw)
            self.assertNotIn("ghp_",raw)

if __name__=="__main__": unittest.main()
