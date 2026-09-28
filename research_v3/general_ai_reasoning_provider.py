"""Unattended provider-neutral general-AI reasoning wake for MXM Research V3.

The active unattended adapter is GitHub Copilot CLI running programmatically in Actions.
The provider creates NON_ECONOMIC research proposals only. Runtime V2 remains the
deterministic safety, accounting, persistence and exactly-once economic authority.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from research_v3.evidence_eligibility import packet, validate_eligibility, EvidenceIneligible
from research_v3.evidence_epoch import current_evidence_binding
from research_v3.general_ai_director_bridge import (
    PROPOSAL_SCHEMA,
    PROTOCOL_VERSION,
    AIProposalRejected,
    project_snapshot,
    validate_proposal,
    _validate_proposed_next_state_routeability,
)
from research_v3.discovery_methodology import validate_proposal_universe_methodology
from research_v3.discovery_governance import validate_proposal_discovery_governance
from research_v3.runtime_v2_primitives import (
    GitCheckpointSink,
    atomic_write_json,
    canonical_bytes,
    iso,
    sha256_bytes,
    sha256_file,
)

PROVIDER_VERSION="MXM_GENERAL_AI_REASONING_PROVIDER_V4"
PROVIDER_KIND="GITHUB_COPILOT_CLI"
DEFAULT_MODEL="auto"
NEXT_REL=Path("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
REQUEST_REL=Path("research_v3/ai_director/AI_REASONING_REQUEST.json")
RESPONSE_REL=Path("research_v3/ai_director/AI_REASONING_RESPONSE.json")
GATE_REL=Path("research_v3/ai_director/AI_REASONING_EXTERNAL_GATE.json")
PROPOSAL_DIR=Path("research_v3/ai_director/proposals")
RAW_CANDIDATE_DIR=Path("research_v3/ai_director/raw_candidates")

# Mutable provider/control-plane transport artifacts are not semantic research evidence.
# Their content can change on retry/recovery while the research question is unchanged;
# including their hashes in the request fingerprint creates false-new semantic requests.
NON_SEMANTIC_REQUEST_FINGERPRINT_REFS=frozenset({
    "research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json",
    "research_v3/ai_director/AI_REASONING_EXTERNAL_GATE.json",
    "research_v3/ai_director/AI_REASONING_REQUEST.json",
    "research_v3/ai_director/AI_REASONING_RESPONSE.json",
    "research_v3/ai_director/PROVIDER_RECOVERY_STATE.json",
    "research_v3/ai_director/PROVIDER_USAGE_V1.json",
    "research_v3/ai_director/PROPOSAL_ELIGIBILITY_REJECTION_V1.json",
    "research_v3/ai_director/EXTERNAL_GENERAL_AI_PROPOSAL_V1.json",
})

BASE_AUTHORITIES=(
    "research_v3/RESEARCH_CONTRACT_V3.json",
    "data/RESEARCH_SCOPE_GOVERNANCE_V1.json",
    "evidence/MECHANISM_SCOPE_REGISTRY_V1.json",
    "evidence/V2_CONSUMED_IDENTITY_SCOPE_AUDIT_V1.json",
    "data/AUTONOMOUS_UNIVERSE_GOVERNOR_V1.json",
    "data/ADAPTIVE_DATA_ACQUISITION_POLICY_V1.json",
    "data/CAPITAL_FLOW_AWARE_CAUSAL_GOVERNOR_V1.json",
    "research_v3/SEARCH_BUDGET_GOVERNANCE_V2.json",
    "data/BROKER_NATIVE_COMPETITION_STRUCTURAL_MAP_SUMMARY_V2.json",
    "data/BROKER_NATIVE_COMPETITION_UNIVERSE_ACCEPTANCE_V2.json",
    "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json",
    "data/C031_STRUCTURAL_EXTENSION_WAVE_01_M5_CAPTURE_PLAN_V1.json",
    "evidence/C031_STRUCTURAL_EXTENSION_WAVE_01_CAPTURE_ACCEPTANCE_V1.json",
    "evidence/SESSION_GAP_STRUCTURAL_EXTENSION_WAVE_01_REPORT_V1.json",
    "evidence/POST_OUTER_DUPLICATE_CAPTURE_SUPERSESSION_V1.json",
    "evidence/AI_SELECTED_SCOPE_FEASIBILITY_AUDIT_V1.json",
    "evidence/AI_SELECTED_SCOPE_FEASIBILITY_AUDIT_V2.json",
    "evidence/GENERAL_AI_RESEARCH_DIRECTOR_ACCEPTANCE_V1.json",
    "research_v3/ai_director/GENERAL_AI_DIRECTOR_ARCHITECTURE_V1.json",
    "research_v3/SESSION_GAP_SELECTED_SIX_PANEL_FREEZE_V1.json",
    "data/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json",
    "evidence/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_DATA_AUDIT_V1.json",
    "evidence/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CONFIRMATORY_RESULT_V1.json",
    "evidence/RETROSPECTIVE_HISTORICAL_RESEARCH_VALIDITY_AUDIT_V1.json",
    "evidence/BROKER_NATIVE_PANEL_SCREEN_AUDIT_V1.json",
    "evidence/SESSION_GAP_SCHEDULE_COVERAGE_DEPENDENCY_REVIEW_V1.json",
    "data/BROKER_NATIVE_ADAPTIVE_INFORMATION_FRONTIER_V1.json",
    "data/BROKER_NATIVE_FRONTIER_M5_PROBE_PLAN_V1.json",
    "evidence/RESEARCH_DISCOVERY_METHODOLOGY_AUDIT_V1.json",
    "research_v3/ADAPTIVE_MECHANISM_DISCOVERY_ARCHITECTURE_V1.json",
    "evidence/RETROSPECTIVE_EVIDENCE_SCOPE_AUDIT_V1.json",
    "research_v3/PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1.json",
    "research_v3/MULTI_FRONTIER_DISCOVERY_GOVERNOR_V1.json",
    "research_v3/DISCOVERY_COVERAGE_LEDGER_V1.json",
    "evidence/EPOCH37_PRE_OUTCOME_METHODOLOGY_VALIDITY_GATE_V1.json",
)

class AIReasoningProviderError(RuntimeError): pass
class AIReasoningExternalGate(RuntimeError): pass
class LocalPreProviderTransportFailure(AIReasoningProviderError): pass

def _load(root:Path,rel:str|Path)->dict[str,Any]:
    p=root/Path(rel)
    if not p.is_file():
        raise AIReasoningProviderError(f"required reasoning authority missing: {p.relative_to(root)}")
    return json.loads(p.read_text(encoding="utf-8"))

def _head(root:Path)->str:
    return subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()

def reasoning_required(next_state:Mapping[str,Any])->bool:
    if next_state.get("user_action_required") is True:
        return False
    if next_state.get("ai_reasoning_required") is True:
        return True
    if next_state.get("research_judgment_required") is True:
        return True
    action=str(next_state.get("next_action") or "").upper()
    status=str(next_state.get("status") or "").upper()
    # Wake detection only. This never maps a state to a research decision.
    return action.startswith("AI_") or "PENDING_AI_INTERPRETATION" in status or "AI_REASONING_REQUIRED" in status

def _state_repository_refs(value:Any, *, key:str|None=None)->list[str]:
    """Collect durable repository refs exposed by NEXT_AUTONOMOUS_STATE.

    If a state document is shown to the semantic provider, any existing repository
    artifact referenced by *_ref / *_refs fields must also be in the provider's
    allowed authority packet.  Maintaining a manual allow-list caused Epoch25 to
    reject a valid proposal merely because one historical evidence ref was visible
    in state but absent from authority_refs.
    """
    found:list[str]=[]
    if isinstance(value,Mapping):
        for child_key,child in value.items():
            child_name=str(child_key)
            if child_name.endswith("_ref") and isinstance(child,str) and child:
                found.append(child)
            elif child_name.endswith("_refs") and isinstance(child,list):
                found.extend(str(x) for x in child if isinstance(x,str) and x)
            found.extend(_state_repository_refs(child,key=child_name))
    elif isinstance(value,list):
        for child in value:
            found.extend(_state_repository_refs(child,key=key))
    return found


def _authority_context(root:Path,next_state:Mapping[str,Any])->tuple[list[dict[str,Any]],list[str]]:
    refs=list(BASE_AUTHORITIES)
    for rel in ("research_v3/CURRENT_RESEARCH_FRONTIER_V1.json",
                "research_v3/ai_director/BLOCKED_FRONTIER_SCOPES_V1.json",
                "research_v3/EPOCH21_OUTCOME_BLIND_CAPACITY_AUDIT_V1.json",
                "research_v3/EPOCH21_ECONOMIC_SEARCH_GOVERNANCE_V1.json",
                "research_v3/ai_director/EVIDENCE_ELIGIBILITY_V1.json",
                "research_v3/EPOCH21_UNSAFE_PROPOSAL_SUPERSESSION_V1.json"):
        if (root/rel).is_file() and rel not in refs: refs.append(rel)
    acceptance_path=root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_ACCEPTANCE_V1.json"
    if acceptance_path.is_file():
        accepted=json.loads(acceptance_path.read_text(encoding="utf-8"))
        rel=accepted.get("requested_ref")
        if accepted.get("status")=="ELIGIBLE_AUTHORITY_ADDED_TO_NEW_PACKET" and isinstance(rel,str) and (root/rel).is_file() and sha256_file(root/rel)==accepted.get("sha256") and rel not in refs:
            refs.append(rel)
    epoch_binding=current_evidence_binding(root)
    for row in epoch_binding["authoritative_evidence_refs_and_hashes"]:
        if row["ref"] not in refs:
            refs.append(row["ref"])
    for row in epoch_binding["provisional_research_artifacts"]:
        if row["ref"] not in refs:
            refs.append(row["ref"])
    for key in (
        "result_ref","pre_economic_acceptance_ref","freeze_ref",
        "source_freeze_ref","authoritative_freeze_ref",
        "outer_capture_plan_ref","outer_data_audit_ref","supersession_ref",
        "external_data_gate_ref","capture_acceptance_ref","structural_screen_freeze_ref",
        "outer_data_binding_ref","interpretation_ref","same_wave01_supersession_ref",
        "completed_capture_ref","completed_capture_plan_ref",
        "completed_structural_report_ref","duplicate_capture_supersession_ref",
        "selected_scope_feasibility_audit_ref","superseded_pre_capture_proposal_ref",
        "scope_resolution_ref","exploratory_regime_screen_ref",
        "alignment_prerequisite_ref","all_frontier_inventory_ref","capture_contract_ref",
        "feature_store_ref","opportunity_map_ref","information_gain_selection_ref",
        "latest_material_structural_result_ref","latest_prospective_freeze_ref",
        "frontier_selection_execution_authority_ref","additional_authority_request_ref",
        "additional_authority_acceptance_ref",
    ):
        value=next_state.get(key)
        if isinstance(value,str) and value and value not in refs:
            refs.append(value)

    # Systemic closure: do not expose a durable state ref to AI while forbidding
    # the same ref as proposal authority.  Include only repository files that
    # actually exist; non-file identifiers never become authorities.
    for rel in _state_repository_refs(next_state):
        if rel not in refs and (root/rel).is_file():
            refs.append(rel)

    # Referential closure over the authority packet itself.  Large authority
    # documents are summarized to the model, but their durable *_ref / *_refs
    # values can still be visible and legitimately cited.  A manually curated
    # top-level list repeatedly rejected such citations (Epoch25).  Expand only
    # existing repository JSON refs, fail closed on runaway graphs, and preserve
    # stable insertion order.
    cursor=0
    max_authority_refs=512
    while cursor < len(refs):
        if len(refs) > max_authority_refs:
            raise AIReasoningProviderError(
                f"authority reference closure exceeded {max_authority_refs} files"
            )
        rel=refs[cursor]
        cursor+=1
        path=root/rel
        if not path.is_file() or path.suffix.lower()!=".json":
            continue
        try:
            doc=json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for nested in _state_repository_refs(doc):
            if nested not in refs and (root/nested).is_file():
                refs.append(nested)

    rows=[]; kept=[]
    for rel in refs:
        p=root/rel
        if not p.is_file():
            continue
        raw=p.read_bytes()
        item={"ref":rel,"sha256":sha256_bytes(raw)}
        try:
            doc=json.loads(raw)
            if len(raw)>3000:
                item["content_summary"]={
                    "schema":doc.get("schema"),"status":doc.get("status"),
                    "byte_length":len(raw),"available_via_repository_view":True,
                    "top_level_keys":list(doc)[:24],
                }
                if rel.endswith("PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json"):
                    item["content_summary"]["current_accessible_symbols_indexed"]=doc.get("current_accessible_symbols_indexed")
                    item["content_summary"]["source_zip_sha256"]=doc.get("source_zip_sha256")
            else:
                item["content"]=doc
        except Exception:
            item["content_text"]=raw.decode("utf-8",errors="replace")[:3000]
        rows.append(item); kept.append(rel)
    return rows,kept

def _authorized_deterministic_operation_catalog(root:Path,evidence_epoch:int)->list[dict[str,Any]]:
    """Return only executable deterministic operation authorities for this epoch.

    Semantic AI must never guess that an evidence/context file is a deterministic
    operation.  The catalog is derived from repository bytes and is the sole set
    of refs the model may place in next_deterministic_operation_ref.
    """
    rows:list[dict[str,Any]]=[]
    research_root=root/"research_v3"
    if not research_root.is_dir():
        return rows
    for path in research_root.rglob("*.json"):
        try:
            doc=json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if doc.get("schema")!="mxm.greenfield.deterministic-next-operation.v1":
            continue
        if doc.get("status")!="AUTHORIZED_DETERMINISTIC_NON_ECONOMIC_OPERATION":
            continue
        if int(doc.get("evidence_epoch") or 0)!=int(evidence_epoch):
            continue
        policy=doc.get("execution_policy") or {}
        effect=doc.get("accounting_effect") or {}
        if (
            policy.get("new_semantic_judgment_required") is True
            or policy.get("copilot_reasoning_required") is True
            or int(effect.get("v2_attempts") or 0)!=0
            or int(effect.get("economic_outcomes") or 0)!=0
        ):
            continue
        rows.append({
            "ref":str(path.relative_to(root)),
            "operation_name":str(doc.get("operation_name") or ""),
            "implementation_ai_required":policy.get("implementation_ai_required") is True,
        })
    rows.sort(key=lambda row:(row["operation_name"],row["ref"]))
    return rows


def build_reasoning_request(root_value:str|Path)->dict[str,Any]:
    root=Path(root_value).resolve()
    next_state=_load(root,NEXT_REL)
    snapshot=project_snapshot(root)
    state_safety=dict(next_state.get("safety") or {})
    report={
        "next_action":next_state.get("next_action"),
        "stage_b_survivors":list(next_state.get("stage_b_survivors") or []),
        "stage_b_revalidation_required_candidate_ids":list(next_state.get("stage_b_revalidation_required_candidate_ids") or []),
        "material_issues":[],
        "recoverable_conditions":[],
        "safety":{
            "protected_evidence_opened":bool(state_safety.get("protected_evidence_opened") or next_state.get("protected_evidence_opened")),
            "live_orders_authorized":bool(state_safety.get("live_orders_authorized") or next_state.get("live_orders_authorized")),
            "competition_start_authorized":bool(state_safety.get("competition_start_authorized") or next_state.get("competition_start_authorized")),
        },
    }
    authorities,refs=_authority_context(root,next_state)
    blocker=_load(root,"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json") if (root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json").is_file() else {}
    blocked_doc=json.loads((root/"research_v3/ai_director/BLOCKED_FRONTIER_SCOPES_V1.json").read_text()) if (root/"research_v3/ai_director/BLOCKED_FRONTIER_SCOPES_V1.json").is_file() else {}
    blocked_scopes=sorted({row["scope_id"] for row in blocked_doc.get("items",[]) if row.get("status")=="PARKED_LOCAL_FRONTIER"}) if blocked_doc.get("schema")=="mxm.greenfield.blocked-frontier-scopes.v1" else (sorted(set(blocker.get("blocked_scope_ids") or [])) if blocker.get("scope_status")=="PARKED_LOCAL_FRONTIER" else [])
    evidence=current_evidence_binding(root)
    deterministic_catalog=_authorized_deterministic_operation_catalog(root,int(evidence["evidence_epoch"]))
    core={
        "provider_version":PROVIDER_VERSION,
        "research_head":_head(root),
        "project_snapshot":snapshot,
        "next_state":next_state,
        "control_plane":{
            "next_action":report.get("next_action"),
            "stage_b_survivors":report.get("stage_b_survivors",[]),
            "stage_b_revalidation_required_candidate_ids":report.get("stage_b_revalidation_required_candidate_ids",[]),
            "material_issues":report.get("material_issues",[]),
            "recoverable_conditions":report.get("recoverable_conditions",[]),
            "safety":report.get("safety",{}),
        },
        "authority_hashes":[{"ref":x["ref"],"sha256":x["sha256"]} for x in authorities],
        "evidence_epoch_seen":evidence["evidence_epoch"],
        "evidence_bundle_sha256":evidence["evidence_bundle_sha256"],
        "universe_basis":evidence["universe_basis"],
        "current_open_mechanism_families":evidence["current_open_mechanism_families"],
        "blocked_scope_set":blocked_scopes,
    }
    # The repository HEAD and full mutable next-state document are transport context,
    # not reasons to buy another semantic judgment on unchanged evidence.
    decision_fingerprint={
        "provider_version":PROVIDER_VERSION,
        "protocol_version":PROTOCOL_VERSION,
        "evidence_epoch":core["evidence_epoch_seen"],
        "evidence_bundle_sha256":core["evidence_bundle_sha256"],
        "authority_hashes":[row for row in core["authority_hashes"] if row["ref"] not in NON_SEMANTIC_REQUEST_FINGERPRINT_REFS],
        "blocked_scope_set":blocked_scopes,
        "decision_class":str(next_state.get("next_action") or ""),
        "pending_status":str(next_state.get("status") or ""),
        "semantic_question":str(next_state.get("semantic_question") or ""),
        "decision_contract":next_state.get("decision_contract") or {},
        "scope_resolution_ref":str(next_state.get("scope_resolution_ref") or ""),
        "accounting":snapshot,
        "universe_basis":core["universe_basis"],
        "open_families":core["current_open_mechanism_families"],
        "authorized_deterministic_operations_current_epoch":deterministic_catalog,
        "eligibility_retry":next_state.get("eligibility_retry"),
    }
    request_id="reason_"+sha256_bytes(canonical_bytes(decision_fingerprint))[:32]
    return {
        "schema":"mxm.greenfield.general-ai-reasoning-request.v2",
        "status":"AI_REASONING_REQUIRED" if reasoning_required(next_state) else "NO_AI_REASONING_REQUIRED",
        "protocol_version":PROTOCOL_VERSION,
        "provider_version":PROVIDER_VERSION,
        "request_id":request_id,
        "research_head":core["research_head"],
        "project_snapshot":snapshot,
        "next_state":{"status":next_state.get("status"),"next_action":next_state.get("next_action"),
                      "semantic_question":next_state.get("semantic_question"),
                      "decision_contract":next_state.get("decision_contract"),
                      "scope_resolution_ref":next_state.get("scope_resolution_ref"),
                      "reason":next_state.get("reason"),
                      "supersession_ref":next_state.get("supersession_ref"),
                      "active_candidate_id":None,"active_target_symbol":None,
                      "active_mechanism_family":None,"active_proposal_id":None,
                      "evidence_epoch":evidence["evidence_epoch"],
                      "current_frontier_ref":"research_v3/CURRENT_RESEARCH_FRONTIER_V1.json"},
        "control_plane":core["control_plane"],
        "authority_refs":refs,
        "authority_hashes":core["authority_hashes"],
        "evidence_epoch_seen":core["evidence_epoch_seen"],
        "evidence_bundle_sha256":core["evidence_bundle_sha256"],
        "authoritative_evidence_refs_and_hashes":evidence["authoritative_evidence_refs_and_hashes"],
        "provisional_research_artifacts":evidence["provisional_research_artifacts"],
        "universe_basis":core["universe_basis"],
        "current_open_mechanism_families":core["current_open_mechanism_families"],
        "blocked_scope_set":blocked_scopes,
        "blocked_authority_request_id":blocker.get("request_id") if blocked_scopes else None,
        "eligibility_retry":next_state.get("eligibility_retry"),
        "authorized_deterministic_operations_current_epoch":deterministic_catalog,
        "created_utc":iso(),
    }

def _context_payload(root:Path,request:Mapping[str,Any])->dict[str,Any]:
    frontier=json.loads((root/"research_v3/CURRENT_RESEARCH_FRONTIER_V1.json").read_text())
    audit=json.loads((root/"research_v3/EPOCH21_OUTCOME_BLIND_CAPACITY_AUDIT_V1.json").read_text())
    epoch_doc=json.loads((root/"research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json").read_text())
    delta=list((epoch_doc.get("trigger_event") or {}).get("refs") or [])
    scope=[{"id":row["candidate_id"],"family":row["mechanism_family"],
            "symbols":row["exact_universe_size"],"design_class":row["classification"],
            "replacement":row["replacement_eligible"],"result_ref":row["latest_result_ref"]}
           for row in audit["per_identity"]]
    p=packet(root,evidence_epoch=request["evidence_epoch_seen"],
             decision_class="FRESH_FRONTIER_LEVEL_RESEARCH",
             refs=request["authority_refs"],accounting=frontier["accounting"],
             universe=frontier["open_frontier"],
             semantic_question=(request.get("next_state") or {}).get("semantic_question") or "From the entire legal broker-native frontier, choose the highest-information prospective research wave for extremely fast and high realizable compounded EUR200 Pepperstone/cTrader equity growth with free-margin survival and recovery capacity. Select mechanism and breadth from reusable evidence, not the last candidate.",
             delta_refs=delta)
    p["allowed_authority_refs"]=[x["ref"] for x in
        p["admissible_inputs"]+p["historical_context"]+p["forbidden_inputs"]]
    next_state_full=json.loads((root/NEXT_REL).read_text(encoding="utf-8"))
    structural_ref=next_state_full.get("latest_material_structural_result_ref") or next_state_full.get("completed_structural_report_ref") or "evidence/EPOCH24_TREND_MOMENTUM_STRUCTURAL_RESULT_V1.json"
    structural=json.loads((root/structural_ref).read_text(encoding="utf-8"))
    registry=json.loads((root/"research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json").read_text())
    selection_authority=json.loads((root/"research_v3/EPOCH25_FRONTIER_SELECTION_EXECUTION_AUTHORITY_V1.json").read_text())
    def bounded_authority(rel:str, keys:tuple[str,...])->dict[str,Any]:
        source=root/rel
        doc=json.loads(source.read_text(encoding="utf-8"))
        return {"ref":rel,"sha256":sha256_file(source),
                "source_bytes":source.stat().st_size,
                "facts":{key:doc[key] for key in keys if key in doc}}
    # The complete authority graph is retained in the request for deterministic
    # validation. The model receives only these provenance-bound decision facts.
    semantic_authorities=[
        bounded_authority("research_v3/DISCOVERY_COVERAGE_LEDGER_V1.json",
                          ("asset_class_frontier_counts","mechanism_family_summary","current_selected_frontier","materially_unexplored_frontiers","anti_starvation")),
        bounded_authority("research_v3/MULTI_FRONTIER_DISCOVERY_GOVERNOR_V1.json",
                          ("priority_inputs","anti_starvation","selection_contract","no_family_burn_law","no_asset_class_burn_law")),
        bounded_authority("research_v3/PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1.json",
                          ("prospective_search_space_requirements","stages","robustness_metrics","no_single_parameter_family_rejection","development_confirmation_boundary")),
        bounded_authority("evidence/RETROSPECTIVE_EVIDENCE_SCOPE_AUDIT_V1.json",
                          ("parameter_detail_rule","preservation","counts","family_exhaustion","global_interpretation")),
        bounded_authority("evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json",
                          ("cohort_policy","source_bindings","source_universe","status","interpretation_boundary","power_design_prerequisites")),
        bounded_authority("research_v3/EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_ACQUISITION_READINESS_V1.json",
                          ("status","accepted_peer_breadth","development_interval","exact_symbols","freeze_ref","frozen_sample_size","market_data_fetched","next_boundary","peer_candidate_cohort_id","resolution")),
        bounded_authority("research_v3/ADAPTIVE_MECHANISM_DISCOVERY_ARCHITECTURE_V1.json",
                          ("structural_panel","adaptive_discovery_universe","funnel","mechanism_specific_policy","statistical_policy","promotion_policy")),
        bounded_authority("evidence/RESEARCH_DISCOVERY_METHODOLOGY_AUDIT_V1.json",
                          ("live_universe","findings","invariants")),
    ]
    semantic_eligibility={key:p[key] for key in
                          ("schema","evidence_epoch","material_delta_since_last_accepted_reasoning",
                           "accounting","open_universe_authority","governing_research_contract",
                           "exact_semantic_question","allowed_authority_refs") if key in p}
    return {"request_id":request["request_id"],"eligibility_packet":semantic_eligibility,
            "current_frontier_content":frontier,
            "latest_structural_result_ref":structural_ref,
            "latest_structural_result_content":{key:structural[key] for key in ("schema","status","evidence_epoch","family","scope","inference","interpretation_boundary","freeze_ref") if key in structural},
            "latest_structural_result_sha256":sha256_file(root/structural_ref),
            "broker_native_representatives":registry["representatives"],
            "frontier_selection_execution_authority":selection_authority,
            "semantic_decision_packet":{"schema":"mxm.greenfield.semantic-decision-packet.v1",
                                        "request_id":request["request_id"],
                                        "evidence_epoch":request["evidence_epoch_seen"],
                                        "evidence_bundle_sha256":request["evidence_bundle_sha256"],
                                        "source_projections":semantic_authorities},
            "pending_decision":{k:(request.get("next_state") or {}).get(k) for k in ("status","next_action","reason","decision_contract","supersession_ref")},
            "historical_consumed_identity_summaries":scope,
            "valid_survivors":["V2-C006","V2-C012","V2-C031"],
            "unresolved_prerequisites":["C006 historical cash-session calendar",
                "C029 development settlement coverage","C030 zero settled trade"],
            "project_objective":{"broker":"Pepperstone","platform":"cTrader",
                "starting_capital_eur":200,"account":"ONE_CONTINUOUS_ACCOUNT",
                "goal":"EXTREMELY_HIGH_AND_FAST_REALIZABLE_COMPOUNDED_EQUITY_GROWTH",
                "must_preserve":["free_margin","recovery_capacity","anti_ruin"]},
            "capacity":{"base_remaining":64,"methodology_replacement_total":15,
                "lifetime_economic_exposure":20,"outcomes_opened":28},
            "authorized_deterministic_operations_current_epoch":list(request.get("authorized_deterministic_operations_current_epoch") or []),
            "blocked_scope_set":list(request.get("blocked_scope_set") or []),
            "blocked_authority_request_id":request.get("blocked_authority_request_id"),
            "causal_prohibitions":["NO_C032_RERUN","NO_C032_OUTCOME_CAPTURE_REUSE",
                "NO_PROTECTED_FORWARD_LEAKAGE","NO_RETROACTIVE_TUNING",
                "NO_OUTCOME_DRIVEN_SCOPE_SELECTION"],
            "authority_protocol":"If a necessary ref is absent, return status ADDITIONAL_AUTHORITY_REQUIRED with requested_authority_or_class and rationale. Do not invent an allowed ref."}


def _system_prompt()->str:
    return """You are the autonomous general AI Research Director for MXM Quant Greenfield V2.
