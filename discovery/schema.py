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

_INTEGER_METRICS = {"event_count", "active_weeks"}
_NUMERIC_METRICS = {
    "gross_pnl", "coarse_net_pnl", "gross_return", "coarse_net_return",
    "gross_per_event", "net_per_event", "cost_burden", "turnover",
    "exposure", "drawdown",
}
_STRUCTURED_METRICS = {
    "weekly_events", "weekday_distribution", "session_distribution", "hold_duration",
    "symbol_contribution", "direction_contribution", "subperiod_contribution",
    "regime_contribution",
}
_GENERIC_QUANTITATIVE_METRICS = {"longest_inactive_gap"}


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


def _metric_envelope(value: Any, label: str) -> tuple[str, Any] | None:
    if not isinstance(value, Mapping) or "state" not in value:
        return None
    state = value.get("state")
    if state not in METRIC_AVAILABILITY_STATES:
        raise SchemaError(f"{label}.state must be one of {sorted(METRIC_AVAILABILITY_STATES)}")
    if state == "AVAILABLE":
        if "value" not in value:
            raise SchemaError(f"{label} AVAILABLE requires value")
        return state, value["value"]
    _require_nonempty_text(value.get("reason"), f"{label}.reason")
    if "value" in value:
        raise SchemaError(f"{label} {state} must not contain value")
    return state, None


