"""Zero-provider executor for explicitly authorized deterministic research operations."""
from __future__ import annotations
import argparse, base64, binascii, gzip, hashlib, importlib.util, json, lzma, os, subprocess
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

def _head(root:Path)->str:
    return subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()

def exact_head_green(root:Path)->dict[str,Any]:
    observed=_head(root)
    expected=os.environ.get("MXM_PREDECESSOR_CI_HEAD","").strip()
    conclusion=os.environ.get("MXM_PREDECESSOR_CI_CONCLUSION","").strip().lower()
    run_id=os.environ.get("MXM_PREDECESSOR_CI_RUN_ID","").strip()
    return {
        "green":bool(expected and conclusion=="success" and expected==observed),
        "head":observed,
        "predecessor_head":expected or None,
        "predecessor_conclusion":conclusion or None,
        "predecessor_run_id":int(run_id) if run_id.isdigit() else None,
    }

def _pending_exact_head(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]|None:
    policy=op.get("execution_policy") or {}
    if policy.get("exact_head_green_required_before_execution") is not True:
        return None
    proof=exact_head_green(root)
    if proof["green"]:
        return None
    return {
        "status":"PENDING_EXACT_HEAD_GREEN",
        "operation_name":op.get("operation_name"),
        "reason":"AUTHORIZED_DETERMINISTIC_OPERATION_AWAITS_EXACT_HEAD_FAST_CI",
        "exact_head":proof,
        "next_state":state,
        "provider_calls_delta":0,
        "state_persisted":False,
    }

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

def _validate_epoch47_compact_result(result:dict[str,Any])->None:
    if result.get("schema")!="mxm.greenfield.epoch47-mean-reversion-wave01-coarse-parameter-region-scan.v1":
        return
    if (result.get("status")!="COMPLETE_NON_ECONOMIC_MEAN_REVERSION_COARSE_PARAMETER_REGION_SCAN"
            or result.get("family")!="MEAN_REVERSION"
            or result.get("evidence_epoch")!=46
            or result.get("research_sequence_label")!="EPOCH47"):
        raise DeterministicOperationRejected("Epoch47 compact result identity mismatch")
    scope=result.get("scope") or {}
    grid=result.get("grid") or {}
    if (scope.get("resolution")!="M5"
            or scope.get("requested_identity_count")!=34
            or scope.get("identities_scanned")!=33
            or scope.get("authentic_zero_history_identities")!=["AMD.US-PERP"]
            or scope.get("total_m5_rows")!=305938
            or scope.get("development_only") is not True
            or scope.get("not_independent_confirmation") is not True):
        raise DeterministicOperationRejected("Epoch47 compact result scope mismatch")
    if (grid.get("lookback_bars")!=[12,24,48,96]
            or grid.get("absolute_standardized_deviation_thresholds")!=[1.0,1.5,2.0]
            or grid.get("cells_per_symbol")!=12
            or grid.get("symbol_cell_records")!=396
            or grid.get("all_probes_recorded") is not True
            or grid.get("winner_selection_performed") is not False):
        raise DeterministicOperationRejected("Epoch47 compact result grid mismatch")
    rows=result.get("symbols")
    if not isinstance(rows,list) or len(rows)!=396:
        raise DeterministicOperationRejected("Epoch47 compact result missing complete symbol-cell surface")
    coords=set(); symbols=set()
    for row in rows:
        if not isinstance(row,dict):
            raise DeterministicOperationRejected("Epoch47 compact cell is not an object")
        symbol=str(row.get("broker_symbol") or ""); lookback=row.get("lookback_bars")
        threshold=row.get("absolute_standardized_deviation_threshold")
        coord=(symbol,lookback,threshold)
        if (not symbol or coord in coords or lookback not in (12,24,48,96)
                or threshold not in (1.0,1.5,2.0)):
            raise DeterministicOperationRejected("Epoch47 compact result has duplicate or unfrozen cell")
        coords.add(coord); symbols.add(symbol)
        for key in ("eligible_contiguous_windows","reversal_event_count","date_cluster_count",
                    "dependence_adjusted_effective_date_clusters","positive_autocorrelation_lags"):
            value=row.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or value<0:
                raise DeterministicOperationRejected(f"Epoch47 compact cell invalid metric: {key}")
        rate=row.get("event_availability_rate")
        if rate is not None and (isinstance(rate,bool) or not isinstance(rate,(int,float)) or rate<0 or rate>1):
            raise DeterministicOperationRejected("Epoch47 compact cell invalid event availability rate")
        powers=row.get("closed_form_power_estimates")
        if not isinstance(powers,list) or [x.get("standardized_effect") for x in powers]!=[0.5,0.3,0.2]:
            raise DeterministicOperationRejected("Epoch47 compact cell power planning mismatch")
    if len(symbols)!=33:
        raise DeterministicOperationRejected("Epoch47 compact result identity breadth mismatch")
    expected={(symbol,lookback,threshold) for symbol in symbols for lookback in (12,24,48,96) for threshold in (1.0,1.5,2.0)}
    if coords!=expected:
        raise DeterministicOperationRejected("Epoch47 compact result incomplete frozen coordinates")
    boundary=result.get("interpretation_boundary") or {}
    if (boundary.get("event_availability_only") is not True
            or any(boundary.get(key) is not False for key in (
                "post_event_directional_or_return_response_computed","strategy_returns_computed",
                "pnl_computed","economic_outcome_opened","candidate_economic_identity_created",
                "winner_cell_or_symbol_selected","protected_forward_opened",
                "independent_confirmation_claimed","mechanism_family_closed",
                "economic_promotion_authorized"))):
        raise DeterministicOperationRejected("Epoch47 compact result crosses pre-response boundary")
    effect=result.get("accounting_effect") or {}
    if any(int(effect.get(key) or 0)!=0 for key in ("economic_outcomes_opened","v2_attempts_consumed","search_budget_change")):
        raise DeterministicOperationRejected("Epoch47 compact result changes accounting")
    safety=result.get("safety") or {}
    if any(safety.get(key) is not False for key in ("protected_forward_opened","live_orders_authorized","competition_start_authorized")):
        raise DeterministicOperationRejected("Epoch47 compact result crosses safety boundary")
    source=result.get("source_authority") or {}
    if (source.get("capture_outer_zip_sha256")!="bfdfcba4e70c699fa3719e15e01ed4f7a4542d7ed0e7439fd836133ab80d1ac1"
            or source.get("capture_canonical_payload_sha256")!="0305ca9d194300d28efde5b21aced13557e986d8d5476e3202ba66c8476774e2"
            or source.get("accepted_proposal_hash")!="453d0ddb418b21ae72107222f5219aea323161e7f37e4bdb65d7f963184f2edc"):
        raise DeterministicOperationRejected("Epoch47 compact result source authority mismatch")
    compact=result.get("transport_compaction") or {}
    if (compact.get("status")!="EXACT_METRIC_PRESERVING_COMPACTION_FROM_ACCEPTED_CAPTURE"
            or compact.get("per_utc_date_event_counts_used_for_effective_n_computation") is not True
            or compact.get("per_utc_date_event_count_vectors_omitted_from_durable_payload") is not True
            or compact.get("research_semantics_changed") is not False
            or compact.get("post_event_response_computed") is not False):
        raise DeterministicOperationRejected("Epoch47 compact transport semantics mismatch")


