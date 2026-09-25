import json,unittest
from pathlib import Path

from research_v3.general_ai_reasoning_provider import _system_prompt, build_reasoning_request
from research_v3.execution_router import classify_execution, implementation_required

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class Epoch23LivenessRecoveryTests(unittest.TestCase):
    def test_structural_gate_honors_carry_first_regime_second_without_economics(self):
        g=load("evidence/EPOCH23_CARRY_REGIME_STRUCTURAL_FEASIBILITY_GATE_V1.json")
        self.assertEqual(g["status"],"COMPLETE_NON_ECONOMIC_DETERMINISTIC_STRUCTURAL_FEASIBILITY_GATE")
        self.assertEqual(g["primary_family"]["family"],"CARRY_TERM_STRUCTURE")
        self.assertEqual(g["primary_family"]["term_structure_metadata"],"FAIL_CLOSED_UNRESOLVED")
        self.assertEqual(g["secondary_family"]["family"],"REGIME_CONTEXT_CONDITIONED")
        self.assertEqual(g["secondary_family"]["result"],"ELIGIBLE_FOR_NEXT_SEMANTIC_MECHANISM_AND_BREADTH_SPECIFICATION")
        self.assertEqual(g["economic_effect"]["v2_attempts"],0)
        self.assertEqual(g["economic_effect"]["economic_outcomes"],0)
        self.assertEqual(g["provider_effect"]["copilot_calls_for_gate"],0)

    def test_scope_recovery_routes_to_new_distinct_semantic_decision(self):
        n=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        self.assertEqual(n["scope_resolution_ref"], "research_v3/EPOCH23_SCOPE_RESOLUTION_V1.json")
        self.assertEqual(n["decision_contract"]["required_action"], "SELECT_DISTINCT_PROSPECTIVE_FRONTIER_WAVE")
        semantic=dict(n)
        semantic.update(status="FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_EPOCH23_SCOPE_RESOLUTION",
                        next_action="AI_SELECT_DISTINCT_FRONTIER_WAVE_AFTER_REGIME_SCOPE_RESOLUTION",
                        ai_reasoning_required=True, implementation_ai_required=False,
                        user_action_required=False)
        self.assertEqual(classify_execution(ROOT,semantic)["execution_class"], "SEMANTIC_REASONING")

    def test_pending_decision_contract_reaches_reasoning_request(self):
        n=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        request=build_reasoning_request(ROOT)
        projected=request["next_state"]
        for field in ("semantic_question","decision_contract","scope_resolution_ref","reason"):
            self.assertEqual(projected[field],n.get(field))
        self.assertEqual(projected["decision_contract"]["required_action"],
                         "SELECT_DISTINCT_PROSPECTIVE_FRONTIER_WAVE")

    def test_router_does_not_reinterpret_accepted_proposal_as_implementation_authority(self):
        n=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        semantic=dict(n)
        semantic["ai_reasoning_required"]=False
        semantic["research_judgment_required"]=False
        semantic["status"]="STRUCTURAL_FEASIBILITY_GATE_REQUIRED"
        semantic["next_action"]="VALIDATE_ALREADY_AUTHORIZED_STRUCTURAL_GATE"
        semantic["implementation_ai_required"]=False
        self.assertFalse(implementation_required(ROOT,semantic))

    def test_next_general_ai_prompt_requires_explicit_routing_intent(self):
        p=_system_prompt()
        self.assertIn("implementation_ai_required",p)
        self.assertIn("research_judgment_required",p)
        self.assertIn("new_market_data_requested=true",p)
        self.assertIn("genuinely novel repository code",p)

    def test_epoch_and_accounting_remain_unchanged_by_deterministic_gate(self):
        e=load("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json")
        n=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        self.assertEqual(e["current_epoch"],23)
        self.assertEqual(n["accounting"],{"v2_attempts_used":20,"v2_search_budget_remaining":64,"economic_outcomes_opened":28})

if __name__=="__main__":
    unittest.main()
