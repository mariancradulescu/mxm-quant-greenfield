"""Candidate-by-candidate frozen-semantics forensic classifier."""
from __future__ import annotations
import json
from pathlib import Path
from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.ledger import derive_active_spec_hashes, read_ledger
from discovery.schema import validate_result

IMPLEMENTATION_ONLY=["V2-C006","V2-C012","V2-C023","V2-C025"]
SPEC_INVALID=["V2-C013","V2-C014","V2-C015","V2-C016","V2-C017","V2-C018","V2-C019","V2-C020","V2-C021","V2-C022","V2-C024","V2-C026"]
ALL=sorted(IMPLEMENTATION_ONLY+SPEC_INVALID)
RESULT_REFS={"V2-C006":"discovery/results/V2-C006_STAGE_A_V1.json","V2-C012":"discovery/results/V2-C012_STAGE_A_V2.json","V2-C013":"discovery/results/V2-C013_STAGE_A_COMPETITION_EXPANSION_V1.json","V2-C014":"discovery/results/V2-C014_STAGE_A_COMPETITION_EXPANSION_V1.json","V2-C015":"discovery/results/V2-C015_STAGE_A_COMPETITION_EXPANSION_V1.json","V2-C016":"discovery/results/V2-C016_STAGE_A_COMPETITION_EXPANSION_V1.json","V2-C017":"discovery/results/V2-C017_STAGE_A_V1.json","V2-C018":"discovery/results/V2-C018_STAGE_A_V1.json","V2-C019":"discovery/results/V2-C019_STAGE_A_V1.json","V2-C020":"discovery/results/V2-C020_STAGE_A_V1.json","V2-C021":"discovery/results/V2-C021_STAGE_A_V1.json","V2-C022":"discovery/results/V2-C022_STAGE_A_V1.json","V2-C023":"discovery/results/V2-C023_STAGE_A_V1.json","V2-C024":"discovery/results/V2-C024_STAGE_A_V1.json","V2-C025":"discovery/results/V2-C025_STAGE_A_V1.json","V2-C026":"discovery/results/V2-C026_STAGE_A_V1.json"}

def load(root, rel): return json.loads((Path(root)/rel).read_text(encoding="utf-8"))
def require_contains(seq,value,cid):
    if value not in seq: raise ValueError(f"{cid}: missing frozen semantic {value}")

def classify_spec(spec):
    cid=spec["id"]
    if spec.get("causal_availability",{}).get("future_information_forbidden") is not True:
        raise ValueError(f"{cid}: future-information prohibition missing")
    if cid in ("V2-C006","V2-C012"):
        if spec["exit"].get("fixed_hold_intent")!="SCHEDULED_AT_ENTRY" or spec["execution_assumptions"].get("missing_bars")!="do_not_fabricate":
            raise ValueError(f"{cid}: causal fixed-hold semantic drift")
        return "IMPLEMENTATION_ONLY_SAME_SEMANTICS_CORRECTABLE"
    if cid in ("V2-C013","V2-C014","V2-C015"):
        require_contains(spec.get("filters",[]),"SESSION_MUST_HAVE_COMPLETE_OFFICIAL_M15_GRID",cid)
        return "FROZEN_SPEC_CAUSALLY_INVALID_REQUIRES_NEW_IDENTITY"
    if cid=="V2-C016":
        require_contains(spec.get("filters",[]),"BOTH_INDEX_SESSIONS_MUST_HAVE_COMPLETE_OFFICIAL_M15_GRID",cid)
        return "FROZEN_SPEC_CAUSALLY_INVALID_REQUIRES_NEW_IDENTITY"
    if cid in ("V2-C017","V2-C018","V2-C019","V2-C020","V2-C021","V2-C022"):
        ex=spec["execution_assumptions"]
        if ex.get("entry_exit_grid")!="REQUIRE_EXACT_CONTIGUOUS_5_MINUTE_OBSERVED_BARS_FOR_LOOKBACK_ENTRY_AND_HOLD" or ex.get("missing_required_grid")!="NO_SIGNAL":
            raise ValueError(f"{cid}: frozen grid semantic drift")
        return "FROZEN_SPEC_CAUSALLY_INVALID_REQUIRES_NEW_IDENTITY"
    if cid=="V2-C023":
        if spec["exit"].get("missing_at_intent")!="keep exit intent pending until first later observed M5 open":
            raise ValueError("C023 pending-exit semantic drift")
        if spec["execution_assumptions"].get("missing_required_grid")!="SYMBOL_INELIGIBLE_ONLY_WHEN_SIGNAL_HISTORY_OR_BOUNDARY_ENTRY_OPEN_IS_UNAVAILABLE":
            raise ValueError("C023 entry-eligibility semantic drift")
        return "IMPLEMENTATION_ONLY_SAME_SEMANTICS_CORRECTABLE"
    if cid=="V2-C024":
        require_contains(spec.get("filters",[]),"CONTIGUOUS_SELECTED_SYMBOL_ENTRY_TO_EXIT_GRID_REQUIRED",cid)
        return "FROZEN_SPEC_CAUSALLY_INVALID_REQUIRES_NEW_IDENTITY"
    if cid=="V2-C025":
        if spec["normalization_training"].get("purge_embargo")!="EXAMPLES_ADMITTED_ONLY_AFTER_THEIR_TARGET_EXIT_COMPLETES":
            raise ValueError("C025 training semantic drift")
        return "IMPLEMENTATION_ONLY_SAME_SEMANTICS_CORRECTABLE"
    if cid=="V2-C026":
        if spec["exit"].get("missing_exact_exit_boundary")!="NO_TRADE_FOR_THAT_SEGMENT" or spec["position_admission_policy"].get("missing_exit_boundary")!="NO_TRADE_AT_ENTRY_BOUNDARY" or "exit_boundary_missing" not in spec["direction"].get("NO_OP",""):
            raise ValueError("C026 frozen future-exit semantic drift")
        return "FROZEN_SPEC_CAUSALLY_INVALID_REQUIRES_NEW_IDENTITY"
    raise ValueError(f"unsupported identity {cid}")

