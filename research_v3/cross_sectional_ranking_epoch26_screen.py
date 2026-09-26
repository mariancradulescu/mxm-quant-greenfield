from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "MXM_EPOCH26_CROSS_SECTIONAL_RANKING_STRUCTURAL_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH26_CROSS_SECTIONAL_RANKING_FRONTIER_FREEZE_V1.json"
PROPOSAL_HASH = "28a9c58cb820a7494e58549b02f520459045680001d703ac992cb4aa00b4876f"
DEVELOPMENT_ZIP_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_ZIP_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
CAPTURE_ACCEPTANCE_SHA256 = "a14e0e59f9fe85e364ae4752d372c8e903b5c4e487276b968fcb51a996b30238"
COVERAGE_SHA256 = "5cfb0662b12f1f42f8f5c503df64f42716dab98ba5729ab7e6eef75bce2c5dec"
START_UTC = datetime(2026, 6, 15, tzinfo=timezone.utc)
END_UTC = datetime(2026, 9, 13, 23, 59, 59, tzinfo=timezone.utc)
PROTECTED_START = datetime(2026, 9, 17, 12, 2, 58, tzinfo=timezone.utc)
M5_SECONDS = 300
LOOKBACK = 12
RESPONSE = 12
STRIDE = 12
MINIMUM_BREADTH = 10
BLOCK_DAYS = 5
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 260926
MINIMUM_DATES = 20
MINIMUM_DATES_PER_HALF = 8
FDR_Q = 0.05
REPLACEMENT_IDS = frozenset({7427, 5352, 2924})
EXPECTED_SYMBOLS = (
    ("VER.AT", 5268), ("GEM.AU", 3693), ("UMI.BE", 5120),
    ("UBSG.CH", 5275), ("Lead", 2791), ("Corn", 306),
    ("LDSugar", 148), ("Sugar", 106), ("TRUMPUSD", 5562),
    ("JPYX", 146), ("AT1d.DE", 3137), ("ORSTED.DK", 5314),
    ("TEF.ES", 5237), ("EIDO.US", 4442), ("NatGas", 251),
    ("SAMPO.FI", 5370), ("STLAP.FR", 5134), ("USDCZK", 56),
    ("ZARJPY", 98), ("USDCLP", 2759), ("USDBRL", 2755),
    ("XAUUSD-F", 2924), ("JPN225-F", 2917), ("EUBobl-F", 7290),
    ("USTN5YR-F", 7296), ("UKGILT-F", 7292), ("MCG.GB", 3377),
    ("1357.HK", 7238), ("BIRG.IE", 5386), ("SCI25", 150),
    ("NETH25", 269), ("US400", 7372), ("CA60", 266),
    ("XPDUSD", 95), ("NHY.NO", 5332), ("BCP.PT", 5217),
    ("WTOIL-PERP", 7393), ("CXMT.CN-PERP", 7427),
    ("ERICB.SE", 5352), ("NIO.US-24", 5479), ("CGC.US", 4120),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def canonicalize_identical_duplicates(
    rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    by_timestamp: dict[datetime, dict[str, Any]] = {}
    duplicates = 0
    for row in rows:
        previous = by_timestamp.get(row["timestamp"])
        if previous is None:
            by_timestamp[row["timestamp"]] = row
            continue
        for field in ("open", "high", "low", "close", "tick_volume"):
            if previous[field] != row[field]:
                raise ValueError(f"conflicting duplicate at {row['time_utc']}")
        duplicates += 1
    return [by_timestamp[key] for key in sorted(by_timestamp)], duplicates


def _rank_percentiles(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted((value, symbol) for symbol, value in values.items())
    count = len(ordered)
    result: dict[str, float] = {}
    first = 0
    while first < count:
        end = first + 1
        while end < count and ordered[end][0] == ordered[first][0]:
            end += 1
        percentile = ((first + 1 + end) / 2 - 1) / (count - 1) if count > 1 else 0.5
        for _, symbol in ordered[first:end]:
            result[symbol] = percentile
        first = end
    return result


def _read_member(archive: zipfile.ZipFile, member: str) -> list[dict[str, Any]]:
    text = archive.read(member).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    required = {"time_utc", "open", "high", "low", "close", "tick_volume"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError(f"missing required M5 CSV fields in {member}")
    rows = []
    for record in reader:
        timestamp = parse_utc(record["time_utc"])
        if timestamp >= PROTECTED_START:
            raise ValueError(f"protected-forward observation found in {member}")
        if START_UTC <= timestamp <= END_UTC:
            row = {
                "time_utc": record["time_utc"],
                "timestamp": timestamp,
                "open": float(record["open"]),
                "high": float(record["high"]),
                "low": float(record["low"]),
                "close": float(record["close"]),
                "tick_volume": float(record["tick_volume"] or 0),
            }
            if not all(math.isfinite(row[key]) for key in ("open", "high", "low", "close", "tick_volume")):
                raise ValueError(f"non-finite OHLCV value in {member}")
            if row["close"] <= 0:
                raise ValueError(f"non-positive close in {member}")
            rows.append(row)
    rows, _ = canonicalize_identical_duplicates(rows)
    return rows


def _find_member(archive: zipfile.ZipFile, symbol_id: int) -> str:
    prefix = f"raw/{symbol_id}_"
    matches = [
        name for name in archive.namelist()
        if name.startswith(prefix) and name.endswith("_M5.csv")
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one raw M5 member for symbol_id={symbol_id}, got {matches}")
    return matches[0]


def validate_freeze(freeze: dict[str, Any]) -> None:
    if (
        freeze.get("schema") != "mxm.greenfield.epoch26-cross-sectional-ranking-frontier-freeze.v1"
        or freeze.get("status") != "FROZEN_BEFORE_CROSS_SECTIONAL_RANKING_STRUCTURAL_OUTCOME"
    ):
        raise ValueError("unsupported or unfrozen cross-sectional-ranking freeze")
    authority = freeze["authority"]
    exact_bindings = {
        "accepted_proposal_hash": PROPOSAL_HASH,
        "replacement_capture_acceptance_sha256": CAPTURE_ACCEPTANCE_SHA256,
        "replacement_structural_coverage_sha256": COVERAGE_SHA256,
        "development_zip_sha256": DEVELOPMENT_ZIP_SHA256,
        "replacement_zip_sha256": REPLACEMENT_ZIP_SHA256,
    }
    if any(authority.get(key) != value for key, value in exact_bindings.items()):
        raise ValueError("freeze data or proposal binding differs from accepted authority")
    scope = freeze["scope"]
    expected_interval = {
        "start_utc": "2026-06-15T00:00:00Z",
        "end_utc": "2026-09-13T23:59:59Z",
    }
    observed = tuple(
        (str(item["broker_symbol"]), int(item["symbol_id"]))
        for item in scope["representatives"]
    )
    if (
        observed != EXPECTED_SYMBOLS
        or len(set(observed)) != 41
        or scope.get("representative_count") != 41
        or scope.get("resolution") != "M5"
        or scope.get("interval") != expected_interval
        or scope.get("protected_forward_start") != "2026-09-17T12:02:58Z"
        or scope.get("selection_law") != (
            "PROCESS_ALL_41_CURRENT_STRUCTURAL_REPRESENTATIVES_IN_AUTHORITY_ORDER_EXACTLY_ONCE"
        )
        or set(scope.get("replacement_capture_symbol_ids", [])) != REPLACEMENT_IDS
        or scope.get("representatives_are_not_economically_equivalent") is not True
    ):
        raise ValueError("freeze scope differs from the exact accepted 41-representative frontier")
    law = freeze["preregistered_structural_law"]
    feature = law["feature"]
    inference = law["inference"]
    if (
        freeze.get("family") != "CROSS_SECTIONAL_RANKING"
        or law.get("hypothesis") != (
            "Across the complete current representative universe, an instrument's trailing one-hour "
            "cross-sectional M5 return percentile is positively associated with its own next one-hour "
            "cross-sectional M5 return percentile."
        )
        or feature.get("lookback_bars") != LOOKBACK
        or feature.get("response_bars") != RESPONSE
        or feature.get("anchor_stride_bars") != STRIDE
        or feature.get("anchor_lattice") != (
            "Within each exact-contiguous M5 segment, use indices 12, 24, 36, and so on; restart at every gap."
        )
        or feature.get("past_measure") != (
            "NATURAL_LOG_CLOSE_AT_ANCHOR_OVER_CLOSE_12_EXACT_CONTIGUOUS_M5_BARS_BEFORE_ANCHOR"
        )
        or feature.get("future_measure") != (
            "NATURAL_LOG_CLOSE_12_EXACT_CONTIGUOUS_M5_BARS_AFTER_ANCHOR_OVER_CLOSE_AT_ANCHOR"
        )
        or feature.get("minimum_panel_breadth") != MINIMUM_BREADTH
        or feature.get("rank") != (
            "At each exact UTC anchor timestamp, independently assign average-tie percentile ranks to "
            "past and future measures among all eligible representatives at that timestamp; "
            "percentile=(average_rank-1)/(panel_count-1)."
        )
        or feature.get("timing") != (
            "Use only completed bars at the anchor; future response is an evaluation outcome, never a feature."
        )
        or law.get("null") != "The mean daily centered percentile co-ranking score is zero for each representative."
        or law.get("missing_data") != (
            "No forward fill, interpolation, resampling, synthetic bars, or cross-gap feature/outcome windows. "
            "A timestamp delta other than exactly 300 seconds starts a new segment. An anchor without both "
            "exact contiguous 12-bar past and future windows is not an eligible observation. For each "
            "timestamp, omit representatives without both windows; if fewer than 10 remain, omit that entire "
            "timestamp from all representative tests."
        )
        or law.get("date_aggregation") != (
            "Use UTC calendar date of anchor; average that representative's scores within date before "
            "inference so high-frequency dates do not receive more weight."
        )
        or law.get("duplicate_timestamps") != (
            "Collapse only rows with identical parsed OHLC and tick volume; any conflicting duplicate fails closed."
        )
        or law.get("censoring") != (
            "Count and report eligible anchor attempts that lack an exact contiguous future response as right-censored; "
            "never impute them."
        )
        or inference.get("block_unit") != "UTC_CALENDAR_DAY"
        or inference.get("block_length_days") != BLOCK_DAYS
        or inference.get("resamples") != BOOTSTRAP_RESAMPLES
        or inference.get("bootstrap_seed") != BOOTSTRAP_SEED
        or inference.get("calendar") != (
            "Build a complete UTC-day grid over the frozen interval; retain missing dates as missing, resample "
            "circular consecutive 5-day index blocks synchronously for every representative, and compute "
            "statistics over sampled nonmissing values."
        )
        or inference.get("null_centering") != (
            "Subtract each representative's observed daily mean from its daily scores before each null bootstrap replicate."
        )
        or inference.get("minimum_observed_dates") != MINIMUM_DATES
        or inference.get("minimum_observed_dates_per_chronological_half") != MINIMUM_DATES_PER_HALF
        or inference.get("chronological_halves") != (
            "Among dates with observed daily scores, first floor(N/2) dates are half 1 and remaining dates are half 2."
        )
        or inference.get("multiplicity") != "BENJAMINI_YEKUTIELI_FDR_ACROSS_ALL_41_REPRESENTATIVES"
        or float(inference.get("fdr_q", -1)) != FDR_Q
        or inference.get("test") != "ONE_SIDED_CENTERED_MOVING_BLOCK_BOOTSTRAP_OF_DAILY_SCORE_MEAN"
        or inference.get("structural_support") != (
            "BY-adjusted q<=0.05, positive overall mean, positive mean in each chronological half, at least 20 "
            "observed dates overall, and at least 8 observed dates in each half."
        )
        or inference.get("reporting") != (
            "Report each of all 41 representatives and the complete fixed test family in authority order; "
            "never select, rank, or promote a subset."
        )
        or law.get("primary_statistic") != (
            "For each representative, the arithmetic mean across UTC dates of its within-anchor product "
            "(past_percentile-0.5)*(future_percentile-0.5), where each date first averages all eligible "
            "anchors for that representative. Test the one-sided alternative that this mean is greater than zero."
        )
        or law.get("no_parameter_search") is not True
    ):
        raise ValueError("freeze parameters differ from the fixed implemented law")
    if (
        freeze.get("accounting_effect", {}).get("economic_outcomes_opened") != 0
        or freeze.get("accounting_effect", {}).get("v2_attempts_consumed") != 0
        or freeze.get("accounting_effect", {}).get("search_budget_change") != 0
        or freeze.get("acceptance", {}).get(
            "non_economic_price_return_features_only_no_pnl_cost_margin_or_economic_outcome"
        ) is not True
        or freeze.get("acceptance", {}).get("no_c023_or_c024_outcome_reuse_or_tuning") is not True
        or freeze.get("acceptance", {}).get("no_protected_forward_rows") is not True
        or freeze.get("acceptance", {}).get("no_candidate_identity_or_family_closure") is not True
        or freeze.get("safety", {}).get("protected_evidence_opened") is not False
        or freeze.get("safety", {}).get("live_orders_authorized") is not False
        or freeze.get("safety", {}).get("competition_start_authorized") is not False
    ):
        raise ValueError("freeze crosses a prohibited economic or safety boundary")


def _symbol_anchors(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    admitted = 0
    censored = 0
    anchors = []
    if not rows:
        return anchors, admitted, censored
    segments: list[list[dict[str, Any]]] = [[rows[0]]]
    for row in rows[1:]:
        delta = (row["timestamp"] - segments[-1][-1]["timestamp"]).total_seconds()
        if delta == M5_SECONDS:
            segments[-1].append(row)
        elif delta > 0:
            segments.append([row])
        else:
            raise ValueError("rows are not strictly chronological")
    for segment in segments:
        for index in range(LOOKBACK, len(segment), STRIDE):
            admitted += 1
            if index + RESPONSE >= len(segment):
                censored += 1
                continue
            past_return = math.log(segment[index]["close"] / segment[index - LOOKBACK]["close"])
            future_return = math.log(segment[index + RESPONSE]["close"] / segment[index]["close"])
            anchors.append({
                "timestamp": segment[index]["timestamp"],
                "past_return": past_return,
                "future_return": future_return,
            })
    return anchors, admitted, censored


def _calendar_days() -> list[date]:
    day = START_UTC.date()
    last = END_UTC.date()
    days = []
    while day <= last:
        days.append(day)
        day += timedelta(days=1)
    return days


def _block_indices(day_count: int, rng: random.Random) -> list[int]:
    indices = []
    while len(indices) < day_count:
        start = rng.randrange(day_count)
        indices.extend((start + offset) % day_count for offset in range(BLOCK_DAYS))
    return indices[:day_count]


def benjamini_yekutieli(p_values: dict[str, float]) -> dict[str, float]:
    if any(not math.isfinite(p) or p < 0 or p > 1 for p in p_values.values()):
        raise ValueError("p-values must be finite and in [0, 1]")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    if not count:
        return {}
    harmonic = sum(1 / rank for rank in range(1, count + 1))
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank in range(count, 0, -1):
        symbol, p_value = ordered[rank - 1]
        running = min(running, p_value * count * harmonic / rank, 1.0)
        adjusted[symbol] = running
    return adjusted


def _daily_null_p_value(
    centered_daily_scores: list[float | None],
    observed_mean: float,
    bootstrap_indices: list[list[int]],
) -> float:
    exceedances = 0
    for indices in bootstrap_indices:
        sample = [centered_daily_scores[index] for index in indices]
        valid = [value for value in sample if value is not None]
        statistic = sum(valid) / len(valid) if valid else 0.0
        if statistic >= observed_mean:
            exceedances += 1
    return (exceedances + 1) / (len(bootstrap_indices) + 1)


def evaluate_symbol_daily_scores(
    daily_scores: list[float | None],
    bootstrap_indices: list[list[int]],
) -> dict[str, Any]:
    active_indices = [index for index, value in enumerate(daily_scores) if value is not None]
    values = [daily_scores[index] for index in active_indices]
    observed_mean = sum(values) / len(values) if values else None
    split = len(values) // 2
    first_half = values[:split]
    second_half = values[split:]
    enough_data = (
        len(values) >= MINIMUM_DATES
        and len(first_half) >= MINIMUM_DATES_PER_HALF
        and len(second_half) >= MINIMUM_DATES_PER_HALF
    )
    p_value = 1.0
    if enough_data and observed_mean is not None:
        centered = [
            value - observed_mean if value is not None else None
            for value in daily_scores
        ]
        p_value = _daily_null_p_value(centered, observed_mean, bootstrap_indices)
    return {
        "observed_dates": len(values),
        "chronological_half_1_dates": len(first_half),
        "chronological_half_2_dates": len(second_half),
        "mean_daily_centered_percentile_score": observed_mean,
        "chronological_half_1_mean": sum(first_half) / len(first_half) if first_half else None,
        "chronological_half_2_mean": sum(second_half) / len(second_half) if second_half else None,
        "one_sided_block_bootstrap_p": p_value,
        "minimum_sample_size_pass": enough_data,
    }


def evaluate(freeze: dict[str, Any], development_zip: Path, replacement_zip: Path) -> dict[str, Any]:
    validate_freeze(freeze)
    development_zip = Path(development_zip)
    replacement_zip = Path(replacement_zip)
    development_hash = sha256_file(development_zip)
    replacement_hash = sha256_file(replacement_zip)
    if development_hash != DEVELOPMENT_ZIP_SHA256 or replacement_hash != REPLACEMENT_ZIP_SHA256:
        raise ValueError("capture ZIP hash does not match the accepted bound artifact")

    representatives = freeze["scope"]["representatives"]
    symbol_anchors: dict[str, list[dict[str, Any]]] = {}
    symbol_ids: dict[str, int] = {}
    source_members: dict[str, str] = {}
    admitted: dict[str, int] = {}
    censored: dict[str, int] = {}
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for representative in representatives:
            symbol = representative["broker_symbol"]
            symbol_id = int(representative["symbol_id"])
            source = replacement if symbol_id in REPLACEMENT_IDS else development
            member = _find_member(source, symbol_id)
            anchors, admitted_count, censored_count = _symbol_anchors(_read_member(source, member))
            symbol_anchors[symbol] = anchors
            symbol_ids[symbol] = symbol_id
            source_members[symbol] = member
            admitted[symbol] = admitted_count
            censored[symbol] = censored_count

    panels: dict[datetime, dict[str, dict[str, float]]] = defaultdict(dict)
    for symbol, anchors in symbol_anchors.items():
        for anchor in anchors:
            panels[anchor["timestamp"]][symbol] = {
                "past": anchor["past_return"],
                "future": anchor["future_return"],
            }
    daily_values: dict[str, dict[date, list[float]]] = {
        symbol: defaultdict(list) for symbol in symbol_anchors
    }
    eligible_panel_counts: list[int] = []
    omitted_breadth_timestamps = 0
    for timestamp in sorted(panels):
        panel = panels[timestamp]
        if len(panel) < MINIMUM_BREADTH:
            omitted_breadth_timestamps += 1
            continue
        eligible_panel_counts.append(len(panel))
        past_ranks = _rank_percentiles({symbol: item["past"] for symbol, item in panel.items()})
        future_ranks = _rank_percentiles({symbol: item["future"] for symbol, item in panel.items()})
        for symbol in panel:
            score = (past_ranks[symbol] - 0.5) * (future_ranks[symbol] - 0.5)
            daily_values[symbol][timestamp.date()].append(score)

    days = _calendar_days()
    rng = random.Random(BOOTSTRAP_SEED)
    bootstrap_indices = [
        _block_indices(len(days), rng) for _ in range(BOOTSTRAP_RESAMPLES)
    ]
    results: dict[str, dict[str, Any]] = {}
    raw_p: dict[str, float] = {}
    for representative in representatives:
        symbol = representative["broker_symbol"]
        scores = [
            sum(daily_values[symbol][day]) / len(daily_values[symbol][day])
            if daily_values[symbol].get(day) else None
            for day in days
        ]
        inference = evaluate_symbol_daily_scores(scores, bootstrap_indices)
        raw_p[symbol] = inference["one_sided_block_bootstrap_p"]
        results[symbol] = {
            "symbol_id": symbol_ids[symbol],
            "source_member": source_members[symbol],
            "admitted_anchors": admitted[symbol],
            "right_censored_future_response": censored[symbol],
            "eligible_anchors_after_panel_breadth": sum(
                len(values) for values in daily_values[symbol].values()
            ),
            **inference,
        }

    adjusted = benjamini_yekutieli(raw_p)
    supported = []
    for representative in representatives:
        symbol = representative["broker_symbol"]
        row = results[symbol]
        row["by_adjusted_q"] = adjusted[symbol]
        row["positive_overall_mean"] = (
            row["mean_daily_centered_percentile_score"] is not None
            and row["mean_daily_centered_percentile_score"] > 0
        )
        row["positive_both_chronological_halves"] = (
            row["chronological_half_1_mean"] is not None
            and row["chronological_half_1_mean"] > 0
            and row["chronological_half_2_mean"] is not None
            and row["chronological_half_2_mean"] > 0
        )
        row["structural_support"] = (
            row["by_adjusted_q"] <= FDR_Q
            and row["minimum_sample_size_pass"]
            and row["positive_overall_mean"]
            and row["positive_both_chronological_halves"]
        )
        if row["structural_support"]:
            supported.append(symbol)

    return {
        "schema": "mxm.greenfield.epoch26-cross-sectional-ranking-structural-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "evidence_epoch": 26,
        "family": "CROSS_SECTIONAL_RANKING",
        "freeze_ref": FREEZE_REF,
        "implementation": {"version": VERSION},
        "source_artifacts": {
            "development_zip_filename": development_zip.name,
            "development_zip_sha256": development_hash,
            "replacement_zip_filename": replacement_zip.name,
            "replacement_zip_sha256": replacement_hash,
            "capture_acceptance_ref": freeze["authority"]["replacement_capture_acceptance_ref"],
            "capture_acceptance_sha256": CAPTURE_ACCEPTANCE_SHA256,
            "structural_coverage_ref": freeze["authority"]["replacement_structural_coverage_ref"],
            "structural_coverage_sha256": COVERAGE_SHA256,
        },
        "scope": {
            "representatives": len(results),
            "all_frozen_representatives_processed_exactly_once": (
                tuple((symbol, results[symbol]["symbol_id"]) for symbol in results)
                == EXPECTED_SYMBOLS
                and len(results) == 41
            ),
            "replacement_capture_symbol_ids": sorted(REPLACEMENT_IDS),
            "eligible_panel_timestamps": len(eligible_panel_counts),
            "omitted_timestamps_below_minimum_breadth": omitted_breadth_timestamps,
            "panel_breadth_minimum": MINIMUM_BREADTH,
            "panel_breadth_minimum_observed": min(eligible_panel_counts) if eligible_panel_counts else 0,
            "panel_breadth_maximum_observed": max(eligible_panel_counts) if eligible_panel_counts else 0,
        },
        "inference": {
            "test_family_size": 41,
            "multiplicity": "BENJAMINI_YEKUTIELI_FDR",
            "fdr_q": FDR_Q,
            "block_unit": "UTC_CALENDAR_DAY",
            "block_length_days": BLOCK_DAYS,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "supported_representatives_count": len(supported),
            "supported_representatives": supported,
            "subset_ranking_performed": False,
        },
        "symbols": results,
        "accounting_effect": {
            "v2_attempts_consumed": 0,
            "economic_outcomes_opened": 0,
            "search_budget_change": 0,
            "non_economic_price_return_features_computed": True,
            "economic_returns_or_pnl_computed": False,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "competition_start_authorized": False,
            "account_mutation": False,
        },
        "interpretation_boundary": {
            "economic_promotion_authorized": False,
            "mechanism_family_closed": False,
            "independent_confirmation": False,
            "result": "NON_ECONOMIC_CROSS_SECTIONAL_STRUCTURAL_SCREEN_ONLY",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--development-zip", required=True)
    parser.add_argument("--replacement-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    freeze = json.loads(Path(args.freeze).read_text(encoding="utf-8"))
    result = evaluate(freeze, Path(args.development_zip), Path(args.replacement_zip))
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "test_family_size": result["inference"]["test_family_size"],
        "supported_representatives_count": result["inference"]["supported_representatives_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
