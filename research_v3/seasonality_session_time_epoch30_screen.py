from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import statistics
import zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "MXM_EPOCH30_SEASONALITY_SESSION_TIME_STRUCTURAL_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH30_SEASONALITY_SESSION_TIME_FRONTIER_FREEZE_V1.json"
FREEZE_SCHEMA = "mxm.greenfield.epoch30-seasonality-session-time-frontier-freeze.v1"
REGISTRY_SHA256 = "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3"
COVERAGE_SHA256 = "5cfb0662b12f1f42f8f5c503df64f42716dab98ba5729ab7e6eef75bce2c5dec"
DEVELOPMENT_ZIP_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_ZIP_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
M5_SECONDS = 300
REPLACEMENT_IDS = frozenset({7427, 5352, 2924})
MINIMUM_DATES_PER_HOUR = 10
MINIMUM_HOURS = 4
MINIMUM_ACTIVITY_CV = 0.10
PERMUTATIONS = 999
RAW_P_THRESHOLD = 0.05
FAMILY_WISE_ERROR_RATE = 0.05
EXPECTED_INTERVAL = {
    "start_utc": "2026-06-15T00:00:00Z",
    "end_utc": "2026-09-13T23:59:59Z",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _expected_law() -> dict[str, Any]:
    return {
        "clock": {
            "representation": "UTC_HOUR_OF_DAY_00_TO_23_FROM_M5_BAR_TIMESTAMP",
            "timezone": "UTC",
            "bucket_assignment": "Assign each close-to-close observation to the UTC hour containing the later M5 bar timestamp.",
            "fixed_buckets": "All 24 UTC hours; no market-local conversion, daylight-saving adjustment, or result-selected session windows.",
        },
        "observation": {
            "primitive": "ABSOLUTE_LOG_CLOSE_TO_CLOSE_CHANGE",
            "formula": "abs(log(close_t/close_t_minus_1))",
            "admission": "Use only adjacent exact M5 bars within the same contiguous segment.",
            "normalization": "For each UTC date, divide each observed hour's mean primitive by the mean primitive across all observed hours that date; give each date-hour equal weight.",
            "zero_activity_date": "Exclude a date whose mean primitive is exactly zero and report its count.",
            "interpretation": "Non-economic realized-activity magnitude only; no directional return, forecast, cost, PnL, or economic outcome.",
        },
        "missing_data": "No forward fill, interpolation, resampling, or synthetic bars. Any timestamp delta other than exactly 300 seconds begins a new segment; no close-to-close observation crosses a segment boundary.",
        "duplicate_timestamps": "Collapse only rows with identical parsed OHLC and tick volume; any conflicting duplicate fails closed.",
        "primary_statistic": "COEFFICIENT_OF_VARIATION_ACROSS_ELIGIBLE_UTC_HOUR_MEANS_OF_DAILY_NORMALIZED_ABSOLUTE_LOG_CHANGE",
        "primary_statistic_definition": "POPULATION_STANDARD_DEVIATION_OF_ELIGIBLE_HOUR_MEANS_DIVIDED_BY_THEIR_ARITHMETIC_MEAN",
        "eligibility": {
            "minimum_distinct_utc_dates_per_hour": MINIMUM_DATES_PER_HOUR,
            "minimum_eligible_utc_hours_per_half": MINIMUM_HOURS,
            "primary_statistic_threshold_each_half": MINIMUM_ACTIVITY_CV,
        },
        "chronological_stability": {
            "split": "FIXED_UTC_CUT_AT_2026-07-30T00:00:00Z",
            "stability_rule": "Both halves must be eligible, have primary statistic at least 0.10, and have the same unique peak UTC hour; ties are not a unique peak and fail stability.",
        },
        "inference": {
            "test": "ONE_SIDED_RANDOMIZATION_TEST_OF_UTC_HOUR_ASSOCIATION",
            "randomization": "Within each UTC date independently, uniformly permute the daily normalized values among that date's observed UTC-hour buckets; this preserves each date's value profile and observed-hour mask.",
            "permutations": PERMUTATIONS,
            "seed": "First 64 bits of SHA256('MXM_EPOCH30_SESSION_TIME_V1|' + broker_symbol + '|' + chronological_half_label), interpreted big-endian.",
            "p_value": "(1 + number of randomized statistics greater than or equal to observed statistic)/(1 + permutations)",
            "per_half_raw_p_threshold": RAW_P_THRESHOLD,
            "symbol_p_value": "Maximum of the two chronological-half p-values; ineligible symbol receives p=1.",
            "multiplicity": "HOLM_STEP_DOWN_FAMILY_WISE_ERROR_CONTROL_ACROSS_ALL_41_SYMBOL_P_VALUES",
            "family_wise_error_rate": FAMILY_WISE_ERROR_RATE,
            "pass_criteria": "Both halves eligible; both primary statistics >=0.10; same unique peak UTC hour in both halves; each raw half p<=0.05; and symbol Holm-adjusted p<=0.05.",
            "reporting": "Report all 41 symbols and all eligible hour summaries. No ranking, subgroup selection, symbol promotion, or mechanism-family closure.",
        },
        "no_parameter_search": True,
    }


def validate_freeze(
    freeze: dict[str, Any],
    registry_path: Path,
    coverage_path: Path,
) -> None:
    if (
        freeze.get("schema") != FREEZE_SCHEMA
        or freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_EPOCH30_STRUCTURAL_SCREEN"
        or freeze.get("evidence_epoch") != 30
    ):
        raise ValueError("unsupported or unfrozen epoch30 screen specification")
    authority = freeze.get("authority", {})
    if (
        authority.get("accepted_proposal_ref")
        != "research_v3/ai_director/proposals/AUTO_reason_ef2b7a0c5a775fc6e22829731b275f7f.json"
        or authority.get("accepted_proposal_hash")
        != "05e487e2b13c3f45ad9af3cb7da64ea844266cd31a2dcc6357750a1e5202245c"
        or authority.get("frontier_registry_ref")
        != "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
        or authority.get("frontier_registry_sha256") != REGISTRY_SHA256
        or authority.get("coverage_ref")
        != "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_STRUCTURAL_COVERAGE_EPOCH23_V1.json"
        or authority.get("coverage_sha256") != COVERAGE_SHA256
        or authority.get("development_acceptance_ref")
        != "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json"
        or authority.get("development_zip_filename")
        != "MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip"
        or authority.get("development_zip_sha256") != DEVELOPMENT_ZIP_SHA256
        or authority.get("replacement_acceptance_ref")
        != "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json"
        or authority.get("replacement_zip_filename")
        != "MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip"
        or authority.get("replacement_zip_sha256") != REPLACEMENT_ZIP_SHA256
    ):
        raise ValueError("freeze does not match accepted epoch30 proposal or capture authority")

    registry_path = Path(registry_path)
    coverage_path = Path(coverage_path)
    if sha256_file(registry_path) != REGISTRY_SHA256:
        raise ValueError("current structural registry hash mismatch")
    if sha256_file(coverage_path) != COVERAGE_SHA256:
        raise ValueError("accepted 13-week coverage evidence hash mismatch")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    if (
        registry.get("status")
        != "CURRENT_STRUCTURAL_FRONTIER_RECOMPUTED_FROM_ACCEPTED_BROKER_NATIVE_METADATA"
        or coverage.get("status")
        != "COMPLETE_NON_ECONOMIC_CURRENT_REPRESENTATIVE_COVERAGE_RESTORED"
        or coverage.get("current_representative_history_coverage", {}).get("status")
        != "PASS_41_OF_41"
    ):
        raise ValueError("frontier or accepted history coverage is not complete")

    representatives = tuple(
        (str(item["broker_symbol"]), int(item["symbol_id"]))
        for item in freeze.get("scope", {}).get("representatives", [])
    )
    registry_representatives = tuple(
        (str(item["broker_symbol"]), int(item["symbol_id"]))
        for item in registry.get("representatives", [])
    )
    if (
        len(representatives) != 41
        or len(set(representatives)) != 41
        or representatives != registry_representatives
    ):
        raise ValueError("freeze must bind all 41 exact current representatives in authority order")
    scope = freeze["scope"]
    if (
        freeze.get("family") != "SEASONALITY_SESSION_TIME"
        or scope.get("representative_count") != 41
        or scope.get("representatives_are_not_economically_equivalent") is not True
        or scope.get("resolution") != "M5"
        or scope.get("interval") != EXPECTED_INTERVAL
        or scope.get("chronological_split_utc") != "2026-07-30T00:00:00Z"
        or scope.get("protected_forward_start") != "2026-09-17T12:02:58Z"
        or set(map(int, scope.get("replacement_capture_symbol_ids", []))) != REPLACEMENT_IDS
    ):
        raise ValueError("freeze scope differs from accepted current-frontier capture authority")
    expected_bindings = [
        {
            "acceptance_ref": "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json",
            "capture_sha256": DEVELOPMENT_ZIP_SHA256,
            "interval": "2026-06-15T00:00:00Z/2026-09-13T23:59:59Z",
            "resolution": "M5",
        },
        {
            "acceptance_ref": "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json",
            "capture_sha256": REPLACEMENT_ZIP_SHA256,
            "symbol_ids": [7427, 5352, 2924],
            "interval": "2026-06-15T00:00:00Z/2026-09-13T23:59:59Z",
            "resolution": "M5",
        },
    ]
    if freeze.get("data_bindings") != expected_bindings:
        raise ValueError("freeze data bindings differ from accepted capture scope")
    if freeze.get("preregistered_structural_law") != _expected_law():
        raise ValueError("freeze parameters differ from the implemented fixed law")
    if freeze.get("interpretation_boundary") != {
        "result_scope": "DESCRIPTIVE_NON_ECONOMIC_DEVELOPMENT_STRUCTURAL_SCREEN_ONLY",
        "mechanism_family_closed": False,
        "economic_promotion_authorized": False,
        "independent_confirmation": False,
        "internal_development_data_is_independent_confirmation": False,
        "candidate_identity_created": False,
        "protected_forward_opened": False,
    }:
        raise ValueError("freeze interpretation boundary differs from non-economic authority")
    if freeze.get("accounting_effect") != {
        "economic_outcomes_opened": 0,
        "v2_attempts_consumed": 0,
        "search_budget_change": 0,
    } or freeze.get("safety") != {
        "account_mutation": False,
        "live_orders_authorized": False,
        "competition_start_authorized": False,
        "protected_forward_opened": False,
    }:
        raise ValueError("freeze crosses a prohibited economic or safety boundary")


def canonicalize_identical_duplicates(
    rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    by_timestamp: dict[datetime, dict[str, Any]] = {}
    duplicates_removed = 0
    for row in rows:
        timestamp = row["timestamp"]
        previous = by_timestamp.get(timestamp)
        if previous is None:
            by_timestamp[timestamp] = row
            continue
        if any(
            previous[field] != row[field]
            for field in ("open", "high", "low", "close", "tick_volume")
        ):
            raise ValueError(f"conflicting duplicate at {row['time_utc']}")
        duplicates_removed += 1
    return [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)], duplicates_removed


def _read_member(
    archive: zipfile.ZipFile,
    member: str,
    freeze: dict[str, Any],
) -> list[dict[str, Any]]:
    interval = freeze["scope"]["interval"]
    start = parse_utc(interval["start_utc"])
    end = parse_utc(interval["end_utc"])
    protected_start = parse_utc(freeze["scope"]["protected_forward_start"])
    reader = csv.DictReader(io.StringIO(archive.read(member).decode("utf-8-sig")))
    expected_fields = ["time_utc", "open", "high", "low", "close", "tick_volume"]
    if reader.fieldnames != expected_fields:
        raise ValueError(f"{member}: unexpected M5 CSV header")
    rows = []
    for source in reader:
        if None in source or any(source[field] is None for field in expected_fields):
            raise ValueError(f"{member}: malformed M5 CSV row")
        timestamp = parse_utc(source["time_utc"])
        if timestamp < start or timestamp > end or timestamp >= protected_start:
            raise ValueError(f"{member}: row outside frozen development interval")
        if timestamp.second or timestamp.microsecond or timestamp.minute % 5:
            raise ValueError(f"{member}: timestamp is off the frozen M5 cadence")
        values = {
            field: float(source[field])
            for field in ("open", "high", "low", "close", "tick_volume")
        }
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError(f"{member}: non-finite market value")
        if (
            min(values[field] for field in ("open", "high", "low", "close")) <= 0
            or values["high"] < max(values["open"], values["close"], values["low"])
            or values["low"] > min(values["open"], values["close"], values["high"])
            or values["tick_volume"] < 0
        ):
            raise ValueError(f"{member}: invalid M5 OHLC or tick volume")
        rows.append({"time_utc": source["time_utc"], "timestamp": timestamp, **values})
    if not rows:
        raise ValueError(f"{member}: frozen representative has no M5 rows")
    canonicalize_identical_duplicates(rows)
    return rows


def _find_member(archive: zipfile.ZipFile, symbol_id: int) -> str:
    matches = [
        name for name in archive.namelist()
        if name.startswith(f"raw/{symbol_id}_") and name.endswith("_M5.csv")
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one root M5 file for symbol_id={symbol_id}")
    return matches[0]


def _daily_profiles(
    rows: list[dict[str, Any]],
) -> tuple[list[tuple[date, dict[int, float]]], int, int, int]:
    daily_hour_values: dict[date, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    contiguous_segments = 0
    observations = 0
    previous: dict[str, Any] | None = None
    for row in rows:
        if previous is None or (
            row["timestamp"] - previous["timestamp"]
        ).total_seconds() != M5_SECONDS:
            contiguous_segments += 1
            previous = row
            continue
        magnitude = abs(math.log(float(row["close"]) / float(previous["close"])))
        daily_hour_values[row["timestamp"].date()][row["timestamp"].hour].append(magnitude)
        observations += 1
        previous = row

    profiles: list[tuple[date, dict[int, float]]] = []
    zero_activity_dates = 0
    for day in sorted(daily_hour_values):
        hour_means = {
            hour: statistics.fmean(values)
            for hour, values in daily_hour_values[day].items()
        }
        daily_mean = statistics.fmean(hour_means.values())
        if daily_mean == 0:
            zero_activity_dates += 1
            continue
        profiles.append((
            day,
            {hour: value / daily_mean for hour, value in hour_means.items()},
        ))
    return profiles, zero_activity_dates, contiguous_segments, observations


def _coefficient_of_variation(values: list[float]) -> float:
    if not values or statistics.fmean(values) == 0:
        return 0.0
    return statistics.pstdev(values) / statistics.fmean(values)


def _hour_summary(profiles: list[dict[int, float]]) -> tuple[list[dict[str, Any]], list[int]]:
    date_counts = [sum(hour in profile for profile in profiles) for hour in range(24)]
    means = []
    for hour in range(24):
        values = [profile[hour] for profile in profiles if hour in profile]
        means.append(statistics.fmean(values) if values else None)
    eligible_hours = [
        hour for hour, count in enumerate(date_counts)
        if count >= MINIMUM_DATES_PER_HOUR
    ]
    rows = [
        {
            "utc_hour": hour,
            "distinct_utc_dates": date_counts[hour],
            "mean_daily_normalized_activity": means[hour],
            "eligible": hour in eligible_hours,
        }
        for hour in range(24)
    ]
    return rows, eligible_hours


def _randomization_p_value(
    profiles: list[dict[int, float]],
    eligible_hours: list[int],
    observed: float,
    broker_symbol: str,
    half_label: str,
) -> float:
    seed_material = (
        f"MXM_EPOCH30_SESSION_TIME_V1|{broker_symbol}|{half_label}"
    ).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    rng = random.Random(seed)
    exceedances = 0
    for _ in range(PERMUTATIONS):
        hour_totals = {hour: 0.0 for hour in eligible_hours}
        hour_counts = {hour: 0 for hour in eligible_hours}
        for profile in profiles:
            hours = sorted(profile)
            values = [profile[hour] for hour in hours]
            rng.shuffle(values)
            for hour, value in zip(hours, values):
                if hour in hour_totals:
                    hour_totals[hour] += value
                    hour_counts[hour] += 1
        randomized_means = [
            hour_totals[hour] / hour_counts[hour]
            for hour in eligible_hours
            if hour_counts[hour]
        ]
        if _coefficient_of_variation(randomized_means) >= observed:
            exceedances += 1
    return (1 + exceedances) / (1 + PERMUTATIONS)


def _evaluate_half(
    profiles: list[dict[int, float]],
    broker_symbol: str,
    half_label: str,
) -> dict[str, Any]:
    hours, eligible_hours = _hour_summary(profiles)
    eligible = len(eligible_hours) >= MINIMUM_HOURS
    activity_values = [
        float(hours[hour]["mean_daily_normalized_activity"])
        for hour in eligible_hours
    ]
    statistic = _coefficient_of_variation(activity_values) if eligible else None
    peak_hour = None
    unique_peak = False
    if eligible:
        max_value = max(activity_values)
        peak_hours = [
            hour for hour in eligible_hours
            if hours[hour]["mean_daily_normalized_activity"] == max_value
        ]
        unique_peak = len(peak_hours) == 1
        peak_hour = peak_hours[0] if unique_peak else None
    p_value = (
        _randomization_p_value(
            profiles, eligible_hours, statistic, broker_symbol, half_label
        )
        if eligible and statistic is not None
        else 1.0
    )
    return {
        "utc_dates_with_observations": len(profiles),
        "eligible": eligible,
        "eligible_utc_hours": eligible_hours,
        "hourly_activity": hours,
        "primary_statistic_activity_cv": statistic,
        "unique_peak_utc_hour": peak_hour,
        "unique_peak": unique_peak,
        "randomization_p_value": p_value,
    }


def evaluate_symbol(
    rows: list[dict[str, Any]],
    broker_symbol: str,
    split_utc: datetime,
) -> dict[str, Any]:
    canonical, duplicates_removed = canonicalize_identical_duplicates(rows)
    profiles, zero_activity_dates, contiguous_segments, observations = _daily_profiles(canonical)
    first_half = [
        profile for day, profile in profiles
        if day < split_utc.date()
    ]
    second_half = [
        profile for day, profile in profiles
        if day >= split_utc.date()
    ]
    first = _evaluate_half(first_half, broker_symbol, "CHRONOLOGICAL_HALF_1")
    second = _evaluate_half(second_half, broker_symbol, "CHRONOLOGICAL_HALF_2")
    stable_peak = (
        first["unique_peak"]
        and second["unique_peak"]
        and first["unique_peak_utc_hour"] == second["unique_peak_utc_hour"]
    )
    passes = (
        first["eligible"]
        and second["eligible"]
        and first["primary_statistic_activity_cv"] >= MINIMUM_ACTIVITY_CV
        and second["primary_statistic_activity_cv"] >= MINIMUM_ACTIVITY_CV
        and stable_peak
        and first["randomization_p_value"] <= RAW_P_THRESHOLD
        and second["randomization_p_value"] <= RAW_P_THRESHOLD
    )
    return {
        "rows": len(canonical),
        "close_to_close_observations": observations,
        "identical_duplicate_rows_removed": duplicates_removed,
        "contiguous_segments": contiguous_segments,
        "zero_activity_dates_excluded": zero_activity_dates,
        "first_half": first,
        "second_half": second,
        "same_unique_peak_hour_both_halves": stable_peak,
        "raw_structural_pass": passes,
        "symbol_p_value": max(
            first["randomization_p_value"], second["randomization_p_value"]
        ) if first["eligible"] and second["eligible"] else 1.0,
    }


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for index, (key, p_value) in enumerate(ordered):
        running = max(running, min(1.0, p_value * (count - index)))
        adjusted[key] = running
    return adjusted


def evaluate(
    freeze: dict[str, Any],
    development_zip: Path,
    replacement_zip: Path,
    registry_path: Path,
    coverage_path: Path,
) -> dict[str, Any]:
    validate_freeze(freeze, registry_path, coverage_path)
    development_hash = sha256_file(Path(development_zip))
    replacement_hash = sha256_file(Path(replacement_zip))
    if development_hash != DEVELOPMENT_ZIP_SHA256:
        raise ValueError("development capture ZIP hash mismatch")
    if replacement_hash != REPLACEMENT_ZIP_SHA256:
        raise ValueError("replacement capture ZIP hash mismatch")

    split_utc = parse_utc(freeze["scope"]["chronological_split_utc"])
    results: dict[str, Any] = {}
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for representative in freeze["scope"]["representatives"]:
            symbol = str(representative["broker_symbol"])
            symbol_id = int(representative["symbol_id"])
            archive = replacement if symbol_id in REPLACEMENT_IDS else development
            member = _find_member(archive, symbol_id)
            results[symbol] = {
                "symbol_id": symbol_id,
                "source_member": member,
                **evaluate_symbol(_read_member(archive, member, freeze), symbol, split_utc),
            }

    adjusted = holm_adjust({
        symbol: result["symbol_p_value"]
        for symbol, result in results.items()
    })
    supported_symbols = []
    for symbol, result in results.items():
        result["holm_adjusted_p"] = adjusted[symbol]
        result["supported"] = (
            result["raw_structural_pass"]
            and adjusted[symbol] <= FAMILY_WISE_ERROR_RATE
        )
        if result["supported"]:
            supported_symbols.append(symbol)
    return {
        "schema": "mxm.greenfield.epoch30-seasonality-session-time-structural-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "evidence_epoch": 30,
        "family": "SEASONALITY_SESSION_TIME",
        "freeze_ref": FREEZE_REF,
        "implementation": {"version": VERSION},
        "input_attestation": {
            "registry_sha256": sha256_file(Path(registry_path)),
            "coverage_sha256": sha256_file(Path(coverage_path)),
            "development_zip_sha256": development_hash,
            "replacement_zip_sha256": replacement_hash,
            "all_41_frozen_representatives_processed_exactly_once": len(results) == 41,
            "protected_forward_rows_read": 0,
        },
        "scope": {
            "representatives_processed": len(results),
            "ordered_representatives": [
                item["broker_symbol"] for item in freeze["scope"]["representatives"]
            ],
            "representatives_are_economic_equivalents": False,
            "clock_representation": "UTC_HOUR_OF_DAY_00_TO_23",
            "chronological_split_utc": freeze["scope"]["chronological_split_utc"],
        },
        "inference": {
            "permutations_per_half": PERMUTATIONS,
            "per_half_raw_p_threshold": RAW_P_THRESHOLD,
            "family_wise_error_rate": FAMILY_WISE_ERROR_RATE,
            "multiplicity": "HOLM_ACROSS_41_SYMBOL_P_VALUES",
            "supported_symbols_count": len(supported_symbols),
            "supported_symbols": sorted(supported_symbols),
            "mechanism_family_closed": False,
        },
        "symbols": results,
        "interpretation_boundary": {
            "result": "FROZEN_NON_ECONOMIC_DEVELOPMENT_STRUCTURAL_SCREEN_ONLY",
            "economic_promotion_authorized": False,
            "independent_confirmation": False,
            "internal_development_data_is_independent_confirmation": False,
            "mechanism_family_closed": False,
            "winner_selected": False,
        },
        "accounting_effect": {
            "v2_attempts_consumed": 0,
            "economic_outcomes_opened": 0,
            "search_budget_change": 0,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "competition_start_authorized": False,
            "account_mutation": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--development-zip", required=True)
    parser.add_argument("--replacement-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    freeze_path = Path(args.freeze)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    result = evaluate(
        freeze,
        Path(args.development_zip),
        Path(args.replacement_zip),
        Path(args.registry),
        Path(args.coverage),
    )
    result["freeze_sha256"] = sha256_file(freeze_path)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "supported_symbols_count": result["inference"]["supported_symbols_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
