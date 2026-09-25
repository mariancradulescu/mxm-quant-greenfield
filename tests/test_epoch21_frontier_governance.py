import copy
import json
import unittest
from pathlib import Path
from research_v3.economic_envelope_governor import (
    BREADTH_UNITS, REQUIRED_FREEZE, REQUIRED_GATES, EnvelopeIneligible,
    capacity, validate, account_first_open)
from research_v3.general_ai_reasoning_provider import _context_payload, _system_prompt

ROOT=Path(__file__).resolve().parents[1]

def envelope():
    return {"evidence_epoch":21,"new_candidate_id":"V2-C033",
            "replacement_for":"V2-C032","mechanism_family":"TREND_MOMENTUM",
            "eligible_symbols_or_relationships":["EURUSD","AUDUSD"],
            "selection_uses_opened_economic_outcomes":False,
            "prospective_freeze":{k:"frozen" for k in REQUIRED_FREEZE},
            "prerequisites":{k:True for k in REQUIRED_GATES},
            "breadth_proof":{"unit":BREADTH_UNITS["TREND_MOMENTUM"],
                "prospective_selection_law":"broker structural coverage only",
                "information_sufficiency_stopping_law":"stop when no new signature remains",
                "structural_heterogeneity":"two distinct signatures",
                "independent_event_evidence":"separately verified event density"}}

