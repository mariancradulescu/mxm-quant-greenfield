import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_reasoning_provider import (
    PROVIDER_KIND,
    PROVIDER_VERSION,
    _system_prompt,
    build_reasoning_request,
    reasoning_required,
    wake,
)

class GeneralAIReasoningProviderTests(unittest.TestCase):
    def test_current_post_ai_decision_state_does_not_repeat_reasoning(self):
        req=build_reasoning_request(".")
        self.assertEqual(req["status"],"NO_AI_REASONING_REQUIRED")
        self.assertEqual(req["project_snapshot"]["v2_attempts_used"],19)
        self.assertEqual(req["project_snapshot"]["v2_search_budget_remaining"],65)
        self.assertEqual(req["project_snapshot"]["economic_outcomes_opened"],27)
        self.assertIn(req["next_state"]["status"],{
            "READY_FOR_MINIMAL_STRUCTURAL_SCREENING",
            "WAITING_EXTERNAL_AUTHENTICATED_DATA",
            "PENDING_EXACT_HEAD_GREEN_STRUCTURAL_EXTENSION_WAVE_01_SCREEN",
        })
        if req["next_state"]["status"]=="WAITING_EXTERNAL_AUTHENTICATED_DATA":
            self.assertTrue(req["next_state"]["user_action_required"])
        else:
            self.assertFalse(req["next_state"].get("user_action_required",False))

    def test_wake_detector_is_generic_not_finite_action_map(self):
        self.assertTrue(reasoning_required({"next_action":"AI_SOMETHING_NEVER_SEEN_BEFORE","user_action_required":False}))
        self.assertTrue(reasoning_required({"status":"ANY_PENDING_AI_INTERPRETATION_STATE","user_action_required":False}))
        self.assertFalse(reasoning_required({"next_action":"IMPLEMENT_SOMETHING","user_action_required":False}))
        self.assertFalse(reasoning_required({"ai_reasoning_required":True,"user_action_required":True}))

    def test_active_provider_is_copilot_cli_not_retired_models_api(self):
        self.assertEqual(PROVIDER_KIND,"GITHUB_COPILOT_CLI")
        self.assertEqual(PROVIDER_VERSION,"MXM_GENERAL_AI_REASONING_PROVIDER_V2")

    def test_prompt_contract_explicitly_protects_deterministic_state(self):
        p=_system_prompt()
        self.assertIn("artifact_attestation_refs: MUST be []",p)
        self.assertIn("competition_start_authorized",p)
        self.assertIn("live_orders_authorized",p)
        self.assertIn("MUST NOT contain",p)

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