def build_audit(root):
    root=Path(root); state=load(root,"CURRENT_STATE.json"); ledger=read_ledger(root/"discovery/ledger.jsonl")
    active=derive_active_spec_hashes(ledger); result_rows=[e for e in ledger if e.get("entry_type")=="RESULT_RECORDED"]
    historical=sorted({e["candidate_id"] for e in result_rows})
    if historical!=ALL: raise ValueError(f"historical set mismatch {historical}")
    classes={}
    for cid in ALL:
        spec=load(root,f"discovery/candidates/{cid}.json"); verify_spec_hash(spec)
        if active.get(cid)!=spec["spec_hash"]: raise ValueError(f"{cid}: active hash mismatch")
        classes[cid]=classify_spec(spec)
        result=load(root,RESULT_REFS[cid]); validate_result(result)
        if result["candidate_id"]!=cid or result["spec_hash"]!=spec["spec_hash"] or result["result_hash"]!=compute_result_hash(result):
            raise ValueError(f"{cid}: result identity/hash mismatch")
        rows=[e for e in result_rows if e["candidate_id"]==cid]
        if not any(e.get("payload",{}).get("result_hash")==result["result_hash"] and e.get("payload",{}).get("result")==result for e in rows):
            raise ValueError(f"{cid}: result/ledger mismatch")
    charged=sorted(cid for cid,c in classes.items() if c=="IMPLEMENTATION_ONLY_SAME_SEMANTICS_CORRECTABLE")
    released=sorted(cid for cid,c in classes.items() if c=="FROZEN_SPEC_CAUSALLY_INVALID_REQUIRES_NEW_IDENTITY")
    return {"status":"COMPLETE_PER_IDENTITY_CLASSIFICATION","candidate_ids":ALL,"classifications":classes,
      "groups":{"implementation_only_same_semantics_correctable":charged,"frozen_spec_causally_invalid_requires_new_identity":released,"valid_with_post_entry_settlement_or_right_censoring":[],"unresolved_requires_targeted_proof":[]},
      "attempt_accounting":{"v2_budget_total":int(state["v2_search_budget"]),"historical_evaluated_candidate_ids":ALL,"historical_evaluated_identity_count":len(ALL),"budget_charged_candidate_ids":charged,"v2_attempts_used":len(charged),"v2_search_budget_remaining":int(state["v2_search_budget"])-len(charged),"released_invalid_spec_candidate_ids":released,"released_invalid_spec_slot_count":len(released),"same_identity_zero_delta_correction_ids":charged,"global_attempts_seen_for_information_exposure":int(state["legacy_prior_attempts"])+len(ALL),"economic_outcomes_opened_historical":int(state["economic_outcomes_opened"]),"historical_bytes_deleted":False},
      "safety":{"protected_evidence_opened":bool(state["protected_evidence_opened"]),"live_orders_authorized":bool(state["live_orders_authorized"]),"competition_start_authorized":bool(state["competition_start_authorized"])}}