def _require_finite_number(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{label} must be a finite numeric value")
    if not math.isfinite(value):
        raise SchemaError(f"{label} must be finite")


def _validate_nonnegative_integer_metric(value: Any, label: str) -> None:
    env = _metric_envelope(value, label)
    if env is not None:
        if env[0] != "AVAILABLE":
            return
        value = env[1]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SchemaError(f"{label} must be an integer >= 0 or an explicit availability envelope")


def _validate_numeric_metric(value: Any, label: str) -> None:
    env = _metric_envelope(value, label)
    if env is not None:
        if env[0] != "AVAILABLE":
            return
        value = env[1]
    _require_finite_number(value, label)


def _validate_quantitative_node(value: Any, label: str, *, allow_scalar: bool = True) -> None:
    if isinstance(value, bool):
        raise SchemaError(f"{label} boolean is not quantitative evidence")
    if isinstance(value, (int, float)):
        if not allow_scalar:
            raise SchemaError(f"{label} must be structured quantitative evidence")
        if not math.isfinite(value):
            raise SchemaError(f"{label} must be finite")
        return
    if isinstance(value, Mapping):
        if not value:
            raise SchemaError(f"{label} must not be an empty object")
        for key, nested in value.items():
            _validate_quantitative_node(nested, f"{label}.{key}", allow_scalar=True)
        return
    if isinstance(value, (list, tuple)):
        if not value:
            raise SchemaError(f"{label} must not be an empty array")
        for i, nested in enumerate(value):
            _validate_quantitative_node(nested, f"{label}[{i}]", allow_scalar=True)
        return
    raise SchemaError(f"{label} must contain quantitative evidence, not arbitrary strings/values")


def _validate_structured_metric(value: Any, label: str) -> None:
    env = _metric_envelope(value, label)
    if env is not None:
        if env[0] != "AVAILABLE":
            return
        value = env[1]
    if not isinstance(value, (Mapping, list, tuple)):
        raise SchemaError(f"{label} must be non-empty structured quantitative evidence or an availability envelope")
    _validate_quantitative_node(value, label, allow_scalar=False)


def _validate_generic_quantitative_metric(value: Any, label: str) -> None:
    env = _metric_envelope(value, label)
    if env is not None:
        if env[0] != "AVAILABLE":
            return
        value = env[1]
    _validate_quantitative_node(value, label, allow_scalar=True)


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
        mapping = _require_mapping(spec[field], field)
        if field in {"position_admission_policy", "stage_a_economic_unit"} and not mapping:
            raise SchemaError(f"{field} must not be empty")
    _require_sha256(spec["spec_hash"], "spec_hash")
    if spec["cost_state"].get("state") not in COST_CONFIDENCE_STATES:
        raise SchemaError("cost_state.state must be VERIFIED, CONSERVATIVE_BOUND, or UNRESOLVED")
    return True


def _validate_result_provenance(provenance: Any) -> Mapping[str, Any]:
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
    return p


def _validate_result_status_consistency(result: Mapping[str, Any]) -> None:
    status = result["status"]
    implementation = result["implementation_validity"]["state"]
    data = result["data_completeness"]["state"]
    cost = result["cost_confidence"]["state"]
    eur200 = result["eur200_feasibility"]["state"]
    stage = result["stage"]

    # Explicit terminal-state precedence:
    # 1 implementation, 2 data, 3 structural EUR200 infeasibility,
    # 4 gross-edge failure, 5 cost-resolution/coarse-net/survivor economics.
    if implementation != "VALID":
        if status != "IMPLEMENTATION_INVALID":
            raise SchemaError("non-VALID implementation requires IMPLEMENTATION_INVALID by precedence")
        return
    if status == "IMPLEMENTATION_INVALID":
        raise SchemaError("IMPLEMENTATION_INVALID requires implementation state INVALID or UNRESOLVED")

    if data != "SUFFICIENT":
        if status != "DATA_INSUFFICIENT":
            raise SchemaError("non-SUFFICIENT data requires DATA_INSUFFICIENT by precedence")
        return
    if status == "DATA_INSUFFICIENT":
        raise SchemaError("DATA_INSUFFICIENT requires data state INSUFFICIENT or UNRESOLVED")

    if eur200 == "INFEASIBLE":
        if status != "STRUCTURALLY_INFEASIBLE":
            raise SchemaError("known EUR200 infeasibility requires STRUCTURALLY_INFEASIBLE by precedence")
        return
    if status == "STRUCTURALLY_INFEASIBLE":
        raise SchemaError("STRUCTURALLY_INFEASIBLE requires eur200_feasibility=INFEASIBLE")

    if status == "GROSS_EDGE_FAIL":
        return

    if status == "COST_UNRESOLVED":
        if cost != "UNRESOLVED":
            raise SchemaError("COST_UNRESOLVED requires cost_confidence=UNRESOLVED")
        return

    if status == "COARSE_NET_FAIL":
        if cost not in {"VERIFIED", "CONSERVATIVE_BOUND"}:
            raise SchemaError("COARSE_NET_FAIL requires VERIFIED or CONSERVATIVE_BOUND cost confidence")
        return

    if status == "DISCOVERY_SURVIVOR":
        if cost not in {"VERIFIED", "CONSERVATIVE_BOUND"}:
            raise SchemaError("DISCOVERY_SURVIVOR requires VERIFIED or CONSERVATIVE_BOUND cost confidence")
        if stage == "B" and eur200 != "FEASIBLE":
            raise SchemaError("Stage-B DISCOVERY_SURVIVOR requires eur200_feasibility=FEASIBLE")
        return

    raise SchemaError(f"unhandled economic result status: {status}")


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
        label = f"metrics.{key}"
        if key in _INTEGER_METRICS:
            _validate_nonnegative_integer_metric(metrics[key], label)
        elif key in _NUMERIC_METRICS:
            _validate_numeric_metric(metrics[key], label)
        elif key in _STRUCTURED_METRICS:
            _validate_structured_metric(metrics[key], label)
        elif key in _GENERIC_QUANTITATIVE_METRICS:
            _validate_generic_quantitative_metric(metrics[key], label)
        else:
            raise SchemaError(f"metric validator missing for {key}")

    if result["stage"] == "B":
        if "capital_realization" not in metrics:
            raise SchemaError("Stage B requires metrics.capital_realization")
        cap = _require_mapping(metrics["capital_realization"], "metrics.capital_realization")
        _require_fields(cap, CAPITAL_REALIZATION_KEYS, "metrics.capital_realization")
        for key in CAPITAL_REALIZATION_KEYS:
            _validate_generic_quantitative_metric(cap[key], f"metrics.capital_realization.{key}")
    elif "capital_realization" in metrics:
        cap = _require_mapping(metrics["capital_realization"], "metrics.capital_realization")
        if not cap:
            raise SchemaError("metrics.capital_realization must not be empty")
        for key, value in cap.items():
            _validate_generic_quantitative_metric(value, f"metrics.capital_realization.{key}")

    provenance = _validate_result_provenance(result["provenance"])
    if provenance["cost_evidence"]["state"] != result["cost_confidence"]["state"]:
        raise SchemaError("provenance.cost_evidence.state must equal cost_confidence.state")

    _validate_result_status_consistency(result)
    return True
