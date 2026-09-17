"""Declarative schemas and validation for the generic V2 Discovery engine.

M3 is structural only. These validators do not evaluate economics and do not
instantiate any candidate identity by themselves.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

CANDIDATE_ID_RE = re.compile(r"^V2-C[0-9]{3,}$")

ALLOWED_RESULT_STATES = {
    "IMPLEMENTATION_INVALID",
    "DATA_INSUFFICIENT",
    "STRUCTURALLY_INFEASIBLE",
    "GROSS_EDGE_FAIL",
    "COARSE_NET_FAIL",
    "COST_UNRESOLVED",
    "DISCOVERY_SURVIVOR",
}

ALLOWED_STAGES = {"A", "B"}

CANDIDATE_REQUIRED_FIELDS = (
    "id", "mechanism", "rationale", "universe", "data", "causal_availability",
    "features", "lookbacks", "normalization_training", "timing", "direction",
    "entry", "exit", "maximum_hold", "execution_assumptions", "filters",
    "parameters", "capital_semantics", "cost_state", "cloud_portability",
    "no_rescue_rule", "spec_hash", "provenance",
)

RESULT_REQUIRED_FIELDS = (
    "candidate_id", "spec_hash", "stage", "status", "implementation_validity",
    "metrics", "eur200_feasibility", "cost_confidence", "data_completeness",
    "provenance",
)

METRIC_KEYS = (
    "event_count", "gross_pnl", "coarse_net_pnl", "gross_return",
    "coarse_net_return", "gross_per_event", "net_per_event", "cost_burden",
    "turnover", "weekly_events", "active_weeks", "longest_inactive_gap",
    "weekday_distribution", "session_distribution", "hold_duration", "exposure",
    "drawdown", "symbol_contribution", "direction_contribution",
    "subperiod_contribution", "regime_contribution", "capital_realization",
)


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


def validate_candidate_spec(spec: Mapping[str, Any]) -> bool:
    spec = _require_mapping(spec, "candidate spec")
    _require_fields(spec, CANDIDATE_REQUIRED_FIELDS, "candidate spec")

    if not CANDIDATE_ID_RE.fullmatch(str(spec["id"])):
        raise SchemaError("candidate id must match V2-CNNN (NNN >= 3 digits namespace form)")

    if not isinstance(spec["universe"], list) or not spec["universe"]:
        raise SchemaError("universe must be a non-empty list")
    if not isinstance(spec["features"], list):
        raise SchemaError("features must be a list")
    if not isinstance(spec["lookbacks"], list):
        raise SchemaError("lookbacks must be a list")
    if not isinstance(spec["filters"], list):
        raise SchemaError("filters must be a list")
    if not isinstance(spec["parameters"], Mapping):
        raise SchemaError("parameters must be an object")

    for field in (
        "data", "causal_availability", "normalization_training", "timing",
        "entry", "exit", "maximum_hold", "execution_assumptions",
        "capital_semantics", "cost_state", "cloud_portability",
        "no_rescue_rule", "provenance",
    ):
        _require_mapping(spec[field], field)

    if not isinstance(spec["spec_hash"], str) or not re.fullmatch(r"[0-9a-f]{64}", spec["spec_hash"]):
        raise SchemaError("spec_hash must be a lowercase SHA-256 hex string")
    if spec["cost_state"].get("state") not in {"VERIFIED", "CONSERVATIVE_BOUND", "UNRESOLVED"}:
        raise SchemaError("cost_state.state must be VERIFIED, CONSERVATIVE_BOUND, or UNRESOLVED")
    return True


def validate_result(result: Mapping[str, Any]) -> bool:
    result = _require_mapping(result, "discovery result")
    _require_fields(result, RESULT_REQUIRED_FIELDS, "discovery result")

    if not CANDIDATE_ID_RE.fullmatch(str(result["candidate_id"])):
        raise SchemaError("result candidate_id must use V2 candidate namespace")
    if not isinstance(result["spec_hash"], str) or not re.fullmatch(r"[0-9a-f]{64}", result["spec_hash"]):
        raise SchemaError("result spec_hash must be a lowercase SHA-256 hex string")
    if result["stage"] not in ALLOWED_STAGES:
        raise SchemaError(f"stage must be one of {sorted(ALLOWED_STAGES)}")
    if result["status"] not in ALLOWED_RESULT_STATES:
        raise SchemaError(f"invalid economic result state: {result['status']}")
    if not isinstance(result["implementation_validity"], Mapping):
        raise SchemaError("implementation_validity must be an object")

    metrics = _require_mapping(result["metrics"], "metrics")
    unknown_metrics = sorted(set(metrics) - set(METRIC_KEYS))
    if unknown_metrics:
        raise SchemaError(f"unknown metric keys: {unknown_metrics}")

    for field in ("eur200_feasibility", "cost_confidence", "data_completeness", "provenance"):
        _require_mapping(result[field], field)

    if result["stage"] == "B" and "capital_realization" not in metrics:
        raise SchemaError("Stage B requires metrics.capital_realization")
    return True
