"""Generic declarative validation for MXM Quant Greenfield V2 Discovery."""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

CANDIDATE_ID_RE = re.compile(r"^V2-C[0-9]{3,}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ALLOWED_RESULT_STATES = {
    "IMPLEMENTATION_INVALID", "DATA_INSUFFICIENT", "STRUCTURALLY_INFEASIBLE",
    "GROSS_EDGE_FAIL", "COARSE_NET_FAIL", "COST_UNRESOLVED", "DISCOVERY_SURVIVOR",
}
ALLOWED_STAGES = {"A", "B"}
IMPLEMENTATION_STATES = {"VALID", "INVALID", "UNRESOLVED"}
DATA_COMPLETENESS_STATES = {"SUFFICIENT", "INSUFFICIENT", "UNRESOLVED"}
EUR200_FEASIBILITY_STATES = {"FEASIBLE", "INFEASIBLE", "NOT_EVALUATED", "UNRESOLVED"}
COST_CONFIDENCE_STATES = {"VERIFIED", "CONSERVATIVE_BOUND", "UNRESOLVED"}
METRIC_AVAILABILITY_STATES = {"AVAILABLE", "UNAVAILABLE", "NOT_APPLICABLE"}

CANDIDATE_REQUIRED_FIELDS = (
    "id", "mechanism", "rationale", "universe", "data", "causal_availability",
    "features", "lookbacks", "normalization_training", "timing", "direction",
    "entry", "exit", "maximum_hold", "execution_assumptions", "filters",
    "parameters", "capital_semantics", "cost_state", "cloud_portability",
    "no_rescue_rule", "position_admission_policy", "stage_a_economic_unit",
    "spec_hash", "provenance",
)

RESULT_REQUIRED_FIELDS = (
    "candidate_id", "spec_hash", "stage", "status", "implementation_validity",
    "metrics", "eur200_feasibility", "cost_confidence", "data_completeness", "provenance",
)

STAGE_A_METRIC_KEYS = (
    "event_count", "gross_pnl", "coarse_net_pnl", "gross_return", "coarse_net_return",
    "gross_per_event", "net_per_event", "cost_burden", "turnover", "weekly_events",
    "active_weeks", "longest_inactive_gap", "weekday_distribution", "session_distribution",
    "hold_duration", "exposure", "drawdown", "symbol_contribution", "direction_contribution",
    "subperiod_contribution", "regime_contribution",
)
CAPITAL_REALIZATION_KEYS = (
    "continuous_capital_path", "weekly_final_equity_distribution",
    "monthly_final_equity_distribution", "capital_occupancy", "margin_blockers",
    "executed_trade_distribution",
)
METRIC_KEYS = STAGE_A_METRIC_KEYS + ("capital_realization",)

class SchemaError(ValueError):
    pass

def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{label} must be an object")
    return value

def _require_fields(obj: Mapping[str, Any], fields, label: str) -> None:
    missing = [field for field in fields if field not in obj]
    if missing:
        raise SchemaError(f"{label} missing required fields: {missing}")

def _require_nonempty_text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{label} must be a non-empty string")

