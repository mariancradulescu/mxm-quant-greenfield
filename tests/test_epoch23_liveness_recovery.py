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

    def test_historical_epoch23_semantic_state_routes_to_reasoning(self):
        semantic={
            "status":"FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_EPOCH23_SCOPE_RESOLUTION",
            "next_action":"AI_SELECT_DISTINCT_FRONTIER_WAVE_AFTER_REGIME_SCOPE_RESOLUTION",
            "ai_reasoning_required":True,
            "implementation_ai_required":False,
            "research_judgment_required":True,
            "user_action_required":False,
        }
        self.assertEqual(classify_execution(ROOT,semantic)["execution_class"],"SEMANTIC_REASONING")

    def test_current_reasoning_request_uses_current_state_not_historical_epoch23_contract(self):
        n=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        request=build_reasoning_request(ROOT)
        self.assertEqual(request["next_state"]["status"],n["status"])
        self.assertEqual(request["next_state"]["next_action"],n["next_action"])
        self.assertEqual(
            request["next_state"].get("evidence_epoch"),
            n.get("current_research_evidence_epoch"),
        )

    def test_router_does_not_reinterpret_accepted_proposal_as_implementation_authority(self):
        state={
            "status":"STRUCTURAL_FEASIBILITY_GATE_REQUIRED",
            "next_action":"VALIDATE_ALREADY_AUTHORIZED_STRUCTURAL_GATE",
            "implementation_ai_required":False,
            "research_judgment_required":False,
        }
        self.assertFalse(implementation_required(ROOT,state))

    def test_next_general_ai_prompt_requires_explicit_routing_intent(self):
        p=_system_prompt()
        self.assertIn("implementation_ai_required",p)
        self.assertIn("research_judgment_required",p)
        self.assertIn("new_market_data_requested=true",p)
        self.assertIn("genuinely novel repository code",p)
        self.assertIn("next_deterministic_operation_ref",p)
        self.assertIn("Never publish an unrouted non-empty action",p)

    def test_epoch23_history_is_immutable_and_later_evidence_preserves_accounting(self):
        e=load("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json")
        n=load("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        epoch23=[row for row in e["history"] if row["epoch"]==23]
        self.assertEqual(len(epoch23),1)
        self.assertEqual(epoch23[0]["event_class"],"AUTHENTICATED_MARKET_DATA_ACCEPTED")
        self.assertGreaterEqual(e["current_epoch"],23)
        self.assertEqual(n["accounting"],{"v2_attempts_used":20,"v2_search_budget_remaining":64,"economic_outcomes_opened":28})

if __name__=="__main__":
    unittest.main()