class Epoch21FrontierGovernanceTests(unittest.TestCase):
    def test_current_frontier_has_no_consumed_or_rejected_active_target(self):
        state=json.loads((ROOT/"research_v3/CURRENT_RESEARCH_FRONTIER_V1.json").read_text())
        nxt=json.loads((ROOT/"research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json").read_text())
        for key in ("active_candidate_id","active_target_symbol","active_mechanism_family","active_proposal_id"):
            self.assertIsNone(state[key])
            self.assertIsNone(nxt[key])
        for key in ("candidate_id","target_symbol","mechanism_family","source_ai_proposal_id"):
            self.assertIsNone(nxt[key])
        self.assertEqual(state["open_frontier"]["eligible_post_exclusion_symbols"],1578)
        self.assertEqual(len(state["open_frontier"]["mechanism_families"]),10)
        self.assertFalse(state["historical_context"]["V2_C032"]["active_target"])

    def test_budget_authority_separates_historical_snapshot(self):
        b=json.loads((ROOT/"research_v3/SEARCH_BUDGET_GOVERNANCE_V2.json").read_text())
        self.assertEqual((b["current"]["used"],b["current"]["remaining"]),(20,64))
        self.assertEqual((b["historical_snapshot"]["counters"]["used"],b["historical_snapshot"]["counters"]["remaining"]),(19,65))

    def test_all_20_outcome_blind_and_unchanged_lifetime_exposure(self):
        audit=capacity(ROOT)
        rows=audit["per_identity"]
        self.assertEqual(len(rows),20)
        self.assertEqual(audit["methodology_replacement_capacity"]["total"],15)
        self.assertEqual(audit["lifetime_economic_exposure"]["distinct_consumed_v2_identities"],20)
        self.assertEqual(audit["lifetime_economic_exposure"]["economic_outcomes_opened"],28)
        self.assertTrue(all(row["result_sign_ignored"] for row in rows))
        by={row["candidate_id"]:row for row in rows}
        self.assertTrue(all(by[f"V2-C{i:03d}"]["replacement_eligible"] for i in
            (13,14,15,16,17,18,19,20,21,22,24,26)))
        self.assertFalse(by["V2-C025"]["replacement_eligible"])
        self.assertEqual(by["V2-C025"]["latest_result_status"],"COARSE_NET_FAIL")
        self.assertFalse(by["V2-C006"]["replacement_eligible"])
        self.assertFalse(by["V2-C012"]["replacement_eligible"])
        self.assertTrue(by["V2-C032"]["replacement_eligible"])
        self.assertTrue(by["V2-C029"]["replacement_eligible"])
        self.assertTrue(by["V2-C030"]["replacement_eligible"])

    def test_new_envelope_requires_all_prerequisites_and_scope(self):
        e=envelope()
        self.assertEqual(validate(ROOT,e)["attempt_units_at_first_economic_outcome"],1)
        for key in REQUIRED_GATES:
            candidate=copy.deepcopy(e);candidate["prerequisites"][key]=False
            with self.assertRaises(EnvelopeIneligible):
                validate(ROOT,candidate)
        candidate=copy.deepcopy(e);candidate["eligible_symbols_or_relationships"]=["EURUSD"]
        with self.assertRaises(EnvelopeIneligible):
            validate(ROOT,candidate)
        candidate=copy.deepcopy(e);candidate["new_candidate_id"]="V2-C032"
        with self.assertRaises(EnvelopeIneligible):
            validate(ROOT,candidate)

    def test_multi_symbol_one_identity_and_no_outcome_driven_selection(self):
        e=envelope();row=account_first_open(ROOT,e,opened=set())
        self.assertEqual(row["economic_attempt_delta"],1)
        self.assertEqual(row["per_symbol_outcomes_do_not_mint_identities"],True)
        e["selection_uses_opened_economic_outcomes"]=True
        with self.assertRaises(EnvelopeIneligible):validate(ROOT,e)

    def test_frontier_packet_not_anchored_to_prior_selected_action(self):
        request={"request_id":"test-frontier","evidence_epoch_seen":21,
                 "next_state":{"next_action":"AI_FRONTIER_RESEARCH"},
                 "authority_refs":["research_v3/CURRENT_RESEARCH_FRONTIER_V1.json",
                    "research_v3/EPOCH21_OUTCOME_BLIND_CAPACITY_AUDIT_V1.json",
                    "discovery/results/V2-C032_STAGE_A_V1.json"],
                 "project_snapshot":{},"universe_basis":{}}
        packet=_context_payload(ROOT,request)
        self.assertNotIn("prior_accepted_reasoning_summary",packet)
        self.assertNotIn("target_symbol",packet["eligibility_packet"]["exact_semantic_question"])
        self.assertEqual(packet["capacity"]["methodology_replacement_total"],15)
        self.assertTrue(any(x["ref"]=="discovery/results/V2-C032_STAGE_A_V1.json"
                            for x in packet["eligibility_packet"]["forbidden_inputs"]))

    def test_prompt_does_not_privilege_prior_symbol_or_panel(self):
        prompt=_system_prompt()
        self.assertNotIn("NETH25",prompt)
        self.assertNotIn("C031",prompt)
        self.assertNotIn("four-panel SESSION_GAP",prompt)
        self.assertIn("complete 1578-symbol eligible frontier",prompt)

    def test_additional_authority_is_not_granted_to_unclassified_file(self):
        import tempfile
        from research_v3.additional_authority_governor import resolve
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            target=root/"evidence/UNKNOWN_UNREVIEWED_V1.json"
            target.parent.mkdir(parents=True)
            target.write_text('{"status":"ACCEPTED"}')
            request=root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json"
            request.parent.mkdir(parents=True)
            request.write_text(json.dumps({"status":"ADDITIONAL_AUTHORITY_REQUIRED",
                "requested_authority_or_class":"evidence/UNKNOWN_UNREVIEWED_V1.json"}))
            registry=root/"research_v3/ai_director/EVIDENCE_ELIGIBILITY_V1.json"
            registry.write_text(json.dumps({"bindings":[]}))
            self.assertEqual(resolve(root)["status"],"AUTHORITY_NOT_CLASSIFIED")
            self.assertFalse((root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_ACCEPTANCE_V1.json").exists())

    def test_rejected_breakout_proposal_never_passes_prospective_eligibility(self):
        from research_v3.evidence_eligibility import validate_eligibility, EvidenceIneligible
        proposal=json.loads((ROOT/"research_v3/ai_director/proposals/AUTO_reason_388458036df2ab11bb8cb7025f95aa74.json").read_text())
        with self.assertRaisesRegex(EvidenceIneligible,"post-event directional followthrough"):
            validate_eligibility(proposal)
        clean=copy.deepcopy(proposal)
        clean["data_bindings"]=[b for b in clean["data_bindings"] if "FOLLOWTHROUGH" not in b["ref"]]
        clean["decision"]["candidate_construction_procedure"]=[]
        with self.assertRaisesRegex(EvidenceIneligible,"fixed symbol/cluster minima"):
            validate_eligibility(clean)

    def test_mapping_of_consumed_capture_cannot_evade_role_check(self):
        from research_v3.evidence_eligibility import validate_eligibility, EvidenceIneligible, C032_CAPTURE
        proposal={"decision":{},"objective":{},
            "data_bindings":[{"ref":C032_CAPTURE,"role":"STRUCTURAL_REUSABLE"}]}
        with self.assertRaisesRegex(EvidenceIneligible,"OUTCOME_EXPOSED"):
            validate_eligibility(proposal)