def _require_sha256(value: Any, label: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise SchemaError(f"{label} must be a lowercase SHA-256 hex string")

def _validate_state_envelope(value: Any, label: str, allowed_states: set[str]) -> Mapping[str, Any]:
    envelope = _require_mapping(value, label)
    if not envelope:
        raise SchemaError(f"{label} must not be empty")
    if envelope.get("state") not in allowed_states:
        raise SchemaError(f"{label}.state must be one of {sorted(allowed_states)}")
    if envelope.get("reason") is not None:
        _require_nonempty_text(envelope["reason"], f"{label}.reason")
    return envelope

def _validate_metric_value(value: Any, label: str) -> None:
    if value is None:
        raise SchemaError(f"{label} must not be null; use an explicit unavailable/not-applicable envelope")
    if isinstance(value, float) and not math.isfinite(value):
        raise SchemaError(f"{label} must be finite")
    if isinstance(value, Mapping):
        if not value:
            raise SchemaError(f"{label} must not be an empty object")
        if "state" in value:
            if value.get("state") not in METRIC_AVAILABILITY_STATES:
                raise SchemaError(f"{label}.state must be one of {sorted(METRIC_AVAILABILITY_STATES)}")
            if value["state"] == "AVAILABLE":
                if "value" not in value:
                    raise SchemaError(f"{label} AVAILABLE requires value")
                _validate_metric_value(value["value"], f"{label}.value")
            else:
                _require_nonempty_text(value.get("reason"), f"{label}.reason")
        else:
            for key, nested in value.items():
                _validate_metric_value(nested, f"{label}.{key}")
    elif isinstance(value, (list, tuple)):
        if not value:
            raise SchemaError(f"{label} must not be an empty array")
        for i, nested in enumerate(value):
            _validate_metric_value(nested, f"{label}[{i}]")

def validate_candidate_spec(spec: Mapping[str, Any]) -> bool:
    spec = _require_mapping(spec, "candidate spec")
    _require_fields(spec, CANDIDATE_REQUIRED_FIELDS, "candidate spec")
    if not CANDIDATE_ID_RE.fullmatch(str(spec["id"])):
        raise SchemaError("candidate id must match V2-CNNN")
    if not isinstance(spec["universe"], list) or not spec["universe"]:
        raise SchemaError("universe must be a non-empty list")
    for field in ("features", "lookbacks", "filters"):
        if not isinstance(spec[field], list):
            raise SchemaError(f"{field} must be a list")
    if not isinstance(spec["parameters"], Mapping):
        raise SchemaError("parameters must be an object")
    for field in (
        "data", "causal_availability", "normalization_training", "timing", "entry", "exit",
        "maximum_hold", "execution_assumptions", "capital_semantics", "cost_state",
        "cloud_portability", "no_rescue_rule", "position_admission_policy",
        "stage_a_economic_unit", "provenance",
    ):
        _require_mapping(spec[field], field)
    _require_sha256(spec["spec_hash"], "spec_hash")
    if spec["cost_state"].get("state") not in COST_CONFIDENCE_STATES:
        raise SchemaError("cost_state.state must be VERIFIED, CONSERVATIVE_BOUND, or UNRESOLVED")
    return True

def _validate_result_provenance(provenance: Any) -> None:
    p = _require_mapping(provenance, "provenance")
    _require_fields(p, ("data_evidence", "cost_evidence", "evaluator"), "provenance")
    data = _require_mapping(p["data_evidence"], "provenance.data_evidence")
    _require_fields(data, ("identity", "binding"), "provenance.data_evidence")
    _require_nonempty_text(data["identity"], "provenance.data_evidence.identity")
    binding = _require_mapping(data["binding"], "provenance.data_evidence.binding")
    if binding.get("type") not in {"DATASET_SHA256", "MANIFEST_SHA256"}:
        raise SchemaError("provenance.data_evidence.binding.type must be DATASET_SHA256 or MANIFEST_SHA256")
    _require_sha256(binding.get("sha256"), "provenance.data_evidence.binding.sha256")
    cost = _require_mapping(p["cost_evidence"], "provenance.cost_evidence")
    _require_fields(cost, ("identity", "state", "sha256"), "provenance.cost_evidence")
    _require_nonempty_text(cost["identity"], "provenance.cost_evidence.identity")
    if cost["state"] not in COST_CONFIDENCE_STATES:
        raise SchemaError("provenance.cost_evidence.state invalid")
    _require_sha256(cost["sha256"], "provenance.cost_evidence.sha256")
    evaluator = _require_mapping(p["evaluator"], "provenance.evaluator")
    _require_fields(evaluator, ("version", "sha256"), "provenance.evaluator")
    _require_nonempty_text(evaluator["version"], "provenance.evaluator.version")
    _require_sha256(evaluator["sha256"], "provenance.evaluator.sha256")

def validate_result(result: Mapping[str, Any]) -> bool:
    result = _require_mapping(result, "discovery result")
    _require_fields(result, RESULT_REQUIRED_FIELDS, "discovery result")
    if not CANDIDATE_ID_RE.fullmatch(str(result["candidate_id"])):
        raise SchemaError("result candidate_id must use V2 candidate namespace")
    _require_sha256(result["spec_hash"], "result spec_hash")
    if result["stage"] not in ALLOWED_STAGES:
        raise SchemaError(f"stage must be one of {sorted(ALLOWED_STAGES)}")
    if result["status"] not in ALLOWED_RESULT_STATES:
        raise SchemaError(f"invalid economic result state: {result['status']}")
    _validate_state_envelope(result["implementation_validity"], "implementation_validity", IMPLEMENTATION_STATES)
    _validate_state_envelope(result["cost_confidence"], "cost_confidence", COST_CONFIDENCE_STATES)
    _validate_state_envelope(result["data_completeness"], "data_completeness", DATA_COMPLETENESS_STATES)
    _validate_state_envelope(result["eur200_feasibility"], "eur200_feasibility", EUR200_FEASIBILITY_STATES)

    metrics = _require_mapping(result["metrics"], "metrics")
    if not metrics:
        raise SchemaError("metrics must not be empty")
    unknown_metrics = sorted(set(metrics) - set(METRIC_KEYS))
    if unknown_metrics:
        raise SchemaError(f"unknown metric keys: {unknown_metrics}")
    _require_fields(metrics, STAGE_A_METRIC_KEYS, "Stage-A metrics")
    for key in STAGE_A_METRIC_KEYS:
        _validate_metric_value(metrics[key], f"metrics.{key}")
    if result["stage"] == "B":
        if "capital_realization" not in metrics:
            raise SchemaError("Stage B requires metrics.capital_realization")
        cap = _require_mapping(metrics["capital_realization"], "metrics.capital_realization")
        _require_fields(cap, CAPITAL_REALIZATION_KEYS, "metrics.capital_realization")
        for key in CAPITAL_REALIZATION_KEYS:
            _validate_metric_value(cap[key], f"metrics.capital_realization.{key}")
    elif "capital_realization" in metrics:
        _validate_metric_value(metrics["capital_realization"], "metrics.capital_realization")
    _validate_result_provenance(result["provenance"])
    return True
