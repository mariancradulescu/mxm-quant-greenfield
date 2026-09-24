import json, unittest
from pathlib import Path
from research_v3.general_ai_implementation_executor import DEFAULT_MODEL as IMPLEMENTATION_MODEL, PROTECTED_PREFIXES, _post_green_output, _resolve_current_proposal, authoritative_reasoning_requirement, implementation_required
from research_v3.general_ai_reasoning_provider import DEFAULT_MODEL, reasoning_required

ROOT=Path(__file__).resolve().parents[1]
class GeneralAIImplementationExecutorTests(unittest.TestCase):
    def test_current_state_routes_by_semantics_not_finite_state_names(self):
        s=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        if s.get("user_action_required") is True:
            self.assertFalse(implementation_required(s))
        elif reasoning_required(s):
            self.assertFalse(implementation_required(s))
        else:
            self.assertTrue(implementation_required(s))
    def test_executor_binds_proposal_when_state_is_proposal_bound_or_preserves_recovery_supersession(self):
        state=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        if state.get("source_ai_proposal_id") or state.get("source_ai_proposal_hash") or state.get("source_runtime_operation_id"):
            ref,proposal,row=_resolve_current_proposal(ROOT,state)
            self.assertEqual(proposal["proposal_id"],state["source_ai_proposal_id"])
            if state.get("source_ai_proposal_hash"):
                self.assertEqual(row["proposal_hash"],state["source_ai_proposal_hash"])
        else:
            self.assertTrue(state.get("supersession_ref") or state.get("outer_capture_plan_ref"))
        source=(ROOT/"research_v3/general_ai_implementation_executor.py").read_text()
        self.assertNotIn("AUTO_reason_a8b81cef686ff74cf678e7e25193f43f.json",source)

    def test_post_green_implementation_returns_to_reasoning(self):
        out={"status":"IMPLEMENTATION_CHANGED_REQUIRES_EXACT_HEAD_GREEN","next_research_state":{"status":"PENDING_EXACT_HEAD_GREEN","next_action":"VALIDATE"}}
        accepted=_post_green_output(out,["research_v3/example.json"])
        self.assertTrue(accepted["next_research_state"]["ai_reasoning_required"])
        self.assertEqual(accepted["next_research_state"]["green_implementation_artifacts"],["research_v3/example.json"])

    def test_authoritative_independent_outer_contract_redirects_before_execution(self):
        s={"source_freeze_ref":"research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json","next_action":"ARBITRARY_EXECUTION","user_action_required":False}
        r=authoritative_reasoning_requirement(ROOT,s)
        self.assertIsNotNone(r)
        self.assertTrue(r["ai_reasoning_required"])
        self.assertEqual(r["next_action"],"GENERAL_AI_SELECT_MINIMAL_DISJOINT_OUTER_WINDOW_AND_REQUIRED_COST_AUTHORITY_BEFORE_ANY_OUTER_OUTCOME")

    def test_outer_binding_satisfies_generic_redirect_guard(self):
        s={"source_freeze_ref":"research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json","next_action":"ARBITRARY_EXECUTION","outer_data_binding_ref":"evidence/some_future_binding.json","user_action_required":False}
        self.assertIsNone(authoritative_reasoning_requirement(ROOT,s))

    def test_arbitrary_non_reasoning_action_is_not_finite_mapped(self):
        self.assertTrue(implementation_required({"status":"ANY_FUTURE_STATE","next_action":"SOMETHING_NEVER_SEEN_BEFORE","user_action_required":False}))
        self.assertFalse(implementation_required({"status":"WAIT","next_action":"EXTERNAL","user_action_required":True}))
    def test_protected_authorities_include_economics_and_ledgers(self):
        joined="\n".join(PROTECTED_PREFIXES)
        for item in ("CURRENT_STATE.json","discovery/ledger.jsonl","research_v3/runtime_v2/","m6/results/","PROPOSAL_REGISTRY_V1.json",".github/workflows/"):
            self.assertIn(item,joined)
    def test_account_policy_falls_back_transparently_to_auto(self):
        self.assertEqual(DEFAULT_MODEL,"auto")
        self.assertEqual(IMPLEMENTATION_MODEL,"auto")
if __name__=="__main__": unittest.main()
