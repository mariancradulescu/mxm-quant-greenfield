"""Durable research-evidence epoch and stale-General-AI guard.

General AI owns research judgment. Runtime V2 may execute already-authorized mechanical
work, but a newer material evidence epoch invalidates an older authorization for any
new mechanism/panel/universe/horizon research judgment.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Mapping, Iterable
from research_v3.runtime_v2_primitives import atomic_write_json, canonical_bytes, sha256_bytes, sha256_file

EPOCH_REL=Path("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json")
NEXT_STATE_REL=Path("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
ACTIVE_PROJECTION_REL=Path("research_v3/ACTIVE_RESEARCH_PROJECTION_V1.json")
SCHEMA="mxm.greenfield.research-evidence-epoch.v1"
MATERIAL_EVENT_CLASSES=frozenset({
    "AUTHENTICATED_MARKET_DATA_ACCEPTED",
    "MATERIAL_DEVELOPMENT_STRUCTURAL_EVIDENCE_ACCEPTED",
    "INDEPENDENT_OUTER_OUTCOME_OPENED",
    "BROKER_FRICTION_COST_MARGIN_EXECUTION_EVIDENCE_ACCEPTED",
    "HISTORICAL_VALIDITY_INTERPRETATION_CHANGED",
    "BROKER_UNIVERSE_FEASIBILITY_AUTHORITY_CHANGED",
    "MATERIAL_DATA_IMPLEMENTATION_CORRECTION",
    "MATERIAL_EVIDENCE_SUPERSESSION",
})

class EvidenceEpochError(RuntimeError):
    pass

def _load(root:Path)->dict[str,Any]:
    path=root/EPOCH_REL
    if not path.is_file():
        raise EvidenceEpochError(f"research evidence epoch missing: {EPOCH_REL}")
    doc=json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema")!=SCHEMA:
        raise EvidenceEpochError("unsupported research evidence epoch schema")
    epoch=doc.get("current_epoch")
    if not isinstance(epoch,int) or epoch<1:
        raise EvidenceEpochError("invalid current research evidence epoch")
    return doc

def _load_active_state(root:Path)->dict[str,Any]:
    path=root/NEXT_STATE_REL
    if not path.is_file():
        return {}
    doc=json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") not in (None,"mxm.greenfield.runtime-v2-next-autonomous-state.v3"):
        raise EvidenceEpochError("unsupported canonical active research state schema")
    return doc

def _state_epoch(state:Mapping[str,Any])->int|None:
    for key in ("current_research_evidence_epoch","evidence_epoch"):
        value=state.get(key)
        if isinstance(value,int) and value>=1:
            return value
    return None

def current_evidence_epoch(root_value:str|Path=".")->int:
    root=Path(root_value).resolve()
    state=_load_active_state(root)
    active=_state_epoch(state)
    if active is not None:
        return active
    return int(_load(root)["current_epoch"])

def derive_active_projection(root_value:str|Path=".")->dict[str,Any]:
    """Pure derived view of the sole mutable active research state.

    A stale projection is never authority and must never block canonical progress.
    """
    root=Path(root_value).resolve()
    state=_load_active_state(root)
    if not state:
        raise EvidenceEpochError(f"canonical active research state missing: {NEXT_STATE_REL}")
    epoch=current_evidence_epoch(root)
    result_ref=state.get("latest_material_structural_result_ref") or state.get("completed_structural_report_ref")
    if isinstance(result_ref,str) and result_ref and not (root/result_ref).is_file():
        raise EvidenceEpochError(f"canonical latest material result missing: {result_ref}")
    if state.get("ai_reasoning_required") is True or state.get("research_judgment_required") is True:
        requirement="FRESH_GENERAL_AI_RESEARCH_JUDGMENT"
        authority="CANONICAL_STATE_FRESH_REASONING"
    elif state.get("next_deterministic_operation_ref") or state.get("deterministic_next_operation"):
        requirement="DETERMINISTIC_NON_ECONOMIC_EXECUTION"
        authority="CANONICAL_STATE_DETERMINISTIC_AUTHORITY"
    elif state.get("implementation_ai_required") is True:
        requirement="GENUINE_GENERAL_AI_IMPLEMENTATION"
        authority="CANONICAL_STATE_IMPLEMENTATION_AUTHORITY"
    elif state.get("external_data_required") is True or state.get("user_action_required") is True:
        requirement="EXTERNAL_DATA_OR_USER_GATE"
        authority="CANONICAL_STATE_EXTERNAL_GATE"
    else:
        requirement="QUIESCENT_OR_MACHINE_ROUTABLE"
        authority="CANONICAL_STATE"
    safety=dict(state.get("safety") or {})
    return {
        "schema":"mxm.greenfield.active-research-projection.v1",
        "derived_from":str(NEXT_STATE_REL),
        "authority":authority,
        "evidence_epoch":epoch,
        "execution_requirement":requirement,
        "latest_accepted_material_result_ref":result_ref,
        "accepted_semantic_decision_ref":state.get("fresh_director_decision_ref"),
        "historical_frontier_ref":state.get("canonical_frontier_ref") or "research_v3/CURRENT_RESEARCH_FRONTIER_V1.json",
        "accounting":dict(state.get("accounting") or {}),
        "safety":{
            "live_orders_authorized":bool(safety.get("live_orders_authorized") or state.get("live_orders_authorized")),
            "protected_forward_opened":bool(safety.get("protected_forward_opened") or safety.get("protected_evidence_opened") or state.get("protected_forward_opened") or state.get("protected_evidence_opened")),
        },
    }

def refresh_derived_views(root_value:str|Path=".")->dict[str,Any]:
    root=Path(root_value).resolve()
    projection=derive_active_projection(root)
    atomic_write_json(root/ACTIVE_PROJECTION_REL,projection)
    return projection

def _unique_refs(values:Iterable[Any])->list[str]:
    out=[]; seen=set()
    for raw in values:
        rel=str(raw)
        if rel and rel not in seen:
            seen.add(rel); out.append(rel)
    return out

def current_evidence_binding(root_value:str|Path=".")->dict[str,Any]:
    root=Path(root_value).resolve(); doc=_load(root); state=_load_active_state(root)
    active_epoch=current_evidence_epoch(root)
    state_material_refs=list(state.get("material_authority_refs") or [])
    refs=_unique_refs(list(doc.get("authoritative_evidence_refs") or []) + state_material_refs + [
        rel for rel in (state.get("latest_material_structural_result_ref"),state.get("completed_structural_report_ref"))
        if isinstance(rel,str) and rel
    ])
    rows=[]
    for rel in refs:
        path=root/rel
        if not path.is_file():
            raise EvidenceEpochError(f"epoch authority missing: {rel}")
        rows.append({"ref":rel,"sha256":sha256_file(path)})
    provisional=[]
    for rel in _unique_refs(doc.get("provisional_research_artifacts") or []):
        path=root/rel
        if not path.is_file():
            raise EvidenceEpochError(f"provisional epoch artifact missing: {rel}")
        provisional.append({"ref":rel,"sha256":sha256_file(path),"authority_role":"PROVISIONAL_NOT_OPENED"})
    hypothesis=json.loads((root/"HYPOTHESIS_SPACE_V1.json").read_text(encoding="utf-8"))
    open_families=list((hypothesis.get("dimensions") or {}).get("mechanism_family") or [])
    structural=json.loads((root/"data/BROKER_NATIVE_COMPETITION_STRUCTURAL_MAP_SUMMARY_V2.json").read_text(encoding="utf-8"))
    current_frontier_path=root/"research_v3/CURRENT_RESEARCH_FRONTIER_V1.json"
    current_frontier=json.loads(current_frontier_path.read_text(encoding="utf-8")) if current_frontier_path.is_file() else {}
    current_feasibility_path=root/"data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json"
    if current_feasibility_path.is_file():
        feasibility=json.loads(current_feasibility_path.read_text(encoding="utf-8"))
        counts=feasibility.get("current_counts") or {}
        current_products=int(counts.get("current_symbols") or 0)
        accessible_symbols=int(counts.get("current_new_entry_accessible") or 0)
        both_direction=int(counts.get("both_direction_eur200_feasible") or 0)
        buy_only=int(counts.get("buy_only_eur200_feasible") or 0)
        test_both=int(counts.get("known_test_products_still_both_feasible") or 0)
        feasible_non_test=max(0,both_direction-test_both)+buy_only
        eligible_post_exclusion=int(counts.get("current_eligible_post_exclusion_frontier") or ((current_frontier.get("open_frontier") or {}).get("eligible_post_exclusion_symbols") or 0))
    else:
        feasibility=json.loads((root/"data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json").read_text(encoding="utf-8"))
        current_products=int(structural.get("current_products") or structural.get("current_symbols") or 5324)
        accessible_symbols=int(structural.get("accessible_symbols") or feasibility.get("current_accessible_symbols_indexed") or 1690)
        both_direction=int(structural.get("both_direction_eur200_feasible") or 1609)
        buy_only=int(structural.get("buy_only_eur200_feasible") or 40)
        feasible_non_test=int(structural.get("feasible_non_test_symbols") or 1641)
        eligible_post_exclusion=int((current_frontier.get("open_frontier") or {}).get("eligible_post_exclusion_symbols") or 0)
    feature_ref=current_frontier.get("feature_store_ref")
    feature={}
    if isinstance(feature_ref,str) and feature_ref and (root/feature_ref).is_file():
        feature=json.loads((root/feature_ref).read_text(encoding="utf-8"))
    feature_summary=feature.get("summary") or {}
    universe_basis={
        "current_products":current_products,
        "accessible_symbols":accessible_symbols,
        "feasible_non_test_symbols":feasible_non_test,
        "both_direction_eur200_feasible":both_direction,
        "buy_only_eur200_feasible":buy_only,
        "eligible_post_exclusion_symbols":eligible_post_exclusion,
        "structural_representatives":int(feature_summary.get("current_structural_representatives") or 0),
        "structural_representatives_with_accepted_13w_data":int(feature_summary.get("current_representatives_with_13w_history") or 0),
        "structural_representation_is_not_economic_equivalence":True,
        "current_authority_ref":"data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json" if current_feasibility_path.is_file() else "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json",
    }
    bundle_payload={"epoch":active_epoch,"authorities":rows,"provisional":provisional}
    return {
        "evidence_epoch":active_epoch,
        "epoch_status":doc.get("status"),
        "epoch_reason":doc.get("reason"),
        "authoritative_evidence_refs_and_hashes":rows,
        "provisional_research_artifacts":provisional,
        "evidence_bundle_sha256":sha256_bytes(canonical_bytes(bundle_payload)),
        "universe_basis":universe_basis,
        "current_open_mechanism_families":open_families,
    }

def advance_evidence_epoch(root_value:str|Path,*,event_class:str,refs:list[str],reason:str,advanced_utc:str)->dict[str,Any]:
    root=Path(root_value).resolve()
    if event_class not in MATERIAL_EVENT_CLASSES:
        raise EvidenceEpochError(f"event class does not advance research evidence epoch: {event_class}")
    if not refs or not reason or not advanced_utc:
        raise EvidenceEpochError("epoch advancement requires refs, reason and advanced_utc")
    doc=_load(root)
    for rel in refs:
        if not (root/rel).is_file():
            raise EvidenceEpochError(f"cannot advance epoch with missing ref: {rel}")
    nxt=max(int(doc["current_epoch"]),current_evidence_epoch(root))+1
    doc["current_epoch"]=nxt
    doc["advanced_utc"]=advanced_utc
    doc["reason"]=reason
    doc["trigger_event"]={"event_class":event_class,"refs":list(refs)}
    doc["authoritative_evidence_refs"]=_unique_refs(list(doc.get("authoritative_evidence_refs") or [])+list(refs))
    doc.setdefault("history",[]).append({
        "epoch":nxt,"advanced_utc":advanced_utc,"event_class":event_class,
        "reason":reason,"refs":list(refs),
    })
    atomic_write_json(root/EPOCH_REL,doc)
    return doc

def state_requires_research_judgment(state:Mapping[str,Any])->bool:
    return state.get("research_judgment_required") is True

def stale_reasoning_redirect(root_value:str|Path,state:Mapping[str,Any])->dict[str,Any]|None:
    root=Path(root_value).resolve()
    if not state_requires_research_judgment(state):
        return None
    current=current_evidence_epoch(root)
    try:
        seen=int(state.get("authorizing_evidence_epoch",0) or 0)
    except (TypeError,ValueError):
        seen=0
    if seen>=current:
        return None
    return {
        "status":"FRESH_GENERAL_AI_REASONING_REQUIRED",
        "next_action":"AI_REASSESS_HIGHEST_INFORMATION_LEGAL_NEXT_ACTION_FROM_CURRENT_EVIDENCE_EPOCH",
        "ai_reasoning_required":True,
        "user_action_required":False,
        "research_judgment_required":True,
        "current_research_evidence_epoch":current,
        "authorizing_evidence_epoch":seen,
        "external_data_gate":None,
        "stale_reasoning_guard":{
            "status":"STALE_FOR_NEW_RESEARCH_JUDGMENT",
            "current_evidence_epoch":current,
            "authorizing_evidence_epoch":seen,
            "previous_status":state.get("status"),
            "previous_next_action":state.get("next_action"),
            "previous_external_data_gate":state.get("external_data_gate"),
            "law":"Historical reasoning remains evidence but cannot authorize new mechanism/panel/universe/horizon judgment after material evidence advances."
        },
    }

def proposal_evidence_binding_is_current(root_value:str|Path,proposal:Mapping[str,Any])->bool:
    current=current_evidence_binding(root_value)
    binding=proposal.get("evidence_binding") or {}
    return (
        int(binding.get("evidence_epoch_seen",0) or 0)==current["evidence_epoch"]
        and binding.get("evidence_bundle_sha256")==current["evidence_bundle_sha256"]
    )