You own advanced research reasoning: interpretation, hypothesis/mechanism generation, universe reasoning,
data sufficiency, research prioritization, methodology design and the highest-information legal next action.
Do NOT behave like a finite state machine and do NOT merely echo next_action. Infer the best research action
from the authoritative context.

Return ONE JSON object only, with these keys:
proposal_id: concise unique string
objective: object with class, goal, information_gain_rationale
decision: arbitrary JSON object expressing your actual research decision and enough implementation semantics
next_research_state: arbitrary JSON object with at least status, next_action, research_judgment_required, and implementation_ai_required; do not include protected accounting/safety keys
authority_refs: non-empty list chosen only from refs provided in context
data_bindings: optional list
artifact_attestation_refs: MUST be [] unless the supplied context explicitly identifies a document whose schema is mxm.greenfield.ai-director-artifact-attestation.v1 and status is VERIFIED
data_policy: object with new_market_data_requested boolean, and if true minimal_acquisition_request with source_domain exactly PEPPERSTONE_ACCOUNT_VIA_CTRADER_OPEN_API, symbols,resolution,start_utc,end_utc,fields,information_gain_justification
mechanism_family_closure_claims: list; normally empty unless prospective exhaustion authority exists

The next_research_state object MUST NOT contain any of these deterministic/protected keys:
accounting, safety, economic_outcomes_opened, v2_attempts_used, v2_search_budget_remaining,
protected_forward, live_orders, competition_start, competition_start_authorized, live_orders_authorized.
Those values are injected and guarded outside the AI layer.

