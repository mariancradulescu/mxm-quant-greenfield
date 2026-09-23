"""Runtime V2 adapter for the prospectively frozen C031 Stage-B event pack.

This module contains no research selection logic. It converts a hash-bound pre-economic
event pack into the already frozen continuous-account evaluator only when Runtime V2 calls
it after authorization, and idempotently projects the resulting Stage-B observation into
canonical project accounting.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from competition.continuous_account_replay_v2 import CapitalEvent, replay_continuous_account
from discovery.accounting import derive_current_accounting
from research_v3.runtime_v2_primitives import atomic_write_json

VERSION = "MXM_C031_STAGE_B_RUNTIME_V2_ADAPTER_V1"
SPEC_HASH = "4a57910026bc8df63446fa8024ac86a18ce8a732039a9388f704a50bbccfc4e1"
PACK_REF = "research_v3/runtime_v2_inputs/C031_STAGE_B_FROZEN_EVENT_PACK_V1.json.gz"
PACK_GZIP_SHA256 = "d0de9ec40d8d1f4268f678fa750886eb4ee561303e18043188fc050a324c4ffc"
PACK_RAW_SHA256 = "996fa9188aa55529159eed23be8928cd8bb7e5d6f7576677c5f43ae87fc459c9"
RESULT_REF = "m6/results/V2-C031_STAGE_B_CURRENT_CONFIG_V1.json"
GUARD = Decimal("1.5")

class C031RuntimeAdapterError(ValueError):
    pass

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _load_pack(root: Path) -> dict[str, Any]:
    path = root / PACK_REF
    if not path.is_file():
        raise C031RuntimeAdapterError("frozen event pack missing")
    compressed = path.read_bytes()
    if _sha(compressed) != PACK_GZIP_SHA256:
        raise C031RuntimeAdapterError("frozen event-pack gzip hash drift")
    raw = gzip.decompress(compressed)
    if _sha(raw) != PACK_RAW_SHA256:
        raise C031RuntimeAdapterError("frozen event-pack raw hash drift")
    doc = json.loads(raw)
    if doc.get("schema") != "mxm.greenfield.c031-stage-b-frozen-event-pack.v1":
        raise C031RuntimeAdapterError("wrong event-pack schema")
    if doc.get("candidate_id") != "V2-C031" or doc.get("spec_hash") != SPEC_HASH:
        raise C031RuntimeAdapterError("event-pack identity drift")
    if doc.get("pre_economic") is not True:
        raise C031RuntimeAdapterError("event pack is not pre-economic")
    if len(doc.get("base") or []) != 1666 or len(doc.get("stress") or []) != 1666:
        raise C031RuntimeAdapterError("event-pack count drift")
    columns = doc.get("columns")
    expected = [
        "timestamp_utc","kind","candidate_id","symbol","position_id","priority","direction",
        "direction_feasibility","volume_cents","min_volume_cents","step_volume_cents",
        "max_volume_cents","margin_eur","price","base_units","quote_to_eur_rate",
        "transaction_cost_eur","financing_eur","cashflow_eur","causal_state",
    ]
    if columns != expected:
        raise C031RuntimeAdapterError("event-pack column contract drift")
    return doc

def _events(doc: Mapping[str, Any], key: str) -> list[CapitalEvent]:
    cols = list(doc["columns"])
    out: list[CapitalEvent] = []
    for row in doc[key]:
        if len(row) != len(cols):
            raise C031RuntimeAdapterError("event row width drift")
        value = dict(zip(cols, row))
        out.append(CapitalEvent(**value))
    return out

def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return value

def _strip_decisions(result: Any) -> dict[str, Any]:
    doc = asdict(result)
    doc.pop("decisions", None)
    return _serialize(doc)

def _validate_runtime_plan(plan: Mapping[str, Any]) -> None:
    binding = plan.get("identity_binding") or {}
    if binding.get("candidate_spec_hash") != SPEC_HASH:
        raise C031RuntimeAdapterError("Runtime V2 candidate binding drift")
    if binding.get("dataset_hash") != PACK_GZIP_SHA256:
        raise C031RuntimeAdapterError("Runtime V2 dataset binding drift")
    gate = plan.get("pre_outcome_gate") or {}
    if gate.get("status") != "PASS" or gate.get("transport_exact_head_green") is not True:
        raise C031RuntimeAdapterError("Stage-B exact-head transport gate not PASS")
    if gate.get("ai_authorization_operation_id") != "op_d564674cb94e61eabe9dd23015062b6d":
        raise C031RuntimeAdapterError("AI authorization operation binding drift")
    if (plan.get("safety") or {}).get("protected_evidence_opened") is not False:
        raise C031RuntimeAdapterError("protected evidence safety drift")
    if (plan.get("safety") or {}).get("live_orders_authorized") is not False:
        raise C031RuntimeAdapterError("live-order safety drift")

def evaluate_runtime_v2(root_value: str | Path, plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(root_value)
    _validate_runtime_plan(plan)
    doc = _load_pack(root)
    kwargs = dict(
        starting_equity_eur=Decimal("200"),
        account_type="HEDGED",
        total_margin_calculation_type="MAX",
        same_symbol_overlap_allowed=False,
        entry_margin_level_floor_ratio=GUARD,
        unresolved_stop_out_guard_ratio=GUARD,
    )
    base = replay_continuous_account(_events(doc, "base"), **kwargs)
    stress = replay_continuous_account(_events(doc, "stress"), **kwargs)
    stopout_dependency = (
        base.status == "HALT_UNRESOLVED_BROKER_STOP_OUT"
        or stress.status == "HALT_UNRESOLVED_BROKER_STOP_OUT"
        or base.accepted_entries != stress.accepted_entries
    )
    if stopout_dependency:
        status = "UNRESOLVED_BROKER_STOP_OUT_DEPENDENCY"
    elif base.status != "COMPLETE" or stress.status != "COMPLETE":
        status = "CAPITAL_PATH_FAILURE"
    elif base.rejected_entries:
        status = "CURRENT_CONFIG_REALIZABLE_WITH_MARGIN_CONSTRAINTS"
    else:
        status = "CURRENT_CONFIG_REALIZABLE_ALL_FROZEN_SIGNALS"

    result: dict[str, Any] = {
        "schema": "mxm.greenfield.c031-stage-b-current-config-result.v1",
        "label": "STAGE_B_CURRENT_CONFIGURATION_SCENARIO",
        "adapter_version": VERSION,
        "candidate_id": "V2-C031",
        "candidate_spec_hash": SPEC_HASH,
        "economic_execution_id": plan["economic_execution_id"],
        "status": status,
        "execution_provenance": {
            "runtime_operation_id": plan["operation_id"],
            "ai_authorization_operation_id": "op_d564674cb94e61eabe9dd23015062b6d",
            "pre_economic_freeze_ref": "evidence/C031_STAGE_B_PRE_ECONOMIC_FREEZE_V1.json",
            "pre_economic_acceptance_ref": "evidence/C031_STAGE_B_PRE_ECONOMIC_ACCEPTANCE_V1.json",
            "runtime_transport_acceptance_ref": "evidence/C031_STAGE_B_RUNTIME_TRANSPORT_ACCEPTANCE_V1.json",
            "event_pack_ref": PACK_REF,
            "event_pack_gzip_sha256": PACK_GZIP_SHA256,
            "event_pack_raw_sha256": PACK_RAW_SHA256,
            "protected_evidence_opened": False,
        },
        "scenario_boundary": {
            "current_configuration_applied_to_development": True,
            "historical_point_in_time_margin_certification": False,
            "exact_account_specific_stop_out_known": False,
            "unknown_stop_out_handling": "FAIL_CLOSED_AT_CAPTURED_150_PERCENT_MARGIN_CALL_GUARD",
        },
        "capital_policy": {
            "starting_equity_eur": 200,
            "continuous_account": True,
            "weekly_reset": False,
            "monthly_reset": False,
            "sizing": "BROKER_MINIMUM_EXECUTABLE_VOLUME_BASELINE",
            "same_symbol_overlap": False,
            "cross_symbol_concurrency": True,
            "deposits_withdrawals": "ENGINE_SUPPORTED_NONE_IN_FROZEN_SCENARIO",
        },
        "cost_policy": "FULL_FROZEN_CONSERVATIVE_ROUNDTRIP_CHARGED_AT_ENTRY",
        "financing": {
            "state": "ZERO_BY_PRE_ECONOMIC_ROLLOVER_PROOF",
            "rollover_crossings": 0,
        },
        "base_path": _strip_decisions(base),
        "adverse_bar_stress_path": _strip_decisions(stress),
        "accounting_effect": {
            "new_v2_identity": False,
            "v2_attempt_delta": 0,
            "economic_outcome_delta": 1,
        },
    }
    raw = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    result["result_sha256"] = _sha(raw)
    return result

def project_canonical_state(root_value: str | Path, plan: dict[str, Any], result_path: Path, digest: str) -> dict[str, Any]:
    """Idempotently project a persisted C031 Stage-B observation into canonical project state."""
    root = Path(root_value)
    result_path = Path(result_path)
    expected = (root / RESULT_REF).resolve()
    if result_path.resolve() != expected:
        raise C031RuntimeAdapterError("Stage-B result path drift")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("candidate_id") != "V2-C031" or result.get("candidate_spec_hash") != SPEC_HASH:
        raise C031RuntimeAdapterError("persisted Stage-B identity drift")
    if result.get("economic_execution_id") != plan.get("economic_execution_id"):
        raise C031RuntimeAdapterError("persisted Stage-B execution-id drift")
    if hashlib.sha256(result_path.read_bytes()).hexdigest() != digest:
        raise C031RuntimeAdapterError("persisted Stage-B byte hash drift")

    derived = derive_current_accounting(root)
    if derived["v2_attempts_used"] != 19 or derived["v2_search_budget_remaining"] != 65:
        raise C031RuntimeAdapterError("Stage-B unexpectedly changed V2 identity budget")
    if derived["stage_b_current_config_economic_observations"] != 3:
        raise C031RuntimeAdapterError("canonical Stage-B observation count is not exactly three")
    if derived["economic_outcomes_opened"] != 27:
        raise C031RuntimeAdapterError("canonical economic-outcome count is not 27")

    state_path = root / "CURRENT_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for key in (
        "v2_search_budget","legacy_prior_attempts","v2_attempts_used","v2_evaluated_identities",
        "v2_search_budget_remaining","global_attempts_seen","economic_outcomes_opened",
        "distinct_identity_outcomes_opened","stage_a_result_recorded_entries",
        "stage_b_current_config_economic_observations","discovery_ledger_entries",
        "discovery_result_recorded_entries","implementation_correction_entries",
    ):
        state[key] = derived[key]
    state["current_config_stage_b_outcomes_opened"] = derived["stage_b_current_config_economic_observations"]
    state.setdefault("active_result_pointers", {})["V2-C031_STAGE_B_CURRENT_CONFIG"] = RESULT_REF

    status = str(result.get("status"))
    stage_b_authority = {
        "state": "CURRENT_CONFIGURATION_DEVELOPMENT_OBSERVATION",
        "result_ref": RESULT_REF,
        "result_sha256": result.get("result_sha256"),
        "runtime_result_bytes_sha256": digest,
        "status": status,
        "historical_point_in_time_margin_certification": False,
        "new_identity_required": False,
        "v2_attempt_delta": 0,
    }
    state.setdefault("current_result_authority", {}).setdefault("V2-C031", {})["stage_b"] = stage_b_authority

    ids = set(state.get("current_live_equivalent_stage_b_authoritative_candidate_ids", []))
    if status.startswith("CURRENT_CONFIG_REALIZABLE"):
        ids.add("V2-C031")
    else:
        ids.discard("V2-C031")
    state["current_live_equivalent_stage_b_authoritative_candidate_ids"] = sorted(ids)

    wave = state.setdefault("performance_research_v3", {}).setdefault("wave06", {})
    wave["stage_b_extension_candidates"] = []
    wave["stage_b_assessed_candidate_ids"] = ["V2-C031"]
    wave["stage_b_current_config_result_ref"] = RESULT_REF
    wave["stage_b_current_config_status"] = status
    wave["stage_b_new_v2_attempt_consumed"] = False
    wave["stage_b_economic_outcome_opened"] = True

    revalidation = set(state.get("stage_b_revalidation_required_candidate_ids", []))
    if status == "UNRESOLVED_BROKER_STOP_OUT_DEPENDENCY":
        revalidation.add("V2-C031")
    else:
        revalidation.discard("V2-C031")
    state["stage_b_revalidation_required_candidate_ids"] = sorted(revalidation)
    atomic_write_json(state_path, state)

    next_path = root / "research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json"
    next_doc = {
        "schema": "mxm.greenfield.runtime-v2-next-autonomous-state.v3",
        "status": "STAGE_B_OUTCOME_OPENED_PENDING_AI_INTERPRETATION",
        "next_action": "AI_INTERPRET_C031_STAGE_B_RESULT_AND_CHOOSE_HIGHEST_INFORMATION_NEXT_ACTION",
        "control_plane_next_action": "REVALIDATE_STAGE_B" if status == "UNRESOLVED_BROKER_STOP_OUT_DEPENDENCY" else "FREEZE_NEXT_HIGH_INFORMATION_WAVE",
        "director_protocol": "MXM_GENERAL_AI_RESEARCH_DIRECTOR_PROTOCOL_V1",
        "result_ref": RESULT_REF,
        "result_sha256": result.get("result_sha256"),
        "runtime_result_bytes_sha256": digest,
        "economic_execution_id": plan.get("economic_execution_id"),
        "user_action_required": False,
        "material_issues": [],
        "recoverable_conditions": [],
        "accounting": {
            "v2_attempts_used": derived["v2_attempts_used"],
            "v2_search_budget_remaining": derived["v2_search_budget_remaining"],
            "economic_outcomes_opened": derived["economic_outcomes_opened"],
        },
        "safety": {
            "protected_evidence_opened": False,
            "live_orders_authorized": False,
            "competition_start_authorized": False,
        },
    }
    atomic_write_json(next_path, next_doc)
    return {
        "status": "PASS",
        "candidate_id": "V2-C031",
        "economic_outcomes_opened": derived["economic_outcomes_opened"],
        "v2_attempts_used": derived["v2_attempts_used"],
        "result_status": status,
    }
