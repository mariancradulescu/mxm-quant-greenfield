import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return json.loads((ROOT / rel).read_text())


class ActiveResearchProjectionTests(unittest.TestCase):
    def test_projection_matches_durable_epoch_and_result(self):
        projection = read("research_v3/ACTIVE_RESEARCH_PROJECTION_V1.json")
        epoch = read("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json")
        state = read("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        result_ref = projection["latest_accepted_material_result_ref"]
        self.assertEqual(projection["evidence_epoch"], epoch["current_epoch"])
        self.assertEqual(state["current_research_evidence_epoch"], epoch["current_epoch"])
        self.assertEqual(result_ref, state["latest_material_structural_result_ref"])
        self.assertTrue((ROOT / result_ref).is_file())
        if state["status"] == "FRESH_GENERAL_AI_REASONING_REQUIRED":
            self.assertTrue(state["ai_reasoning_required"])
        else:
            self.assertTrue(state.get("source_ai_proposal_id"))
            self.assertEqual(state["authorizing_evidence_epoch"], epoch["current_epoch"])

    def test_economic_accounting_unchanged(self):
        projection = read("research_v3/ACTIVE_RESEARCH_PROJECTION_V1.json")
        state = read("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        result = read("evidence/EPOCH27_BREAKOUT_STABILITY_BREADTH_RESULT_V1.json")
        self.assertEqual(projection["accounting"], state["accounting"])
        self.assertEqual(state["accounting"], {
            "economic_outcomes_opened": 28,
            "v2_attempts_used": 20,
            "v2_search_budget_remaining": 64,
        })
        self.assertEqual(result["economic_effect"], {
            "economic_outcomes_opened": 0, "search_budget_change": 0,
            "v2_attempts_consumed": 0,
        })
