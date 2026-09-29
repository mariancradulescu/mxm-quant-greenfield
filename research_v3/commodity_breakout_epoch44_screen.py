"""Prospectively frozen non-economic commodity-cash-CFD breakout discovery."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "MXM_EPOCH44_COMMODITY_BREAKOUT_COARSE_REGION_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH44_COMMODITY_BREAKOUT_DISCOVERY_FREEZE_V1.json"
RESULT_REF = "evidence/EPOCH45_COMMODITY_BREAKOUT_COARSE_REGION_RESULT_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_fd77b36965efba11da293f8a9c7a7782.json"
PROPOSAL_FILE_SHA256 = "d1f09390627de743519d70ce53a94ae716bff7db457d477e57c47498552a8c1e"
PROPOSAL_HASH = "f2046bf7da29b2da28c8bfb45e237af9c06686beb4428b0b86fc236fea32876c"
PROPOSAL_REGISTRY_REF = "research_v3/ai_director/PROPOSAL_REGISTRY_V1.json"
ACCEPTED_OPERATION_ID = "op_61c37b499421a4ef06da08fee22042e1"
ACCEPTANCE_REF = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json"
PLAN_REF = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_PLAN_V1.json"
PLAN_SHA256 = "b29e6f95dcd1adc3374f71124628388df7e235829fc019d31b1183166b9c7d6a"
DEVELOPMENT_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
FEASIBILITY_REF = "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json"
FEASIBILITY_SHA256 = "fbad721388da7f5e48dd54056aaf00fca8554d41daa9fb728e4c546ed50f7851"
CAPITAL_FRONTIER_REF = "data/BROKER_NATIVE_ADAPTIVE_INFORMATION_FRONTIER_V1.json"
CAPITAL_FRONTIER_SHA256 = "8fb15e9983f9a14bdc9a1b24667f03c83d2d15fcfc7f661f5e5f50d51852e9cf"
REGISTRY_REF = "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
REGISTRY_SHA256 = "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3"
COVERAGE_REF = "evidence/EPOCH21_ALL_FRONTIER_PREREQUISITE_COVERAGE_INVENTORY_V1.json"
COVERAGE_SHA256 = "c0898404076a27ac8063c20d490562cd85c0ee20a142617579bef949570bb092"
ARCHITECTURE_REF = "research_v3/ADAPTIVE_MECHANISM_DISCOVERY_ARCHITECTURE_V1.json"
ARCHITECTURE_SHA256 = "6b14648bad0aa8e0753f3771896892d0a7d70bd89911800ce9bdbafc0e96a568"
PARAMETER_GOVERNOR_REF = "research_v3/PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1.json"
PARAMETER_GOVERNOR_SHA256 = "9e7f911f60034b1a2daca6e70c473b2fa6504054beae87257656b6f245f3dc39"
START_UTC = "2026-06-15T00:00:00Z"
END_UTC = "2026-09-13T23:59:59Z"
LOOKBACKS = (12, 36, 48)
EXPANSION_MULTIPLES = (1.25, 1.5, 2.0)
HORIZONS = (3, 6, 12)
TARGETS = (
    ("Lead", 2791, "Commodities (Cash)"),
    ("Corn", 306, "Commodities (Cash)"),
    ("LDSugar", 148, "Commodities (Cash)"),
    ("Sugar", 106, "Commodities (Cash)"),
)
M5_SECONDS = 300
MIN_EFFECTIVE_DAYS = 10
MIN_HALF_DAYS = 5
CSV_FIELDS = ["time_utc", "open", "high", "low", "close", "tick_volume"]
NEIGHBOR_SUPPORT_FRACTION = 0.75


class CommodityBreakoutScanError(ValueError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CommodityBreakoutScanError(f"{path}: expected JSON object")
    return value


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommodityBreakoutScanError(f"invalid UTC timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise CommodityBreakoutScanError(f"timestamp lacks timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def _target_dicts() -> list[dict[str, Any]]:
    return [{"symbol": symbol, "symbol_id": symbol_id, "asset_class": asset_class}
            for symbol, symbol_id, asset_class in TARGETS]


def validate_freeze(freeze: dict[str, Any], root: Path) -> dict[str, Any]:
    if (freeze.get("schema") != "mxm.greenfield.epoch44-commodity-breakout-discovery-freeze.v1"
            or freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_COMMODITY_BREAKOUT_SURFACE_EVALUATION"
            or freeze.get("evidence_epoch") != 44
            or freeze.get("family") != "BREAKOUT_VOLATILITY_EXPANSION"
            or freeze.get("stage") != "NON_ECONOMIC_COMMODITY_CASH_CFD_COARSE_PARAMETER_REGION_DISCOVERY"):
        raise CommodityBreakoutScanError("unsupported or unfrozen commodity-breakout authority")

    authority = freeze.get("authority") or {}
    expected_authority = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
        "accepted_proposal_hash": PROPOSAL_HASH,
        "proposal_registry_ref": PROPOSAL_REGISTRY_REF,
        "accepted_operation_id": ACCEPTED_OPERATION_ID,
        "development_acceptance_ref": ACCEPTANCE_REF,
        "development_capture_plan_ref": PLAN_REF,
        "development_capture_plan_sha256": PLAN_SHA256,
        "development_zip_filename": "MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip",
        "development_zip_sha256": DEVELOPMENT_SHA256,
        "development_library_file_id": "libfile_f31adb42d4e88191b7b372af4f3f077a",
        "eur200_feasibility_index_ref": FEASIBILITY_REF,
        "eur200_feasibility_index_sha256": FEASIBILITY_SHA256,
        "capital_efficiency_frontier_ref": CAPITAL_FRONTIER_REF,
        "capital_efficiency_frontier_sha256": CAPITAL_FRONTIER_SHA256,
        "registry_ref": REGISTRY_REF,
        "registry_sha256": REGISTRY_SHA256,
        "coverage_inventory_ref": COVERAGE_REF,
        "coverage_inventory_sha256": COVERAGE_SHA256,
        "discovery_architecture_ref": ARCHITECTURE_REF,
        "discovery_architecture_sha256": ARCHITECTURE_SHA256,
        "parameter_governor_ref": PARAMETER_GOVERNOR_REF,
        "parameter_governor_sha256": PARAMETER_GOVERNOR_SHA256,
    }
    if authority != expected_authority:
        raise CommodityBreakoutScanError("accepted proposal or capture authority binding mismatch")

    for ref, expected in (
        (PROPOSAL_REF, PROPOSAL_FILE_SHA256),
        (FEASIBILITY_REF, FEASIBILITY_SHA256),
        (CAPITAL_FRONTIER_REF, CAPITAL_FRONTIER_SHA256),
        (REGISTRY_REF, REGISTRY_SHA256),
        (COVERAGE_REF, COVERAGE_SHA256),
        (ARCHITECTURE_REF, ARCHITECTURE_SHA256),
        (PARAMETER_GOVERNOR_REF, PARAMETER_GOVERNOR_SHA256),
    ):
        path = root / ref
        if not path.is_file() or sha256_file(path) != expected:
            raise CommodityBreakoutScanError(f"bound authority hash mismatch: {ref}")

    proposal = _load_json(root / PROPOSAL_REF)
    decision = proposal.get("decision") or {}
    implementation_scope = decision.get("implementation_scope") or {}
    scope = decision.get("scope") or {}
    if (proposal.get("proposal_id") != "E44_COMMODITY_BREAKOUT_DISCOVERY"
            or proposal.get("data_policy", {}).get("new_market_data_requested") is not False
            or decision.get("frontier") != "COMMODITIES_CASH_CFD"
            or decision.get("selected_mechanism_family") != "BREAKOUT_VOLATILITY_EXPANSION"
            or implementation_scope.get("next_action") != "IMPLEMENT_PROSPECTIVE_COMMODITY_BREAKOUT_DISCOVERY"
            or scope.get("stage") != "NON_ECONOMIC_DEVELOPMENT"
            or decision.get("economic_authorization") != "NONE"):
        raise CommodityBreakoutScanError("accepted proposal scope or non-economic boundary mismatch")
    registry_doc = _load_json(root / PROPOSAL_REGISTRY_REF)
    if not any(
        row.get("operation_id") == ACCEPTED_OPERATION_ID
        and row.get("proposal_id") == "E44_COMMODITY_BREAKOUT_DISCOVERY"
        and row.get("proposal_ref") == PROPOSAL_REF
        and row.get("proposal_hash") == PROPOSAL_HASH
        and row.get("economic_outcome_opened") is False
        and row.get("v2_attempt_consumed") == 0
        for row in registry_doc.get("accepted", [])
    ):
        raise CommodityBreakoutScanError("bound E44 decision is not accepted in proposal registry")

    acceptance = _load_json(root / ACCEPTANCE_REF)
    source = acceptance.get("source") or {}
    validation = acceptance.get("validation") or {}
    interval = acceptance.get("interval") or {}
    if (acceptance.get("status") != "ACCEPTED_COMPLETE_NON_ECONOMIC_DEVELOPMENT_CAPTURE"
            or source.get("zip_sha256") != DEVELOPMENT_SHA256
            or source.get("plan_sha256") != PLAN_SHA256
            or source.get("external_name") != "MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip"
            or validation.get("series_planned") != 40
            or validation.get("series_complete") != 40
            or validation.get("duplicate_timestamps_total") != 0
            or validation.get("out_of_interval_rows") != 0
            or validation.get("protected_forward_rows") != 0
            or validation.get("synthetic_fill_detected") is not False
            or validation.get("forward_fill_detected") is not False
            or interval != {"start_utc": START_UTC, "end_utc": END_UTC, "resolution": "M5"}):
        raise CommodityBreakoutScanError("accepted M5 development capture authority mismatch")

    plan = _load_json(root / PLAN_REF)
    if (plan.get("plan_sha256") != PLAN_SHA256
            or plan.get("resolution") != "M5"
            or plan.get("interval") != {"start_utc": START_UTC, "end_utc": END_UTC}
            or plan.get("protected_evidence_opened") is not False):
        raise CommodityBreakoutScanError("accepted M5 development plan scope mismatch")
    plan_commodities = []
    for item in plan.get("symbols", []):
        signature = item.get("structural_signature") or {}
        if signature.get("asset_class") == "Commodities (Cash)":
            plan_commodities.append({
                "symbol": item.get("broker_symbol"),
                "symbol_id": item.get("symbol_id"),
                "asset_class": signature.get("asset_class"),
            })
    expected_symbols = _target_dicts()
    if plan_commodities != expected_symbols:
        raise CommodityBreakoutScanError("cash-commodity scope does not match complete outcome-blind capture plan")

    structural = _load_json(root / REGISTRY_REF)
    representatives = structural.get("representatives") or []
    by_symbol = {item.get("broker_symbol"): item for item in representatives}
    for target in expected_symbols:
        row = by_symbol.get(target["symbol"])
        signature = row.get("signature") if row else None
        if (row is None or row.get("symbol_id") != target["symbol_id"]
                or not isinstance(signature, list) or not signature
                or signature[0] != "Commodities (Cash)"
                or row.get("has_13w_history") is not True):
            raise CommodityBreakoutScanError(f"target registry/history mismatch: {target['symbol']}")

    feasibility_index = _load_json(root / FEASIBILITY_REF)
    capital_frontier = _load_json(root / CAPITAL_FRONTIER_REF)
    frontier_rows = {
        item.get("broker_symbol"): item for item in capital_frontier.get("frontier", [])
    }
    for target in expected_symbols:
        product = (feasibility_index.get("products") or {}).get(target["symbol"])
        frontier_row = frontier_rows.get(target["symbol"])
        frontier_signature = frontier_row.get("signature") if frontier_row else None
        if (not isinstance(product, list) or len(product) < 2
                or product[0] != target["symbol_id"]
                or product[1] not in {"BOTH_FEASIBLE", "BUY_ONLY", "NEITHER_FEASIBLE"}
                or frontier_row is None
                or frontier_row.get("symbol_id") != target["symbol_id"]
                or not isinstance(frontier_signature, list) or not frontier_signature
                or frontier_signature[0] != "Commodities (Cash)"
                or not isinstance(frontier_row.get("min_margin_eur"), (int, float))
                or not math.isfinite(frontier_row["min_margin_eur"])
                or not isinstance(frontier_row.get("surface_minutes_per_margin_eur"), (int, float))
                or not math.isfinite(frontier_row["surface_minutes_per_margin_eur"])):
            raise CommodityBreakoutScanError(f"outcome-blind feasibility/capital authority mismatch: {target['symbol']}")

    expected_scope = {
        "frontier": "COMMODITIES_CASH_CFD",
        "selection_law": (
            "Process every symbol classified as Commodities (Cash) in the already accepted M5 development "
            "capture plan that has complete accepted M5 history; do not use price outcomes or prior screen "
            "results to select or omit symbols."
        ),
        "symbols": expected_symbols,
        "resolution": "M5",
        "interval": {"start_utc": START_UTC, "end_utc": END_UTC},
        "data_source": "EXACT_HASH_BOUND_ACCEPTED_DEVELOPMENT_ARCHIVE_ONLY",
        "parameter_cells_per_symbol": 27,
        "total_parameter_cells": 108,
        "structural_representatives_are_not_economically_equivalent": True,
        "broader_eligible_frontier_remains_open": True,
    }
    if freeze.get("scope") != expected_scope:
        raise CommodityBreakoutScanError("frozen commodity symbol/data scope mismatch")
    if freeze.get("universe_feature_policy") != {
        "outcome_blind": True,
        "include_every_cash_commodity_with_complete_accepted_m5_history": True,
        "reported_features": [
            "asset class, broker product type, and structural schedule signature",
            "accepted M5 rows and observed interval coverage",
            "breakout event density and volatility-expansion opportunity",
            "effective independent UTC-date sample size",
            "EUR200 directional feasibility and minimum-margin/capital-efficiency proxies",
        ],
        "conservative_friction_proxy": (
            "UNAVAILABLE_IN_BOUND_AUTHORITIES; DO_NOT_INFER_SPREAD_FROM_SINGLE_PRICE_OHLC"
        ),
        "price_outcomes_may_change_universe_membership": False,
        "prior_breakout_screen_results_may_change_universe_membership": False,
        "low_or_unavailable_power_does_not_close_the_frontier": True,
    }:
        raise CommodityBreakoutScanError("outcome-blind universe feature policy mismatch")

    grid = freeze.get("parameter_grid") or {}
    if grid != {
        "lookback_bars_M5": list(LOOKBACKS),
        "range_expansion_multiple": list(EXPANSION_MULTIPLES),
        "followthrough_horizon_bars_M5": list(HORIZONS),
        "cells_per_symbol": 27,
        "ranges_frozen_before_surface_evaluation": True,
        "record_every_probe": True,
        "winner_only_logging": False,
        "prior_breakout_diagnostic_exact_24bar_1_5x_cell_evaluated": False,
    }:
        raise CommodityBreakoutScanError("frozen parameter grid mismatch")

    mechanism = freeze.get("mechanism_law") or {}
    required_mechanism = {
        "event": (
            "At close of bar t, close_t is strictly above the maximum high or below the minimum low of the "
            "immediately preceding lookback completed, contiguous M5 bars, and the current high-low range is "
            "at least the frozen multiple of the median high-low range of those same preceding bars."
        ),
        "direction": (
            "UP when close_t exceeds the preceding maximum high; DOWN when close_t is below the preceding "
            "minimum low; all other bars are not events."
        ),
        "causal_timing": (
            "Event, direction, and reference range use only completed bars at or before t. Follow-through "
            "uses the close at t+h and only bars t+1 through t+h."
        ),
        "missing_data": (
            "No fill, interpolation, resampling, or synthetic bars. Every event and follow-through window "
            "must have exact 300-second timestamp increments; gaps invalidate any window crossing them."
        ),
        "zero_range_policy": (
            "A zero prior median range permits an event only when the current range is positive; such an event "
            "has no valid normalized response scale and is reported as excluded from response inference."
        ),
        "independence": (
            "Retain the first qualifying event per symbol, parameter cell, and UTC date only when the full "
            "event and follow-through windows are contiguous and the prior median range is positive."
        ),
        "daily_statistic": (
            "For each retained event/date, compute direction times (close at t+h minus close at t) divided by "
            "the prior median high-low range. This is a dimensionless structural price-response statistic, not "
            "a strategy return, PnL, executable result, or cost-adjusted outcome."
        ),
        "uncertainty": (
            "Average event responses within each UTC date; report the mean of daily cluster values, standard "
            "error across daily clusters, descriptive normal-approximation 95% interval, and effective sample "
            "size in UTC dates. Chronological halves are descriptive stability diagnostics."
        ),
        "multiplicity": (
            "Compute a one-sided exact positive-sign test over daily cluster values for every symbol-cell; "
            "apply Benjamini-Yekutieli adjustment across all 108 predeclared symbol-cell tests. Adjusted values "
            "are exploratory and do not authorize promotion."
        ),
    }
    if mechanism != required_mechanism:
        raise CommodityBreakoutScanError("frozen event, outcome, or inference law mismatch")

    robustness = freeze.get("robustness_law") or {}
    if robustness != {
        "local_support": (
            "Positive overall mean daily response, at least 10 effective UTC dates, at least 5 dates in each "
            "chronological half, and positive mean response in both halves."
        ),
        "direct_neighborhood": (
            "Cells differing by exactly one adjacent frozen grid step on exactly one parameter axis are direct neighbors."
        ),
        "broad_local_neighborhood_support": (
            "Local support and positive effects for at least 75% of all direct neighbors, with at least two direct neighbors."
        ),
        "commodity_breadth": (
            "A parameter cell has breadth support when at least two of the four frozen cash-commodity symbols "
            "meet local support; this is descriptive and not a significance requirement."
        ),
        "robust_region": (
            "A connected direct-adjacent component of breadth-supported parameter cells containing at least "
            "three cells and varying on at least two parameter dimensions."
        ),
        "winner_selection": "No observed per-symbol or per-cell winner may be selected for promotion.",
    }:
        raise CommodityBreakoutScanError("frozen neighborhood or breadth law mismatch")

    boundary = freeze.get("interpretation_boundary") or {}
    safety = freeze.get("safety") or {}
    if (boundary.get("prior_breakout_screen_results_are_inputs") is not False
            or boundary.get("internal_development_data_is_independent_confirmation") is not False
            or boundary.get("economic_promotion_authorized") is not False
            or boundary.get("mechanism_family_closed") is not False
            or boundary.get("asset_class_closed") is not False
            or boundary.get("winner_selected") is not False
            or boundary.get("candidate_identity_created") is not False
            or boundary.get("protected_forward_opened") is not False
            or safety.get("protected_forward_opened") is not False
            or safety.get("live_orders_authorized") is not False
            or safety.get("competition_start_authorized") is not False
            or freeze.get("accounting_effect") != {
                "economic_outcomes_opened": 0,
                "v2_attempts_consumed": 0,
                "search_budget_change": 0,
            }):
        raise CommodityBreakoutScanError("non-economic safety or interpretation boundary mismatch")
    return structural


def _read_symbol(archive: zipfile.ZipFile, symbol_id: int, symbol: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        manifest = json.loads(archive.read("capture_manifest.json"))
    except (KeyError, json.JSONDecodeError) as exc:
        raise CommodityBreakoutScanError("accepted capture manifest missing or invalid") from exc
    series = [
        item for item in manifest.get("series", [])
        if item.get("broker_symbol") == symbol and item.get("symbol_id") == symbol_id
    ]
    if len(series) != 1:
        raise CommodityBreakoutScanError(f"accepted series identity missing or ambiguous: {symbol}/{symbol_id}")
    item = series[0]
    if (item.get("capture_status") != "SERIES_CAPTURE_COMPLETE"
            or item.get("synthetic_fill") is not False or item.get("forward_fill") is not False):
        raise CommodityBreakoutScanError(f"series not accepted complete without fill: {symbol}")
    member = item.get("file")
    if not isinstance(member, str) or member not in archive.namelist():
        raise CommodityBreakoutScanError(f"exact accepted series member missing: {symbol}")
    raw = archive.read(member)
    if sha256_bytes(raw) != item.get("sha256"):
        raise CommodityBreakoutScanError(f"series member hash mismatch: {symbol}")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames != CSV_FIELDS:
        raise CommodityBreakoutScanError(f"unexpected M5 CSV columns: {symbol}")

    start, end = _parse_utc(START_UTC), _parse_utc(END_UTC)
    rows: list[dict[str, Any]] = []
    previous: datetime | None = None
    for source in reader:
        timestamp = _parse_utc(source["time_utc"])
        try:
            values = {name: float(source[name]) for name in CSV_FIELDS[1:]}
        except (TypeError, ValueError) as exc:
            raise CommodityBreakoutScanError(f"invalid numeric M5 field: {symbol}") from exc
        if (not all(math.isfinite(value) for value in values.values())
                or min(values[name] for name in ("open", "high", "low", "close")) <= 0.0
                or values["tick_volume"] < 0.0
                or values["high"] < max(values["open"], values["close"], values["low"])
                or values["low"] > min(values["open"], values["close"], values["high"])
                or timestamp < start or timestamp > end):
            raise CommodityBreakoutScanError(f"invalid or out-of-scope market row: {symbol}")
        if previous is not None and (timestamp - previous).total_seconds() <= 0:
            raise CommodityBreakoutScanError(f"non-increasing or duplicate M5 timestamp: {symbol}")
        previous = timestamp
        rows.append({"timestamp": timestamp, **values})
    if not rows or len(rows) != item.get("row_count"):
        raise CommodityBreakoutScanError(f"empty series or manifest row-count mismatch: {symbol}")
    return rows, {
        "member": member,
        "sha256": item["sha256"],
        "row_count": len(rows),
        "first_timestamp_utc": rows[0]["timestamp"].isoformat().replace("+00:00", "Z"),
        "last_timestamp_utc": rows[-1]["timestamp"].isoformat().replace("+00:00", "Z"),
    }


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _positive_sign_p(values: list[float]) -> float:
    nonzero = [value for value in values if value != 0.0]
    if not nonzero:
        return 1.0
    positive = sum(value > 0.0 for value in nonzero)
    n = len(nonzero)
    return math.fsum(math.comb(n, index) for index in range(positive, n + 1)) / (2 ** n)


def _benjamini_yekutieli(p_values: dict[str, float]) -> dict[str, float]:
    count = len(p_values)
    if not count:
        return {}
    harmonic = math.fsum(1.0 / index for index in range(1, count + 1))
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank in range(count, 0, -1):
        key, p_value = ordered[rank - 1]
        running = min(running, p_value * count * harmonic / rank)
        adjusted[key] = min(1.0, running)
    return adjusted


def _cell_key(lookback: int, expansion: float, horizon: int) -> str:
    return f"L{lookback}_R{expansion:g}_H{horizon}"


def _neighbor_keys(lookback: int, expansion: float, horizon: int) -> list[str]:
    indices = (
        (LOOKBACKS.index(lookback), LOOKBACKS),
        (EXPANSION_MULTIPLES.index(expansion), EXPANSION_MULTIPLES),
        (HORIZONS.index(horizon), HORIZONS),
    )
    neighbors = []
    for axis, (index, values) in enumerate(indices):
        for delta in (-1, 1):
            next_index = index + delta
            if not 0 <= next_index < len(values):
                continue
            params = [lookback, expansion, horizon]
            params[axis] = values[next_index]
            neighbors.append(_cell_key(int(params[0]), float(params[1]), int(params[2])))
    return neighbors


def _evaluate_cell(rows: list[dict[str, Any]], lookback: int, expansion: float, horizon: int) -> dict[str, Any]:
    daily: dict[str, float] = {}
    examined = candidates = retained = 0
    excluded = {
        "noncontiguous_lookback_windows": 0,
        "noncontiguous_or_incomplete_followthrough": 0,
        "zero_prior_median_range": 0,
        "duplicate_utc_date_event": 0,
    }
    for index in range(lookback, len(rows)):
        prior = rows[index - lookback:index]
        current = rows[index]
        if any((prior[pos]["timestamp"] - prior[pos - 1]["timestamp"]).total_seconds() != M5_SECONDS
               for pos in range(1, len(prior))):
            excluded["noncontiguous_lookback_windows"] += 1
            continue
        if (current["timestamp"] - prior[-1]["timestamp"]).total_seconds() != M5_SECONDS:
            excluded["noncontiguous_lookback_windows"] += 1
            continue
        examined += 1
        prior_high = max(row["high"] for row in prior)
        prior_low = min(row["low"] for row in prior)
        prior_median_range = statistics.median(row["high"] - row["low"] for row in prior)
        current_range = current["high"] - current["low"]
        direction = 1 if current["close"] > prior_high else -1 if current["close"] < prior_low else 0
        expands = current_range >= expansion * prior_median_range if prior_median_range > 0 else current_range > 0
        if direction == 0 or not expands:
            continue
        candidates += 1
        end_index = index + horizon
        if end_index >= len(rows) or any(
            (rows[pos]["timestamp"] - rows[pos - 1]["timestamp"]).total_seconds() != M5_SECONDS
            for pos in range(index + 1, end_index + 1)
        ):
            excluded["noncontiguous_or_incomplete_followthrough"] += 1
            continue
        if prior_median_range <= 0:
            excluded["zero_prior_median_range"] += 1
            continue
        day = current["timestamp"].date().isoformat()
        if day in daily:
            excluded["duplicate_utc_date_event"] += 1
            continue
        response = direction * (rows[end_index]["close"] - current["close"]) / prior_median_range
        if not math.isfinite(response):
            raise CommodityBreakoutScanError("non-finite normalized response")
        daily[day] = response
        retained += 1

    ordered = sorted(daily.items())
    values = [value for _, value in ordered]
    midpoint = len(values) // 2
    halves = (values[:midpoint], values[midpoint:])
    half_means = [_mean(part) for part in halves]
    effect = _mean(values)
    se = statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None
    local_support = bool(
        effect is not None and effect > 0.0 and len(values) >= MIN_EFFECTIVE_DAYS
        and len(halves[0]) >= MIN_HALF_DAYS and len(halves[1]) >= MIN_HALF_DAYS
        and all(mean is not None and mean > 0.0 for mean in half_means)
    )
    return {
        "effect_size": effect,
        "effect_size_unit": "MEAN_DAILY_DIRECTIONAL_DISPLACEMENT_IN_PRIOR_MEDIAN_RANGES",
        "uncertainty": {
            "cluster_standard_error": se,
            "descriptive_95pct_interval": [effect - 1.96 * se, effect + 1.96 * se]
            if effect is not None and se is not None else None,
            "method": "UTC_DATE_CLUSTERED_SAMPLE_STANDARD_ERROR_NORMAL_APPROXIMATION",
        },
        "effective_independent_sample_size_utc_dates": len(values),
        "daily_cluster_responses": dict(ordered),
        "chronological_half_stability": {
            "partition": "CHRONOLOGICAL_UTC_EVENT_DATE_HALVES",
            "half_1_effective_dates": len(halves[0]),
            "half_2_effective_dates": len(halves[1]),
            "half_1_mean_response": half_means[0],
            "half_2_mean_response": half_means[1],
            "both_halves_positive": bool(
                half_means[0] is not None and half_means[1] is not None
                and half_means[0] > 0.0 and half_means[1] > 0.0
            ),
        },
        "event_accounting": {
            "eligible_contiguous_windows": examined,
            "event_candidates": candidates,
            "retained_independent_date_events": retained,
            "excluded_events": excluded,
            "events_per_eligible_window": candidates / examined if examined else 0.0,
        },
        "local_support": local_support,
        "uncorrected_one_sided_exact_positive_sign_p": _positive_sign_p(values),
    }


def evaluate_symbol_rows(rows: list[dict[str, Any]], symbol: str, symbol_id: int, asset_class: str) -> dict[str, Any]:
    cells: dict[str, dict[str, Any]] = {}
    for lookback in LOOKBACKS:
        for expansion in EXPANSION_MULTIPLES:
            for horizon in HORIZONS:
                key = _cell_key(lookback, expansion, horizon)
                cell = _evaluate_cell(rows, lookback, expansion, horizon)
                cell.update({
                    "symbol": symbol,
                    "symbol_id": symbol_id,
                    "asset_class": asset_class,
                    "lookback_bars_M5": lookback,
                    "range_expansion_multiple": expansion,
                    "followthrough_horizon_bars_M5": horizon,
                })
                cells[key] = cell
    if len(cells) != 27:
        raise CommodityBreakoutScanError(f"not all frozen parameter cells emitted for {symbol}")
    for key, cell in cells.items():
        lookback = cell["lookback_bars_M5"]
        expansion = cell["range_expansion_multiple"]
        horizon = cell["followthrough_horizon_bars_M5"]
        adjacent = [cells[neighbor] for neighbor in _neighbor_keys(lookback, expansion, horizon)]
        positive_fraction = (
            sum(item["effect_size"] is not None and item["effect_size"] > 0 for item in adjacent) / len(adjacent)
            if adjacent else 0.0
        )
        cell["robust_neighborhood_metrics"] = {
            "direct_neighbor_count": len(adjacent),
            "positive_effect_neighbor_fraction": positive_fraction,
            "broad_local_neighborhood_support": bool(
                cell["local_support"] and len(adjacent) >= 2
                and positive_fraction >= NEIGHBOR_SUPPORT_FRACTION
            ),
        }
    return {
        "symbol": symbol,
        "symbol_id": symbol_id,
        "asset_class": asset_class,
        "observed_rows": len(rows),
        "observed_interval_utc": {
            "first": rows[0]["timestamp"].isoformat().replace("+00:00", "Z") if rows else None,
            "last": rows[-1]["timestamp"].isoformat().replace("+00:00", "Z") if rows else None,
        },
        "volatility_opportunity_proxy": {
            "median_relative_m5_high_low_range": statistics.median(
                (row["high"] - row["low"]) / row["close"] for row in rows
            ) if rows else None,
            "interpretation": "DESCRIPTIVE_RANGE_OPPORTUNITY_PROXY_NOT_DIRECTIONAL_OR_ECONOMIC_OUTCOME",
        },
        "parameter_cells_emitted": len(cells),
        "cells": cells,
    }


def _surface_summary(symbols: dict[str, dict[str, Any]]) -> dict[str, Any]:
    per_cell = []
    for lookback in LOOKBACKS:
        for expansion in EXPANSION_MULTIPLES:
            for horizon in HORIZONS:
                key = _cell_key(lookback, expansion, horizon)
                supported = [name for name, data in symbols.items() if data["cells"][key]["local_support"]]
                effects = [data["cells"][key]["effect_size"] for data in symbols.values()
                           if data["cells"][key]["effect_size"] is not None]
                per_cell.append({
                    "cell": key,
                    "lookback_bars_M5": lookback,
                    "range_expansion_multiple": expansion,
                    "followthrough_horizon_bars_M5": horizon,
                    "supported_symbol_count": len(supported),
                    "supported_symbols": supported,
                    "median_symbol_effect_size": statistics.median(effects) if effects else None,
                    "commodity_breadth_support": len(supported) >= 2,
                })
    by_key = {item["cell"]: item for item in per_cell}
    qualifying = {item["cell"] for item in per_cell if item["commodity_breadth_support"]}
    visited: set[str] = set()
    components = []
    for start in sorted(qualifying):
        if start in visited:
            continue
        stack = [start]
        component = []
        while stack:
            key = stack.pop()
            if key in visited or key not in qualifying:
                continue
            visited.add(key)
            component.append(key)
            item = by_key[key]
            stack.extend(neighbor for neighbor in _neighbor_keys(
                item["lookback_bars_M5"], item["range_expansion_multiple"],
                item["followthrough_horizon_bars_M5"],
            ) if neighbor in qualifying and neighbor not in visited)
        items = [by_key[key] for key in component]
        varied_dimensions = sum(
            len({item[field] for item in items}) > 1
            for field in ("lookback_bars_M5", "range_expansion_multiple", "followthrough_horizon_bars_M5")
        )
        components.append({
            "cells": sorted(component),
            "cell_count": len(component),
            "varied_parameter_dimensions": varied_dimensions,
            "broad_robust_region": len(component) >= 3 and varied_dimensions >= 2,
        })
    return {
        "predeclared_cell_breadth": per_cell,
        "connected_breadth_components": components,
        "robust_region_count": sum(item["broad_robust_region"] for item in components),
        "criterion": ">=2/4 locally supported symbols at a cell; a broad region is a connected component of >=3 such cells varying in >=2 grid dimensions.",
    }


def evaluate(freeze: dict[str, Any], development_zip: Path, root: Path) -> dict[str, Any]:
    validate_freeze(freeze, root)
    observed_zip_hash = sha256_file(development_zip)
    if observed_zip_hash != DEVELOPMENT_SHA256:
        raise CommodityBreakoutScanError(
            f"accepted development ZIP hash mismatch: expected {DEVELOPMENT_SHA256}, observed {observed_zip_hash}"
        )
    symbols: dict[str, dict[str, Any]] = {}
    input_series = {}
    with zipfile.ZipFile(development_zip) as archive:
        try:
            capture_manifest = json.loads(archive.read("capture_manifest.json"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise CommodityBreakoutScanError("accepted capture manifest missing or invalid") from exc
        if (capture_manifest.get("resolution") != "M5"
                or capture_manifest.get("protected_evidence_opened") is not False
                or capture_manifest.get("economic_outcomes_opened") != 0):
            raise CommodityBreakoutScanError("capture archive safety or resolution mismatch")
        for symbol, symbol_id, asset_class in TARGETS:
            rows, attestation = _read_symbol(archive, symbol_id, symbol)
            symbols[symbol] = evaluate_symbol_rows(rows, symbol, symbol_id, asset_class)
            input_series[symbol] = attestation
    if len(symbols) != 4 or sum(item["parameter_cells_emitted"] for item in symbols.values()) != 108:
        raise CommodityBreakoutScanError("incomplete frozen commodity screen")

    p_values = {
        f"{symbol}|{key}": cell["uncorrected_one_sided_exact_positive_sign_p"]
        for symbol, data in symbols.items() for key, cell in data["cells"].items()
    }
    adjusted = _benjamini_yekutieli(p_values)
    for symbol, data in symbols.items():
        for key, cell in data["cells"].items():
            test_key = f"{symbol}|{key}"
            cell["multiplicity"] = {
                "family_size": len(p_values),
                "family_scope": "ALL_4_FROZEN_SYMBOLS_X_27_FROZEN_PARAMETER_CELLS",
                "benjamini_yekutieli_adjusted_p": adjusted[test_key],
                "interpretation": "EXPLORATORY_DATE_CLUSTER_SIGN_TEST_NOT_CONFIRMATORY_OR_PROMOTIONAL",
            }
    feasibility_index = _load_json(root / FEASIBILITY_REF)
    capital_frontier = _load_json(root / CAPITAL_FRONTIER_REF)
    frontier_rows = {
        item["broker_symbol"]: item for item in capital_frontier["frontier"]
        if item.get("broker_symbol") in symbols
    }
    registry_rows = {
        item["broker_symbol"]: item for item in _load_json(root / REGISTRY_REF)["representatives"]
        if item.get("broker_symbol") in symbols
    }
    universe_context = {}
    for symbol, symbol_id, asset_class in TARGETS:
        product = feasibility_index["products"][symbol]
        capital_row = frontier_rows[symbol]
        structural_row = registry_rows[symbol]
        attestation = input_series[symbol]
        universe_context[symbol] = {
            "symbol_id": symbol_id,
            "asset_class": asset_class,
            "product_type": structural_row["signature"][1],
            "structural_signature": structural_row["signature"],
            "structural_schedule_signature": structural_row["signature"][2:],
            "accepted_m5_observed_rows": attestation["row_count"],
            "accepted_m5_first_timestamp_utc": attestation["first_timestamp_utc"],
            "accepted_m5_last_timestamp_utc": attestation["last_timestamp_utc"],
            "eur200_directional_feasibility_status": product[1],
            "minimum_margin_eur_outcome_blind_proxy": capital_row["min_margin_eur"],
            "surface_minutes_per_margin_eur_outcome_blind_proxy": capital_row["surface_minutes_per_margin_eur"],
            "conservative_friction_proxy": "UNAVAILABLE_IN_BOUND_AUTHORITIES; NOT_INFERRED_FROM_SINGLE_PRICE_OHLC",
        }
    return {
        "schema": "mxm.greenfield.epoch45-commodity-breakout-coarse-region-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_COMMODITY_BREAKOUT_STRUCTURAL_DISCOVERY",
        "authorizing_evidence_epoch": 44,
        "evidence_epoch": 45,
        "family": "BREAKOUT_VOLATILITY_EXPANSION",
        "stage": "NON_ECONOMIC_COMMODITY_CASH_CFD_COARSE_PARAMETER_REGION_DISCOVERY",
        "freeze_ref": FREEZE_REF,
        "implementation": {"version": VERSION},
        "input_attestation": {
            "accepted_proposal_file_sha256": PROPOSAL_FILE_SHA256,
            "accepted_proposal_hash": PROPOSAL_HASH,
            "development_capture_plan_sha256": PLAN_SHA256,
            "development_zip_sha256": observed_zip_hash,
            "development_library_file_id": "libfile_f31adb42d4e88191b7b372af4f3f077a",
            "eur200_feasibility_index_sha256": FEASIBILITY_SHA256,
            "capital_efficiency_frontier_sha256": CAPITAL_FRONTIER_SHA256,
            "series": input_series,
            "protected_forward_rows_read": 0,
            "new_market_data_acquired": False,
            "prior_breakout_screen_results_used": False,
        },
        "scope": {
            "frontier": "COMMODITIES_CASH_CFD",
            "symbols_processed": len(symbols),
            "parameter_cells_per_symbol": 27,
            "parameter_cells_evaluated": 108,
            "internal_development_data_is_independent_confirmation": False,
            "broader_eligible_frontier_remains_open": True,
        },
        "multiplicity": {
            "method": "BENJAMINI_YEKUTIELI",
            "family_size": len(p_values),
            "family_scope": "ALL_4_FROZEN_SYMBOLS_X_27_FROZEN_PARAMETER_CELLS",
            "p_value": "ONE_SIDED_EXACT_POSITIVE_SIGN_TEST_ON_DAILY_CLUSTER_RESPONSES",
            "confirmatory_authority": False,
        },
        "symbols": symbols,
        "outcome_blind_universe_features": universe_context,
        "structural_diversity": {
            "unique_broker_structural_signatures": len({
                tuple(universe_context[symbol]["structural_signature"])
                for symbol, _, _ in TARGETS
            }),
            "unique_schedule_signatures": len({
                tuple(universe_context[symbol]["structural_schedule_signature"])
                for symbol, _, _ in TARGETS
            }),
            "representatives_are_economically_equivalent": False,
        },
        "surface_summary": _surface_summary(symbols),
        "interpretation_boundary": {
            "structural_price_response_only": True,
            "strategy_returns_or_pnl_computed": False,
            "cost_or_friction_adjustment_computed": False,
            "prior_breakout_screen_results_used": False,
            "internal_development_data_is_independent_confirmation": False,
            "winner_selected": False,
            "candidate_identity_created": False,
            "economic_promotion_authorized": False,
            "mechanism_family_closed": False,
            "asset_class_closed": False,
            "protected_forward_opened": False,
        },
        "accounting_effect": {
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "search_budget_change": 0,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "competition_start_authorized": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--development-zip", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    source = args.development_zip or root / (
        "research_v3/runtime_v2_inputs/MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip"
    )
    output = args.output or root / RESULT_REF
    if output.exists():
        raise CommodityBreakoutScanError("result already exists; exactly-once operation will not overwrite it")
    result = evaluate(_load_json(root / FREEZE_REF), source, root)
    result["freeze_sha256"] = sha256_file(root / FREEZE_REF)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "result_ref": str(output),
        "symbols_processed": result["scope"]["symbols_processed"],
        "parameter_cells_evaluated": result["scope"]["parameter_cells_evaluated"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
