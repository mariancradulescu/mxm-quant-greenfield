"""Zero-provider executor for explicitly authorized deterministic research operations."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

from research_v3.execution_router import (
    deterministic_operation_required, load_authorized_deterministic_operation, liveness_fingerprint,
)
from research_v3.frontier_information_gain import (
    CONTRACT_REL, FEATURE_REL, OPPORTUNITY_REL, SELECTOR_REL, ACQUISITION_REL,
    build_capture_contract, build_feature_store, build_opportunity_map,
    build_information_gain_selection, build_next_acquisition_plan,
)
from research_v3.general_ai_director_bridge import NEXT_STATE_REL, project_snapshot
from research_v3.evidence_epoch import advance_evidence_epoch
from research_v3.runtime_v2_primitives import GitCheckpointSink, atomic_write_json, load_json, iso, sha256_file

VERSION="MXM_DETERMINISTIC_OPERATION_EXECUTOR_V1"
ROUTING_REPAIR_REL=Path("research_v3/EPOCH21_DETERMINISTIC_ROUTING_REPAIR_V1.json")
EXECUTION_RECORD_REL=Path("research_v3/EPOCH21_DETERMINISTIC_OPERATION_EXECUTION_V1.json")
LAYER_OPERATION_REL=Path("research_v3/EPOCH21_FRONTIER_SELECTION_LAYER_OPERATION_V1.json")
DEDUP_REL=Path("research_v3/LIVENESS_DEDUP_V1.json")

class DeterministicOperationRejected(RuntimeError):
    pass

def _provider_count(root:Path)->int:
    doc=load_json(root/"research_v3/ai_director/PROVIDER_USAGE_V1.json",{}) or {}
    return int(doc.get("provider_invocations") or len(doc.get("invocations") or []))

def _publish_state(root:Path,state:dict[str,Any],before:dict[str,Any])->None:
    atomic_write_json(root/NEXT_STATE_REL,state)
    if project_snapshot(root)!=before:
        raise DeterministicOperationRejected("deterministic operation changed project economics/accounting")

def _execute_contract(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    contract=build_capture_contract(root)
    repair={
        "schema":"mxm.greenfield.deterministic-routing-repair.v1",
        "status":"REPAIRED_AND_SUPERSEDED_STALE_AI_IMPLEMENTATION_REQUEST",
        "evidence_epoch":21,
        "root_cause":"general_ai_implementation_executor.implementation_required treated any non-empty next_action as AI implementation authority and ignored the explicit deterministic execution_policy.",
        "stale_request_ref":"research_v3/ai_director/IMPLEMENTATION_REQUEST.json",
        "stale_request_preserved_for_audit":True,
        "provider_transport_reached":False,
        "copilot_provider_calls_delta":0,
        "correct_routing_order":[
            "MATERIAL_INTEGRITY_OR_EXTERNAL_GATE","FRESH_SEMANTIC_REASONING_IF_EXPLICITLY_REQUIRED",
            "AUTHORIZED_DETERMINISTIC_OPERATION","NOVEL_AI_IMPLEMENTATION_IF_EXPLICITLY_REQUIRED",
            "ECONOMIC_MATERIALIZATION_IF_AUTHORIZED","QUIESCENT",
        ],
        "current_operation":op["operation_name"],
        "capture_contract_ref":str(CONTRACT_REL),
        "recorded_utc":iso(),
    }
    atomic_write_json(root/ROUTING_REPAIR_REL,repair)
    state=dict(state)
    state.update({
        "status":"DETERMINISTIC_CAPTURE_CONTRACT_COMPLETE",
        "capture_contract_ref":str(CONTRACT_REL),
        "routing_repair_ref":str(ROUTING_REPAIR_REL),
        "next_action":"BUILD_FRONTIER_FEATURE_STORE_OPPORTUNITY_MAP_AND_INFORMATION_GAIN_SELECTOR",
        "next_deterministic_operation_ref":str(LAYER_OPERATION_REL),
        "deterministic_next_operation":{
            "operation_ref":str(LAYER_OPERATION_REL),
            "operation_name":"BUILD_FRONTIER_FEATURE_STORE_OPPORTUNITY_MAP_AND_INFORMATION_GAIN_SELECTOR",
            "implementation_ai_required":False,
            "copilot_reasoning_required":False,
            "v2_attempts":0,"economic_outcomes":0,
        },
        "research_judgment_required":False,
        "ai_reasoning_required":False,
        "external_data_required":False,
        "external_data_gate":None,
        "user_action_required":False,
        "implementation_ai_required":False,
    })
    return state

def _execute_selection_layer(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    fs=build_feature_store(root)
    om=build_opportunity_map(root)
    sel=build_information_gain_selection(root)
    plan=build_next_acquisition_plan(root)
    state=dict(state)
    state.update({
        "status":"INFORMATION_GAIN_ACQUISITION_PLAN_READY",
        "frontier_feature_store_ref":str(FEATURE_REL),
        "frontier_opportunity_map_ref":str(OPPORTUNITY_REL),
        "information_gain_selection_ref":str(SELECTOR_REL),
        "next_acquisition_plan_ref":str(ACQUISITION_REL),
        "next_action":"AWAIT_HASH_BOUND_STRUCTURAL_DERIVATIVE_OR_COMPACT_METADATA_REFRESH_1578",
        "next_deterministic_operation_ref":None,
        "deterministic_next_operation":None,
        "research_judgment_required":False,
        "ai_reasoning_required":False,
        "implementation_ai_required":False,
        "external_data_required":True,
        "user_action_required":True,
        "external_data_gate":{
            "classification":"READ_ONLY_BROKER_METADATA_OR_ACCEPTED_BYTE_RECOVERY_GATE",
            "primary":"RECOVER_ACCEPTED_HASH_BOUND_STRUCTURAL_DERIVATIVE_IF_USER_OR_DURABLE_EXTERNAL_BYTES_ARE_AVAILABLE",
            "fallback":"RUN_COMPACT_STRUCTURAL_METADATA_REFRESH_1578",
            "plan_ref":str(ACQUISITION_REL),
            "economic_outcomes_opened":0,
            "v2_attempts_consumed":0,
        },
        "selected_next_acquisition":sel["selected_next_acquisition"],
        "information_gain_summary":{
            "eligible_identities":fs["universe_identity_count"],
            "structural_metadata_known":fs["summary"]["structural_signature_known"],
            "structural_metadata_missing":fs["universe_identity_count"]-fs["summary"]["structural_signature_known"],
            "mechanism_layers":len(om["mechanism_layers"]),
        },
    })
    return state

def _execute_existing_structural_result(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    """Accept an already-materialized, explicitly bound non-economic structural result.

    This is deliberately generic: the operation document supplies the result ref,
    expected schema/family/source epoch and the fresh-reasoning transition.
    """
    result_ref=str(op.get("result_ref") or "").strip()
    if not result_ref or not (root/result_ref).is_file():
        raise DeterministicOperationRejected("structural result authority missing")
    result=dict(load_json(root/result_ref,{}) or {})
    expected=dict(op.get("result_validation") or {})
    if expected.get("schema") and result.get("schema")!=expected["schema"]:
        raise DeterministicOperationRejected("structural result schema mismatch")
    if expected.get("status") and result.get("status")!=expected["status"]:
        raise DeterministicOperationRejected("structural result status mismatch")
    if expected.get("family") and result.get("family")!=expected["family"]:
        raise DeterministicOperationRejected("structural result family mismatch")
    source_epoch=int(result.get("source_evidence_epoch") or result.get("evidence_epoch") or 0)
    if source_epoch!=int(op.get("evidence_epoch") or 0):
        raise DeterministicOperationRejected("structural result evidence epoch mismatch")
    effect=result.get("accounting_effect") or {}
    if any(int(effect.get(k) or 0)!=0 for k in ("v2_attempts_consumed","economic_outcomes_opened","search_budget_change")):
        raise DeterministicOperationRejected("structural result declares prohibited accounting effect")
    safety=result.get("safety") or {}
    if safety.get("protected_forward_opened") is not False or safety.get("live_orders_authorized") is not False:
        raise DeterministicOperationRejected("structural result crosses protected/live safety boundary")
    interpretation=result.get("interpretation_boundary") or {}
    if interpretation.get("economic_promotion_authorized") is not False:
        raise DeterministicOperationRejected("structural result attempts economic promotion")
    expected_sha=str(op.get("result_sha256") or "").strip()
    if expected_sha and sha256_file(root/result_ref)!=expected_sha:
        raise DeterministicOperationRejected("structural result hash mismatch")

    reason=str(op.get("acceptance_reason") or "").strip()
    if not reason:
        raise DeterministicOperationRejected("structural result operation missing acceptance_reason")
    epoch_doc=advance_evidence_epoch(
        root,
        event_class="MATERIAL_DEVELOPMENT_STRUCTURAL_EVIDENCE_ACCEPTED",
        refs=[result_ref],
        reason=reason,
        advanced_utc=iso(),
    )
    new_epoch=int(epoch_doc["current_epoch"])
    new_state=dict(state)
    new_state.update({
        "status":str(op.get("next_status") or "FRESH_GENERAL_AI_REASONING_REQUIRED_AFTER_DETERMINISTIC_STRUCTURAL_RESULT"),
        "next_action":str(op.get("next_reasoning_action") or "AI_INTERPRET_NEW_MATERIAL_STRUCTURAL_RESULT_AND_SELECT_HIGHEST_INFORMATION_LEGAL_NEXT_FRONTIER_ACTION"),
        "current_research_evidence_epoch":new_epoch,
        "evidence_epoch":new_epoch,
        "authorizing_evidence_epoch":new_epoch,
        "completed_family":result.get("family"),
        "completed_structural_report_ref":result_ref,
        "latest_material_structural_result_ref":result_ref,
        "family_result":op.get("family_result"),
        "result_sha256":sha256_file(root/result_ref),
        "next_deterministic_operation_ref":None,
        "deterministic_next_operation":None,
        "ai_reasoning_required":True,
        "research_judgment_required":True,
        "implementation_ai_required":False,
        "external_data_required":False,
        "external_data_gate":None,
        "external_gate":None,
        "user_action_required":False,
    })
    return new_state


def execute_one(root_value:str|Path=".",*,git_checkpoint:bool=False,git_push:bool=False)->dict[str,Any]:
    root=Path(root_value).resolve()
    state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
    if not deterministic_operation_required(root,state):
        return {"status":"NO_DETERMINISTIC_OPERATION_REQUIRED"}
    op=load_authorized_deterministic_operation(root,state)
    before=project_snapshot(root)
    provider_before=_provider_count(root)
    name=op["operation_name"]
    if op.get("materializer")=="ACCEPT_EXISTING_NON_ECONOMIC_STRUCTURAL_RESULT":
        new_state=_execute_existing_structural_result(root,state,op)
    elif name=="BUILD_READ_ONLY_ALL_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT":
        new_state=_execute_contract(root,state,op)
    elif name=="BUILD_FRONTIER_FEATURE_STORE_OPPORTUNITY_MAP_AND_INFORMATION_GAIN_SELECTOR":
        new_state=_execute_selection_layer(root,state,op)
    else:
        raise DeterministicOperationRejected(f"unsupported authorized deterministic materializer: {name}")
    _publish_state(root,new_state,before)
    fingerprint=liveness_fingerprint(root,new_state)
    atomic_write_json(root/DEDUP_REL,{
        "schema":"mxm.greenfield.liveness-dedup.v1",
        "status":"ACTIVE",
        "dedup_key_components":["evidence_epoch","next_action","relevant_authority_hashes","external_gate_state"],
        "last_completed_fingerprint":fingerprint,
        "last_completed_operation":name,
        "recorded_utc":iso(),
        "rule":"An identical completed liveness fingerprint must not create another material execution cycle.",
    })
    provider_after=_provider_count(root)
    if provider_after!=provider_before:
        raise DeterministicOperationRejected("deterministic operation changed provider invocation count")
    record=dict(load_json(root/EXECUTION_RECORD_REL,{}) or {})
    rows=list(record.get("operations") or [])
    rows.append({
        "operation_name":name,
        "evidence_epoch":op.get("evidence_epoch"),
        "completed_utc":iso(),
        "provider_invocations_before":provider_before,
        "provider_invocations_after":provider_after,
        "provider_calls_delta":provider_after-provider_before,
        "v2_attempts_delta":0,
        "economic_outcomes_delta":0,
        "resulting_status":new_state.get("status"),
        "resulting_next_action":new_state.get("next_action"),
    })
    atomic_write_json(root/EXECUTION_RECORD_REL,{
        "schema":"mxm.greenfield.deterministic-operation-execution-record.v1",
        "status":"PASS_ZERO_PROVIDER_ZERO_ECONOMIC_EFFECT",
        "executor_version":VERSION,
        "operations":rows,
    })
    if project_snapshot(root)!=before:
        raise DeterministicOperationRejected("execution record changed project economics/accounting")
    GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("deterministic_operation_chain",None)
    return {"status":"DETERMINISTIC_OPERATION_COMPLETE","operation_name":name,"next_state":new_state,"provider_calls_delta":0}

def execute_chain(root_value:str|Path=".",*,max_operations:int=8,git_checkpoint:bool=False,git_push:bool=False)->dict[str,Any]:
    root=Path(root_value).resolve(); completed=[]
    for _ in range(max_operations):
        state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
        if not deterministic_operation_required(root,state):
            break
        out=execute_one(root,git_checkpoint=False,git_push=False)
        completed.append(out["operation_name"])
    if completed:
        GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("deterministic_operation_chain",None)
    return {
        "status":"DETERMINISTIC_CHAIN_COMPLETE" if completed else "NO_DETERMINISTIC_OPERATION_REQUIRED",
        "completed_operations":completed,
        "next_state":dict(load_json(root/NEXT_STATE_REL,{}) or {}),
        "provider_calls_delta":0,
    }

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=VERSION)
    p.add_argument("command",choices=("execute","execute-chain"))
    p.add_argument("--root",default=".")
    p.add_argument("--max-operations",type=int,default=8)
    p.add_argument("--git-checkpoint",action="store_true")
    p.add_argument("--git-push",action="store_true")
    a=p.parse_args(argv)
    if a.command=="execute":
        out=execute_one(a.root,git_checkpoint=a.git_checkpoint,git_push=a.git_push)
    else:
        out=execute_chain(a.root,max_operations=a.max_operations,git_checkpoint=a.git_checkpoint,git_push=a.git_push)
    print(json.dumps(out,sort_keys=True,indent=2)); return 0

if __name__=="__main__":
    raise SystemExit(main())
