"""Restartable control plane for Performance Research V3, valid before and after Wave01 persistence."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.ledger import read_ledger
from discovery.schema import validate_result

CIDS=("V2-C013","V2-C014","V2-C015","V2-C016")
HASHES={"V2-C013":"cd91f3b0008fef672fd5722ed44db23046fb516ad174b60205a55cd0c54cfea1","V2-C014":"7bb7a21f40dd742357f4800f7762314724b73609c34c2de04b10329df2221e6d","V2-C015":"aa067cc4aa807731ec3a0caa9029b574eeae43e068e241790d994d55a1f8ff64","V2-C016":"fdd6286d1a8fdbbe53610af45c91e3f949bb75805b7cc7ab790b997c77458783"}
RESULT_REFS={
    "V2-C013":"discovery/results/V2-C013_STAGE_A_COMPETITION_EXPANSION_V1.json",
    "V2-C014":"discovery/results/V2-C014_STAGE_A_COMPETITION_EXPANSION_V1.json",
    "V2-C015":"discovery/results/V2-C015_STAGE_A_COMPETITION_EXPANSION_V1.json",
    "V2-C016":"discovery/results/V2-C016_STAGE_A_COMPETITION_EXPANSION_V1.json",
}
RUNNER_REF="m7/competition_expansion_index_m15.py"
RUNNER_BLOB="61e7834aafd54514b4fd1791d66b0fb88acda0b7"

def _load(root, rel):
    return json.loads((Path(root)/rel).read_text(encoding="utf-8"))

def git_blob_sha1(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def _common(root):
    root=Path(root)
    contract=_load(root,"research_v3/RESEARCH_CONTRACT_V3.json")
    inv=_load(root,"research_v3/UNOPENED_READINESS_V1.json")
    gate=_load(root,"research_v3/WAVE_01_PRE_OUTCOME_GATE_V1.json")
    auth=_load(root,"research_v3/WAVE_01_EXECUTION_AUTHORIZATION_V1.json")
    state=_load(root,"CURRENT_STATE.json")
    if contract.get("status")!="FROZEN_PRE_V3_ECONOMIC_OUTCOME": raise ValueError("V3 contract not frozen")
    if gate.get("candidate_ids")!=list(CIDS) or gate.get("candidate_spec_hashes")!=HASHES: raise ValueError("V3 Wave01 frozen identity drift")
    if git_blob_sha1(root/RUNNER_REF)!=RUNNER_BLOB: raise ValueError("V3 economic runner drift")
    for cid in CIDS:
        spec=_load(root,f"discovery/candidates/{cid}.json"); verify_spec_hash(spec)
        if spec.get("spec_hash")!=HASHES[cid]: raise ValueError(f"{cid} spec drift")
        if inv["classifications"][cid]["classification"]!="READY_NOW_WITH_EXISTING_EVIDENCE": raise ValueError(f"{cid} readiness drift")
    if state.get("protected_evidence_opened") is not False or state.get("live_orders_authorized") is not False or state.get("competition_start_authorized") is not False: raise ValueError("authorization invariant drift")
    if auth.get("status") not in {"PENDING_EXACT_HEAD_GREEN","AUTHORIZED_AFTER_EXACT_HEAD_GREEN"}: raise ValueError("invalid V3 authorization state")
    return root,state,read_ledger(root/"discovery/ledger.jsonl")

def validate_bootstrap(root="."):
    root,state,ledger=_common(root)
    row_types={cid:[x.get("entry_type") for x in ledger if x.get("candidate_id")==cid] for cid in CIDS}
    frozen_only=all(row_types[cid]==["CANDIDATE_FROZEN"] for cid in CIDS)
    recorded=all(row_types[cid]==["CANDIDATE_FROZEN","RESULT_RECORDED"] for cid in CIDS)
    if frozen_only:
        if state.get("v2_attempts_used")!=9 or state.get("v2_search_budget_remaining")!=75: raise ValueError("pre-outcome V2 accounting drift")
        if state.get("performance_research_v3",{}).get("candidate_own_outcomes_opened") is not False: raise ValueError("pre-outcome state incorrectly marked opened")
        return {"candidate_ids":list(CIDS),"v2_attempts_used":9,"v2_search_budget_remaining":75,"economic_outcomes_opened":False}
    if not recorded:
        raise ValueError(f"partial or duplicate V3 Wave01 persistence: {row_types}")
    hashes={}; statuses={}
    for cid in CIDS:
        result=_load(root,RESULT_REFS[cid]); validate_result(result)
        if result.get("candidate_id")!=cid or result.get("spec_hash")!=HASHES[cid]: raise ValueError(f"{cid} standalone result identity drift")
        if result.get("result_hash")!=compute_result_hash(result): raise ValueError(f"{cid} standalone result_hash mismatch")
        rows=[x for x in ledger if x.get("candidate_id")==cid]
        rec=rows[1]
        if rec.get("payload",{}).get("result")!=result: raise ValueError(f"{cid} ledger payload differs from standalone result")
        if rec.get("payload",{}).get("result_hash")!=result["result_hash"]: raise ValueError(f"{cid} ledger result_hash mismatch")
        hashes[cid]=result["result_hash"]; statuses[cid]=result["status"]
    perf=state.get("performance_research_v3",{})
    if perf.get("candidate_own_outcomes_opened") is not True: raise ValueError("post-outcome state not marked opened")
    if perf.get("v2_attempts_used_after_wave01")!=13 or perf.get("v2_search_budget_remaining_after_wave01")!=71: raise ValueError("Wave01 historical accounting projection drift")
    if perf.get("wave01_result_hashes")!=hashes or perf.get("wave01_result_statuses")!=statuses: raise ValueError("Wave01 result projection drift")
    if state.get("v2_attempts_used",0)<13 or state.get("v2_search_budget_remaining",84)>71: raise ValueError("current accounting regressed behind persisted Wave01")
    return {"candidate_ids":list(CIDS),"v2_attempts_used":state["v2_attempts_used"],"v2_search_budget_remaining":state["v2_search_budget_remaining"],"economic_outcomes_opened":True,"result_statuses":statuses,"result_hashes":hashes}

def project_post_batch_state(state, results):
    out=json.loads(json.dumps(state))
    statuses={cid:results[cid]["status"] for cid in CIDS}
    hashes={cid:results[cid]["result_hash"] for cid in CIDS}
    perf=out.setdefault("performance_research_v3",{})

    # Historical/current separation: once Wave01 is already persisted, this
    # projector is validation-only. Later Wave02/Wave03 lifecycle growth must
    # remain untouched rather than being projected back onto the Wave01 snapshot.
    if perf.get("candidate_own_outcomes_opened") is True:
        if perf.get("v2_attempts_used_after_wave01")!=13 or perf.get("v2_search_budget_remaining_after_wave01")!=71:
            raise ValueError("Wave01 historical accounting projection drift")
        if perf.get("wave01_result_statuses")!=statuses or perf.get("wave01_result_hashes")!=hashes:
            raise ValueError("Wave01 historical result projection drift")
        if out.get("v2_attempts_used",0)<13 or out.get("v2_search_budget_remaining",84)>71:
            raise ValueError("current accounting regressed behind persisted Wave01")
        return out

    if out.get("v2_attempts_used")!=9 or out.get("v2_search_budget_remaining")!=75:
        raise ValueError("cannot project Wave01 from non-preoutcome accounting")
    out["v2_attempts_used"]=13
    out["v2_search_budget_remaining"]=71
    out["v2_evaluated_identities"]=int(out.get("v2_evaluated_identities",9))+4
    out["global_attempts_seen"]=int(out.get("legacy_prior_attempts",16))+13
    out["economic_outcomes_opened"]=int(out.get("economic_outcomes_opened",12))+4
    out["discovery_ledger_entries"]=int(out.get("discovery_ledger_entries",42))+4
    out["discovery_result_recorded_entries"]=int(out.get("discovery_result_recorded_entries",10))+4
    perf["candidate_own_outcomes_opened"]=True
    perf["v2_attempts_used_after_wave01"]=13
    perf["v2_search_budget_remaining_after_wave01"]=71
    perf["wave01_result_statuses"]=statuses
    perf["wave01_result_hashes"]=hashes
    out["phase"]="PERFORMANCE_RESEARCH_V3_WAVE01_RESULTS_RECORDED"
    out["next_action"]="Continue prospective performance discovery from the persisted Wave01 evidence without rescue tuning."
    return out
