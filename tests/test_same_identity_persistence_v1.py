import json
import tempfile
import unittest
from pathlib import Path

from discovery.canonical import compute_result_hash
from discovery.ledger import append_entry, read_ledger
from discovery.schema import STAGE_A_METRIC_KEYS, validate_result
from research_v3.same_identity_persistence_v1 import (
    CORRECTION_ID, CORRECTION_IDS, RESULT_REFS,
    SameIdentityPersistenceError, persist_same_identity_corrections,
)


def result(cid, spec_hash, status="DATA_INSUFFICIENT"):
    reason="synthetic settlement unavailable"
    r={
      "candidate_id":cid,"spec_hash":spec_hash,"stage":"A","status":status,
      "implementation_validity":{"state":"VALID","reason":"synthetic correction"},
      "metrics":{k:{"state":"UNAVAILABLE","reason":reason} for k in STAGE_A_METRIC_KEYS},
      "eur200_feasibility":{"state":"NOT_EVALUATED","reason":reason},
      "cost_confidence":{"state":"CONSERVATIVE_BOUND","reason":reason},
      "data_completeness":{"state":"INSUFFICIENT","reason":reason},
      "provenance":{
        "data_evidence":{"identity":"SYNTH","binding":{"type":"DATASET_SHA256","sha256":"1"*64}},
        "cost_evidence":{"identity":"SYNTH_COST","state":"CONSERVATIVE_BOUND","sha256":"2"*64},
        "evaluator":{"version":"TEST","sha256":"3"*64},
      },
    }
    validate_result(r); r["result_hash"]=compute_result_hash(r); validate_result(r); return r


class SameIdentityPersistenceV1Tests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name)
        (self.root/"discovery/results").mkdir(parents=True)
        (self.root/"evidence").mkdir(parents=True)
        (self.root/"research_v3").mkdir(parents=True)
        self.specs={cid:(str(i+1)*64)[:64] for i,cid in enumerate(CORRECTION_IDS)}
        ledger=self.root/"discovery/ledger.jsonl"
        old_refs={}
        for i,cid in enumerate(CORRECTION_IDS):
            sh=self.specs[cid]
            append_entry(ledger,entry_type="CANDIDATE_FROZEN",candidate_id=cid,spec_hash=sh,payload={"test":True},timestamp_utc="2026-01-01T00:00:00Z")
            old=result(cid,sh)
            ref=f"discovery/results/{cid}_STAGE_A_V1.json"; old_refs[cid]=ref
            (self.root/ref).write_text(json.dumps(old,sort_keys=True,indent=2)+"\n")
            append_entry(ledger,entry_type="RESULT_RECORDED",candidate_id=cid,spec_hash=sh,payload={"result_hash":old["result_hash"],"result":old},timestamp_utc="2026-01-02T00:00:00Z")
        state={
          "v2_search_budget":84,"legacy_prior_attempts":16,"v2_attempts_used":4,"v2_evaluated_identities":4,
          "v2_search_budget_remaining":80,"global_attempts_seen":20,"economic_outcomes_opened":6,
          "stage_b_current_config_economic_observations":2,"discovery_result_recorded_entries":4,
          "stage_a_result_recorded_entries":4,"distinct_identity_outcomes_opened":4,
          "v2_historical_evaluated_candidate_ids":list(CORRECTION_IDS),
          "pending_same_identity_correction_candidate_ids":list(CORRECTION_IDS),
          "current_live_equivalent_authoritative_candidate_ids":[],
          "current_result_authority":{cid:{"stage_a":{"state":"HISTORICAL","result_ref":old_refs[cid],"result_hash":json.loads((self.root/old_refs[cid]).read_text())["result_hash"],"status":"DATA_INSUFFICIENT","live_equivalent_replay_state":"IMPLEMENTATION_ONLY_SAME_SEMANTICS_CORRECTABLE","current_live_equivalent_authoritative":False}} for cid in CORRECTION_IDS},
          "active_result_pointers":{f"{cid}_STAGE_A":None for cid in CORRECTION_IDS},
          "performance_research_v3":{"status":"PENDING"},
          "discovery_survivors":[],"current_stage_b_survivor_input_set":[],"live_equivalent_discovery_survivors":[],
        }
        (self.root/"CURRENT_STATE.json").write_text(json.dumps(state,indent=2)+"\n")
        audit={"status":"X","groups":{"implementation_only_same_semantics_correctable":list(CORRECTION_IDS)},"attempt_accounting":{"historical_evaluated_candidate_ids":list(CORRECTION_IDS),"budget_charged_candidate_ids":list(CORRECTION_IDS),"pending_same_identity_correction_candidate_ids":list(CORRECTION_IDS)}}
        (self.root/"evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V3.json").write_text(json.dumps(audit,indent=2)+"\n")
    def tearDown(self): self.t.cleanup()

    def test_persists_successors_without_new_identity_attempt_and_is_idempotent(self):
        docs={cid:result(cid,self.specs[cid]) for cid in CORRECTION_IDS}
        m1=persist_same_identity_corrections(self.root,results=docs,recorded_utc="2026-09-23T09:30:00Z",authority_ref="evidence/CORR.json")
        ledger1=(self.root/"discovery/ledger.jsonl").read_bytes(); state1=(self.root/"CURRENT_STATE.json").read_bytes()
        s=json.loads(state1)
        self.assertEqual(s["v2_attempts_used"],4); self.assertEqual(s["v2_search_budget_remaining"],80)
        self.assertEqual(s["v2_evaluated_identities"],4); self.assertEqual(s["distinct_identity_outcomes_opened"],4)
        self.assertEqual(s["stage_a_result_recorded_entries"],8); self.assertEqual(s["economic_outcomes_opened"],10)
        self.assertEqual(s["pending_same_identity_correction_candidate_ids"],[])
        self.assertEqual(set(s["current_live_equivalent_authoritative_candidate_ids"]),set(CORRECTION_IDS))
        rows=read_ledger(self.root/"discovery/ledger.jsonl")
        self.assertEqual(sum(r["entry_type"]=="IMPLEMENTATION_CORRECTION" and r.get("payload",{}).get("correction_id")==CORRECTION_ID for r in rows),4)
        self.assertEqual(sum(r["entry_type"]=="RESULT_RECORDED" and r.get("payload",{}).get("correction_id")==CORRECTION_ID for r in rows),4)
        for cid in CORRECTION_IDS: self.assertTrue((self.root/RESULT_REFS[cid]).exists())
        m2=persist_same_identity_corrections(self.root,results=docs,recorded_utc="2026-09-23T09:30:00Z",authority_ref="evidence/CORR.json")
        self.assertEqual((self.root/"discovery/ledger.jsonl").read_bytes(),ledger1)
        self.assertEqual((self.root/"CURRENT_STATE.json").read_bytes(),state1)
        self.assertEqual(m2["final"]["appended"],{})

    def test_conflicting_successor_fails_closed(self):
        docs={cid:result(cid,self.specs[cid]) for cid in CORRECTION_IDS}
        persist_same_identity_corrections(self.root,results=docs,recorded_utc="2026-09-23T09:30:00Z",authority_ref="evidence/CORR.json")
        bad=json.loads(json.dumps(docs["V2-C006"])); bad["implementation_validity"]["reason"]="changed"; bad.pop("result_hash"); bad["result_hash"]=compute_result_hash(bad)
        with self.assertRaises(SameIdentityPersistenceError):
            persist_same_identity_corrections(self.root,results={"V2-C006":bad},recorded_utc="2026-09-23T09:30:00Z",authority_ref="evidence/CORR.json")

if __name__=="__main__": unittest.main(verbosity=2)
