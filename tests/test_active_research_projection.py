import json
import tempfile
import unittest
from pathlib import Path

from research_v3.evidence_epoch import derive_active_projection, refresh_derived_views

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return json.loads((ROOT / rel).read_text())


class ActiveResearchProjectionTests(unittest.TestCase):
    def test_projection_is_derived_from_canonical_active_state(self):
        projection = read("research_v3/ACTIVE_RESEARCH_PROJECTION_V1.json")
        expected = derive_active_projection(ROOT)
        state = read("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        self.assertEqual(projection, expected)
        self.assertEqual(projection["evidence_epoch"], state["current_research_evidence_epoch"])
        result_ref = projection["latest_accepted_material_result_ref"]
        self.assertEqual(result_ref, state["latest_material_structural_result_ref"])
        self.assertTrue((ROOT / result_ref).is_file())
        if state.get("ai_reasoning_required") is True:
            self.assertEqual(projection["execution_requirement"], "FRESH_GENERAL_AI_RESEARCH_JUDGMENT")

    def test_stale_projection_is_regenerated_not_used_as_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "research_v3/runtime_v2_acceptance").mkdir(parents=True)
            (root / "evidence").mkdir(parents=True)
            result_ref = "evidence/result.json"
            (root / result_ref).write_text("{}", encoding="utf-8")
            state = {
                "schema":"mxm.greenfield.runtime-v2-next-autonomous-state.v3",
                "status":"FRESH_GENERAL_AI_REASONING_REQUIRED",
                "next_action":"AI_SELECT_NEXT_ACTION",
                "current_research_evidence_epoch":29,
                "evidence_epoch":29,
                "ai_reasoning_required":True,
                "research_judgment_required":True,
                "latest_material_structural_result_ref":result_ref,
                "canonical_frontier_ref":"research_v3/CURRENT_RESEARCH_FRONTIER_V1.json",
                "accounting":{"economic_outcomes_opened":28,"v2_attempts_used":20,"v2_search_budget_remaining":64},
                "safety":{"live_orders_authorized":False,"protected_evidence_opened":False},
            }
            (root / "research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").write_text(json.dumps(state), encoding="utf-8")
            (root / "research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json").write_text(json.dumps({
                "schema":"mxm.greenfield.research-evidence-epoch.v1","current_epoch":28,
                "authoritative_evidence_refs":[],"provisional_research_artifacts":[]
            }), encoding="utf-8")
            (root / "research_v3/ACTIVE_RESEARCH_PROJECTION_V1.json").write_text(json.dumps({"evidence_epoch":28}), encoding="utf-8")
            projection=refresh_derived_views(root)
            self.assertEqual(projection["evidence_epoch"],29)
            persisted=json.loads((root/"research_v3/ACTIVE_RESEARCH_PROJECTION_V1.json").read_text())
            self.assertEqual(persisted,projection)

    def test_economic_accounting_unchanged(self):
        projection = read("research_v3/ACTIVE_RESEARCH_PROJECTION_V1.json")
        state = read("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
        result = read(state["latest_material_structural_result_ref"])
        self.assertEqual(projection["accounting"], state["accounting"])
        self.assertEqual(state["accounting"], {
            "economic_outcomes_opened": 28,
            "v2_attempts_used": 20,
            "v2_search_budget_remaining": 64,
        })
        effect=result.get("accounting_effect") or result.get("economic_effect") or {}
        self.assertEqual(int(effect.get("economic_outcomes_opened",0)),0)
        self.assertEqual(int(effect.get("search_budget_change",0)),0)
        self.assertEqual(int(effect.get("v2_attempts_consumed",0)),0)


if __name__=="__main__":
    unittest.main()
