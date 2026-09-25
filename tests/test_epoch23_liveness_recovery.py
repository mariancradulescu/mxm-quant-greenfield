import json,unittest
from pathlib import Path

from research_v3.general_ai_reasoning_provider import _system_prompt
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

    def test_recovered_state_routes_to_one_fresh_semantic_boundary(self):
        n=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        self.assertTrue(n["status"].startswith("FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_EPOCH23_CARRY_REGIME"))
        self.assertTrue(n["research_judgment_required"])
        self.assertTrue(n["ai_reasoning_required"])
        self.assertFalse(n["implementation_ai_required"])
        self.assertFalse(n["external_data_required"])
        self.assertFalse(n["user_action_required"])
        self.assertEqual(n["semantic_focus_family"],"REGIME_CONTEXT_CONDITIONED")
        self.assertEqual(classify_execution(ROOT,n)["execution_class"],"SEMANTIC_REASONING")

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
