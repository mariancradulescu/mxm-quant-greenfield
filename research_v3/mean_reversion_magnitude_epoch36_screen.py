"""Prospectively frozen, non-economic Epoch36 unsigned reversion-magnitude screen."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import zipfile
from pathlib import Path
from typing import Any

from research_v3.breakout_unsigned_volatility_epoch35_screen import (
    DEVELOPMENT_SHA256,
    DEVELOPMENT_ACCEPTANCE_REF,
    REPLACEMENT_ACCEPTANCE_REF,
    REPLACEMENT_IDS,
    REPLACEMENT_SHA256,
    SUPERSEDED_DEVELOPMENT_IDS,
    _load_archive,
    _load_replacement_archive,
)

VERSION = "MXM_EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_STRUCTURAL_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_FRONTIER_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_60c35177b58bab7c680cec8c9ef01bae.json"
PROPOSAL_SHA256 = "52276c4b1c0103bdcf7d4bc6d000eca5e97b314ce8d2be1db9af80f16b671a85"
CURRENT_FRONTIER_REF = "research_v3/CURRENT_RESEARCH_FRONTIER_V1.json"
CURRENT_FRONTIER_SHA256 = "2e8cbe434a776d36ec494e7fbd642c36098400c38132cb57c734d6a60ab0f69b"
REGISTRY_REF = "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
REGISTRY_SHA256 = "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3"
COVERAGE_REF = "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_STRUCTURAL_COVERAGE_EPOCH23_V1.json"
COVERAGE_SHA256 = "5cfb0662b12f1f42f8f5c503df64f42716dab98ba5729ab7e6eef75bce2c5dec"
M5_SECONDS = 300
WINDOW_BARS = 12
ANCHOR_STRIDE_BARS = 12
FORWARD_BARS = 12
Z_THRESHOLD = 2.0
MIN_DATES_PER_HALF = 10
FDR = 0.05
RESULT_REF = "evidence/EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_STRUCTURAL_RESULT_V1.json"


class Epoch36ScreenError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    from hashlib import sha256

    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Epoch36ScreenError(f"{path}: expected JSON object")
    return value


def _bound_file(root: Path, ref: str, expected: str) -> dict[str, Any]:
    path = root / ref
    if not path.is_file() or sha256_file(path) != expected:
        raise Epoch36ScreenError(f"bound authority hash mismatch: {ref}")
    return _load_json(path)


def validate_freeze(freeze: dict[str, Any], root: Path) -> dict[str, Any]:
    if (freeze.get("schema") != "mxm.greenfield.epoch36-mean-reversion-magnitude-persistence-frontier-freeze.v1"
            or freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_EPOCH36_MEAN_REVERSION_MAGNITUDE_SCREEN"
            or freeze.get("evidence_epoch") != 35
            or freeze.get("family") != "MEAN_REVERSION"):
        raise Epoch36ScreenError("unsupported or unfrozen Epoch36 authority")

    authority = freeze.get("authority") or {}
    expected_authority = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "accepted_proposal_file_sha256": PROPOSAL_SHA256,
        "current_frontier_ref": CURRENT_FRONTIER_REF,
        "current_frontier_sha256": CURRENT_FRONTIER_SHA256,
        "registry_ref": REGISTRY_REF,
        "registry_sha256": REGISTRY_SHA256,
        "coverage_ref": COVERAGE_REF,
        "coverage_sha256": COVERAGE_SHA256,
        "development_acceptance_ref": DEVELOPMENT_ACCEPTANCE_REF,
        "development_zip_filename": "MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip",
        "development_zip_sha256": DEVELOPMENT_SHA256,
        "replacement_acceptance_ref": REPLACEMENT_ACCEPTANCE_REF,
        "replacement_zip_filename": "MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip",
        "replacement_zip_sha256": REPLACEMENT_SHA256,
    }
    if any(authority.get(key) != value for key, value in expected_authority.items()):
        raise Epoch36ScreenError("Epoch36 authority binding mismatch")
    proposal = _bound_file(root, PROPOSAL_REF, PROPOSAL_SHA256)
    current = _bound_file(root, CURRENT_FRONTIER_REF, CURRENT_FRONTIER_SHA256)
    registry = _bound_file(root, REGISTRY_REF, REGISTRY_SHA256)
    coverage = _bound_file(root, COVERAGE_REF, COVERAGE_SHA256)
    if (proposal.get("proposal_id") != "AUTO_reason_60c35177b58bab7c680cec8c9ef01bae"
            or current.get("current_structural_registry_ref") != REGISTRY_REF
            or current.get("evidence_epoch") != 28
            or registry.get("status") != "CURRENT_STRUCTURAL_FRONTIER_RECOMPUTED_FROM_ACCEPTED_BROKER_NATIVE_METADATA"
            or registry.get("counts", {}).get("representative_count") != 41
            or not isinstance(registry.get("representatives"), list)
            or len(registry["representatives"]) != 41
            or coverage.get("status") != "COMPLETE_NON_ECONOMIC_CURRENT_REPRESENTATIVE_COVERAGE_RESTORED"
            or coverage.get("current_representative_history_coverage", {}).get("status") != "PASS_41_OF_41"):
        raise Epoch36ScreenError("bound 41-representative accepted data authority is incomplete")
    representatives = registry["representatives"]
    symbols = [item.get("broker_symbol") for item in representatives]
    ids = [item.get("symbol_id") for item in representatives]
    if (len(set(symbols)) != 41 or len(set(ids)) != 41
            or not all(isinstance(symbol, str) and symbol for symbol in symbols)
            or not all(isinstance(symbol_id, int) for symbol_id in ids)):
        raise Epoch36ScreenError("bound registry has missing or duplicate symbol identities")
    development_acceptance = _load_json(root / DEVELOPMENT_ACCEPTANCE_REF)
    replacement_acceptance = _load_json(root / REPLACEMENT_ACCEPTANCE_REF)
    if (development_acceptance.get("status") != "ACCEPTED_COMPLETE_NON_ECONOMIC_DEVELOPMENT_CAPTURE"
            or development_acceptance.get("source", {}).get("zip_sha256") != DEVELOPMENT_SHA256
            or development_acceptance.get("validation", {}).get("series_complete") != 40
            or replacement_acceptance.get("status") != "ACCEPTED_AFTER_DETERMINISTIC_CANONICALIZATION_OF_IDENTICAL_DUPLICATES"
            or replacement_acceptance.get("capture_provenance", {}).get("returned_transport_zip_sha256") != REPLACEMENT_SHA256):
        raise Epoch36ScreenError("accepted capture records do not bind the exact frozen archives")

    scope = freeze.get("scope") or {}
    if (scope.get("frontier") != "ALL_41_CURRENT_STRUCTURAL_REPRESENTATIVES_EXACTLY_ONCE"
            or scope.get("representative_count") != 41
            or scope.get("representatives_are_not_economically_equivalent") is not True
            or scope.get("resolution") != "M5"
            or scope.get("interval") != {
                "start_utc": "2026-06-15T00:00:00Z",
                "end_utc": "2026-09-13T23:59:59Z",
            }
            or scope.get("development_representative_count") != 38
            or scope.get("replacement_representative_ids") != [7427, 5352, 2924]
            or scope.get("selection_law") != "PROCESS_ALL_41_CURRENT_REGISTRY_REPRESENTATIVES_WITHOUT_OUTCOME_BASED_SUBSETTING"
            or not REPLACEMENT_IDS.issubset(set(ids))):
        raise Epoch36ScreenError("frozen Epoch36 data and frontier scope mismatch")

    law = freeze.get("preregistered_structural_law") or {}
    inference = law.get("inference") or {}
    if (law.get("signal_window_bars") != WINDOW_BARS
            or law.get("signal_window_includes_event_bar") is not True
            or law.get("signal_center") != "ARITHMETIC_MEAN_OF_THE_12_CLOSES_ENDING_AT_EVENT_BAR"
            or law.get("signal_scale") != "POPULATION_STANDARD_DEVIATION_OF_THE_SAME_12_CLOSES"
            or law.get("extreme_z_threshold") != Z_THRESHOLD
            or law.get("zero_scale_policy") != "No event is emitted when the 12-close population standard deviation is zero."
            or law.get("anchor_lattice") != (
                "Within each exact-contiguous M5 segment, evaluate index 11 and then every 12 observed bars; "
                "restart at index 11 after each missing or off-cadence interval."
            )
            or law.get("outcome") != (
                "At t+12 completed M5 bars, calculate the absolute distance of the close from the event-time "
                "rolling mean. The standardized absolute-distance contraction is "
                "(abs(close_t - center_t) - abs(close_t+12 - center_t)) / scale_t. "
                "Positive values indicate movement toward the frozen event-time mean, for upper and lower extremes alike."
            )
            or law.get("causal_timing") != (
                "The event, center, and scale use only the 12 completed closes ending at t; the outcome uses only "
                "close at t+12 and the event-time center and scale."
            )
            or law.get("independence") != (
                "Retain at most one eligible event per symbol per UTC date: the first extreme anchor with a "
                "complete exact-contiguous 12-bar forward window and nonzero event-time scale."
            )
            or inference.get("minimum_eligible_dates_per_half") != MIN_DATES_PER_HALF
            or inference.get("partition") != (
                "Sort eligible UTC event dates chronologically; first floor(N/2) dates are half 1 "
                "and remaining dates are half 2."
            )
            or inference.get("test") != (
                "ONE_SIDED_EXACT_BINOMIAL_SIGN_TEST_OF_POSITIVE_STANDARDIZED_ABSOLUTE_DISTANCE_CONTRACTION; "
                "omit exact-zero outcomes from the sign-test denominator."
            )
            or inference.get("raw_symbol_support") != (
                "Both halves meet minimum date sufficiency, both sample medians are strictly positive, "
                "and both one-sided exact sign-test p-values are at most 0.05."
            )
            or inference.get("symbol_family") != (
                "Fixed family of all 41 current structural representatives; insufficient symbols remain in the family with p-value 1."
            )
            or inference.get("multiplicity") != (
                "BENJAMINI_HOCHBERG_FALSE_DISCOVERY_RATE_ACROSS_41_SYMBOLS_USING_LARGER_HALF_P_VALUE_PER_SYMBOL"
            )
            or inference.get("false_discovery_rate") != FDR
            or law.get("missing_data") != (
                "No fill, interpolation, resampling, or synthetic bars. Any timestamp delta other than exactly "
                "300 seconds invalidates a window that crosses it. Missing, invalid, non-contiguous, or zero-scale "
                "event windows are excluded, not repaired."
            )
            or law.get("input_validation") != (
                "Require exact accepted archive hashes, M5 manifests, the frozen 41-symbol registry split "
                "(38 development and 3 replacements), matching series identities and member hashes, finite positive "
                "OHLC, valid OHLC bounds, UTC timestamps within the accepted interval, and no synthetic or forward fill."
            )
            or law.get("prior_epoch_results_are_not_inputs") is not True
            or law.get("no_parameter_search") is not True
            or law.get("internal_development_data_is_not_independent_confirmation") is not True):
        raise Epoch36ScreenError("fixed Epoch36 estimand or inference law mismatch")
    if freeze.get("accounting_effect") != {
        "economic_outcomes_opened": 0, "v2_attempts_consumed": 0, "search_budget_change": 0,
    }:
        raise Epoch36ScreenError("Epoch36 economic accounting boundary violated")
    interpretation = freeze.get("interpretation_boundary") or {}
    safety = freeze.get("safety") or {}
    if (interpretation.get("economic_promotion_authorized") is not False
            or interpretation.get("mechanism_family_closed") is not False
            or interpretation.get("protected_forward_opened") is not False
            or interpretation.get("independent_confirmation") is not False
            or interpretation.get("candidate_identity_created") is not False
            or interpretation.get("winner_selected") is not False
            or safety.get("protected_forward_opened") is not False
            or safety.get("live_orders_authorized") is not False
            or safety.get("competition_start_authorized") is not False):
        raise Epoch36ScreenError("Epoch36 safety or interpretation boundary violated")
    return registry


def _segments(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not rows:
        return []
    result = [[rows[0]]]
    for row in rows[1:]:
        delta = (row["timestamp"] - result[-1][-1]["timestamp"]).total_seconds()
        if delta <= 0:
            raise Epoch36ScreenError("rows are not strictly chronological after canonicalization")
        if delta == M5_SECONDS:
            result[-1].append(row)
        else:
            result.append([row])
    return result


def _exact_positive_sign_p(values: list[float]) -> float:
    nonzero = [value for value in values if value != 0.0]
    if not nonzero:
        return 1.0
    positives = sum(value > 0.0 for value in nonzero)
    n = len(nonzero)
    return math.fsum(math.comb(n, count) for count in range(positives, n + 1)) / (2 ** n)


def _split_inference(daily: dict[str, float]) -> tuple[list[dict[str, Any]], bool]:
    dates = sorted(daily)
    midpoint = len(dates) // 2
    halves = (dates[:midpoint], dates[midpoint:])
    reports = []
    sufficient = True
    for label, selected in zip(("CHRONOLOGICAL_HALF_1", "CHRONOLOGICAL_HALF_2"), halves):
        values = [daily[day] for day in selected]
        eligible = len(values) >= MIN_DATES_PER_HALF
        sufficient = sufficient and eligible
        median = statistics.median(values) if values else None
        reports.append({
            "label": label,
            "eligible_dates": len(values),
            "minimum_dates_pass": eligible,
            "median_standardized_absolute_distance_contraction": median,
            "positive_median": median is not None and median > 0.0,
            "one_sided_exact_sign_p": _exact_positive_sign_p(values) if eligible else 1.0,
            "positive_signs": sum(value > 0.0 for value in values),
            "negative_signs": sum(value < 0.0 for value in values),
            "zero_signs": sum(value == 0.0 for value in values),
        })
    return reports, sufficient


def _screen_rows(rows: list[dict[str, Any]], symbol_id: int) -> dict[str, Any]:
    daily: dict[str, float] = {}
    excluded = {
        "incomplete_or_noncontiguous_forward_window": 0,
        "duplicate_utc_date_event": 0,
    }
    event_candidates = 0
    for segment in _segments(rows):
        for index in range(WINDOW_BARS - 1, len(segment), ANCHOR_STRIDE_BARS):
            window = segment[index - WINDOW_BARS + 1:index + 1]
            closes = [float(row["close"]) for row in window]
            scale = statistics.pstdev(closes)
            if scale == 0.0:
                continue
            center = statistics.fmean(closes)
            z_score = (closes[-1] - center) / scale
            if abs(z_score) < Z_THRESHOLD:
                continue
            event_candidates += 1
            if index + FORWARD_BARS >= len(segment):
                excluded["incomplete_or_noncontiguous_forward_window"] += 1
                continue
            event_day = segment[index]["timestamp"].date().isoformat()
            if event_day in daily:
                excluded["duplicate_utc_date_event"] += 1
                continue
            future_close = float(segment[index + FORWARD_BARS]["close"])
            contraction = (
                abs(closes[-1] - center) - abs(future_close - center)
            ) / scale
            daily[event_day] = contraction

    halves, sufficient = _split_inference(daily)
    raw_support = sufficient and all(
        report["positive_median"] and report["one_sided_exact_sign_p"] <= FDR
        for report in halves
    )
    return {
        "symbol_id": symbol_id,
        "event_candidates": event_candidates,
        "eligible_events": len(daily),
        "eligible_utc_dates": sorted(daily),
        "daily_standardized_absolute_distance_contractions": dict(sorted(daily.items())),
        "excluded_events": excluded,
        "chronological_half_1": halves[0],
        "chronological_half_2": halves[1],
        "minimum_data_sufficiency_pass": sufficient,
        "max_half_p_value": max((part["one_sided_exact_sign_p"] for part in halves), default=1.0),
        "raw_positive_median_pass": raw_support,
    }


def benjamini_hochberg(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 1.0
    count = len(ordered)
    for index in range(count - 1, -1, -1):
        symbol, value = ordered[index]
        running = min(running, value * count / (index + 1), 1.0)
        adjusted[symbol] = running
    return adjusted


def evaluate(
    freeze: dict[str, Any], development_zip: Path, replacement_zip: Path, root: Path,
) -> dict[str, Any]:
    registry = validate_freeze(freeze, root)
    if (sha256_file(development_zip) != DEVELOPMENT_SHA256
            or sha256_file(replacement_zip) != REPLACEMENT_SHA256):
        raise Epoch36ScreenError("accepted capture ZIP hash mismatch")
    representatives = registry["representatives"]
    by_id = {int(item["symbol_id"]): str(item["broker_symbol"]) for item in representatives}
    development_ids = set(by_id) - REPLACEMENT_IDS
    if len(development_ids) != 38 or len(REPLACEMENT_IDS) != 3:
        raise Epoch36ScreenError("frozen archive split does not cover exactly 41 representatives")
    interval = freeze["scope"]["interval"]
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        development_rows = _load_archive(
            development,
            {symbol_id: by_id[symbol_id] for symbol_id in development_ids},
            interval,
            allowed_superseded_ids=set(SUPERSEDED_DEVELOPMENT_IDS),
        )
        replacement_rows = _load_replacement_archive(
            replacement,
            {symbol_id: by_id[symbol_id] for symbol_id in REPLACEMENT_IDS},
            interval,
        )
    all_rows = {**development_rows, **replacement_rows}
    if set(all_rows) != set(by_id):
        raise Epoch36ScreenError("Epoch36 did not load all current representatives")
    for series in all_rows.values():
        if any(
            row["timestamp"].second != 0
            or row["timestamp"].microsecond != 0
            or row["timestamp"].minute % 5 != 0
            for row in series
        ):
            raise Epoch36ScreenError("capture contains a timestamp off the frozen M5 cadence")
    per_symbol: dict[str, Any] = {}
    for item in representatives:
        symbol_id = int(item["symbol_id"])
        symbol = str(item["broker_symbol"])
        result = _screen_rows(all_rows[symbol_id], symbol_id)
        result["broker_symbol"] = symbol
        result["supported_after_bh_fdr"] = False
        per_symbol[symbol] = result
    if len(per_symbol) != 41:
        raise Epoch36ScreenError("Epoch36 did not process the full 41-symbol panel exactly once")
    adjusted = benjamini_hochberg({
        symbol: result["max_half_p_value"] for symbol, result in per_symbol.items()
    })
    for symbol, result in per_symbol.items():
        result["bh_adjusted_p"] = adjusted[symbol]
        result["supported_after_bh_fdr"] = (
            result["raw_positive_median_pass"] and adjusted[symbol] <= FDR
        )
    return {
        "schema": "mxm.greenfield.epoch36-mean-reversion-magnitude-persistence-structural-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "evidence_epoch": 36,
        "source_evidence_epoch": 36,
        "family": "MEAN_REVERSION",
        "freeze_ref": FREEZE_REF,
        "implementation": {"version": VERSION},
        "scope": {
            "representatives_processed": len(per_symbol),
            "all_41_processed_exactly_once": len(per_symbol) == 41,
            "representatives_are_economic_equivalents": False,
            "resolution": "M5",
        },
        "input_attestation": {
            "proposal_file_sha256": sha256_file(root / PROPOSAL_REF),
            "current_frontier_sha256": sha256_file(root / CURRENT_FRONTIER_REF),
            "registry_sha256": sha256_file(root / REGISTRY_REF),
            "coverage_sha256": sha256_file(root / COVERAGE_REF),
            "development_zip_sha256": sha256_file(development_zip),
            "replacement_zip_sha256": sha256_file(replacement_zip),
            "protected_forward_rows_read": 0,
            "prior_epoch_screen_results_used_as_inputs": False,
            "new_market_data_acquired": False,
        },
        "inference": {
            "eligible_symbols": sum(result["minimum_data_sufficiency_pass"] for result in per_symbol.values()),
            "supported_symbols_after_bh_fdr": sum(result["supported_after_bh_fdr"] for result in per_symbol.values()),
            "family_size": 41,
            "method": "ONE_SIDED_EXACT_SIGN_TEST_BY_CHRONOLOGICAL_HALF_WITH_BH_FDR",
            "false_discovery_rate": FDR,
        },
        "symbols": per_symbol,
        "interpretation_boundary": {
            "unsigned_reversion_magnitude_structure_only": True,
            "independent_confirmation": False,
            "economic_promotion_authorized": False,
            "mechanism_family_closed": False,
            "winner_selected": False,
            "candidate_identity_created": False,
            "protected_forward_opened": False,
            "internal_development_data_is_independent_confirmation": False,
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
    parser.add_argument("--replacement-zip", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    development_zip = args.development_zip or root / "research_v3/runtime_v2_inputs/MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip"
    replacement_zip = args.replacement_zip or root / "research_v3/runtime_v2_inputs/MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip"
    freeze = _load_json(root / FREEZE_REF)
    result = evaluate(freeze, development_zip, replacement_zip, root)
    result["freeze_sha256"] = sha256_file(root / FREEZE_REF)
    output = args.output or root / RESULT_REF
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "result_ref": str(output), "symbols": 41}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