def _materialize_embedded_structural_result(root:Path,op:dict[str,Any])->str:
    """Materialize a hash-bound, transport-only JSON payload before deterministic acceptance."""
    payload_ref=str(op.get("payload_ref") or "").strip()
    payload_refs=op.get("payload_refs") or []
    result_ref=str(op.get("result_ref") or "").strip()
    if payload_ref and payload_refs:
        raise DeterministicOperationRejected("embedded structural result must use payload_ref or payload_refs, not both")
    if payload_refs:
        if not isinstance(payload_refs,list) or any(not isinstance(x,str) or not x for x in payload_refs):
            raise DeterministicOperationRejected("embedded structural result payload_refs invalid")
        pieces=[]
        for rel in payload_refs:
            path=root/rel
            if not path.is_file():
                raise DeterministicOperationRejected(f"embedded structural result payload fragment missing: {rel}")
            pieces.append(path.read_text(encoding="ascii").strip())
        encoded_payload="".join(pieces)
    elif payload_ref:
        payload_path=root/payload_ref
        if not payload_path.is_file():
            raise DeterministicOperationRejected("embedded structural result payload missing")
        encoded_payload=payload_path.read_text(encoding="ascii").strip()
    else:
        raise DeterministicOperationRejected("embedded structural result operation missing payload_ref/payload_refs")
    if not result_ref:
        raise DeterministicOperationRejected("embedded structural result operation missing result_ref")
    expected_payload_sha=str(op.get("payload_sha256") or "").strip()
    if expected_payload_sha:
        normalized_payload_sha=hashlib.sha256(encoded_payload.encode("ascii")).hexdigest()
        if normalized_payload_sha!=expected_payload_sha:
            raise DeterministicOperationRejected("embedded structural result payload hash mismatch")
    if op.get("payload_encoding")!="BASE64_GZIP_JSON":
        raise DeterministicOperationRejected("unsupported embedded structural result payload encoding")
    try:
        packed=base64.b64decode(encoded_payload,validate=True)
        decoded=gzip.decompress(packed)
        result=json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        raise DeterministicOperationRejected(f"embedded structural result payload decode failed: {exc}") from exc
    expected_decoded_sha=str(op.get("decoded_result_sha256") or "").strip()
    if expected_decoded_sha and hashlib.sha256(decoded).hexdigest()!=expected_decoded_sha:
        raise DeterministicOperationRejected("embedded structural result decoded JSON hash mismatch")
    if not isinstance(result,dict):
        raise DeterministicOperationRejected("embedded structural result payload must decode to a JSON object")
    _validate_epoch47_compact_result(result)
    for field,file_ref in dict(op.get("sha256_attestations") or {}).items():
        if not isinstance(field,str) or "." in field or not field:
            raise DeterministicOperationRejected("sha256 attestation field must be a simple top-level JSON field")
        bound=root/str(file_ref)
        if not bound.is_file():
            raise DeterministicOperationRejected(f"sha256 attestation authority missing: {file_ref}")
        result[field]=sha256_file(bound)
    atomic_write_json(root/result_ref,result)
    return result_ref

def verify_trend_surface(root:Path)->dict[str,Any]:
    """Reconstruct every frozen cell before accepting a TREND completion claim."""
    manifest=load_json(root/"evidence/EPOCH38_TREND_MOMENTUM_COARSE_PARAMETER_REGION_SURFACE_MANIFEST_V1.json",{}) or {}
    surface=manifest.get("surface") or {}
    ref=surface.get("transport_ref")
    if not isinstance(ref,str) or not ref.startswith("research_v3/runtime_v2_inputs/"):
        raise DeterministicOperationRejected("TREND transport authority missing")
    encoded=(root/ref).read_bytes()
    if hashlib.sha256(encoded).hexdigest()!=surface.get("transport_sha256"):
        raise DeterministicOperationRejected("TREND transport hash mismatch")
    try:
        compressed=base64.b64decode(encoded,validate=True)
        if not compressed.startswith(b"\xfd7zXZ\x00"):
            raise ValueError("XZ magic missing")
        decoded=lzma.decompress(compressed)
        compact=json.loads(decoded)
    except (ValueError, binascii.Error, lzma.LZMAError, json.JSONDecodeError) as exc:
        raise DeterministicOperationRejected("TREND full surface cannot be reconstructed") from exc
    if hashlib.sha256(decoded).hexdigest()!=surface.get("decoded_compact_json_sha256"):
        raise DeterministicOperationRejected("TREND decoded surface hash mismatch")
    columns=compact.get("columns")
    rows=compact.get("rows")
    if columns!=surface.get("columns") or not isinstance(rows,list) or len(rows)!=560:
        raise DeterministicOperationRejected("TREND full grid shape mismatch")
    coordinate=set()
    counts={symbol:0 for symbol in surface.get("symbols",[])}
    for row in rows:
        if not isinstance(row,list) or len(row)!=len(columns):
            raise DeterministicOperationRejected("TREND surface row shape mismatch")
        point=(row[0],row[2],row[3],row[4])
        if row[0] not in counts or point in coordinate:
            raise DeterministicOperationRejected("TREND duplicate or unfrozen symbol cell")
        counts[row[0]]+=1
        coordinate.add(point)
    if len(counts)!=7 or any(count!=80 for count in counts.values()):
        raise DeterministicOperationRejected("TREND symbol grid incomplete")
    expected={(symbol,lookback,threshold,hold) for symbol in counts
              for lookback in (12,24,48,96,192) for threshold in (0.5,1.0,1.5,2.0)
              for hold in ("15m","1h","4h","1d")}
    if coordinate!=expected:
        raise DeterministicOperationRejected("TREND frozen parameter coordinates mismatch")
    return {"rows":len(rows),"symbols":counts}

