"""Frozen non-economic Epoch-24 relative-value structural diagnostic.

The accepted family and 820-pair availability inventory are already durable. This
module implements only the remaining bounded hedge/stationarity/stability phase.
It cannot rank pairs, calculate returns/PnL, open economics, touch protected-forward
data, or fit/tune on holdout observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence
from zipfile import ZipFile

from research_v3.relative_value_epoch24_prerequisite import (
    PairDataError,
    build_accepted_price_series,
    prepare_inventory_bound_pair,
)

IMPLEMENTATION_VERSION = "MXM_EPOCH24_RELATIVE_VALUE_DIAGNOSTIC_V1"
PLAN_SCHEMA = "mxm.greenfield.epoch24-relative-value-diagnostic-plan.v1"
PLAN_STATUS = "FROZEN_NON_ECONOMIC_DIAGNOSTIC_PLAN"
RESULT_SCHEMA = "mxm.greenfield.epoch24-relative-value-structural-diagnostic.v1"
CURRENT_BROKER_UNIVERSE_ZIP_SHA256 = "3d1db9a65e93fe5c7ea69411a9c76d8d6381927ce1224e02532640394076e8a9"
CURRENT_BROKER_UNIVERSE_PAYLOAD_SHA256 = "7b268eae05fad325cb1f0fc962511ca41236b3b58bb83023735fd22b94301452"
CURRENT_BROKER_UNIVERSE_MEMBER = "BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V2.json"


class DiagnosticError(ValueError):
    """Fail-closed diagnostic construction or execution error."""


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_plan(plan: Mapping[str, Any]) -> None:
    if plan.get("schema") != PLAN_SCHEMA or plan.get("status") != PLAN_STATUS:
        raise DiagnosticError("diagnostic plan is not the frozen Epoch-24 plan")
    scope = plan.get("scope") or {}
    split = plan.get("time_split") or {}
    stationarity = plan.get("stationarity") or {}
    stability = plan.get("stability") or {}
    if int(scope.get("representatives") or 0) != 41:
        raise DiagnosticError("plan representative scope changed")
    if int(scope.get("unordered_pair_inventory") or 0) != 820:
        raise DiagnosticError("plan pair inventory changed")
    fractions = (
        float(split.get("development_fraction", 0)),
        float(split.get("validation_fraction", 0)),
        float(split.get("holdout_fraction", 0)),
    )
    if abs(sum(fractions) - 1.0) > 1e-12 or min(fractions) <= 0:
        raise DiagnosticError("invalid chronological split fractions")
    if split.get("holdout_refit") is not False or split.get("holdout_tuning") is not False:
        raise DiagnosticError("holdout mutation is forbidden")
    if int(stationarity.get("adf_lag") or -1) != 1:
        raise DiagnosticError("only frozen ADF lag-1 plan is accepted")
    if int(stationarity.get("monte_carlo_simulations") or 0) < 99:
        raise DiagnosticError("stationarity Monte Carlo resolution is too low")
    if int(stability.get("development_subwindows") or 0) != 3:
        raise DiagnosticError("development stability subwindow count changed")



def _normalized_contract_family(record: Mapping[str, Any]) -> str:
    asset_class = str(record.get("asset_class") or "").strip()
    product_type = str(record.get("product_type") or "").strip()
    if asset_class.endswith(" Equities"):
        return "EQUITY_CFD"
    if asset_class == "Commodities (Cash)":
        return "CASH_COMMODITY_CFD"
    if product_type and product_type != "OTHER_OR_TEST_CFD":
        return product_type
    if product_type and asset_class:
        return f"{product_type}|{asset_class}"
    raise DiagnosticError("broker product metadata cannot resolve contract family")


def build_broker_product_authority(
    broker_universe_zip: Path,
    registry: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Derive exact 41-representative comparability metadata from accepted broker capture."""
    raw_zip = broker_universe_zip.read_bytes()
    if hashlib.sha256(raw_zip).hexdigest() != CURRENT_BROKER_UNIVERSE_ZIP_SHA256:
        raise DiagnosticError("current broker-universe transport hash mismatch")
    with ZipFile(broker_universe_zip) as archive:
        if archive.testzip():
            raise DiagnosticError("current broker-universe zip CRC failure")
        payload = archive.read(CURRENT_BROKER_UNIVERSE_MEMBER)
    if hashlib.sha256(payload).hexdigest() != CURRENT_BROKER_UNIVERSE_PAYLOAD_SHA256:
        raise DiagnosticError("current broker-universe canonical payload hash mismatch")
    capture = json.loads(payload)
    symbol_rows = {
        str(row["broker_symbol"]): row for row in capture.get("symbols") or []
    }
    representatives = list(registry.get("representatives") or [])
    if len(representatives) != 41:
        raise DiagnosticError("broker product authority requires accepted 41 representatives")

    authority: dict[str, dict[str, Any]] = {}
    for representative in representatives:
        symbol = str(representative["broker_symbol"])
        row = symbol_rows.get(symbol)
        if row is None:
            raise DiagnosticError(f"broker product metadata missing: {symbol}")
        if int(row["symbol_id"]) != int(representative["symbol_id"]):
            raise DiagnosticError(f"broker product identity mismatch: {symbol}")
        quote_asset = str(row.get("quote_asset") or "").strip().upper()
        product_type = str(row.get("product_type") or "").strip()
        lot_size = str(row.get("lot_size") or "").strip()
        unit_family = _normalized_contract_family(row)
        if not all((quote_asset, product_type, lot_size, unit_family)):
            raise DiagnosticError(f"incomplete broker product metadata: {symbol}")
        authority[symbol] = {
            "symbol_id": int(row["symbol_id"]),
            "product_type": product_type,
            "unit_family": unit_family,
            "asset_class": str(row.get("asset_class") or ""),
            "base_asset": str(row.get("base_asset") or ""),
            "quote_asset": quote_asset,
            "lot_size": lot_size,
            "measurement_units": row.get("measurement_units"),
            "digits": row.get("digits"),
            "pip_position": row.get("pip_position"),
            "schedule_minutes_per_week": row.get("schedule_minutes_per_week"),
            "schedule_time_zone": row.get("schedule_time_zone"),
            "broker_metadata_complete": True,
            "source_ref": (
                "MXM_COMPETITION_BROKER_UNIVERSE_V2.zip#"
                + CURRENT_BROKER_UNIVERSE_PAYLOAD_SHA256
            ),
        }
    if len(authority) != 41:
        raise DiagnosticError("broker product authority scope mismatch")
    return authority


