import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_v3.general_ai_reasoning_provider import (
    PROVIDER_KIND,
    PROVIDER_VERSION,
    _system_prompt,
    _authority_context,
    build_reasoning_request,
    reasoning_required,
    wake,
)

class GeneralAIReasoningProviderTests(unittest.TestCase):
    def test_large_broker_native_index_is_hash_bound_and_readable_without_oversized_cli_argument(self):
        rows,refs=_authority_context(Path("."),{})
        name="data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json"
        self.assertIn(name,refs)
        row=next(x for x in rows if x["ref"]==name)
        self.assertEqual(row["content_summary"]["current_accessible_symbols_indexed"],1690)
        self.assertTrue(row["content_summary"]["available_via_repository_view"])
        self.assertNotIn("products",row)
        self.assertNotIn("content",row)

    def test_current_state_reasoning_request_matches_generic_wake_semantics(self):
        req=build_reasoning_request(".")
        expected="AI_REASONING_REQUIRED" if reasoning_required(req["next_state"]) else "NO_AI_REASONING_REQUIRED"
        self.assertEqual(req["status"],expected)
        current=__import__("json").loads(Path("CURRENT_STATE.json").read_text())
        self.assertEqual(req["project_snapshot"]["v2_attempts_used"],current["v2_attempts_used"])
        self.assertEqual(req["project_snapshot"]["v2_search_budget_remaining"],current["v2_search_budget_remaining"])
        self.assertEqual(req["project_snapshot"]["economic_outcomes_opened"],current["economic_outcomes_opened"])
        if req["next_state"].get("user_action_required") is True:
            self.assertEqual(req["status"],"NO_AI_REASONING_REQUIRED")

    def test_reasoning_context_includes_authoritative_outer_refs(self):
        req=build_reasoning_request(".")
        for rel in (
            "research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json",
            "data/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json",
            "evidence/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_DATA_AUDIT_V1.json",
        ):
            self.assertIn(rel,req["authority_refs"])

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


    def test_reasoning_request_id_ignores_head_and_nonmaterial_checkpoint_fields(self):
        import json
        from research_v3.general_ai_reasoning_provider import NEXT_REL
        original=json.loads((Path(".")/NEXT_REL).read_text())
        with patch("research_v3.general_ai_reasoning_provider._head",return_value="a"*40), patch("research_v3.general_ai_reasoning_provider._load",return_value=original):
            first=build_reasoning_request(".")
        changed=dict(original)
        changed["last_liveness_wake_utc"]="later"
        with patch("research_v3.general_ai_reasoning_provider._head",return_value="b"*40), patch("research_v3.general_ai_reasoning_provider._load",return_value=changed):
            second=build_reasoning_request(".")
        self.assertEqual(first["request_id"],second["request_id"])

    def test_missing_token_creates_explicit_gate_without_secret(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch("research_v3.general_ai_reasoning_provider.build_reasoning_request",return_value={"status":"AI_REASONING_REQUIRED","request_id":"reason_test","next_state":{}}), patch.dict(os.environ,{},clear=True):
                out=wake(root,token=None)
            self.assertEqual(out["status"],"EXTERNAL_AUTHORIZATION_REQUIRED")
            raw=(root/"research_v3/ai_director/AI_REASONING_EXTERNAL_GATE.json").read_text()
            self.assertNotIn("Bearer",raw)
            self.assertNotIn("ghp_",raw)


    def test_monthly_quota_is_attempted_once(self):
        from research_v3.general_ai_reasoning_provider import AIReasoningProviderError
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            calls=[]
            def exhausted(*args,**kwargs):
                calls.append(1)
                raise AIReasoningProviderError("You have exceeded your monthly quota")
            with patch("research_v3.general_ai_reasoning_provider.build_reasoning_request",return_value={"status":"AI_REASONING_REQUIRED","request_id":"reason_quota","next_state":{}}), patch("research_v3.general_ai_reasoning_provider._context_payload",return_value={}), patch("research_v3.general_ai_reasoning_provider.GitCheckpointSink.checkpoint",return_value=None):
                with self.assertRaisesRegex(AIReasoningProviderError,"monthly quota"):
                    wake(root,token="test-token",transport=exhausted)
            self.assertEqual(len(calls),1)

if __name__=="__main__": unittest.main()
