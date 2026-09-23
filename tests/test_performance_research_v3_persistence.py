import json
import tempfile
import unittest
from pathlib import Path

from discovery.ledger import append_entry, read_ledger
from research_v3.persistence import WavePersistenceError, persist_wave_results

ROOT=Path(__file__).resolve().parents[1]

class WavePersistenceTests(unittest.TestCase):
    def fixture(self):
        tmp=tempfile.TemporaryDirectory()
        root=Path(tmp.name)
        (root/"discovery/results").mkdir(parents=True)
        (root/"research_v3").mkdir(parents=True)
        r24=json.loads((ROOT/"discovery/results/V2-C024_STAGE_A_V1.json").read_text())
        r25=json.loads((ROOT/"discovery/results/V2-C025_STAGE_A_V1.json").read_text())
        ledger=root/"discovery/ledger.jsonl"
        append_entry(ledger,entry_type="CANDIDATE_FROZEN",candidate_id="V2-C024",spec_hash=r24["spec_hash"],payload={"test":True},timestamp_utc="2026-01-01T00:00:00Z")
        append_entry(ledger,entry_type="CANDIDATE_FROZEN",candidate_id="V2-C025",spec_hash=r25["spec_hash"],payload={"test":True},timestamp_utc="2026-01-01T00:00:01Z")
        freeze={"accounting_before":{"v2_attempts_used":0,"v2_search_budget_remaining":84,"v2_evaluated_identities":0,"economic_outcomes_opened":0,"discovery_ledger_entries":2,"discovery_result_recorded_entries":0}}
        (root/"research_v3/WAVE_99_PRE_OUTCOME_FREEZE_V1.json").write_text(json.dumps(freeze))
        state={
            "v2_search_budget":84,"v2_attempts_used":0,"v2_evaluated_identities":0,
            "v2_search_budget_remaining":84,"economic_outcomes_opened":0,
            "legacy_prior_attempts":16,"global_attempts_seen":16,
            "discovery_ledger_entries":2,"discovery_result_recorded_entries":0,
            "stage_a_result_recorded_entries":0,"distinct_identity_outcomes_opened":0,
            "stage_b_current_config_economic_observations":0,
            "v2_budget_charged_candidate_ids":[],"v2_historical_evaluated_candidate_ids":[],
            "current_live_equivalent_authoritative_candidate_ids":[],
            "current_invalid_result_authority_candidate_ids":[],
            "protected_evidence_opened":False,"live_orders_authorized":False,
            "competition_start_authorized":False,"structural_only_since_previous_economic_outcome":True,
            "current_result_authority":{},"active_result_pointers":{},
            "performance_research_v3":{"status":"WAVE99_AUTHORIZED_NOT_EXECUTED","wave99":{
                "status":"AUTHORIZED_AFTER_EXACT_HEAD_GREEN",
                "freeze_ref":"research_v3/WAVE_99_PRE_OUTCOME_FREEZE_V1.json",
                "authorization_ref":"research_v3/WAVE_99_EXECUTION_AUTHORIZATION_V1.json",
                "candidate_ids":["V2-C024","V2-C025"],
                "candidate_spec_hashes":{"V2-C024":r24["spec_hash"],"V2-C025":r25["spec_hash"]},
                "v2_attempts_used_before_wave99":0,
                "execution_gate_head":"0"*40,"execution_gate_ci_run_id":1,"execution_gate_ci_conclusion":"SUCCESS",
            }}
        }
        (root/"CURRENT_STATE.json").write_text(json.dumps(state))
        return tmp,root,r24,r25,state

    def test_idempotent_two_candidate_persistence_and_state_behind_resume(self):
        tmp,root,r24,r25,initial=self.fixture()
        self.addCleanup(tmp.cleanup)
        kwargs=dict(root=root,wave_key="wave99",results={"V2-C024":r24,"V2-C025":r25},recorded_utc="2026-01-02T00:00:00Z",execution_result_ref="research_v3/WAVE_99_EXECUTION_RESULT_V1.json")
        first=persist_wave_results(**kwargs)
        ledger1=(root/"discovery/ledger.jsonl").read_bytes()
        state1=(root/"CURRENT_STATE.json").read_bytes()
        self.assertEqual(first["new_result_ids_this_invocation"],["V2-C024","V2-C025"])
        self.assertEqual((first["v2_attempts_used"],first["v2_search_budget_remaining"],first["economic_outcomes_opened"]),(2,82,2))
        second=persist_wave_results(**kwargs)
        self.assertEqual(second["new_result_ids_this_invocation"],[])
        self.assertEqual((root/"discovery/ledger.jsonl").read_bytes(),ledger1)
        self.assertEqual((root/"CURRENT_STATE.json").read_bytes(),state1)
        (root/"CURRENT_STATE.json").write_text(json.dumps(initial))
        resumed=persist_wave_results(**kwargs)
        self.assertEqual(resumed["new_result_ids_this_invocation"],[])
        recovered=json.loads((root/"CURRENT_STATE.json").read_text())
        self.assertEqual(recovered["v2_attempts_used"],2)
        self.assertEqual(recovered["discovery_result_recorded_entries"],2)
        self.assertEqual(recovered["stage_a_result_recorded_entries"],2)
        self.assertEqual(recovered["distinct_identity_outcomes_opened"],2)
        self.assertEqual(recovered["v2_budget_charged_candidate_ids"],["V2-C024","V2-C025"])
        self.assertEqual(sum(e["entry_type"]=="RESULT_RECORDED" for e in read_ledger(root/"discovery/ledger.jsonl")),2)

    def test_partial_one_then_second_converges_without_duplicate(self):
        tmp,root,r24,r25,_=self.fixture()
        self.addCleanup(tmp.cleanup)
        first=persist_wave_results(root,wave_key="wave99",results={"V2-C024":r24},recorded_utc="2026-01-02T00:00:00Z",execution_result_ref="research_v3/WAVE_99_EXECUTION_RESULT_V1.json")
        self.assertEqual(first["v2_attempts_used"],1)
        second=persist_wave_results(root,wave_key="wave99",results={"V2-C025":r25},recorded_utc="2026-01-03T00:00:00Z",execution_result_ref="research_v3/WAVE_99_EXECUTION_RESULT_V1.json")
        self.assertEqual(second["v2_attempts_used"],2)
        rows=read_ledger(root/"discovery/ledger.jsonl")
        for cid in ("V2-C024","V2-C025"):
            self.assertEqual(sum(e["entry_type"]=="RESULT_RECORDED" and e["candidate_id"]==cid for e in rows),1)

    def test_explicit_live_equivalent_authority_is_projected_without_changing_budget_law(self):
        tmp,root,r24,_,_=self.fixture()
        self.addCleanup(tmp.cleanup)
        persist_wave_results(
            root,wave_key="wave99",results={"V2-C024":r24},
            recorded_utc="2026-01-02T00:00:00Z",
            execution_result_ref="research_v3/WAVE_99_EXECUTION_RESULT_V1.json",
            live_equivalent_candidate_ids=["V2-C024"],
        )
        state=json.loads((root/"CURRENT_STATE.json").read_text())
        self.assertEqual(state["v2_attempts_used"],1)
        self.assertEqual(state["distinct_identity_outcomes_opened"],1)
        self.assertEqual(state["current_live_equivalent_authoritative_candidate_ids"],["V2-C024"])
        authority=state["current_result_authority"]["V2-C024"]["stage_a"]
        self.assertTrue(authority["current_live_equivalent_authoritative"])
        self.assertEqual(authority["live_equivalent_replay_state"],"VALID_AS_FROZEN_AND_IMPLEMENTED")

    def test_conflicting_partial_result_fails_closed(self):
        tmp,root,r24,_,_=self.fixture()
        self.addCleanup(tmp.cleanup)
        persist_wave_results(root,wave_key="wave99",results={"V2-C024":r24},recorded_utc="2026-01-02T00:00:00Z",execution_result_ref="research_v3/WAVE_99_EXECUTION_RESULT_V1.json")
        bad=dict(r24)
        bad["status"]="COARSE_NET_FAIL" if r24["status"]!="COARSE_NET_FAIL" else "GROSS_EDGE_FAIL"
        with self.assertRaises(WavePersistenceError):
            persist_wave_results(root,wave_key="wave99",results={"V2-C024":bad},recorded_utc="2026-01-02T00:00:00Z",execution_result_ref="research_v3/WAVE_99_EXECUTION_RESULT_V1.json")

if __name__=="__main__":
    unittest.main(verbosity=2)