def chronological_split(n: int, plan: Mapping[str, Any]) -> dict[str, tuple[int, int]]:
    validate_plan(plan)
    split = plan["time_split"]
    minimum = int(split["minimum_partition_observations"])
    d_end = int(n * float(split["development_fraction"]))
    v_end = d_end + int(n * float(split["validation_fraction"]))
    partitions = {
        "development": (0, d_end),
        "validation": (d_end, v_end),
        "holdout": (v_end, n),
    }
    if n < int(plan["scope"]["minimum_aligned_observations"]):
        raise DiagnosticError("insufficient aligned observations")
    if any(end - start < minimum for start, end in partitions.values()):
        raise DiagnosticError("chronological partition below frozen minimum")
    return partitions


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        raise DiagnosticError("sample standard deviation requires two observations")
    m = _mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def _ols_intercept_slope(x: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    if len(x) != len(y) or len(x) < 3:
        raise DiagnosticError("OLS input length invalid")
    mx, my = _mean(x), _mean(y)
    variance = sum((v - mx) ** 2 for v in x)
    if not math.isfinite(variance) or variance <= 1e-18:
        raise DiagnosticError("singular hedge regressor")
    beta = sum((vx - mx) * (vy - my) for vx, vy in zip(x, y)) / variance
    intercept = my - beta * mx
    if not math.isfinite(beta) or not math.isfinite(intercept):
        raise DiagnosticError("non-finite hedge fit")
    return intercept, beta


def fit_development_hedge(
    log_left: Sequence[float],
    log_right: Sequence[float],
    development_end: int,
) -> dict[str, float]:
    """Fit lexicographic left-on-right hedge using development observations only."""
    intercept, beta = _ols_intercept_slope(
        log_right[:development_end], log_left[:development_end]
    )
    return {"intercept": intercept, "beta": beta, "fit_end_exclusive": development_end}


def _residuals(
    log_left: Sequence[float],
    log_right: Sequence[float],
    *,
    intercept: float,
    beta: float,
) -> list[float]:
    out = [y - intercept - beta * x for y, x in zip(log_left, log_right)]
    if not out or not all(math.isfinite(v) for v in out):
        raise DiagnosticError("non-finite residual")
    return out


def _invert_matrix(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(matrix)
    work = [
        [float(v) for v in row] + [1.0 if i == j else 0.0 for j in range(n)]
        for i, row in enumerate(matrix)
    ]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(work[row][col]))
        if abs(work[pivot][col]) <= 1e-14:
            raise DiagnosticError("singular ADF design")
        work[col], work[pivot] = work[pivot], work[col]
        scale = work[col][col]
        work[col] = [v / scale for v in work[col]]
        for row in range(n):
            if row == col:
                continue
            factor = work[row][col]
            work[row] = [
                work[row][k] - factor * work[col][k] for k in range(2 * n)
            ]
    return [row[n:] for row in work]


def _adf_lag1_t_stat(series: Sequence[float]) -> float:
    """ADF with intercept and one lag of delta; returns t statistic on lagged level."""
    if len(series) < 30:
        raise DiagnosticError("ADF requires at least 30 observations")
    delta = [series[i] - series[i - 1] for i in range(1, len(series))]
    rows: list[list[float]] = []
    target: list[float] = []
    for i in range(1, len(delta)):
        rows.append([1.0, float(series[i]), float(delta[i - 1])])
        target.append(float(delta[i]))
    k = 3
    xtx = [
        [sum(row[i] * row[j] for row in rows) for j in range(k)]
        for i in range(k)
    ]
    xty = [sum(row[i] * y for row, y in zip(rows, target)) for i in range(k)]
    inv = _invert_matrix(xtx)
    coeff = [sum(inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    residual = [
        y - sum(c * x for c, x in zip(coeff, row))
        for row, y in zip(rows, target)
    ]
    dof = len(target) - k
    if dof <= 0:
        raise DiagnosticError("ADF degrees of freedom invalid")
    sigma2 = sum(v * v for v in residual) / dof
    variance = sigma2 * inv[1][1]
    if not math.isfinite(variance) or variance <= 0:
        raise DiagnosticError("ADF lagged-level variance invalid")
    t_stat = coeff[1] / math.sqrt(variance)
    if not math.isfinite(t_stat):
        raise DiagnosticError("non-finite ADF statistic")
    return t_stat


@lru_cache(maxsize=32)
def _unit_root_null_distribution(
    length: int, simulations: int, seed: int
) -> tuple[float, ...]:
    """Deterministic finite-simulation unit-root null for the exact same ADF statistic."""
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(simulations):
        series = [0.0]
        for _ in range(length - 1):
            series.append(series[-1] + rng.gauss(0.0, 1.0))
        stats.append(_adf_lag1_t_stat(series))
    return tuple(sorted(stats))


def adf_stationarity(
    series: Sequence[float], plan: Mapping[str, Any]
) -> dict[str, Any]:
    stationarity = plan["stationarity"]
    observed = _adf_lag1_t_stat(series)
    bucket_size = int(stationarity["null_length_bucket"])
    low = int(stationarity["null_length_min"])
    high = int(stationarity["null_length_max"])
    bucket = int(round(len(series) / bucket_size) * bucket_size)
    bucket = max(low, min(high, bucket))
    simulations = int(stationarity["monte_carlo_simulations"])
    seed = int(stationarity["monte_carlo_seed_base"]) + bucket
    null = _unit_root_null_distribution(bucket, simulations, seed)
    p_value = (1 + sum(stat <= observed for stat in null)) / (1 + len(null))
    return {
        "test": stationarity["test"],
        "lag": 1,
        "n": len(series),
        "t_statistic": observed,
        "p_value": p_value,
        "p_value_method": stationarity["p_value_law"],
        "null_length": bucket,
        "null_simulations": simulations,
        "null_seed": seed,
    }


def _ar1_half_life(series: Sequence[float]) -> dict[str, Any]:
    x = list(series[:-1])
    y = list(series[1:])
    intercept, rho = _ols_intercept_slope(x, y)
    half_life = None
    if 0.0 < abs(rho) < 1.0:
        half_life = -math.log(2.0) / math.log(abs(rho))
    return {"intercept": intercept, "rho": rho, "half_life_bars": half_life}


def _development_subwindow_stability(
    log_left: Sequence[float],
    log_right: Sequence[float],
    *,
    development_end: int,
    full_beta: float,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    stability = plan["stability"]
    count = int(stability["development_subwindows"])
    edges = [round(i * development_end / count) for i in range(count + 1)]
    betas: list[float] = []
    for i in range(count):
        start, end = edges[i], edges[i + 1]
        _, beta = _ols_intercept_slope(log_right[start:end], log_left[start:end])
        betas.append(beta)
    reference_sign = 1 if full_beta > 0 else (-1 if full_beta < 0 else 0)
    signs = [1 if beta > 0 else (-1 if beta < 0 else 0) for beta in betas]
    sign_consistent = reference_sign != 0 and all(sign == reference_sign for sign in signs)
    denominator = max(abs(full_beta), 1e-12)
    deviations = [abs(beta - full_beta) / denominator for beta in betas]
    max_deviation = max(deviations)
    passes = (
        sign_consistent
        and max_deviation <= float(stability["max_beta_relative_deviation"])
    )
    return {
        "subwindow_betas": betas,
        "beta_sign_consistent": sign_consistent,
        "relative_deviations": deviations,
        "max_relative_deviation": max_deviation,
        "max_allowed_relative_deviation": float(
            stability["max_beta_relative_deviation"]
        ),
        "passes": passes,
    }


def diagnose_pair(pair: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Run the frozen structural diagnostic on one already-synchronized pair."""
    validate_plan(plan)
    symbols = list(pair.get("symbols") or [])
    if len(symbols) != 2 or symbols != sorted(symbols):
        raise DiagnosticError("pair orientation must be lexicographic")
    if not (pair.get("comparability") or {}).get("comparable"):
        return {
            "symbols": symbols,
            "classification": "NOT_ADMISSIBLE_PRODUCT_COMPARABILITY",
            "failure_reasons": list((pair.get("comparability") or {}).get("reasons") or []),
            "diagnostic_executed": False,
        }

    rows = list(pair.get("synchronized_closes") or [])
    common_dates = int(
        (pair.get("alignment_inventory_binding") or {}).get(
            "expected_common_utc_dates", 0
        )
    )
    if len(rows) < int(plan["scope"]["minimum_aligned_observations"]):
        return {
            "symbols": symbols,
            "classification": "NOT_ADMISSIBLE_INSUFFICIENT_ALIGNMENT",
            "failure_reasons": ["INSUFFICIENT_ALIGNED_OBSERVATIONS"],
            "diagnostic_executed": False,
        }
    if common_dates < int(plan["scope"]["minimum_common_utc_dates"]):
        return {
            "symbols": symbols,
            "classification": "NOT_ADMISSIBLE_INSUFFICIENT_ALIGNMENT",
            "failure_reasons": ["INSUFFICIENT_COMMON_UTC_DATES"],
            "diagnostic_executed": False,
        }

    partitions = chronological_split(len(rows), plan)
    log_left: list[float] = []
    log_right: list[float] = []
    for row in rows:
        try:
            left = float(row["left_close"])
            right = float(row["right_close"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DiagnosticError("invalid synchronized close") from exc
        if (
            not math.isfinite(left)
            or not math.isfinite(right)
            or left <= 0
            or right <= 0
        ):
            raise DiagnosticError("non-positive/non-finite synchronized close")
        log_left.append(math.log(left))
        log_right.append(math.log(right))

    d0, d1 = partitions["development"]
    hedge = fit_development_hedge(log_left, log_right, d1)
    residual = _residuals(
        log_left, log_right, intercept=hedge["intercept"], beta=hedge["beta"]
    )
    diagnostics: dict[str, Any] = {}
    for name, (start, end) in partitions.items():
        diagnostics[name] = adf_stationarity(residual[start:end], plan)

    stability = _development_subwindow_stability(
        log_left,
        log_right,
        development_end=d1,
        full_beta=hedge["beta"],
        plan=plan,
    )
    perturbations = []
    h0, h1 = partitions["holdout"]
    for factor in plan["stability"]["coefficient_perturbation_factors"]:
        beta = hedge["beta"] * float(factor)
        perturbed = _residuals(
            log_left[h0:h1],
            log_right[h0:h1],
            intercept=hedge["intercept"],
            beta=beta,
        )
        stat = adf_stationarity(perturbed, plan)
        perturbations.append({"factor": float(factor), "beta": beta, **stat})

    alpha_dev = float(plan["stationarity"]["alpha_development"])
    alpha_hold = float(plan["stationarity"]["alpha_holdout"])
    perturb_alpha = float(plan["stability"]["perturbation_holdout_alpha"])
    failures: list[str] = []
    if diagnostics["development"]["p_value"] > alpha_dev:
        failures.append("DEVELOPMENT_STATIONARITY_P_GT_ALPHA")
    if diagnostics["holdout"]["p_value"] > alpha_hold:
        failures.append("HOLDOUT_STATIONARITY_P_GT_ALPHA")
    if not stability["beta_sign_consistent"]:
        failures.append("HEDGE_SIGN_INSTABILITY")
    if stability["max_relative_deviation"] > stability["max_allowed_relative_deviation"]:
        failures.append("HEDGE_RELATIVE_DEVIATION_GT_LIMIT")
    if any(item["p_value"] > perturb_alpha for item in perturbations):
        failures.append("PERTURBED_HOLDOUT_STATIONARITY_P_GT_ALPHA")

    dev_residual = residual[d0:d1]
    return {
        "symbols": symbols,
        "symbol_ids": list(pair.get("symbol_ids") or []),
        "classification": (
            "MEETS_PREDECLARED_NON_ECONOMIC_STRUCTURAL_CRITERIA"
            if not failures
            else "FAILS_PREDECLARED_NON_ECONOMIC_STRUCTURAL_CRITERIA"
        ),
        "failure_reasons": failures,
        "diagnostic_executed": True,
        "alignment": dict(pair.get("alignment") or {}),
        "comparability": dict(pair.get("comparability") or {}),
        "partitions": {
            name: {"start_index": start, "end_index_exclusive": end, "n": end - start}
            for name, (start, end) in partitions.items()
        },
        "hedge": {
            "orientation": plan["hedge"]["orientation"],
            "fit": plan["hedge"]["fit"],
            "intercept": hedge["intercept"],
            "beta": hedge["beta"],
            "fit_end_exclusive": hedge["fit_end_exclusive"],
            "validation_refit": False,
            "holdout_refit": False,
        },
        "stationarity": diagnostics,
        "stability": {
            "development_subwindows": stability,
            "coefficient_perturbations_holdout": perturbations,
        },
        "spread_diagnostics_development": {
            "residual_volatility": _sample_std(dev_residual),
            **_ar1_half_life(dev_residual),
        },
        "economic_effect": {
            "returns_or_pnl_computed": False,
            "economic_edge_inferred": False,
            "winning_pair_selected": False,
            "transaction_cost_claim": False,
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "protected_forward_opened": False,
            "live_orders_authorized": False,
        },
    }


def run_complete_scope(
    series_by_symbol: Mapping[str, Mapping[str, Any]],
    registry: Mapping[str, Any],
    alignment_inventory: Mapping[str, Any],
    quote_unit_authority: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Enumerate all 820 accepted pairs without ranking or retroactive narrowing."""
    validate_plan(plan)
    records = []
    for inventory_row in alignment_inventory.get("pairs") or []:
        left, right = inventory_row["symbols"]
        pair = prepare_inventory_bound_pair(
            left,
            right,
            series_by_symbol,
            registry,
            alignment_inventory,
            quote_unit_authority=quote_unit_authority,
        )
        records.append(diagnose_pair(pair, plan))
    if len(records) != 820:
        raise DiagnosticError("complete accepted pair scope was not enumerated")
    counts: dict[str, int] = {}
    for record in records:
        counts[record["classification"]] = counts.get(record["classification"], 0) + 1
    return {
        "schema": RESULT_SCHEMA,
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_DIAGNOSTIC_NO_PAIR_RANKING",
        "implementation_version": IMPLEMENTATION_VERSION,
        "plan_sha256": _canonical_sha256(plan),
        "accepted_pair_inventory_count": 820,
        "pair_records": records,
        "classification_counts": counts,
        "ranking": None,
        "winner": None,
        "economic_interpretation": None,
        "accounting_effect": {
            "v2_attempts_consumed": 0,
            "economic_outcomes_opened": 0,
            "search_budget_change": 0,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "account_mutation": False,
        },
    }


def execute(
    old_zip: Path,
    replacement_zip: Path,
    broker_universe_zip: Path,
    registry: Mapping[str, Any],
    replacement_acceptance: Mapping[str, Any],
    alignment_inventory: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    product_authority = build_broker_product_authority(broker_universe_zip, registry)
    series = build_accepted_price_series(
        old_zip,
        replacement_zip,
        registry,
        replacement_acceptance,
        alignment_inventory=alignment_inventory,
    )
    return run_complete_scope(
        series, registry, alignment_inventory, product_authority, plan
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=IMPLEMENTATION_VERSION)
    parser.add_argument("--old-zip", type=Path, required=True)
    parser.add_argument("--replacement-zip", type=Path, required=True)
    parser.add_argument("--broker-universe-zip", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--replacement-acceptance", type=Path, required=True)
    parser.add_argument("--alignment-inventory", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = execute(
        args.old_zip,
        args.replacement_zip,
        args.broker_universe_zip,
        load(args.registry),
        load(args.replacement_acceptance),
        load(args.alignment_inventory),
        load(args.plan),
    )
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
