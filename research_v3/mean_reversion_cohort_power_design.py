"""Reusable, freeze-driven outcome-blind mean-reversion cohort and power design."""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any

from research_v3.regime_context_data_sufficiency_audit import _effective_n

OUTCOME_FEATURE_TOKENS = (
    "return",
    "pnl",
    "profit",
    "loss",
    "win",
    "performance",
    "outcome",
)
STRUCTURAL_HYPOTHESIS_FIELDS = (
    "event_definition",
    "response_estimand",
    "causal_timing",
)
PARAMETER_FIELDS = (
    "lookback_bars",
    "threshold",
    "horizon_bars",
    "anchor_stride_bars",
)
ALLOWED_SELECTION_FEATURES = frozenset(
    {
        "directional_eur200_margin",
        "minimum_executable_volume",
        "product_type",
        "trading_schedule",
        "session_overlap",
        "data_availability",
        "data_completeness",
        "event_density",
        "volatility_opportunity",
        "conservative_friction_proxy",
        "capital_efficiency",
        "redundancy",
        "expected_information_gain",
    }
)


class DesignError(ValueError):
    pass


def load_prior_freeze_scopes(root: str | Path) -> dict[str, dict[str, Any]]:
    """Load the exact prior specifications; prior result artifacts are never inputs."""
    repository = Path(root)
    freeze_specs = {
        "EPOCH25": (
            "research_v3/EPOCH25_MEAN_REVERSION_FRONTIER_FREEZE_V1.json",
            "preregistered_structural_law",
            "mxm.greenfield.epoch25-mean-reversion-frontier-freeze.v1",
            "FROZEN_BEFORE_MEAN_REVERSION_STRUCTURAL_OUTCOME",
        ),
        "EPOCH36": (
            "research_v3/EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_FRONTIER_FREEZE_V1.json",
            "preregistered_structural_law",
            "mxm.greenfield.epoch36-mean-reversion-magnitude-persistence-frontier-freeze.v1",
            "PROSPECTIVELY_FROZEN_BEFORE_EPOCH36_MEAN_REVERSION_MAGNITUDE_SCREEN",
        ),
    }
    scopes = {}
    for name, (relative, law_key, expected_schema, expected_status) in freeze_specs.items():
        try:
            freeze = json.loads((repository / relative).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DesignError(f"{name} prospective freeze is missing or unreadable") from exc
        law = freeze.get(law_key) if isinstance(freeze, dict) else None
        if (
            freeze.get("schema") != expected_schema
            or freeze.get("status") != expected_status
            or freeze.get("family") != "MEAN_REVERSION"
            or not isinstance(law, dict)
        ):
            raise DesignError(f"{name} prospective freeze has no structural specification")
        if name == "EPOCH25":
            signal = law.get("signal") or {}
            response = law.get("response") or {}
            scope = {
                "event_definition": {
                    "resolution": (freeze.get("scope") or {}).get("resolution"),
                    "directional_event": "UPPER_DEVIATION_SHORT_LOWER_DEVIATION_LONG",
                    "center": "ARITHMETIC_MEAN_OF_FROZEN_TRAILING_CLOSE_WINDOW",
                    "scale": "POPULATION_STANDARD_DEVIATION_OF_SAME_WINDOW",
                    "zero_scale_policy": "NO_EVENT_WHEN_SCALE_ZERO",
                },
                "response_estimand": {
                    "measure": response.get("measure"),
                    "success": response.get("success"),
                    "failure": response.get("failure"),
                    "flat": response.get("flat"),
                },
                "causal_timing": "AFTER_COMPLETED_EVENT_BAR_USING_ONLY_TRAILING_CLOSES",
                "lookback_bars": signal.get("window_bars"),
                "threshold": signal.get("threshold"),
                "horizon_bars": response.get("bars"),
                "anchor_stride_bars": law.get("anchor_stride_bars"),
            }
        else:
            scope = {
                "event_definition": {
                    "resolution": (freeze.get("scope") or {}).get("resolution"),
                    "directional_event": "UPPER_DEVIATION_SHORT_LOWER_DEVIATION_LONG",
                    "center": "ARITHMETIC_MEAN_OF_FROZEN_TRAILING_CLOSE_WINDOW",
                    "scale": "POPULATION_STANDARD_DEVIATION_OF_SAME_WINDOW",
                    "zero_scale_policy": "NO_EVENT_WHEN_SCALE_ZERO",
                },
                "response_estimand": {
                    "measure": (
                        "STANDARDIZED_ABSOLUTE_DISTANCE_CONTRACTION_TO_EVENT_TIME_MEAN"
                    ),
                },
                "causal_timing": "AFTER_COMPLETED_EVENT_BAR_USING_ONLY_TRAILING_CLOSES",
                "lookback_bars": law.get("signal_window_bars"),
                "threshold": law.get("extreme_z_threshold"),
                "horizon_bars": 12,
                "anchor_stride_bars": 12,
            }
        scopes[name] = scope
    return scopes


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _contains_outcome_feature(name: str) -> bool:
    normalized = name.lower()
    return any(token in normalized for token in OUTCOME_FEATURE_TOKENS)


def audit_prior_scope_distinctness(
    candidate: dict[str, Any], prior_scopes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Compare a frozen candidate definition with prior freeze scopes, not their results."""
    missing = [
        field
        for field in (*STRUCTURAL_HYPOTHESIS_FIELDS, *PARAMETER_FIELDS)
        if field not in candidate
    ]
    if missing:
        raise DesignError(f"candidate hypothesis is missing frozen fields: {', '.join(missing)}")
    if set(prior_scopes) != {"EPOCH25", "EPOCH36"}:
        raise DesignError("both exact prior freeze scopes must be supplied")

    comparisons = {}
    for name, prior in sorted(prior_scopes.items()):
        absent = [
            field
            for field in (*STRUCTURAL_HYPOTHESIS_FIELDS, *PARAMETER_FIELDS)
            if field not in prior
        ]
        if absent:
            raise DesignError(f"{name} prior scope is missing fields: {', '.join(absent)}")
        structural_matches = {
            field: _canonical(candidate[field]) == _canonical(prior[field])
            for field in STRUCTURAL_HYPOTHESIS_FIELDS
        }
        parameter_matches = {
            field: _canonical(candidate[field]) == _canonical(prior[field])
            for field in PARAMETER_FIELDS
        }
        if all(structural_matches.values()) and all(parameter_matches.values()):
            classification = "EXACT_SCOPE_MATCH"
        elif all(structural_matches.values()):
            classification = "PARAMETERIZATION_ONLY"
        else:
            classification = "STRUCTURAL_DIFFERENCE_REQUIRES_PROSPECTIVE_JUDGMENT"
        comparisons[name] = {
            "classification": classification,
            "structural_field_matches": structural_matches,
            "parameter_field_matches": parameter_matches,
            "distinct_hypothesis_authorized": False,
        }
    return {
        "comparisons": comparisons,
        "prior_results_read": False,
        "distinct_hypothesis_authorized": False,
        "interpretation": (
            "Structural differences identify candidates for prospective review; they do not "
            "by themselves establish scientific distinctness or authorize a diagnostic."
        ),
    }


def select_outcome_blind_cohort(
    identities: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, Any]:
    """Apply explicit frozen filters and ordering; never infer missing features or outcomes."""
    size = policy.get("cohort_size")
    feature_fields = policy.get("feature_fields")
    rationale = policy.get("rationale")
    filters = policy.get("filters")
    ranking = policy.get("ranking")
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise DesignError("frozen cohort_size must be a positive integer")
    if not isinstance(feature_fields, list) or not feature_fields:
        raise DesignError("frozen feature_fields must be a nonempty list")
    if not isinstance(rationale, str) or not rationale.strip():
        raise DesignError("frozen cohort rationale must be nonempty")
    if any(not isinstance(field, str) for field in feature_fields):
        raise DesignError("frozen feature_fields must contain strings")
    if len(set(feature_fields)) != len(feature_fields):
        raise DesignError("frozen feature_fields contain duplicates")
    if any(
        not isinstance(name, str)
        or name not in ALLOWED_SELECTION_FEATURES
        or _contains_outcome_feature(name)
        for name in feature_fields
    ):
        raise DesignError("cohort features include an unauthorized or outcome-derived field")
    if not isinstance(filters, list) or not isinstance(ranking, list) or not ranking:
        raise DesignError("frozen filters and nonempty ranking are required")

    seen_ids: set[int] = set()
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in identities:
        symbol_id = row.get("symbol_id")
        if isinstance(symbol_id, bool) or not isinstance(symbol_id, int) or symbol_id in seen_ids:
            raise DesignError("identity inventory has an invalid or duplicate symbol_id")
        seen_ids.add(symbol_id)
        reasons = []
        if row.get("current_entry_accessible") is not True:
            reasons.append("NOT_CURRENT_ENTRY_ACCESSIBLE")
        if row.get("both_direction_eur200_feasible") is not True:
            reasons.append("NOT_BOTH_DIRECTION_EUR200_FEASIBLE")
        if row.get("post_exclusion_eligible") is not True:
            reasons.append("NOT_POST_EXCLUSION_ELIGIBLE")
        absent = [name for name in feature_fields if name not in row or row[name] is None]
        if absent:
            reasons.append("MISSING_FROZEN_FEATURE:" + ",".join(absent))
        if reasons:
            excluded.append({"symbol_id": symbol_id, "reasons": reasons})
            continue
        eligible.append(row)

    exclusion_reasons: dict[int, list[str]] = {
        int(item["symbol_id"]): list(item["reasons"]) for item in excluded
    }
    excluded = []
    for symbol_id, reasons in exclusion_reasons.items():
        excluded.append({"symbol_id": symbol_id, "reasons": reasons})

    for condition in filters:
        if not isinstance(condition, dict):
            raise DesignError("each frozen filter must be an object")
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        if field not in feature_fields:
            raise DesignError("frozen filter refers to a feature outside feature_fields")
        if operator not in {"eq", "gte", "gt", "lte", "lt", "in"}:
            raise DesignError("unsupported frozen filter operator")
        retained = []
        for row in eligible:
            observed = row[field]
            if operator == "eq":
                passed = observed == value
            elif operator == "in":
                if not isinstance(value, list):
                    raise DesignError("the frozen 'in' filter value must be a list")
                passed = observed in value
            else:
                if (
                    isinstance(observed, bool)
                    or not isinstance(observed, (int, float))
                    or not math.isfinite(observed)
                    or isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise DesignError("numeric frozen filters require finite numeric values")
                passed = {
                    "gte": observed >= value,
                    "gt": observed > value,
                    "lte": observed <= value,
                    "lt": observed < value,
                }[operator]
            if passed:
                retained.append(row)
            else:
                exclusion_reasons.setdefault(row["symbol_id"], []).append(
                    f"FILTER_FAILED:{field}:{operator}"
                )
        eligible = retained

    ranking_fields = []
    for item in ranking:
        if not isinstance(item, dict):
            raise DesignError("each ranking rule must be an object")
        field = item.get("field")
        direction = item.get("direction")
        if field not in feature_fields or direction not in {"asc", "desc"}:
            raise DesignError("invalid frozen ranking field or direction")
        ranking_fields.append((field, direction))

    def rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
        parts = []
        for field, direction in ranking_fields:
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                raise DesignError(f"ranking feature {field} is not an ordered scalar")
            if isinstance(value, float) and not math.isfinite(value):
                raise DesignError(f"ranking feature {field} is not finite")
            if direction == "desc":
                value = -value if isinstance(value, (int, float)) else _Descending(value)
            parts.append(value)
        return (*parts, row["symbol_id"])

    try:
        ranked = sorted(eligible, key=rank_key)
    except TypeError as exc:
        raise DesignError("ranking values are not mutually comparable") from exc
    selected = ranked[:size]
    for row in ranked[size:]:
        exclusion_reasons.setdefault(row["symbol_id"], []).append("OUTSIDE_FROZEN_COHORT_SIZE")
    return {
        "selected_symbol_ids": [row["symbol_id"] for row in selected],
        "selected_identities": [
            {
                "symbol_id": row["symbol_id"],
                "broker_symbol": row.get("broker_symbol"),
                "selection_feature_values": {
                    field: row[field] for field in feature_fields
                },
            }
            for row in selected
        ],
        "selected_identity_count": len(selected),
        "eligible_after_frozen_filters": len(eligible),
        "feature_data_sufficiency": {
            field: {
                "identities_with_value": sum(
                    field in row and row[field] is not None for row in identities
                ),
                "identities_without_value": sum(
                    field not in row or row[field] is None for row in identities
                ),
                "denominator": len(identities),
            }
            for field in feature_fields
        },
        "cohort_size_target": size,
        "cohort_target_met": len(selected) == size,
        "selection_outcome_blind": True,
        "structural_representatives_substituted": False,
        "exclusions": [
            {"symbol_id": symbol_id, "reasons": reasons}
            for symbol_id, reasons in sorted(exclusion_reasons.items())
        ],
        "rationale": rationale,
        "selection_policy": policy,
    }


class _Descending:
    def __init__(self, value: str) -> None:
        self.value = value

    def __lt__(self, other: _Descending) -> bool:
        return self.value > other.value


def dependence_adjusted_effective_sample_size(
    date_cluster_values: dict[Any, float],
) -> dict[str, Any]:
    """Use the established positive-autocorrelation truncation rule on date-level proxies."""
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in date_cluster_values.values()
    ):
        raise DesignError("date-cluster series must contain only finite numeric values")
    result = _effective_n(date_cluster_values)
    return {
        **result,
        "series_semantics": "OUTCOME_BLIND_DATE_LEVEL_EVENT_OR_COVERAGE_PROXY",
        "raw_bar_count_used_as_independent_n": False,
    }


def required_effective_sample_size(
    standardized_effect: float,
    *,
    hypothesis_count: int,
    target_power: float,
    familywise_alpha: float,
) -> int:
    if not math.isfinite(standardized_effect) or standardized_effect <= 0:
        raise DesignError("standardized_effect must be finite and positive")
    if (
        isinstance(hypothesis_count, bool)
        or not isinstance(hypothesis_count, int)
        or hypothesis_count < 1
        or not 0 < target_power < 1
        or not 0 < familywise_alpha < 1
    ):
        raise DesignError("invalid frozen power assumptions")
    normal = NormalDist()
    alpha = familywise_alpha / hypothesis_count
    return math.ceil(
        ((normal.inv_cdf(1 - alpha) + normal.inv_cdf(target_power)) / standardized_effect)
        ** 2
    )


def build_power_preflight(
    date_cluster_values: dict[Any, float] | None,
    *,
    standardized_effect_scenarios: list[float],
    hypothesis_count: int,
    target_power: float,
    familywise_alpha: float,
) -> dict[str, Any]:
    if not standardized_effect_scenarios:
        raise DesignError("at least one frozen standardized-effect scenario is required")
    scenarios = [
        {
            "standardized_effect": effect,
            "required_effective_date_clusters": required_effective_sample_size(
                effect,
                hypothesis_count=hypothesis_count,
                target_power=target_power,
                familywise_alpha=familywise_alpha,
            ),
            "target_power": target_power,
            "familywise_alpha": familywise_alpha,
            "hypothesis_count": hypothesis_count,
            "interpretation": "PLANNING_SENSITIVITY_ONLY_NOT_AN_ECONOMIC_THRESHOLD",
        }
        for effect in standardized_effect_scenarios
    ]
    if date_cluster_values is None:
        observed = None
        status = "NOT_ESTIMABLE_NO_ACCEPTED_DATE_LEVEL_PROXY"
    else:
        observed = dependence_adjusted_effective_sample_size(date_cluster_values)
        status = (
            "DATE_LEVEL_PROXY_AVAILABLE_POWER_NOT_OBSERVED"
            if observed["date_clusters"] > 0
            else "NOT_ESTIMABLE_NO_ACCEPTED_DATE_LEVEL_PROXY"
        )
    return {
        "status": status,
        "effective_sample_size": observed,
        "required_sample_size_scenarios": scenarios,
        "achieved_power_estimated": False,
        "strategy_outcomes_read": False,
        "pnl_computed": False,
    }