Important boundaries:
- Begin with the complete current eligible frontier from CURRENT_RESEARCH_FRONTIER_V1.json and every open mechanism family. No consumed candidate, historical symbol, old panel, or rejected proposal is an active default.
- Treat blocked_scope_set as local unavailable families. Select the highest-information legal ready action outside them. Do not request the same unresolved authority again. If no legal ready action remains, return ADDITIONAL_AUTHORITY_REQUIRED with a machine-checkable blocked_scope_id and explain why all remaining actions require it.
- Choose mechanism-specific breadth from non-economic structural heterogeneity, data availability, event independence, and expected information gain. Do not assume a fixed panel size.
- One prospectively frozen economic experiment envelope may contain many symbols; do not authorize an economic outcome until causality, data sufficiency, cost, EUR200 margin feasibility, breadth, freeze, and exact-head CI all pass.
- Historical survivors and failures remain valid context. Never rerun an opened identity, use outcome-exposed evidence as new prospective input, erase lifetime trial exposure, or retroactively select a winning subgroup.
- When an authoritative structural result explicitly requires fresh family/frontier selection and forbids reuse/rerun of its diagnostic without new predeclared authority, do not immediately reparameterize or rerun that same family on the same observed bytes. A different split, test statistic, lag rule, multiplicity correction, or threshold after seeing the prior result is not a fresh prospective family decision. The same family may return only through a genuinely distinct prospectively justified hypothesis/authority that does not reuse the observed diagnostic outcome to redesign the test.
- Distinguish structural representatives from economic equivalence. The 41 structural representatives are a BROKER-TOPOLOGY COVERAGE PANEL, not the default inferential discovery universe. Do not reuse all 41 for a predictive/economic mechanism merely because their 13-week data are convenient.
- For every selected mechanism family, decision MUST include universe_methodology. Use role MECHANISM_SPECIFIC_DISCOVERY for inferential discovery, set structural_representatives_are_economic_equivalents=false, outcome_blind_selection=true, source_universe_ref to an allowed full-feasible-universe authority, and list non-outcome selection_features. Use role STRUCTURAL_COVERAGE_ONLY only for topology/pipeline/cheap feasibility work and set inferential_discovery=false.
- CROSS_SECTIONAL_RANKING, RELATIVE_VALUE_COINTEGRATION and CROSS_MARKET_LEAD_LAG additionally require universe_methodology.aligned_history_required=true and a concrete peer_coherence_basis. Peer-set construction is part of the estimand.
- Treat statistical power as a design input: use effective independent sample size rather than raw M5 bars, avoid universal both-half per-ticker significance as an early discovery veto, and retain multiplicity control at the appropriate confirmatory level. Pooled, hierarchical, clustered or portfolio-level inference is allowed only when prospectively justified by the scientific/economic estimand.
- A broad corrected structural result must have an explicit legal promotion path. Family-level evidence may motivate a fresh prospective follow-on, but observed per-symbol winners may not be cherry-picked into the economic universe.\n- Historical nulls are scope-bounded: one exact specification, one arbitrary parameter point, one symbol/small cohort, LOW_POWER_INCONCLUSIVE, DATA_INSUFFICIENT or a cost rejection cannot exhaust a mechanism family or another asset class. Preserve the exact negative result while reopening only broader materially distinct prospective DEVELOPMENT questions.\n- For tunable mechanisms use PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1 before confirmatory freeze: predeclare defensible coarse regions, record every probe, prefer broad stable neighborhoods, reject isolated winner cells, and never use protected/forward evidence for parameter selection.\n- Use DISCOVERY_COVERAGE_LEDGER_V1 plus MULTI_FRONTIER_DISCOVERY_GOVERNOR_V1 for fresh frontier selection. Record alternatives considered and exact information-gain rationale. Anti-starvation has no fixed quota and PARKED_LOCAL_FRONTIER is never family exhaustion.\n- Do not claim family closure unless an explicit family-level closure audit proves adequate power, meaningful parameter-region coverage, universe/asset/horizon breadth, and no material plausible unexplored frontier.\n- Prioritize material information gain and expected realizable economic value: edge per turnover, opportunity density, breadth, capital utilization, friction, margin efficiency, concurrency, compounding and recovery capacity. Commits/tests/epochs are not research progress by themselves.
- Use authenticated Pepperstone account cTrader/Open API evidence for market, cost, margin and execution facts. Verify exact broker symbol names and EUR200 feasibility before selecting any symbols.
- Cite only supplied authority refs. If an additional authority is needed, return status ADDITIONAL_AUTHORITY_REQUIRED, requested_authority_or_class, rationale, and a top-level blocked_scope_id equal to exactly one current_open_mechanism_families enum. Do not bury the scope inside rationale.
- Never ask the human to choose routine research parameters. Preserve one continuous EUR200 account, margin survivability, recovery capacity and anti-ruin.
- Set implementation_ai_required=true ONLY when genuinely novel repository code or machinery is required and deterministic existing capability is insufficient. Deterministic-in-principle is NOT enough.
- next_deterministic_operation_ref may reference ONLY a ref listed in authorized_deterministic_operations_current_epoch, and its operation_name must exactly equal next_action. Evidence, context, freeze, selection, or routing-contract files are NEVER deterministic-operation refs merely because their names contain "authority" or "execution". If the catalog is empty or has no exact operation_name match, do not invent or repurpose a ref: route genuinely missing repository machinery as implementation AI with explicit implementation_scope, request exact new data through data_policy when data is the true dependency, or choose another legal routed action.
- Never publish an unrouted non-empty action.
- If new broker data is genuinely required, express it through data_policy.new_market_data_requested=true with the exact minimal acquisition request; do not disguise a data gate as implementation AI.
- The proposal itself is non-economic and consumes zero attempts. Return concise decision rationale, not chain-of-thought.
"""

def _user_prompt(context:Mapping[str,Any], correction:str|None=None)->str:
    base=_system_prompt()+"\n\nAUTHORITATIVE REPOSITORY CONTEXT:\n"+json.dumps(context,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    contract=(context.get("pending_decision") or {}).get("decision_contract") or {}
    retry=context.get("eligibility_retry") or {}
    if retry:
        base+="\n\nPREVIOUS PROPOSAL REJECTED BEFORE REGISTRY. Generate a distinct proposal and correct the eligibility defect. Rejection feedback: "+json.dumps(retry,sort_keys=True)
    if contract:
        if contract.get("require_implementation_ai"):
            base+="\n\nIMPLEMENTATION ROUTING REQUIRED: Set next_research_state.implementation_ai_required=true, next_research_state.research_judgment_required=false, and decision.implementation_scope to concrete non-economic repository code, accepted inputs and tests. Preserve the selected mechanism family; never authorize economic execution or use development-selected winning pairs as independent confirmation."
        base+="\n\nPENDING DECISION CONTRACT (MANDATORY): Set decision.action to required_action and decision.selected_mechanism_family to one current open family outside temporarily_unavailable_families. Set next_research_state.selected_family to that same family and specify an executable pre-economic next_action. This contract governs the immediate decision only; unavailable families remain open for later research. Do not request an economic outcome. A proposal missing these exact fields or selecting an excluded family will be rejected before implementation."
    if correction:
        base+="\n\nYOUR PREVIOUS JSON WAS REJECTED BY DETERMINISTIC VALIDATION. CORRECT IT WITHOUT CHANGING THE RESEARCH GOAL:\n"+correction
    return base

def _extract_json(text:str)->dict[str,Any]:
    s=text.strip()
    fence=chr(96)*3
    if s.startswith(fence):
        s=re.sub("^"+re.escape(fence)+r"(?:json)?\s*","",s,flags=re.I)
        s=re.sub(r"\s*"+re.escape(fence)+r"$","",s)
    try:
        obj=json.loads(s)
    except Exception:
        a=s.find("{"); b=s.rfind("}")
        if a<0 or b<=a:
            raise AIReasoningProviderError("provider response contains no JSON object")
        obj=json.loads(s[a:b+1])
    if not isinstance(obj,dict):
        raise AIReasoningProviderError("provider response is not a JSON object")
    return obj

def _looks_external_gate(text:str)->bool:
    s=text.lower()
    markers=(
        "copilot requests permission",
        "copilot-requests",
        "not entitled",
        "no copilot",
        "copilot subscription",
        "copilot plan",
        "authentication failed",
        "unauthorized",
        "forbidden",
        "billing",
        "policy",
    )
    return any(x in s for x in markers)

def copilot_cli_transport(token:str,model:str,prompt:str,*,root:Path)->tuple[dict[str,Any],dict[str,Any]]:
    if not shutil.which("copilot"):
        raise LocalPreProviderTransportFailure("GitHub Copilot CLI executable is not installed")
    cmd=[
        "copilot",
        "-s",
        "--model="+model,
        "--no-ask-user",
        "--no-auto-update",
        "--no-color",
        "--no-custom-instructions",
        "--deny-tool=shell",
        "--deny-tool=write",
        "--deny-tool=url",
    ]
    env=dict(os.environ)
    env["GITHUB_TOKEN"]=token
    env["COPILOT_GITHUB_TOKEN"]=token
    try:
        proc=subprocess.run(cmd,input=prompt,cwd=root,env=env,text=True,capture_output=True,timeout=240)
    except OSError as exc:
        raise LocalPreProviderTransportFailure(f"local process launch failed: {exc}") from exc
    if proc.returncode!=0:
        detail=(proc.stderr+"\n"+proc.stdout).strip()
        if _looks_external_gate(detail):
            raise AIReasoningExternalGate(detail[:1600])
        raise AIReasoningProviderError("Copilot CLI failed: "+detail[:2000])
    output=proc.stdout.strip()
    if not output:
        raise AIReasoningProviderError("Copilot CLI returned empty output")
    return _extract_json(output),{
        "provider":"github-copilot-cli",
        "model":model,
        "model_selection":"AUTO_ACCOUNT_AVAILABLE" if model=="auto" else "EXPLICIT",
        "actual_model_identity":None if model=="auto" else model,
        "actual_model_identity_known":model!="auto",
        "model_identity_limitation":"Copilot CLI silent programmatic mode does not expose the model selected behind Auto." if model=="auto" else None,
        "cli":"@github/copilot",
    }

def _canonical_implementation_scope(request:Mapping[str,Any],candidate:Mapping[str,Any])->dict[str,Any]:
    next_state=dict(candidate.get("next_research_state") or {})
    decision=dict(candidate.get("decision") or {})
    action=str(next_state.get("next_action") or "").strip()
    selected=(
        decision.get("selected_mechanism_family")
        or next_state.get("selected_family")
        or next_state.get("mechanism_family")
        or next_state.get("active_mechanism_family")
    )
    return {
        "scope_type":"NON_ECONOMIC_REPOSITORY_IMPLEMENTATION_FOR_BOUND_AI_DECISION",
        "next_action":action,
        "selected_mechanism_family":selected,
        "research_semantics_source":"BOUND_ACCEPTED_AI_DECISION",
        "authority_refs":list(candidate.get("authority_refs") or []),
        "data_bindings":list(candidate.get("data_bindings") or []),
        "requirements":[
            "IMPLEMENT_ONLY_MACHINERY_REQUIRED_TO_EXECUTE_THE_BOUND_NON_ECONOMIC_DECISION",
            "INSPECT_AND_REUSE_EXISTING_REPOSITORY_CAPABILITY_BEFORE_CREATING_NEW_CODE",
            "ADD_OR_UPDATE_TARGETED_TESTS_AND_PROSPECTIVE_MANIFESTS_AS_NEEDED",
            "PRESERVE_THE_ACCEPTED_RESEARCH_MECHANISM_SCOPE_AND_CAUSAL_BOUNDARIES",
        ],
        "prohibitions":[
            "NO_NEW_RESEARCH_SELECTION_BY_IMPLEMENTATION_AGENT",
            "NO_ECONOMIC_OUTCOME_OPENING",
            "NO_V2_ATTEMPT_CONSUMPTION",
            "NO_PROTECTED_FORWARD_OPENING",
            "NO_LIVE_ORDER_AUTHORIZATION",
        ],
    }


def _normalize_candidate_routing(request:Mapping[str,Any],candidate:Mapping[str,Any])->dict[str,Any]:
    """Repair routing syntax without changing semantic research selection.

    Provider output is semantic authority, but routing representation is an
    implementation detail.  Do not spend another semantic call because the model
    omitted a wrapper field or guessed a deterministic ref that is not in the
    machine-derived executable catalog.
    """
    doc=json.loads(json.dumps(candidate))
    next_state=doc.get("next_research_state")
    decision=doc.get("decision")
    if not isinstance(next_state,dict) or not isinstance(decision,dict):
        return doc

    action=str(next_state.get("next_action") or "").strip()
    if not action:
        return doc

    data_policy=doc.get("data_policy") or {}
    if isinstance(data_policy,Mapping) and data_policy.get("new_market_data_requested") is True:
        return doc

    status=str(next_state.get("status") or "").upper()
    decision_status=str(decision.get("status") or "").upper()
    if decision_status=="ADDITIONAL_AUTHORITY_REQUIRED":
        blocked=str(decision.get("blocked_scope_id") or "").strip()
        requested=str(decision.get("requested_authority_or_class") or "").strip()
        if blocked:
            next_state["blocked_scope_id"]=blocked
        if requested:
            next_state["requested_authority_or_class"]=requested
        next_state["status"]="ADDITIONAL_AUTHORITY_REQUIRED"
        next_state["implementation_ai_required"]=False
        next_state["ai_reasoning_required"]=False
        next_state["research_judgment_required"]=False
        next_state["implementation_satisfied"]=False
        next_state["implementation_scope_complete"]=False
        next_state["user_action_required"]=False
        next_state["external_data_required"]=False
        return doc
    if (
        next_state.get("implementation_ai_required") is not True
        and (
        next_state.get("ai_reasoning_required") is True
        or action.upper().startswith("AI_")
        or status=="AI_REASONING_REQUIRED"
        or "PENDING_AI_INTERPRETATION" in status
        or "FRESH_GENERAL_AI_REASONING_REQUIRED" in status
        )
    ):
        return doc

    catalog=list(request.get("authorized_deterministic_operations_current_epoch") or [])
    ref=str(next_state.get("next_deterministic_operation_ref") or "").strip()
    if ref:
        exact=[
            row for row in catalog
            if row.get("ref")==ref and str(row.get("operation_name") or "").strip()==action
        ]
        if not exact:
            next_state.pop("next_deterministic_operation_ref",None)
            next_state.pop("deterministic_next_operation",None)
            next_state["implementation_ai_required"]=True
            next_state["research_judgment_required"]=False

    if next_state.get("implementation_ai_required") is True:
        # One canonical stage only: a proposal that hands off to implementation
        # must not inherit or advertise fresh semantic reasoning/completion flags.
        next_state["ai_reasoning_required"]=False
        next_state["research_judgment_required"]=False
        next_state["implementation_satisfied"]=False
        next_state["implementation_scope_complete"]=False
        next_state["user_action_required"]=False
        next_state["external_data_required"]=False
        if not decision.get("implementation_scope"):
            decision["implementation_scope"]=_canonical_implementation_scope(request,doc)
        return doc

    if (
        next_state.get("authority_ci_required") is True
        or status=="PENDING_EXACT_HEAD_GREEN"
        or next_state.get("economic_execution_authorized") is True
        or next_state.get("economic_materialization_authorized") is True
        or next_state.get("ctrader_build_or_certification_required") is True
    ):
        return doc

    # A non-empty action with no legal current-epoch deterministic executor, no
    # data gate, and no semantic/CI/economic route needs repository machinery.
    # This conversion is routing-only: it preserves action, family, authorities,
    # objective and all research semantics chosen by the provider.
    next_state.pop("next_deterministic_operation_ref",None)
    next_state.pop("deterministic_next_operation",None)
    next_state["implementation_ai_required"]=True
    next_state["ai_reasoning_required"]=False
    next_state["research_judgment_required"]=False
    next_state["implementation_satisfied"]=False
    next_state["implementation_scope_complete"]=False
    next_state["user_action_required"]=False
    next_state["external_data_required"]=False
    decision["implementation_scope"]=_canonical_implementation_scope(request,doc)
    return doc


def _wrap(root:Path,request:Mapping[str,Any],candidate:Mapping[str,Any],provider_meta:Mapping[str,Any])->dict[str,Any]:
    objective=candidate.get("objective"); decision=candidate.get("decision"); next_state=candidate.get("next_research_state")
    if not isinstance(objective,Mapping) or not isinstance(decision,Mapping) or not isinstance(next_state,Mapping):
        raise AIProposalRejected("provider candidate missing objective/decision/next_research_state objects")
    allowed=set(request["authority_refs"])
    refs=candidate.get("authority_refs") or []
    if not isinstance(refs,list) or not refs:
        raise AIProposalRejected("provider candidate authority_refs must be non-empty")
    refs=[str(x) for x in refs]
    # A guessed directory may be resolved only to a unique supplied basename.
    # An existing artifact outside the packet remains forbidden.
    for i, ref in enumerate(refs):
        if ref in allowed or (root/ref).exists():
            continue
        matches=[known for known in allowed if Path(known).name==Path(ref).name]
        if len(matches)==1:
            refs[i]=matches[0]
    unknown=[x for x in refs if x not in allowed]
    if unknown:
        sanitized=[x for x in unknown if re.fullmatch(r"[A-Za-z0-9_./-]{1,220}",x)]
        raise AIProposalRejected("provider candidate referenced authority outside supplied context: "+json.dumps(sanitized[:8]))
    raw_policy=candidate.get("data_policy") or {}
    new_data=bool(raw_policy.get("new_market_data_requested"))
    data_policy={"no_default_multi_year_download":True,"user_selects_symbols_or_horizon":False,"new_market_data_requested":new_data}
    if new_data:
        data_policy["minimal_acquisition_request"]=raw_policy.get("minimal_acquisition_request") or {}
    closure=candidate.get("mechanism_family_closure_claims") or []
    if not isinstance(closure,list):
        raise AIProposalRejected("mechanism_family_closure_claims must be list")
    pid=str(candidate.get("proposal_id") or f"AUTO-{request['request_id']}").strip()
    response_id="reason_response_"+sha256_bytes(canonical_bytes({"request_id":request["request_id"],"candidate":candidate}))[:32]
    contract=(request.get("next_state") or {}).get("decision_contract") or {}
    if contract:
        expected=contract.get("required_action")
        if expected and decision.get("action")!=expected:
            raise AIProposalRejected("proposal action does not resolve the pending decision contract")
        selected=decision.get("selected_mechanism_family")
        forbidden=set(contract.get("temporarily_unavailable_families") or [])
        if not isinstance(selected,str) or selected not in request["current_open_mechanism_families"]:
            raise AIProposalRejected("pending decision requires a named open mechanism family")
        if selected in forbidden:
            raise AIProposalRejected("selected family lacks a legal independent next step under the pending decision contract")
        for field in ("selected_family","mechanism_family","active_mechanism_family"):
            declared=next_state.get(field)
            if declared is not None and declared!=selected:
                raise AIProposalRejected("proposed next state contradicts selected mechanism family")
        if contract.get("require_no_economic_opening") and (decision.get("open_economic_outcome") or next_state.get("economic_outcome_opened")):
            raise AIProposalRejected("pending decision forbids an economic outcome")
        required_family=contract.get("required_family")
        if required_family and selected!=required_family:
            raise AIProposalRejected("pending decision requires the already selected mechanism family")
        if contract.get("require_implementation_ai") and next_state.get("implementation_ai_required") is not True:
            raise AIProposalRejected("pending decision requires explicit novel implementation routing")
        if next_state.get("implementation_ai_required") is True and not decision.get("implementation_scope"):
            raise AIProposalRejected("pending decision cannot authorize implementation without explicit implementation scope")
    proposed_next=dict(next_state)
    proposed_next.setdefault("research_judgment_required",False)
    proposed_next["authorizing_evidence_epoch"]=int(request["evidence_epoch_seen"])
    proposal={
        "schema":PROPOSAL_SCHEMA,
        "proposal_id":pid,
        "provider":{"kind":"GITHUB_COPILOT_CLI_GENERAL_REASONING","vendor":"GitHub Copilot","model":provider_meta.get("model"),"provider_version":PROVIDER_VERSION,"reasoning_request_id":request["request_id"]},
        "basis":{"research_head":request["research_head"],"accounting":{"v2_attempts_used":request["project_snapshot"]["v2_attempts_used"],"v2_search_budget_remaining":request["project_snapshot"]["v2_search_budget_remaining"],"economic_outcomes_opened":request["project_snapshot"]["economic_outcomes_opened"]},"discovery_ledger_sha256":request["project_snapshot"]["discovery_ledger_sha256"]},
        "objective":dict(objective),
        "decision":dict(decision),
        "next_research_state":proposed_next,
        "authority_refs":refs,
        "data_bindings":candidate.get("data_bindings") or [],
        "artifact_attestation_refs":candidate.get("artifact_attestation_refs") or [],
        "economic_effect":{"open_economic_outcome":False,"consume_v2_attempt":0,"create_new_v2_identity":False},
        "safety":{"protected_forward_opened":False,"live_orders_authorized":False,"competition_start_authorized":False},
        "scope_law":{"rerun_exact_observed_identity":False,"refund_observed_attempts":False,"mechanism_family_closure_claims":closure},
        "data_policy":data_policy,
        "causal_contract":{"chronological_incremental_replay":True,"causal_entry_admission":True,"future_information_forbidden":True,"protected_forward_leakage_forbidden":True,"learned_procedure_freeze_before_outer_outcome":True},
        "publication":{"apply_to_next_state":True},
        "evidence_binding":{
            "reasoning_request_id":request["request_id"],
            "reasoning_response_id":response_id,
            "evidence_epoch_seen":int(request["evidence_epoch_seen"]),
            "evidence_bundle_sha256":request.get("evidence_bundle_sha256"),
            "authoritative_evidence_refs_and_hashes":list(request["authoritative_evidence_refs_and_hashes"]),
            "accounting_basis":dict(request["project_snapshot"]),
            "universe_basis":dict(request["universe_basis"]),
            "current_open_mechanism_families":list(request["current_open_mechanism_families"]),
        },
    }
    try:
        validate_proposal_universe_methodology(root,proposal)
        validate_proposal_discovery_governance(root,proposal)
    except ValueError as exc:
        raise AIProposalRejected(str(exc)) from exc
    validate_proposal(root,proposal)
    _validate_proposed_next_state_routeability(root, proposal)
    return proposal

def _proposal_ref(request_id:str)->Path:
    return PROPOSAL_DIR/f"AUTO_{request_id}.json"

def wake(root_value:str|Path=".",*,token:str|None=None,transport:Callable[...,tuple[dict[str,Any],dict[str,Any]]]=copilot_cli_transport,git_checkpoint:bool=False,git_push:bool=False)->dict[str,Any]:
    root=Path(root_value).resolve()
    request=build_reasoning_request(root)
    atomic_write_json(root/REQUEST_REL,request)
    sink=GitCheckpointSink(root,enabled=git_checkpoint,push=git_push)
    if request["status"]!="AI_REASONING_REQUIRED":
        sink.checkpoint("general_ai_reasoning_request_noop",None)
        return {"status":"NO_AI_REASONING_REQUIRED","request_id":request["request_id"]}

    rel=_proposal_ref(request["request_id"]); path=root/rel
    if path.is_file():
        proposal=json.loads(path.read_text(encoding="utf-8"))
        validate_proposal(root,proposal)
        sink.checkpoint("general_ai_reasoning_reused",None)
        return {"status":"PROPOSAL_ALREADY_DURABLE","request_id":request["request_id"],"proposal_ref":str(rel),"proposal_hash":sha256_file(path)}

    external=root/"research_v3/ai_director/EXTERNAL_GENERAL_AI_PROPOSAL_V1.json"
    if external.is_file():
        candidate=json.loads(external.read_text(encoding="utf-8"))
        binding=candidate.get("evidence_binding") or {}
        if (candidate.get("provider") or {}).get("kind")=="EXTERNAL_CHATGPT_GENERAL_REASONING" and binding.get("reasoning_request_id")==request["request_id"] and binding.get("evidence_epoch_seen")==request["evidence_epoch_seen"]:
            try:
                validate_proposal_universe_methodology(root,candidate)
                validate_proposal_discovery_governance(root,candidate)
            except ValueError as exc:
                raise AIProposalRejected(str(exc)) from exc
            validate_proposal(root,candidate)
            _validate_proposed_next_state_routeability(root,candidate)
            path.parent.mkdir(parents=True,exist_ok=True)
            atomic_write_json(path,candidate)
            sink.checkpoint("external_general_ai_reasoning_reused",None)
            return {"status":"EXTERNAL_PROPOSAL_REUSED","proposal_ref":str(rel),
                    "request_id":request["request_id"],"provider":candidate["provider"]}
    token=token or os.environ.get("GITHUB_TOKEN") or os.environ.get("COPILOT_GITHUB_TOKEN")
    if not token:
        gate={"schema":"mxm.greenfield.general-ai-reasoning-external-gate.v1","status":"EXTERNAL_AUTHORIZATION_REQUIRED","provider":"github-copilot-cli","required":"GITHUB_TOKEN with copilot-requests: write and repository-owner Copilot access","request_id":request["request_id"],"created_utc":iso()}
        atomic_write_json(root/GATE_REL,gate); sink.checkpoint("general_ai_reasoning_external_gate",None)
        return gate

    context=_context_payload(root,request)
    prompt=_user_prompt(context)
    packet_doc=context.get("semantic_decision_packet") or {}
    observation={"schema":"mxm.greenfield.semantic-context-observability.v1",
                 "request_id":request["request_id"],
                 "request_fingerprint":request["request_id"],
                 "semantic_packet_bytes":len(canonical_bytes(packet_doc)),
                 "final_prompt_bytes":len(prompt.encode("utf-8")),
                 "validation_authority_ref_count":len(request.get("authority_refs") or []),
                 "semantic_context_ref_count":len(packet_doc.get("source_projections") or []),
                 "largest_embedded_context_items":sorted(
                     ({"ref":row["ref"],"bytes":len(canonical_bytes(row))}
                      for row in packet_doc.get("source_projections") or []),
                     key=lambda row:row["bytes"],reverse=True)[:8],
                 "transport_mode":"STDIN_PIPE","provider_process_started":False,
                 "provider_response_received":False,"provider_duration_seconds":None,
                 "provider_exit_code_or_failure_class":None}
    observation_path=root/"research_v3/ai_director/SEMANTIC_CONTEXT_OBSERVABILITY_V1.json"
    atomic_write_json(observation_path,observation)
    raw_path=root/RAW_CANDIDATE_DIR/f"{request['request_id']}.json"
    saved=json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.is_file() else {}
    if saved and (saved.get("request_id")!=request["request_id"] or saved.get("evidence_bundle_sha256")!=request.get("evidence_bundle_sha256")):
        raise AIProposalRejected("saved raw candidate has mismatched evidence binding")
    correction=None; errors=[]; chosen_meta=None; proposal=None
    model=os.environ.get("MXM_COPILOT_MODEL",DEFAULT_MODEL).strip() or DEFAULT_MODEL
    for attempt in range(1):
        try:
            if saved:
                candidate,meta=saved["candidate"],saved["provider_meta"]
            else:
                started=time.monotonic()
                try:
                    candidate,meta=transport(token,model,prompt if correction is None else _user_prompt(context,correction),root=root)
                except LocalPreProviderTransportFailure:
                    observation["provider_exit_code_or_failure_class"]="LOCAL_PRE_PROVIDER_TRANSPORT_FAILURE"
                    observation["provider_duration_seconds"]=round(time.monotonic()-started,3)
                    atomic_write_json(observation_path,observation)
                    raise
                observation.update(provider_process_started=True,provider_response_received=True,
                                   provider_duration_seconds=round(time.monotonic()-started,3),
                                   provider_exit_code_or_failure_class="SUCCESS")
                atomic_write_json(observation_path,observation)
                atomic_write_json(raw_path,{"request_id":request["request_id"],
                    "evidence_bundle_sha256":request.get("evidence_bundle_sha256"),
                    "candidate":candidate,"provider_meta":meta or {},"captured_utc":iso()})
                sink.checkpoint("general_ai_raw_candidate_before_routing",None)
            if candidate.get("status")=="ADDITIONAL_AUTHORITY_REQUIRED":
                requested=str(candidate.get("requested_authority_or_class") or "")[:220]
                rationale=str(candidate.get("rationale") or "")[:700]
                scope=str(candidate.get("blocked_scope_id") or "").strip()
                if not requested or not rationale:
                    raise AIProposalRejected("additional authority request lacks explicit ref/class or rationale")
                if scope and (scope not in request["current_open_mechanism_families"] or scope in request.get("blocked_scope_set",[])):
                    raise AIProposalRejected("additional authority blocked_scope_id is not a new open frontier family")
                requirement={"schema":"mxm.greenfield.additional-authority-request.v1",
                             "status":"ADDITIONAL_AUTHORITY_REQUIRED",
                             "requested_authority_or_class":requested,"rationale":rationale,
                             "request_id":request["request_id"],"evidence_epoch":request["evidence_epoch_seen"],
                             "no_economic_outcome":True,"created_utc":iso()}
                if scope:
                    requirement["blocked_scope_ids"]=[scope]
                response={"schema":"mxm.greenfield.general-ai-reasoning-response.v1",
                          "status":"ADDITIONAL_AUTHORITY_REQUIRED",
                          "request_id":request["request_id"],
                          "provider":{"kind":"github-copilot-cli",**dict(meta or {})},
                          "evidence_epoch_seen":request["evidence_epoch_seen"],
                          "requested_authority_or_class":requested,
                          "rationale":rationale,
                          "economic_outcome_opened":False,"v2_attempt_consumed":0,
                          "created_utc":requirement["created_utc"]}
                atomic_write_json(root/"research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json",requirement)
                atomic_write_json(root/RESPONSE_REL,response)
                sink.checkpoint("general_ai_additional_authority_request",None)
                return requirement
            candidate=_normalize_candidate_routing(request,candidate)
            proposal=_wrap(root,request,candidate,meta); chosen_meta=meta
            break
        except AIProposalRejected as exc:
            rejection={"schema":"mxm.greenfield.ai-proposal-eligibility-rejection.v1",
                       "status":"REJECTED_BEFORE_REGISTRY_AND_IMPLEMENTATION",
                       "reason":str(exc),"request_id":request["request_id"],
                       "evidence_epoch":request["evidence_epoch_seen"],
                       "economic_outcomes_opened_delta":0,"v2_attempts_consumed_delta":0,
                       "implementation_provider_calls":0,"created_utc":iso()}
            atomic_write_json(root/"research_v3/ai_director/PROPOSAL_ELIGIBILITY_REJECTION_V1.json",rejection)
            sink.checkpoint("general_ai_semantic_rejection",None)
            return rejection
        except AIReasoningExternalGate as exc:
            gate={"schema":"mxm.greenfield.general-ai-reasoning-external-gate.v1","status":"EXTERNAL_AUTHORIZATION_REQUIRED","provider":"github-copilot-cli","request_id":request["request_id"],"detail":str(exc),"created_utc":iso()}
            atomic_write_json(root/GATE_REL,gate); sink.checkpoint("general_ai_reasoning_external_gate",None)
            return gate
        except LocalPreProviderTransportFailure as exc:
            gate={"schema":"mxm.greenfield.general-ai-reasoning-external-gate.v1",
                  "status":"LOCAL_PRE_PROVIDER_TRANSPORT_FAILURE","request_id":request["request_id"],
                  "provider_process_started":False,"detail":str(exc),"created_utc":iso()}
            atomic_write_json(root/GATE_REL,gate)
            sink.checkpoint("general_ai_local_transport_failure",None)
            raise
        except Exception as exc:
            correction=f"{type(exc).__name__}: {exc}"
            errors.append({"model":model,"attempt":attempt+1,"error":correction})
            if "monthly quota" in correction.lower() or "exceeded your quota" in correction.lower():
                raise AIReasoningProviderError("monthly quota exhausted; no duplicate provider retries") from exc
    if proposal is None:
        gate={"schema":"mxm.greenfield.general-ai-reasoning-external-gate.v1","status":"PROVIDER_RETRY_REQUIRED","provider":"github-copilot-cli","request_id":request["request_id"],"errors":errors[-8:],"created_utc":iso()}
        atomic_write_json(root/GATE_REL,gate); sink.checkpoint("general_ai_reasoning_provider_retry",None)
        raise AIReasoningProviderError("all configured general reasoning attempts failed")

    try:
        validate_eligibility(proposal)
    except EvidenceIneligible as exc:
        rejection={"schema":"mxm.greenfield.ai-proposal-eligibility-rejection.v1",
                   "status":"REJECTED_BEFORE_REGISTRY_AND_IMPLEMENTATION",
                   "reason":str(exc),"request_id":request["request_id"],
                   "proposal_id":proposal.get("proposal_id"),
                   "evidence_epoch":request["evidence_epoch_seen"],
                   "economic_outcomes_opened_delta":0,"v2_attempts_consumed_delta":0,
                   "implementation_provider_calls":0,"created_utc":iso()}
        atomic_write_json(root/"research_v3/ai_director/PROPOSAL_ELIGIBILITY_REJECTION_V1.json",rejection)
        sink.checkpoint("general_ai_eligibility_rejection",None)
        return rejection
    path.parent.mkdir(parents=True,exist_ok=True)
    atomic_write_json(path,proposal)
    binding=proposal["evidence_binding"]; created=iso()
    response={"schema":"mxm.greenfield.general-ai-reasoning-response.v1","status":"PROPOSAL_GENERATED_PENDING_RUNTIME_V2_MATERIALIZATION",
              "request_id":request["request_id"],"response_id":binding["reasoning_response_id"],
              "proposal_ref":str(rel),"proposal_sha256":sha256_file(path),
              "provider":{"kind":"github-copilot-cli",**dict(chosen_meta or {})},
              "evidence_epoch_seen":binding["evidence_epoch_seen"],"evidence_bundle_sha256":binding["evidence_bundle_sha256"],
              "authoritative_evidence_refs_and_hashes":binding["authoritative_evidence_refs_and_hashes"],
              "accounting_basis":binding["accounting_basis"],"universe_basis":binding["universe_basis"],
              "current_open_mechanism_families":binding["current_open_mechanism_families"],
              "economic_outcome_opened":False,"v2_attempt_consumed":0,"created_utc":created}
    atomic_write_json(root/RESPONSE_REL,response)
    if (root/GATE_REL).exists():
        (root/GATE_REL).unlink()
    sink.checkpoint("general_ai_reasoning_response",None)
    return response

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=PROVIDER_VERSION)
    p.add_argument("command",choices=("request","wake"))
    p.add_argument("--root",default=".")
    p.add_argument("--git-checkpoint",action="store_true")
    p.add_argument("--git-push",action="store_true")
    a=p.parse_args(argv)
    if a.command=="request":
        payload=build_reasoning_request(a.root)
        atomic_write_json(Path(a.root)/REQUEST_REL,payload)
    else:
        payload=wake(a.root,git_checkpoint=a.git_checkpoint,git_push=a.git_push)
    print(json.dumps(payload,sort_keys=True,indent=2))
    return 0
if __name__=="__main__": raise SystemExit(main())
