import json, unittest
from pathlib import Path
from research_v3.evidence_epoch import (
    MATERIAL_EVENT_CLASSES,current_evidence_binding,current_evidence_epoch,
    stale_reasoning_redirect,state_requires_research_judgment,
)
from research_v3.general_ai_reasoning_provider import build_reasoning_request
from research_v3.general_ai_director_bridge import AIProposalRejected, validate_proposal

ROOT=Path(__file__).resolve().parents[1]

class ResearchEvidenceEpochTests(unittest.TestCase):
    def test_current_epoch_binds_complete_40_symbol_evidence(self):
        self.assertGreaterEqual(current_evidence_epoch(ROOT),1)
        b=current_evidence_binding(ROOT)
        refs={x["ref"] for x in b["authoritative_evidence_refs_and_hashes"]}
        self.assertIn("data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json",refs)
        self.assertIn("evidence/BROKER_NATIVE_FRONTIER_13W_SESSION_GAP_STRUCTURAL_SCREEN_V1.json",refs)
        self.assertEqual(len(b["evidence_bundle_sha256"]),64)

    def test_stale_general_ai_proposal_cannot_authorize_new_research(self):
        p=json.loads((ROOT/"research_v3/ai_director/proposals/AUTO_reason_6c3ec041d59c9fadfe5c74fb861b7d48.json").read_text())
        current=current_evidence_binding(ROOT)
        p["evidence_binding"]={
            "reasoning_request_id":"historical",
            "reasoning_response_id":"historical",
            "evidence_epoch_seen":0,
            "evidence_bundle_sha256":current["evidence_bundle_sha256"],
            "authoritative_evidence_refs_and_hashes":current["authoritative_evidence_refs_and_hashes"],
            "accounting_basis":p.get("basis",{}).get("accounting",{}),
            "universe_basis":current["universe_basis"],
            "current_open_mechanism_families":current["current_open_mechanism_families"],
        }
        with self.assertRaisesRegex(AIProposalRejected,"stale for new research judgment"):
            validate_proposal(ROOT,p)

    def test_new_development_evidence_forces_fresh_ai_before_panel_outer(self):
        state={"research_judgment_required":True,"authorizing_evidence_epoch":0,
               "status":"FOUR_PANEL_OUTER_READY","next_action":"RUN_FOUR_PANEL_OUTER",
               "user_action_required":True,"external_data_gate":{"package":"four-panel.zip"}}
        r=stale_reasoning_redirect(ROOT,state)
        self.assertIsNotNone(r)
        self.assertEqual(r["status"],"FRESH_GENERAL_AI_REASONING_REQUIRED")
        self.assertTrue(r["ai_reasoning_required"])
        self.assertFalse(r["user_action_required"])
        self.assertIsNone(r["external_data_gate"])

    def test_deterministic_repair_does_not_trigger_fresh_reasoning(self):
        for classification in ("PAGINATION_REPAIR","CHECKSUM_VALIDATION","PERSISTENCE_REPAIR","CI_REPAIR"):
            state={"research_judgment_required":False,"authorizing_evidence_epoch":0,
                   "execution_classification":classification}
            self.assertFalse(state_requires_research_judgment(state))
            self.assertIsNone(stale_reasoning_redirect(ROOT,state))

    def test_already_authorized_capture_may_continue_across_new_epoch(self):
        state={"research_judgment_required":False,"authorizing_evidence_epoch":0,
               "deterministic_execution_authorized":True,
               "next_action":"RUN_ALREADY_PROSPECTIVELY_AUTHORIZED_CAPTURE"}
        self.assertIsNone(stale_reasoning_redirect(ROOT,state))

    def test_reasoning_request_is_bound_to_current_epoch_and_material_refs(self):
        req=build_reasoning_request(ROOT)
        self.assertEqual(req["evidence_epoch_seen"],current_evidence_epoch(ROOT))
        self.assertEqual(len(req["evidence_bundle_sha256"]),64)
        refs={x["ref"] for x in req["authoritative_evidence_refs_and_hashes"]}
        self.assertIn("data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json",refs)
        self.assertIn("evidence/BROKER_NATIVE_FRONTIER_13W_SESSION_GAP_STRUCTURAL_SCREEN_V1.json",refs)
        self.assertEqual(req["project_snapshot"]["v2_attempts_used"],19)
        self.assertEqual(req["project_snapshot"]["v2_search_budget_remaining"],65)
        self.assertEqual(req["project_snapshot"]["economic_outcomes_opened"],27)
        self.assertGreater(len(req["current_open_mechanism_families"]),1)

    def test_epoch_advance_classes_cover_required_material_events(self):
        expected={
          "AUTHENTICATED_MARKET_DATA_ACCEPTED","MATERIAL_DEVELOPMENT_STRUCTURAL_EVIDENCE_ACCEPTED",
          "INDEPENDENT_OUTER_OUTCOME_OPENED","BROKER_FRICTION_COST_MARGIN_EXECUTION_EVIDENCE_ACCEPTED",
          "HISTORICAL_VALIDITY_INTERPRETATION_CHANGED","BROKER_UNIVERSE_FEASIBILITY_AUTHORITY_CHANGED",
          "MATERIAL_DATA_IMPLEMENTATION_CORRECTION","MATERIAL_EVIDENCE_SUPERSESSION"
        }
        self.assertEqual(set(MATERIAL_EVENT_CLASSES),expected)

if __name__=="__main__":
    unittest.main()
