"""Automated consumed-identity integrity audit for MXM Quant Greenfield V2/V3."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.ledger import derive_active_spec_hashes, read_ledger
from discovery.schema import validate_result

IDS=["V2-C006","V2-C012","V2-C013","V2-C014","V2-C015","V2-C016","V2-C017","V2-C018","V2-C019","V2-C020","V2-C021","V2-C022","V2-C023","V2-C024","V2-C025","V2-C026"]
RESULT_REFS={"V2-C006":"discovery/results/V2-C006_STAGE_A_V1.json","V2-C012":"discovery/results/V2-C012_STAGE_A_V2.json","V2-C013":"discovery/results/V2-C013_STAGE_A_COMPETITION_EXPANSION_V1.json","V2-C014":"discovery/results/V2-C014_STAGE_A_COMPETITION_EXPANSION_V1.json","V2-C015":"discovery/results/V2-C015_STAGE_A_COMPETITION_EXPANSION_V1.json","V2-C016":"discovery/results/V2-C016_STAGE_A_COMPETITION_EXPANSION_V1.json","V2-C017":"discovery/results/V2-C017_STAGE_A_V1.json","V2-C018":"discovery/results/V2-C018_STAGE_A_V1.json","V2-C019":"discovery/results/V2-C019_STAGE_A_V1.json","V2-C020":"discovery/results/V2-C020_STAGE_A_V1.json","V2-C021":"discovery/results/V2-C021_STAGE_A_V1.json","V2-C022":"discovery/results/V2-C022_STAGE_A_V1.json","V2-C023":"discovery/results/V2-C023_STAGE_A_V1.json","V2-C024":"discovery/results/V2-C024_STAGE_A_V1.json","V2-C025":"discovery/results/V2-C025_STAGE_A_V1.json","V2-C026":"discovery/results/V2-C026_STAGE_A_V1.json"}
EVALUATOR_SOURCE={
    "V2-C006":"m6/stage_a_evaluator.py","V2-C012":"m6/stage_a_evaluator.py",
    "V2-C013":"m7/competition_expansion_index_m15.py","V2-C014":"m7/competition_expansion_index_m15.py",
    "V2-C015":"m7/competition_expansion_index_m15.py","V2-C016":"m7/competition_expansion_index_m15.py",
    "V2-C017":"m7/competition_ultra_fast_stage_a_evaluator.py","V2-C018":"m7/competition_ultra_fast_stage_a_evaluator.py",
    "V2-C019":"m7/competition_ultra_fast_stage_a_evaluator.py","V2-C020":"m7/competition_ultra_fast_stage_a_evaluator.py",
    "V2-C021":"m7/competition_ultra_fast_stage_a_evaluator.py","V2-C022":"m7/competition_ultra_fast_stage_a_evaluator.py",
    "V2-C023":"m7/competition_ultra_fast_stage_a_frontier_v2_evaluator.py",
    "V2-C024":"m7/competition_performance_v3_wave02_evaluator.py","V2-C025":"m7/competition_performance_v3_wave02_evaluator.py",
    "V2-C026":"m7/competition_performance_v3_wave03_c026_evaluator.py",
}
REPLAY_SOURCE={
    "V2-C006":"m6/tier1_candidate_replay.py","V2-C012":"m6/tier1_candidate_replay.py",
    "V2-C013":"m7/competition_expansion_index_m15.py","V2-C014":"m7/competition_expansion_index_m15.py",
    "V2-C015":"m7/competition_expansion_index_m15.py","V2-C016":"m7/competition_expansion_index_m15.py",
    "V2-C017":"m7/competition_ultra_fast_stage_a_evaluator.py","V2-C018":"m7/competition_ultra_fast_stage_a_evaluator.py",
    "V2-C019":"m7/competition_ultra_fast_stage_a_evaluator.py","V2-C020":"m7/competition_ultra_fast_stage_a_evaluator.py",
    "V2-C021":"m7/competition_ultra_fast_stage_a_evaluator.py","V2-C022":"m7/competition_ultra_fast_stage_a_evaluator.py",
    "V2-C023":"m7/competition_ultra_fast_stage_a_frontier_v2_evaluator.py",
    "V2-C024":"m7/competition_performance_v3_wave02_evaluator.py","V2-C025":"m7/competition_performance_v3_wave02_evaluator.py",
    "V2-C026":"m7/competition_performance_v3_wave03_c026_evaluator.py",
}
DEFECT_MARKERS={
    "V2-C006":["if len(executable) < 12:","exit_bar = executable[11]"],
    "V2-C012":["if exit_index>=len(pairs):","exit_lagger=pairs[exit_index][1]"],
    "V2-C013":["if exit_i >= len(bars):","exit_price=float(bars[exit_i][\"close\"])"],
    "V2-C014":["if exit_i >= len(bars):","exit_price=float(bars[exit_i][\"close\"])"],
    "V2-C015":["if exit_i >= len(bars):","exit_price=float(bars[exit_i][\"close\"])"],
    "V2-C016":["if exit_i >= len(opens):","exit_price=float(nb[exit_i][\"close\"])"],
    "V2-C017":["if not cont(q,i-look,xi):","out.append(trade(cid"],
    "V2-C018":["if not cont(q,i-look,xi):","out.append(trade(cid"],
    "V2-C019":["if not cont(q,i-look,xi):","out.append(trade(cid"],
    "V2-C020":["if not cont(q,i-look,xi):","out.append(trade(cid"],
    "V2-C021":["range(i-12,xi)","out.append(trade(cid"],
    "V2-C022":["range(i-12,xi)","out.append(trade(cid"],
    "V2-C023":["if j<len(q) and q[j][\"t\"]<E:","trades.append"],
    "V2-C024":["if i+12 >= len(q) or not contiguous(q,i,i+12):","eligible.append"],
    "V2-C025":["if not contiguous(rows,i,xi): continue","out.append"],
    "V2-C026":["xr = by_time.get(x)","if xr is None or x > END:"],
}
PRIMARY_DATA_SHA="88c68f1724eba71ef58fe02a929c935dc1cbf4be432897db599be7b37fd4ae72"
V6_DATA_SHA="dd0736c3156abfa057303a9b2a31ef3db36b02d66afc5fa33ddccc7f416f5d3d"
V6_COST_SHA="b7ca6191b5570c1cc22f644feb6b0124c6bec0f00fc5ad5a8c772419bcb481b9"

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def git_blob_sha1(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def contains_value(value, target):
    if value == target:
        return True
    if isinstance(value, dict):
        return any(contains_value(v,target) for v in value.values())
    if isinstance(value, list):
        return any(contains_value(v,target) for v in value)
    return False

def build_audit(root):
    root=Path(root)
    state=json.loads((root/"CURRENT_STATE.json").read_text(encoding="utf-8"))
    ledger=read_ledger(root/"discovery/ledger.jsonl")
    active=derive_active_spec_hashes(ledger)
    result_rows=[e for e in ledger if e.get("entry_type")=="RESULT_RECORDED"]
    consumed=sorted({e["candidate_id"] for e in result_rows})
    if consumed != sorted(IDS):
        raise ValueError(f"consumed identity set mismatch: {consumed}")
    if state["v2_attempts_used"] != len(consumed):
        raise ValueError("v2_attempts_used does not equal distinct consumed identity count")
    if state["v2_search_budget_remaining"] != state["v2_search_budget"]-state["v2_attempts_used"]:
        raise ValueError("search budget accounting mismatch")
    if state["discovery_result_recorded_entries"] != len(result_rows):
        raise ValueError("ledger result count projection mismatch")

    v6_accept=json.loads((root/"data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json").read_text())
    v6_cost_path=root/"evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json"
    if v6_accept["source"]["zip_sha256"] != V6_DATA_SHA or sha256_file(v6_cost_path) != V6_COST_SHA:
        raise ValueError("V6 data/cost authority binding mismatch")

    findings={}
    for cid in IDS:
        spec=json.loads((root/f"discovery/candidates/{cid}.json").read_text())
        verify_spec_hash(spec)
        if active.get(cid) != spec["spec_hash"]:
            raise ValueError(f"{cid} active spec hash mismatch")
        rows=[e for e in result_rows if e["candidate_id"]==cid]
        if cid=="V2-C012":
            if len(rows)!=2:
                raise ValueError("C012 must preserve original and corrected RESULT_RECORDED rows")
        elif len(rows)!=1:
            raise ValueError(f"{cid} must have exactly one RESULT_RECORDED row")

        freezes=[e for e in ledger if e.get("candidate_id")==cid and e.get("entry_type") in ("CANDIDATE_FROZEN","CANDIDATE_REFROZEN_PRE_OUTCOME")]
        if not freezes or min(e["sequence"] for e in rows) <= max(e["sequence"] for e in freezes):
            raise ValueError(f"{cid} freeze did not precede own result")

        result=json.loads((root/RESULT_REFS[cid]).read_text(encoding="utf-8"))
        validate_result(result)
        if result["candidate_id"]!=cid or result["spec_hash"]!=spec["spec_hash"]:
            raise ValueError(f"{cid} result identity mismatch")
        if result["result_hash"] != compute_result_hash(result):
            raise ValueError(f"{cid} standalone result hash mismatch")
        if not any(e["payload"].get("result_hash")==result["result_hash"] and e["payload"].get("result")==result for e in rows):
            raise ValueError(f"{cid} authoritative result does not roundtrip through ledger")

        evaluator_path=root/EVALUATOR_SOURCE[cid]
        if sha256_file(evaluator_path) != result["provenance"]["evaluator"]["sha256"]:
            raise ValueError(f"{cid} evaluator SHA binding mismatch")
        data_sha=result["provenance"]["data_evidence"]["binding"]["sha256"]
        if data_sha==V6_DATA_SHA:
            data_trace=True
        elif data_sha==PRIMARY_DATA_SHA:
            data_trace=state["m6"]["raw_materialization"]["reconciled_capture_bundle_sha256"]==PRIMARY_DATA_SHA
        else:
            data_trace=contains_value(state,data_sha)
        if not data_trace:
            raise ValueError(f"{cid} dataset binding is not traceable")

        cost_sha=result["provenance"]["cost_evidence"]["sha256"]
        if cost_sha == V6_COST_SHA:
            cost_trace = True
        else:
            # Tier-1 cost identities are derived evidence commitments. They are
            # authoritative through the frozen pre-economic materialization and
            # transaction-local cost-rule authorities; they need not be copied
            # redundantly into mutable CURRENT_STATE.
            tier1_materialization = json.loads(
                (root/"evidence/M6_STAGE_A_TIER1_PRE_ECONOMIC_MATERIALIZATION_V1.json").read_text(encoding="utf-8")
            )
            tier1_cost_rule = json.loads(
                (root/"evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json").read_text(encoding="utf-8")
            )
            cost_trace = (
                contains_value(tier1_materialization, cost_sha)
                and contains_value(tier1_cost_rule, cost_sha)
            )
        if not cost_trace:
            raise ValueError(f"{cid} cost binding is not traceable")

        replay_text=(root/REPLAY_SOURCE[cid]).read_text(encoding="utf-8")
        missing=[m for m in DEFECT_MARKERS[cid] if m not in replay_text]
        if missing:
            raise ValueError(f"{cid} forensic defect marker drift: {missing}")

        if spec.get("causal_availability",{}).get("future_information_forbidden") is not True:
            raise ValueError(f"{cid} does not prospectively forbid future information")
        if spec.get("normalization_training",{}).get("random_temporal_shuffle") is True:
            raise ValueError(f"{cid} permits random temporal shuffle")

        findings[cid]={
            "classification":"IMPLEMENTATION_INVALID_SAME_SEMANTICS_CORRECTABLE",
            "candidate_spec_hash":spec["spec_hash"],
            "mechanism_family":spec["mechanism"]["family"],
            "authoritative_result_ref":RESULT_REFS[cid],
            "authoritative_result_hash":result["result_hash"],
            "historical_status":result["status"],
            "evaluator_source":EVALUATOR_SOURCE[cid],
            "evaluator_sha256":result["provenance"]["evaluator"]["sha256"],
            "replay_source":REPLAY_SOURCE[cid],
            "data_binding_sha256":data_sha,
            "cost_binding_sha256":cost_sha,
            "identity_and_persistence_checks":"PASS",
            "other_semantic_dimensions":"TRACEABLE_BUT_REVALIDATION_REQUIRED_WITH_CORRECTED_LIVE_EQUIVALENT_REPLAY",
            "material_defect":"FUTURE_EXIT_AVAILABILITY_OR_FUTURE_SESSION_COMPLETENESS_IS_QUERIED_BEFORE_HISTORICAL_ENTRY_ADMISSION",
            "same_identity_correction_attempt_delta":0,
        }

    return {
        "schema":"mxm.greenfield.v2.consumed-identity-forensic-audit.v2",
        "status":"COMPLETE_LIVE_EQUIVALENT_CORRECTIONS_REQUIRED",
        "supersedes_for_current_replay_validity":"evidence/V2_CONSUMED_IDENTITY_FORENSIC_AUDIT_V1.json",
        "live_equivalent_contract_ref":"research_v3/LIVE_EQUIVALENT_HISTORICAL_REPLAY_CONTRACT_V1.json",
        "distinct_consumed_identities":len(consumed),
        "result_recorded_entries":len(result_rows),
        "candidate_ids":IDS,
        "classifications":{cid:findings[cid]["classification"] for cid in IDS},
        "findings":findings,
        "c012_history":{
            "prior_normalization_defect_preserved":True,
            "corrected_successor_ref":"discovery/results/V2-C012_STAGE_A_V2.json",
            "new_live_equivalent_defect_is_independent_of_prior_rolling_window_fix":True,
        },
        "projection_drift":{
            "historical_result_candidates_missing_from_current_result_authority_before_v2_audit":["V2-C017","V2-C018","V2-C019","V2-C020","V2-C021","V2-C022","V2-C023"],
            "classification":"PERSISTENCE_ONLY_DEFECT",
            "additional_attempts_consumed":0,
        },
        "attempt_accounting":{
            "v2_budget_total":state["v2_search_budget"],
            "v2_attempts_used":state["v2_attempts_used"],
            "v2_search_budget_remaining":state["v2_search_budget_remaining"],
            "action":"KEEP_ONE_SLOT_PER_DISTINCT_IDENTITY; SAME_IDENTITY_CORRECTION_CONSUMES_ZERO_ADDITIONAL_ATTEMPTS",
        },
        "correction_rule":{
            "do_not_change_candidate_spec_hash":True,
            "do_not_rescue_tune":True,
            "do_not_use_protected_evidence":True,
            "admission_must_not_query_future_exit_bar_existence_or_price":True,
            "post_entry_missing_target_data_must_be_handled_as_SETTLEMENT_OR_DATA_VALIDITY_NOT_RETROACTIVE_NO_TRADE":True,
        },
        "safety":{
            "protected_evidence_opened":state["protected_evidence_opened"],
            "live_orders_authorized":state["live_orders_authorized"],
            "competition_start_authorized":state["competition_start_authorized"],
        },
    }

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",default=".")
    parser.add_argument("--write")
    args=parser.parse_args()
    audit=build_audit(args.root)
    text=json.dumps(audit,sort_keys=True,indent=2,ensure_ascii=False)+"\n"
    if args.write:
        Path(args.write).write_text(text,encoding="utf-8")
    else:
        print(text,end="")

if __name__=="__main__":
    main()