def _execute_existing_structural_result(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    """Accept an already-materialized, explicitly bound non-economic structural result.

    This is deliberately generic: the operation document supplies the result ref,
    expected schema/family/source epoch and the fresh-reasoning transition.
    """
    result_ref=str(op.get("result_ref") or "").strip()
    if not result_ref or not (root/result_ref).is_file():
        raise DeterministicOperationRejected("structural result authority missing")
    result=dict(load_json(root/result_ref,{}) or {})
    if result_ref=="evidence/EPOCH38_TREND_MOMENTUM_COARSE_PARAMETER_REGION_RESULT_V1.json":
        verify_trend_surface(root)
    expected=dict(op.get("result_validation") or {})
    if expected.get("schema") and result.get("schema")!=expected["schema"]:
        raise DeterministicOperationRejected("structural result schema mismatch")
    if expected.get("status") and result.get("status")!=expected["status"]:
        raise DeterministicOperationRejected("structural result status mismatch")
    if expected.get("family") and result.get("family")!=expected["family"]:
        raise DeterministicOperationRejected("structural result family mismatch")
    source_epoch=int(result.get("source_evidence_epoch") or result.get("evidence_epoch") or 0)
    operation_epoch=int(op.get("evidence_epoch") or 0)
    expected_result_epoch=int(expected.get("evidence_epoch") or operation_epoch)
    if source_epoch!=expected_result_epoch:
        raise DeterministicOperationRejected("structural result evidence epoch mismatch")
    if expected_result_epoch not in (operation_epoch,operation_epoch+1):
        raise DeterministicOperationRejected("structural result target epoch is not current or next evidence epoch")
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

def _run_epoch34_composite_screen(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    from research_v3.epoch34_composite_causal_ml_regime_screen import (
        evaluate as evaluate_epoch34,
        sha256_file as epoch34_sha256_file,
    )

    expected={
        "implementation_ref":"research_v3/epoch34_composite_causal_ml_regime_screen.py",
        "freeze_ref":"research_v3/EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_FRONTIER_FREEZE_V1.json",
        "registry_ref":"research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json",
        "development_zip_ref":"research_v3/runtime_v2_inputs/MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip",
        "replacement_zip_ref":"research_v3/runtime_v2_inputs/MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip",
        "result_ref":"evidence/EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_STRUCTURAL_RESULT_V1.json",
        "operation_name":"RUN_FROZEN_EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_SCREEN_ON_ACCEPTED_HASH_BOUND_CAPTURE_BYTES",
        "development_zip_sha256":"64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503",
        "replacement_zip_sha256":"d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75",
    }
    for field,value in expected.items():
        if op.get(field)!=value:
            raise DeterministicOperationRejected(f"Epoch34 operation authority mismatch: {field}")
    if op.get("materializer")!="RUN_FROZEN_EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_SCREEN":
        raise DeterministicOperationRejected("unsupported Epoch34 screen materializer")
    if op.get("evidence_epoch")!=33 or (op.get("result_validation") or {}).get("evidence_epoch")!=34:
        raise DeterministicOperationRejected("Epoch34 operation epoch binding mismatch")
    expected_validation={
        "schema":"mxm.greenfield.epoch34-composite-causal-ml-regime-structural-result.v1",
        "status":"COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "family":"CAUSAL_ML_PREDICTIVE_OR_STATE_MODEL_CONDITIONAL_ON_REGIME_CONTEXT",
        "evidence_epoch":34,
    }
    if op.get("operation_name")!=expected["operation_name"] or op.get("result_validation")!=expected_validation:
        raise DeterministicOperationRejected("Epoch34 operation result authority mismatch")
    policy=op.get("execution_policy") or {}
    if any(policy.get(field) is not False for field in (
        "implementation_ai_required","copilot_reasoning_required","new_semantic_judgment_required",
    )):
        raise DeterministicOperationRejected("Epoch34 operation is not explicitly deterministic and non-semantic")
    if policy.get("exact_head_green_required_before_execution") is not True:
        raise DeterministicOperationRejected("Epoch34 operation is missing its exact-head green prerequisite")
    if not exact_head_green(root)["green"]:
        raise DeterministicOperationRejected("Epoch34 screen execution is blocked until exact-head CI is green")
    freeze_path=root/expected["freeze_ref"]
    development_path=root/expected["development_zip_ref"]
    replacement_path=root/expected["replacement_zip_ref"]
    if not freeze_path.is_file():
        raise DeterministicOperationRejected("Epoch34 prospective freeze is missing")
    if not development_path.is_file() or not replacement_path.is_file():
        raise DeterministicOperationRejected(
            "accepted hash-bound capture bytes are not transport-materialized; no new market-data acquisition is required"
        )
    result=evaluate_epoch34(
        json.loads(freeze_path.read_text(encoding="utf-8")),
        development_path,
        replacement_path,
        root,
    )
    result["freeze_sha256"]=epoch34_sha256_file(freeze_path)
    atomic_write_json(root/expected["result_ref"],result)
    return _execute_existing_structural_result(root,state,op)

def _run_epoch35_unsigned_volatility_screen(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    from research_v3.breakout_unsigned_volatility_epoch35_screen import (
        evaluate as evaluate_epoch35,
        sha256_file as epoch35_sha256_file,
    )

    expected={
        "implementation_ref":"research_v3/breakout_unsigned_volatility_epoch35_screen.py",
        "freeze_ref":"research_v3/EPOCH35_BREAKOUT_UNSIGNED_VOLATILITY_FRONTIER_FREEZE_V1.json",
        "registry_ref":"research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json",
        "development_zip_ref":"research_v3/runtime_v2_inputs/MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip",
        "replacement_zip_ref":"research_v3/runtime_v2_inputs/MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip",
        "result_ref":"evidence/EPOCH35_BREAKOUT_UNSIGNED_VOLATILITY_PERSISTENCE_STRUCTURAL_RESULT_V1.json",
        "operation_name":"RUN_FROZEN_EPOCH35_BREAKOUT_UNSIGNED_VOLATILITY_SCREEN_ON_ACCEPTED_HASH_BOUND_CAPTURE_BYTES",
        "development_zip_sha256":"64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503",
        "replacement_zip_sha256":"d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75",
    }
    for field,value in expected.items():
        if op.get(field)!=value:
            raise DeterministicOperationRejected(f"Epoch35 operation authority mismatch: {field}")
    if op.get("materializer")!="RUN_FROZEN_EPOCH35_BREAKOUT_UNSIGNED_VOLATILITY_SCREEN":
        raise DeterministicOperationRejected("unsupported Epoch35 screen materializer")
    if op.get("evidence_epoch")!=34 or (op.get("result_validation") or {}).get("evidence_epoch")!=35:
        raise DeterministicOperationRejected("Epoch35 operation epoch binding mismatch")
    expected_validation={
        "schema":"mxm.greenfield.epoch35-breakout-unsigned-volatility-structural-result.v1",
        "status":"COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "family":"BREAKOUT_VOLATILITY_EXPANSION",
        "evidence_epoch":35,
    }
    if op.get("operation_name")!=expected["operation_name"] or op.get("result_validation")!=expected_validation:
        raise DeterministicOperationRejected("Epoch35 operation result authority mismatch")
    policy=op.get("execution_policy") or {}
    if any(policy.get(field) is not False for field in (
        "implementation_ai_required","copilot_reasoning_required","new_semantic_judgment_required",
    )):
        raise DeterministicOperationRejected("Epoch35 operation is not explicitly deterministic and non-semantic")
    if policy.get("exact_head_green_required_before_execution") is not True:
        raise DeterministicOperationRejected("Epoch35 operation is missing its exact-head green prerequisite")
    if not exact_head_green(root)["green"]:
        raise DeterministicOperationRejected("Epoch35 screen execution is blocked until exact-head CI is green")
    freeze_path=root/expected["freeze_ref"]
    development_path=root/expected["development_zip_ref"]
    replacement_path=root/expected["replacement_zip_ref"]
    if not freeze_path.is_file():
        raise DeterministicOperationRejected("Epoch35 prospective freeze is missing")
    result_path=root/expected["result_ref"]
    if result_path.is_file() and op.get("result_sha256"):
        # The complete result was computed on the exact accepted capture bytes
        # before transport. Git retains its hash-bound evidence even where CI
        # cannot access the large original archives.
        result=load_json(result_path,{}) or {}
        attestation=result.get("input_attestation") or {}
        if (sha256_file(result_path)!=op["result_sha256"]
                or attestation.get("development_zip_sha256")!=expected["development_zip_sha256"]
                or attestation.get("replacement_zip_sha256")!=expected["replacement_zip_sha256"]
                or result.get("freeze_sha256")!=epoch35_sha256_file(freeze_path)
                or result.get("scope",{}).get("all_41_processed_exactly_once") is not True
                or len(result.get("symbols") or {})!=41):
            raise DeterministicOperationRejected("Epoch35 precomputed result binding mismatch")
        if development_path.is_file() and replacement_path.is_file():
            recomputed=evaluate_epoch35(json.loads(freeze_path.read_text(encoding="utf-8")),development_path,replacement_path,root)
            recomputed["freeze_sha256"]=epoch35_sha256_file(freeze_path)
            if recomputed!=result:
                raise DeterministicOperationRejected("Epoch35 materialized result differs from recomputation")
    else:
        if not development_path.is_file() or not replacement_path.is_file():
            raise DeterministicOperationRejected(
                "accepted hash-bound capture bytes and precomputed result are absent"
            )
        result=evaluate_epoch35(json.loads(freeze_path.read_text(encoding="utf-8")),development_path,replacement_path,root)
        result["freeze_sha256"]=epoch35_sha256_file(freeze_path)
        atomic_write_json(result_path,result)
    return _execute_existing_structural_result(root,state,op)

def _run_epoch36_mean_reversion_magnitude_screen(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    from research_v3.mean_reversion_magnitude_epoch36_screen import (
        evaluate as evaluate_epoch36,
        sha256_file as epoch36_sha256_file,
    )
    from research_v3.breakout_unsigned_volatility_epoch35_screen import (
        DEVELOPMENT_SHA256,
        REPLACEMENT_SHA256,
    )

    expected={
        "implementation_ref":"research_v3/mean_reversion_magnitude_epoch36_screen.py",
        "freeze_ref":"research_v3/EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_FRONTIER_FREEZE_V1.json",
        "registry_ref":"research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json",
        "development_zip_ref":"research_v3/runtime_v2_inputs/MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip",
        "replacement_zip_ref":"research_v3/runtime_v2_inputs/MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip",
        "result_ref":"evidence/EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_STRUCTURAL_RESULT_V1.json",
        "operation_name":"RUN_FROZEN_EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_SCREEN_ON_ACCEPTED_HASH_BOUND_CAPTURE_BYTES",
        "development_zip_sha256":DEVELOPMENT_SHA256,
        "replacement_zip_sha256":REPLACEMENT_SHA256,
    }
    for field,value in expected.items():
        if op.get(field)!=value:
            raise DeterministicOperationRejected(f"Epoch36 operation authority mismatch: {field}")
    if op.get("materializer")!="RUN_FROZEN_EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_SCREEN":
        raise DeterministicOperationRejected("unsupported Epoch36 screen materializer")
    if op.get("evidence_epoch")!=35 or (op.get("result_validation") or {}).get("evidence_epoch")!=36:
        raise DeterministicOperationRejected("Epoch36 operation epoch binding mismatch")
    expected_validation={
        "schema":"mxm.greenfield.epoch36-mean-reversion-magnitude-persistence-structural-result.v1",
        "status":"COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "family":"MEAN_REVERSION",
        "evidence_epoch":36,
    }
    if op.get("operation_name")!=expected["operation_name"] or op.get("result_validation")!=expected_validation:
        raise DeterministicOperationRejected("Epoch36 operation result authority mismatch")
    policy=op.get("execution_policy") or {}
    if any(policy.get(field) is not False for field in (
        "implementation_ai_required","copilot_reasoning_required","new_semantic_judgment_required",
    )):
        raise DeterministicOperationRejected("Epoch36 operation is not explicitly deterministic and non-semantic")
    if policy.get("exact_head_green_required_before_execution") is not True:
        raise DeterministicOperationRejected("Epoch36 operation is missing its exact-head green prerequisite")
    if not exact_head_green(root)["green"]:
        raise DeterministicOperationRejected("Epoch36 screen execution is blocked until exact-head CI is green")

    freeze_path=root/expected["freeze_ref"]
    development_path=root/expected["development_zip_ref"]
    replacement_path=root/expected["replacement_zip_ref"]
    result_path=root/expected["result_ref"]
    if not freeze_path.is_file():
        raise DeterministicOperationRejected("Epoch36 prospective freeze is missing")
    if result_path.is_file():
        existing=load_json(result_path,{}) or {}
        attestation=existing.get("input_attestation") or {}
        if (not op.get("result_sha256") or sha256_file(result_path)!=op["result_sha256"]
                or existing.get("freeze_sha256")!=epoch36_sha256_file(freeze_path)
                or attestation.get("development_zip_sha256")!=DEVELOPMENT_SHA256
                or attestation.get("replacement_zip_sha256")!=REPLACEMENT_SHA256
                or attestation.get("protected_forward_rows_read")!=0
                or attestation.get("prior_epoch_screen_results_used_as_inputs") is not False
                or attestation.get("new_market_data_acquired") is not False
                or existing.get("scope",{}).get("all_41_processed_exactly_once") is not True
                or len(existing.get("symbols") or {})!=41):
            raise DeterministicOperationRejected("Epoch36 precomputed result binding mismatch")
        if development_path.is_file() and replacement_path.is_file():
            recomputed=evaluate_epoch36(
                json.loads(freeze_path.read_text(encoding="utf-8")),
                development_path,
                replacement_path,
                root,
            )
            recomputed["freeze_sha256"]=epoch36_sha256_file(freeze_path)
            if recomputed!=existing:
                raise DeterministicOperationRejected("Epoch36 materialized result differs from recomputation")
    else:
        if not development_path.is_file() or not replacement_path.is_file():
            raise DeterministicOperationRejected(
                "exact accepted hash-bound capture bytes are not transport-materialized; no new market-data acquisition is required"
            )
        result=evaluate_epoch36(
            json.loads(freeze_path.read_text(encoding="utf-8")),
            development_path,
            replacement_path,
            root,
        )
        result["freeze_sha256"]=epoch36_sha256_file(freeze_path)
        atomic_write_json(result_path,result)
    return _execute_existing_structural_result(root,state,op)

def _run_hash_bound_python_json_transform(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    contract=op.get("operation_contract") or {}
    if contract.get("kind")!="HASH_BOUND_PYTHON_JSON_TRANSFORM_V1":
        raise DeterministicOperationRejected("unsupported hash-bound deterministic transform contract")
    transport=contract.get("input_transport") or {}
    refs=transport.get("fragment_refs") or []
    hashes=transport.get("fragment_sha256") or []
    if len(refs)!=len(hashes) or not refs:
        raise DeterministicOperationRejected("invalid hash-bound transport fragment contract")
    pieces=[]
    for rel,expected in zip(refs,hashes):
        path=root/rel
        if not path.is_file():
            raise DeterministicOperationRejected(f"hash-bound input fragment missing: {rel}")
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:
            raise DeterministicOperationRejected(f"hash-bound input fragment mismatch: {rel}")
        try:
            pieces.append(raw.decode("ascii"))
        except UnicodeDecodeError as exc:
            raise DeterministicOperationRejected("hash-bound input fragment is not ASCII") from exc
    encoded="".join(pieces).encode("ascii")
    if hashlib.sha256(encoded).hexdigest()!=transport.get("concatenated_base64_sha256"):
        raise DeterministicOperationRejected("hash-bound concatenated transport mismatch")
    if transport.get("encoding")!="CONCAT_BASE64_GZIP_JSON":
        raise DeterministicOperationRejected("unsupported hash-bound input encoding")
    try:
        decoded=gzip.decompress(base64.b64decode(encoded,validate=True))
    except Exception as exc:
        raise DeterministicOperationRejected("hash-bound input transport cannot be decoded") from exc
    if hashlib.sha256(decoded).hexdigest()!=transport.get("decoded_json_sha256"):
        raise DeterministicOperationRejected("hash-bound decoded JSON mismatch")
    try:
        payload=json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        raise DeterministicOperationRejected("hash-bound decoded input is not valid JSON") from exc

    implementation_ref=str(contract.get("implementation_ref") or "")
    implementation_path=root/implementation_ref
    if not implementation_path.is_file():
        raise DeterministicOperationRejected("hash-bound transform implementation missing")
    data=implementation_path.read_bytes()
    git_blob=hashlib.sha1(f"blob {len(data)}\0".encode("ascii")+data).hexdigest()
    if git_blob!=contract.get("implementation_git_blob_sha1"):
        raise DeterministicOperationRejected("hash-bound transform implementation blob mismatch")
    callable_name=str(contract.get("callable") or "")
    spec=importlib.util.spec_from_file_location(
        "mxm_hash_bound_transform_"+git_blob[:12], implementation_path
    )
    if spec is None or spec.loader is None:
        raise DeterministicOperationRejected("cannot load hash-bound transform implementation")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    transform=getattr(module,callable_name,None)
    if not callable(transform):
        raise DeterministicOperationRejected("hash-bound transform callable missing")
    kwargs=dict(contract.get("call_kwargs") or {})
    try:
        result=transform(payload,**kwargs)
    except Exception as exc:
        raise DeterministicOperationRejected(f"hash-bound transform rejected accepted input: {exc}") from exc
    if not isinstance(result,dict):
        raise DeterministicOperationRejected("hash-bound transform result must be an object")

    output=contract.get("output") or {}
    if result.get("schema")!=output.get("expected_schema") or result.get("status")!=output.get("expected_status"):
        raise DeterministicOperationRejected("hash-bound transform result schema/status mismatch")
    expected_count=int(output.get("expected_indexed_identity_count") or 0)
    source_universe=result.get("source_universe") or {}
    coverage=result.get("coverage") or {}
    if (int(source_universe.get("indexed_identity_count") or 0)!=expected_count
            or int(coverage.get("cohort_breadth_total") or 0)!=expected_count):
        raise DeterministicOperationRejected("hash-bound transform did not process the full authorized universe")
    boundary=result.get("interpretation_boundary") or {}
    if (boundary.get("strategy_or_price_outcome_evaluated") is not False
            or boundary.get("returns_or_pnl_computed") is not False
            or boundary.get("economic_equivalence_claimed") is not False
            or boundary.get("protected_forward_opened") is not False
            or int(boundary.get("economic_outcomes_opened") or 0)!=0
            or int(boundary.get("v2_attempts_consumed") or 0)!=0):
        raise DeterministicOperationRejected("hash-bound transform crossed non-economic interpretation boundary")
    policy=result.get("cohort_policy") or {}
    if policy.get("structural_representatives_used_as_substitutes") is not False:
        raise DeterministicOperationRejected("hash-bound transform substituted structural representatives")

    output_ref=str(output.get("ref") or "")
    output_path=root/output_ref
    if not output_ref.startswith("evidence/"):
        raise DeterministicOperationRejected("hash-bound transform output path is not evidence-scoped")
    if output_path.is_file():
        existing=json.loads(output_path.read_text(encoding="utf-8"))
        if existing!=result:
            raise DeterministicOperationRejected("existing deterministic output differs from recomputation")
    else:
        atomic_write_json(output_path,result)

    new_state=dict(state)
    new_state.update(dict(op.get("post_execution_state") or {}))
    new_state.update({
        "next_deterministic_operation_ref":None,
        "deterministic_next_operation":None,
        "transport_materialization_required":False,
        "implementation_ai_required":False,
        "implementation_satisfied":True,
        "implementation_scope_complete":True,
        "peer_cohort_index_ref":output_ref,
        "peer_cohort_index_sha256":sha256_file(output_path),
        "peer_cohort_index_identity_count":expected_count,
        "peer_cohort_index_transport_decoded_sha256":transport.get("decoded_json_sha256"),
    })
    return new_state



def _execute_epoch38_alignment_readiness(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    """Validate the already-frozen Epoch38 scope and emit a non-economic readiness artifact."""
    if op.get("materializer")!="EMIT_EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_READINESS":
        raise DeterministicOperationRejected("unsupported Epoch38 readiness materializer")
    if op.get("freeze_ref")!="research_v3/EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_SCOPE_FREEZE_V1.json":
        raise DeterministicOperationRejected("Epoch38 readiness freeze authority mismatch")
    output_ref=str(op.get("output_ref") or "")
    if output_ref!="research_v3/EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_ACQUISITION_READINESS_V1.json":
        raise DeterministicOperationRejected("Epoch38 readiness output authority mismatch")
    from research_v3.epoch38_cross_sectional_aligned_history_scope_freeze import emit_readiness
    readiness=emit_readiness(root)
    if readiness.get("status")!="READY_FOR_FRESH_SEMANTIC_ACQUISITION_DECISION":
        raise DeterministicOperationRejected("Epoch38 readiness validator returned unexpected status")
    new_state=dict(state)
    new_state.update(dict(op.get("post_execution_state") or {}))
    new_state.update({
        "epoch38_alignment_readiness_ref":output_ref,
        "epoch38_alignment_readiness_status":readiness["status"],
        "next_deterministic_operation_ref":None,
        "deterministic_next_operation":None,
        "implementation_ai_required":False,
        "implementation_satisfied":True,
        "implementation_scope_complete":True,
        "external_data_required":False,
        "external_data_gate":None,
        "external_gate":None,
        "user_action_required":False,
    })
    return new_state

def _run_epoch41_regime_context_cohort_preflight(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    expected={
        "operation_name":"RUN_EPOCH41_REGIME_CONTEXT_COHORT_POWER_PREFLIGHT",
        "implementation_ref":"research_v3/regime_context_cohort_power_preflight.py",
        "freeze_ref":"research_v3/EPOCH41_REGIME_CONTEXT_COHORT_POWER_PREFLIGHT_FREEZE_V1.json",
        "result_ref":"evidence/EPOCH41_REGIME_CONTEXT_COHORT_POWER_PREFLIGHT_V1.json",
    }
    if op.get("materializer")!="RUN_EPOCH41_REGIME_CONTEXT_COHORT_POWER_PREFLIGHT":
        raise DeterministicOperationRejected("unsupported Epoch41 cohort preflight materializer")
    for field,value in expected.items():
        if op.get(field)!=value:
            raise DeterministicOperationRejected(f"Epoch41 operation authority mismatch: {field}")
    if op.get("evidence_epoch")!=41 or op.get("result_validation")!={
        "schema":"mxm.greenfield.epoch41-regime-context-cohort-power-preflight.v1",
        "status":"COMPLETE_NON_ECONOMIC_COHORT_POWER_PREFLIGHT",
        "evidence_epoch":41,
    }:
        raise DeterministicOperationRejected("Epoch41 result authority mismatch")
    policy=op.get("execution_policy") or {}
    if any(policy.get(field) is not False for field in (
        "implementation_ai_required","copilot_reasoning_required","new_semantic_judgment_required",
    )) or policy.get("exact_head_green_required_before_execution") is not True:
        raise DeterministicOperationRejected("Epoch41 operation is not explicitly deterministic and non-semantic")
    from research_v3.regime_context_cohort_power_preflight import build_preflight
    result=build_preflight(root)
    if (
        result.get("freeze_sha256")!=sha256_file(root/expected["freeze_ref"])
        or result.get("sampling_frame",{}).get("structural_41_used_as_inferential_universe") is not False
        or result.get("sampling_frame",{}).get("selected_inferential_identity_count") is not None
        or result.get("interpretation_boundary",{}).get("relative_value_alignment_inventory_recomputed") is not False
        or any(int((result.get("accounting_effect") or {}).get(key) or 0)!=0 for key in (
            "economic_outcomes_opened","v2_attempts_consumed","search_budget_change",
        ))
        or result.get("safety",{}).get("protected_forward_opened") is not False
        or result.get("safety",{}).get("live_orders_authorized") is not False
    ):
        raise DeterministicOperationRejected("Epoch41 preflight result crossed its frozen boundary")
    result_path=root/expected["result_ref"]
    if result_path.is_file():
        if load_json(result_path,{})!=result:
            raise DeterministicOperationRejected("existing Epoch41 preflight differs from recomputation")
    else:
        atomic_write_json(result_path,result)
    return _execute_existing_structural_result(root,state,op)

def _run_epoch42_mean_reversion_cohort_preflight(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    expected={
        "operation_name":"RUN_EPOCH42_MEAN_REVERSION_COHORT_POWER_PREFLIGHT",
        "implementation_ref":"research_v3/mean_reversion_hypothesis_power_preflight.py",
        "freeze_ref":"research_v3/EPOCH42_MEAN_REVERSION_COHORT_POWER_PREFLIGHT_FREEZE_V1.json",
        "accepted_proposal_ref":"research_v3/ai_director/proposals/AUTO_reason_e32a4b75e24fa8b92aaa3effdce7d093.json",
        "result_ref":"evidence/EPOCH42_MEAN_REVERSION_COHORT_POWER_PREFLIGHT_V1.json",
        "accepted_proposal_file_sha256":"c590959baabd63a15a93b9c675cc08c3e727e31a0ab9634dfe06a08e80d56875",
        "accepted_proposal_hash":"7792544546520fe7db374a8654036c452f70b009aa50491c1245edd760eaf3ad",
    }
    if op.get("materializer")!="RUN_EPOCH42_MEAN_REVERSION_COHORT_POWER_PREFLIGHT":
        raise DeterministicOperationRejected("unsupported Epoch42 mean-reversion preflight materializer")
    for field,value in expected.items():
        if op.get(field)!=value:
            raise DeterministicOperationRejected(f"Epoch42 operation authority mismatch: {field}")
    expected_validation={
        "schema":"mxm.greenfield.epoch42-mean-reversion-cohort-power-preflight.v1",
        "status":"COMPLETE_NON_ECONOMIC_HYPOTHESIS_AND_POWER_PREFLIGHT",
        "family":"MEAN_REVERSION",
        "evidence_epoch":42,
    }
    if op.get("evidence_epoch")!=42 or op.get("result_validation")!=expected_validation:
        raise DeterministicOperationRejected("Epoch42 result authority mismatch")
    policy=op.get("execution_policy") or {}
    if any(policy.get(field) is not False for field in (
        "implementation_ai_required","copilot_reasoning_required","new_semantic_judgment_required",
        "new_market_data_required",
    )) or policy.get("exact_head_green_required_before_execution") is not True:
        raise DeterministicOperationRejected("Epoch42 operation is not explicitly deterministic and non-economic")
    from research_v3.mean_reversion_hypothesis_power_preflight import build_preflight
    result=build_preflight(root)
    if (
        result.get("freeze_sha256")!=sha256_file(root/expected["freeze_ref"])
        or result.get("sampling_frame",{}).get("structural_41_used_as_inferential_universe") is not False
        or result.get("sampling_frame",{}).get("selected_inferential_cohort") is not None
        or result.get("power_preflight",{}).get("response_statistics_computed") is not False
        or result.get("novelty_audit",{}).get("prior_results_read") is not False
        or any(int((result.get("accounting_effect") or {}).get(key) or 0)!=0 for key in (
            "economic_outcomes_opened","v2_attempts_consumed","search_budget_change",
        ))
        or result.get("safety",{}).get("protected_forward_opened") is not False
        or result.get("safety",{}).get("live_orders_authorized") is not False
    ):
        raise DeterministicOperationRejected("Epoch42 preflight result crossed its frozen boundary")
    result_path=root/expected["result_ref"]
    if result_path.is_file():
        if load_json(result_path,{})!=result:
            raise DeterministicOperationRejected("existing Epoch42 preflight differs from recomputation")
    else:
        atomic_write_json(result_path,result)
    return _execute_existing_structural_result(root,state,op)

def _run_epoch43_mean_reversion_power_aware_discovery(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    expected={
        "operation_name":"RUN_EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY",
        "implementation_ref":"research_v3/mean_reversion_power_aware_discovery.py",
        "freeze_ref":"research_v3/EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY_FREEZE_V1.json",
        "accepted_proposal_ref":"research_v3/ai_director/proposals/AUTO_reason_22da232dfe8db8062f3951c98cadda8e.json",
        "result_ref":"evidence/EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY_V1.json",
        "accepted_proposal_file_sha256":"efa2306ee44e558711eac4db63aa09b037c460045c9f81b26b8dddf69e5d6151",
        "accepted_proposal_hash":"a089ac3cdc3763ef8311a0eaad7d5e4e09fb63e73bdc2bb46b7fd175321084e2",
    }
    if op.get("materializer")!="RUN_EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY":
        raise DeterministicOperationRejected("unsupported Epoch43 mean-reversion discovery materializer")
    for field,value in expected.items():
        if op.get(field)!=value:
            raise DeterministicOperationRejected(f"Epoch43 operation authority mismatch: {field}")
    expected_validation={
        "schema":"mxm.greenfield.epoch43-mean-reversion-power-aware-discovery.v1",
        "status":"COMPLETE_NON_ECONOMIC_POWER_AWARE_DISCOVERY_PREFLIGHT",
        "family":"MEAN_REVERSION",
        "evidence_epoch":43,
    }
    if op.get("evidence_epoch")!=43 or op.get("result_validation")!=expected_validation:
        raise DeterministicOperationRejected("Epoch43 result authority mismatch")
    policy=op.get("execution_policy") or {}
    if any(policy.get(field) is not False for field in (
        "implementation_ai_required","copilot_reasoning_required","new_semantic_judgment_required",
        "new_market_data_required",
    )) or policy.get("exact_head_green_required_before_execution") is not True:
        raise DeterministicOperationRejected("Epoch43 operation is not explicitly deterministic and non-economic")
    from research_v3.mean_reversion_power_aware_discovery import build_preflight
    result=build_preflight(root)
    if (
        result.get("freeze_sha256")!=sha256_file(root/expected["freeze_ref"])
        or result.get("sampling_frame",{}).get("eligible_identity_count")!=1576
        or result.get("sampling_frame",{}).get("selected_inferential_cohort") is not None
        or result.get("sampling_frame",{}).get("structural_41_used_as_inferential_universe") is not False
        or result.get("cohort_decision",{}).get("selected") is not False
        or result.get("accepted_data_coverage",{}).get("absence_claim_for_other_capture_scopes") is not False
        or result.get("power_preflight",{}).get("epoch42_diagnostic_rerun") is not False
        or result.get("power_preflight",{}).get("response_statistics_computed") is not False
        or result.get("interpretation_boundary",{}).get("returns_or_pnl_computed") is not False
        or result.get("interpretation_boundary",{}).get("economic_outcome_opened") is not False
        or result.get("interpretation_boundary",{}).get("relative_value_alignment_inventory_recomputed") is not False
        or any(int((result.get("accounting_effect") or {}).get(key) or 0)!=0 for key in (
            "economic_outcomes_opened","v2_attempts_consumed","search_budget_change",
        ))
        or result.get("safety",{}).get("protected_forward_opened") is not False
        or result.get("safety",{}).get("live_orders_authorized") is not False
        or result.get("safety",{}).get("competition_start_authorized") is not False
    ):
        raise DeterministicOperationRejected("Epoch43 discovery preflight crossed its frozen boundary")
    result_path=root/expected["result_ref"]
    if result_path.is_file():
        if load_json(result_path,{})!=result:
            raise DeterministicOperationRejected("existing Epoch43 discovery preflight differs from recomputation")
    else:
        atomic_write_json(result_path,result)
    return _execute_existing_structural_result(root,state,op)

def _run_epoch45_mean_reversion_capture_scope_audit(root:Path,state:dict[str,Any],op:dict[str,Any])->dict[str,Any]:
    expected={
        "operation_name":"RUN_MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45",
        "materializer":"RUN_MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45",
        "evidence_epoch":44,
        "freeze_ref":"research_v3/MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45_FREEZE_V1.json",
        "implementation_ref":"research_v3/mean_reversion_capture_scope_audit.py",
        "result_ref":"evidence/MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45_V1.json",
        "accepted_proposal_ref":"research_v3/ai_director/proposals/AUTO_reason_538b7957124ef714729f7ac22553ee30.json",
        "accepted_proposal_file_sha256":"b1cee8481beb44a69a1e77aaadf6db19c7045db818266b0939be12544b8c6fc5",
        "accepted_proposal_hash":"766dcafc60825666a7ce2f394091ca5172c62b64d2f43f8d21bc47faae36c1cc",
    }
    for field,value in expected.items():
        if op.get(field)!=value:
            raise DeterministicOperationRejected(f"Epoch45 scope-audit authority mismatch: {field}")
    expected_validation={
        "schema":"mxm.greenfield.mean-reversion-capture-scope-audit-epoch45.v1",
        "status":"COMPLETE_NON_ECONOMIC_SCOPE_RECONCILIATION_NO_COHORT_OR_ACQUISITION_AUTHORIZED",
        "evidence_epoch":45,
    }
    if op.get("result_validation")!=expected_validation:
        raise DeterministicOperationRejected("Epoch45 scope-audit result authority mismatch")
    policy=op.get("execution_policy") or {}
    if any(policy.get(field) is not False for field in (
        "implementation_ai_required","copilot_reasoning_required",
        "new_semantic_judgment_required","new_market_data_required",
    )) or policy.get("exact_head_green_required_before_execution") is not True:
        raise DeterministicOperationRejected("Epoch45 scope audit is not explicitly deterministic and non-economic")
    from research_v3.mean_reversion_capture_scope_audit import build_scope_audit
    result=build_scope_audit(root)
    if (
        result.get("schema")!=expected_validation["schema"]
        or result.get("status")!=expected_validation["status"]
        or result.get("eligible_frame",{}).get("eligible_identity_count")!=1576
        or result.get("disjoint_increment",{}).get("smallest_increment_selected") is not False
        or result.get("disjoint_increment",{}).get("exact_symbols_selected")!=[]
        or result.get("disjoint_increment",{}).get("new_market_data_requested_or_authorized") is not False
        or result.get("interpretation_boundary",{}).get("strategy_events_or_response_statistics_computed") is not False
        or result.get("interpretation_boundary",{}).get("returns_or_pnl_computed") is not False
        or result.get("interpretation_boundary",{}).get("economic_outcome_opened") is not False
        or result.get("interpretation_boundary",{}).get("relative_value_alignment_inventory_recomputed") is not False
        or any(int((result.get("accounting_effect") or {}).get(key) or 0)!=0 for key in (
            "economic_outcomes_opened","v2_attempts_consumed","search_budget_change",
        ))
        or result.get("safety",{}).get("protected_forward_opened") is not False
        or result.get("safety",{}).get("live_orders_authorized") is not False
        or result.get("safety",{}).get("competition_start_authorized") is not False
    ):
        raise DeterministicOperationRejected("Epoch45 scope audit crossed its frozen boundary")
    result_path=root/expected["result_ref"]
    if result_path.is_file():
        if load_json(result_path,{})!=result:
            raise DeterministicOperationRejected("existing Epoch45 scope audit differs from recomputation")
    else:
        atomic_write_json(result_path,result)
    new_state=dict(state)
    new_state.update({
        "status":"MEAN_REVERSION_SCOPE_AUDIT_COMPLETE_PROSPECTIVE_SCOPE_JUDGMENT_REQUIRED",
        "mean_reversion_capture_scope_audit_ref":expected["result_ref"],
        "mean_reversion_capture_scope_audit_sha256":sha256_file(result_path),
        "next_action":"DECIDE_IF_MINIMAL_DISJOINT_MEAN_REVERSION_M5_DATA_SCOPE_IS_JUSTIFIED",
        "next_deterministic_operation_ref":None,
        "deterministic_next_operation":None,
        "research_judgment_required":True,
        "ai_reasoning_required":True,
        "external_data_required":False,
        "external_data_gate":None,
        "user_action_required":False,
        "implementation_ai_required":False,
        "implementation_satisfied":True,
        "implementation_scope_complete":True,
    })
    return new_state

def execute_one(root_value:str|Path=".",*,git_checkpoint:bool=False,git_push:bool=False)->dict[str,Any]:
    root=Path(root_value).resolve()
    state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
    if not deterministic_operation_required(root,state):
        return {"status":"NO_DETERMINISTIC_OPERATION_REQUIRED"}
    op=load_authorized_deterministic_operation(root,state)
    if op.get("materializer")=="RUN_REGIME_CONTEXT_DATA_SUFFICIENCY_AUDIT":
        missing=[ref for ref in (op["development_zip_ref"],op["replacement_zip_ref"]) if not (root/ref).is_file()]
        recovery=dict(op.get("recovery_transport") or {})
        recovery_payload_ref=str(recovery.get("payload_ref") or "").strip()
        recovery_ready=bool(
            missing
            and recovery.get("classification")=="RECOVERED_ALREADY_ACCEPTED_HASH_BOUND_RESULT_TRANSPORT"
            and recovery.get("encoding")=="BASE64_GZIP_JSON"
            and recovery_payload_ref
            and (root/recovery_payload_ref).is_file()
        )
        if missing and not recovery_ready:
            return {"status":"PENDING_ACCEPTED_CAPTURE_BYTES","operation_name":op["operation_name"],
                    "missing_refs":missing,"expected_sha256":{
                        op["development_zip_ref"]:op["development_zip_sha256"],
                        op["replacement_zip_ref"]:op["replacement_zip_sha256"]},
                    "next_state":state,"provider_calls_delta":0,"state_persisted":False}
    pending=_pending_exact_head(root,state,op)
    if pending is not None:
        return pending
    before=project_snapshot(root)
    provider_before=_provider_count(root)
    name=op["operation_name"]
    if (op.get("operation_contract") or {}).get("kind")=="HASH_BOUND_PYTHON_JSON_TRANSFORM_V1":
        new_state=_run_hash_bound_python_json_transform(root,state,op)
    elif name=="RUN_AUTHORIZED_DETERMINISTIC_OPERATION_AFTER_EXACT_HEAD_GREEN":
        new_state=_execute_epoch38_alignment_readiness(root,state,op)
    elif op.get("materializer")=="MATERIALIZE_BASE64_GZIP_NON_ECONOMIC_STRUCTURAL_RESULT":
        _materialize_embedded_structural_result(root,op)
        new_state=_execute_existing_structural_result(root,state,op)
    elif op.get("materializer")=="ACCEPT_EXISTING_NON_ECONOMIC_STRUCTURAL_RESULT":
        new_state=_execute_existing_structural_result(root,state,op)
    elif op.get("materializer")=="RUN_FROZEN_EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_SCREEN":
        new_state=_run_epoch34_composite_screen(root,state,op)
    elif op.get("materializer")=="RUN_FROZEN_EPOCH35_BREAKOUT_UNSIGNED_VOLATILITY_SCREEN":
        new_state=_run_epoch35_unsigned_volatility_screen(root,state,op)
    elif op.get("materializer")=="RUN_FROZEN_EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_SCREEN":
        new_state=_run_epoch36_mean_reversion_magnitude_screen(root,state,op)
    elif op.get("materializer")=="RUN_REGIME_CONTEXT_DATA_SUFFICIENCY_AUDIT":
        from research_v3.regime_context_data_sufficiency_audit import evaluate, sha256_file
        freeze_path=root/op["freeze_ref"]
        registry_path=root/op["registry_ref"]
        development_path=root/op["development_zip_ref"]
        replacement_path=root/op["replacement_zip_ref"]
        if development_path.is_file() and replacement_path.is_file():
            result=evaluate(json.loads(freeze_path.read_text(encoding="utf-8")),registry_path,development_path,replacement_path)
            result["freeze_sha256"]=sha256_file(freeze_path)
        else:
            recovery=dict(op.get("recovery_transport") or {})
            payload_ref=str(recovery.get("payload_ref") or "").strip()
            attestation_ref=str(recovery.get("accepted_byte_recovery_attestation_ref") or "").strip()
            if (recovery.get("classification")!="RECOVERED_ALREADY_ACCEPTED_HASH_BOUND_RESULT_TRANSPORT"
                    or recovery.get("encoding")!="BASE64_GZIP_JSON" or not payload_ref or not attestation_ref):
                raise DeterministicOperationRejected("accepted REGIME bytes missing and no authorized exact-result recovery transport exists")
            payload_path=root/payload_ref
            attestation_path=root/attestation_ref
            if not payload_path.is_file() or not attestation_path.is_file():
                raise DeterministicOperationRejected("REGIME recovery transport or accepted-byte attestation is missing")
            expected_payload_length=recovery.get("payload_text_length_bytes")
            if expected_payload_length is not None and payload_path.stat().st_size!=int(expected_payload_length):
                raise DeterministicOperationRejected("REGIME recovery transport length mismatch")
            if sha256_file(payload_path)!=recovery.get("payload_transport_sha256"):
                raise DeterministicOperationRejected("REGIME recovery transport hash mismatch")
            try:
                encoded=payload_path.read_text(encoding="ascii").strip()
                decoded=gzip.decompress(base64.b64decode(encoded,validate=True))
                result=json.loads(decoded.decode("utf-8"))
            except (ValueError,UnicodeError,binascii.Error,OSError,json.JSONDecodeError) as exc:
                raise DeterministicOperationRejected("REGIME recovery transport decode failed") from exc
            if hashlib.sha256(decoded).hexdigest()!=recovery.get("decoded_result_sha256"):
                raise DeterministicOperationRejected("REGIME recovered deterministic result hash mismatch")
            byte_attestation=dict(load_json(attestation_path,{}) or {})
            if byte_attestation.get("status")!="EXACT_ACCEPTED_BYTES_RECOVERED_AND_USED_FOR_DETERMINISTIC_AUDIT":
                raise DeterministicOperationRejected("REGIME accepted-byte recovery attestation is not accepted")
            input_attestation=result.get("input_attestation") or {}
            if (input_attestation.get("development_zip_sha256")!=op["development_zip_sha256"]
                    or input_attestation.get("replacement_zip_sha256")!=op["replacement_zip_sha256"]
                    or input_attestation.get("all_41_representatives_processed_exactly_once") is not True
                    or input_attestation.get("protected_forward_rows_read")!=0
                    or result.get("freeze_sha256")!=sha256_file(freeze_path)):
                raise DeterministicOperationRejected("REGIME recovered result does not attest the exact frozen accepted inputs")
        atomic_write_json(root/op["result_ref"],result)
        new_state=_execute_existing_structural_result(root,state,op)
    elif op.get("materializer")=="RUN_EPOCH39_MEAN_REVERSION_SCOPE_POWER_PREFLIGHT":
        from research_v3.mean_reversion_scope_power_preflight import build_preflight
        result=build_preflight(root)
        atomic_write_json(root/op["result_ref"],result)
        new_state=_execute_existing_structural_result(root,state,op)
    elif op.get("materializer")=="RUN_EPOCH41_REGIME_CONTEXT_COHORT_POWER_PREFLIGHT":
        new_state=_run_epoch41_regime_context_cohort_preflight(root,state,op)
    elif op.get("materializer")=="RUN_EPOCH42_MEAN_REVERSION_COHORT_POWER_PREFLIGHT":
        new_state=_run_epoch42_mean_reversion_cohort_preflight(root,state,op)
    elif op.get("materializer")=="RUN_EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY":
        new_state=_run_epoch43_mean_reversion_power_aware_discovery(root,state,op)
    elif op.get("materializer")=="RUN_MEAN_REVERSION_CAPTURE_SCOPE_AUDIT_EPOCH45":
        new_state=_run_epoch45_mean_reversion_capture_scope_audit(root,state,op)
    elif name=="BUILD_READ_ONLY_ALL_FRONTIER_EXECUTION_PREREQUISITE_CAPTURE_CONTRACT":
        new_state=_execute_contract(root,state,op)
    elif name=="BUILD_FRONTIER_FEATURE_STORE_OPPORTUNITY_MAP_AND_INFORMATION_GAIN_SELECTOR":
        new_state=_execute_selection_layer(root,state,op)
    else:
        raise DeterministicOperationRejected(f"unsupported authorized deterministic materializer: {name}")
    _publish_state(root,new_state,before)
    # Dedup the execution input that was actually consumed, never the resulting
    # frontier. Hashing new_state here can suppress the next legal action.
    fingerprint=liveness_fingerprint(root,state)
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
        if out.get("status") in {"PENDING_EXACT_HEAD_GREEN","PENDING_ACCEPTED_CAPTURE_BYTES"}:
            if completed:
                GitCheckpointSink(root,enabled=git_checkpoint,push=git_push).checkpoint("deterministic_operation_chain",None)
            return {
                "status":out["status"],
                "completed_operations":completed,
                "operation_name":out.get("operation_name"),
                "exact_head":out.get("exact_head"),
                "missing_refs":out.get("missing_refs"),
                "expected_sha256":out.get("expected_sha256"),
                "next_state":out.get("next_state") or state,
                "provider_calls_delta":0,
                "state_persisted":False,
            }
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
