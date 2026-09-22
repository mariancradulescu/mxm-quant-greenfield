"""Minimal restartable control plane for Performance Research V3."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger

CIDS=("V2-C013","V2-C014","V2-C015","V2-C016")
HASHES={"V2-C013":"cd91f3b0008fef672fd5722ed44db23046fb516ad174b60205a55cd0c54cfea1","V2-C014":"7bb7a21f40dd742357f4800f7762314724b73609c34c2de04b10329df2221e6d","V2-C015":"aa067cc4aa807731ec3a0caa9029b574eeae43e068e241790d994d55a1f8ff64","V2-C016":"fdd6286d1a8fdbbe53610af45c91e3f949bb75805b7cc7ab790b997c77458783"}
RUNNER_REF="m7/competition_expansion_index_m15.py"
RUNNER_BLOB="61e7834aafd54514b4fd1791d66b0fb88acda0b7"

def _load(root, rel):
    return json.loads((Path(root)/rel).read_text(encoding="utf-8"))

def git_blob_sha1(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def validate_bootstrap(root="."):
    root=Path(root)
    contract=_load(root,"research_v3/RESEARCH_CONTRACT_V3.json")
    inv=_load(root,"research_v3/UNOPENED_READINESS_V1.json")
    gate=_load(root,"research_v3/WAVE_01_PRE_OUTCOME_GATE_V1.json")
    auth=_load(root,"research_v3/WAVE_01_EXECUTION_AUTHORIZATION_V1.json")
    state=_load(root,"CURRENT_STATE.json")
    if contract.get("status")!="FROZEN_PRE_V3_ECONOMIC_OUTCOME": raise ValueError("V3 contract not frozen")
    if gate.get("candidate_ids")!=list(CIDS): raise ValueError("V3 Wave01 candidate set drift")
    if gate.get("candidate_spec_hashes")!=HASHES: raise ValueError("V3 Wave01 candidate hash drift")
    if git_blob_sha1(root/RUNNER_REF)!=RUNNER_BLOB: raise ValueError("V3 economic runner drift")
    ledger=read_ledger(root/"discovery/ledger.jsonl")
    for cid in CIDS:
        spec=_load(root,f"discovery/candidates/{cid}.json"); verify_spec_hash(spec)
        if spec.get("spec_hash")!=HASHES[cid]: raise ValueError(f"{cid} spec drift")
        rows=[x for x in ledger if x.get("candidate_id")==cid]
        if [x.get("entry_type") for x in rows]!=["CANDIDATE_FROZEN"]: raise ValueError(f"{cid} is not unopened frozen-only")
        cls=inv["classifications"][cid]["classification"]
        if cls!="READY_NOW_WITH_EXISTING_EVIDENCE": raise ValueError(f"{cid} readiness drift")
    if state.get("v2_attempts_used")!=9 or state.get("v2_search_budget_remaining")!=75: raise ValueError("V2 accounting drift")
    if state.get("protected_evidence_opened") is not False or state.get("live_orders_authorized") is not False or state.get("competition_start_authorized") is not False: raise ValueError("authorization invariant drift")
    if auth.get("status") not in {"PENDING_EXACT_HEAD_GREEN","AUTHORIZED_AFTER_EXACT_HEAD_GREEN"}: raise ValueError("invalid V3 authorization state")
    return {"candidate_ids":list(CIDS),"v2_attempts_used":9,"v2_search_budget_remaining":75,"economic_outcomes_opened":False}

def project_post_batch_state(state, results):
    out=json.loads(json.dumps(state))
    statuses={cid:results[cid]["status"] for cid in CIDS}
    out["phase"]="PERFORMANCE_RESEARCH_V3_WAVE01_RESULTS_RECORDED"
    out["next_action"]="Move every V3 Wave01 Stage-A survivor promptly to CURRENT-config EUR200 realization; retain non-survivor mechanism-family information without rescue tuning."
    out["performance_research_v3"]["status"]="WAVE01_RESULTS_RECORDED"
    out["performance_research_v3"]["wave01_result_statuses"]=statuses
    return out
