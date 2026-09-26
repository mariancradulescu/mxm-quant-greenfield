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
from typing import Any, Iterable

VERSION = "MXM_EPOCH29_REGIME_CONTEXT_CONDITIONED_STRUCTURAL_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH29_REGIME_CONTEXT_CONDITIONED_FRONTIER_FREEZE_V1.json"
FREEZE_SCHEMA = "mxm.greenfield.epoch29-regime-context-conditioned-frontier-freeze.v1"
REGISTRY_SHA256 = "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3"
DEVELOPMENT_ZIP_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_ZIP_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
M5_SECONDS = 300
REPLACEMENT_IDS = frozenset({7427, 5352, 2924})
CONTEXTS = ("HIGH_VOL_EXPANDING", "LOW_VOL_COMPRESSED")
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
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def validate_freeze(freeze: dict[str, Any], registry_path: Path) -> None:
    if freeze.get("schema") != FREEZE_SCHEMA:
        raise ValueError("unsupported epoch29 freeze schema")
    if freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_EPOCH29_STRUCTURAL_SCREEN":
        raise ValueError("epoch29 law is not prospectively frozen")
    authority = freeze["authority"]
    if (
        authority.get("accepted_proposal_ref")
        != "research_v3/ai_director/proposals/AUTO_reason_0282192e6861bbbc8540e81125ce260a.json"
        or authority.get("accepted_proposal_hash")
        != "1e3cbd5dd134c72eb58c889056a1d476d0f6757665ba7a348c4fa258e7a2ef22"
        or authority.get("frontier_registry_ref")
        != "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
        or authority.get("frontier_registry_sha256") != REGISTRY_SHA256
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
        raise ValueError("freeze does not match accepted epoch29 authority")
    if sha256_file(registry_path) != REGISTRY_SHA256:
        raise ValueError("current structural registry hash mismatch")
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    if registry.get("status") != "CURRENT_STRUCTURAL_FRONTIER_RECOMPUTED_FROM_ACCEPTED_BROKER_NATIVE_METADATA":
        raise ValueError("structural registry is not authoritative")
    representatives = tuple(
        (str(item["broker_symbol"]), int(item["symbol_id"]))
        for item in freeze["scope"]["representatives"]
    )
    registry_representatives = tuple(
        (str(item["broker_symbol"]), int(item["symbol_id"]))
        for item in registry["representatives"]
    )
    if representatives != EXPECTED_SYMBOLS or representatives != registry_representatives:
        raise ValueError("freeze must bind all exact current representatives in authority order")
    scope = freeze["scope"]
    if (
        freeze.get("family") != "REGIME_CONTEXT_CONDITIONED"
        or int(scope.get("representative_count", 0)) != 41
        or scope.get("resolution") != "M5"
        or scope.get("interval") != {
            "start_utc": "2026-06-15T00:00:00Z",
            "end_utc": "2026-09-13T23:59:59Z",
        }
        or scope.get("protected_forward_start") != "2026-09-17T12:02:58Z"
        or scope.get("representatives_are_not_economically_equivalent") is not True
        or set(map(int, scope.get("replacement_capture_symbol_ids", []))) != REPLACEMENT_IDS
    ):
        raise ValueError("freeze scope differs from accepted data authority")
    if freeze.get("data_bindings") != [
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
    ]:
        raise ValueError("freeze data bindings differ from accepted capture scope")
    law = freeze["preregistered_structural_law"]
    event = law["event"]
    regime = law["regime_classifier"]
    outcome = law["outcome"]
    partition = law["partition"]
    inference = law["inference"]
    if (
        event != {
            "resolution_seconds": 300,
            "contiguous_history_bars": 25,
            "lookback_bars": 24,
            "direction": "close_t_above_maximum_prior_24_highs_is_up; close_t_below_minimum_prior_24_lows_is_down; otherwise_no_event",
            "range_expansion": "current_high_minus_low_at_least_1.5_times_median_prior_24_high_minus_low",
            "zero_prior_median_range": "require_current_range_strictly_positive",
            "selection": "CHRONOLOGICAL_EARLIEST_FIRST_PER_SYMBOL",
            "minimum_spacing_bars": 3,
            "spacing_rule": "Selected event bar indices must differ by at least 3 within a contiguous segment; restart event selection after a timestamp gap.",
        }
        or regime != {
            "atr_bars": 14,
            "atr_definition": "ARITHMETIC_MEAN_OF_14_TRUE_RANGES; TRUE_RANGE_IS_MAX(HIGH-LOW,ABS(HIGH-PREVIOUS_CLOSE),ABS(LOW-PREVIOUS_CLOSE))",
            "classification_timing": "At event bar t, use ATR(t-1) only, ranked against the immediately preceding 48 ATR values ending at t-2.",
            "percentile_rank": "COUNT(reference_ATR<=current_ATR)/48",
            "high_context": "HIGH_VOL_EXPANDING when percentile_rank>=0.80",
            "low_context": "LOW_VOL_COMPRESSED when percentile_rank<=0.20",
            "middle_context": "UNCLASSIFIED; exclude from context-specific tests and report",
            "warmup": "An event without 49 consecutive prior/current ATR observations on the same contiguous segment is UNCLASSIFIED.",
        }
        or outcome != {
            "horizon_bars": 3,
            "reference": "close_at_event_bar",
            "continuation": "event_direction*(close_t_plus_3-close_t)>0",
            "reversal": "event_direction*(close_t_plus_3-close_t)<0",
            "flat": "exactly_zero_directional_change; report separately and exclude from the binomial denominator",
            "settlement": "Require each of the next 3 exact M5 bars in the same contiguous segment; otherwise right-censor the event.",
        }
        or partition != {
            "rule": "WITHIN_EACH_SYMBOL_AND_REGIME_SORT_SETTLED_NONFLAT_EVENTS_BY_TIMESTAMP_AND_SPLIT_INTO_FIRST_FLOOR_N_OVER_2_AND_REMAINDER",
            "minimum_nonflat_events_per_half": 30,
            "tie_rule": "Timestamp order is strict after canonicalization; earlier floor(N/2) events form half 1.",
        }
        or inference != {
            "per_half_test": "ONE_SIDED_EXACT_BINOMIAL_CONTINUATION_VS_0_5",
            "per_half_raw_p_threshold": 0.025,
            "context_selection_adjustment": "For each symbol, regime p is max(half_1_p,half_2_p); symbol p is min(1,2*min(high_regime_p,low_regime_p)). A regime with fewer than 30 nonflat outcomes in either half has regime p=1.",
            "multiplicity": "BENJAMINI_HOCHBERG_FDR_ACROSS_ALL_41_SYMBOL_P_VALUES",
            "fdr_q": 0.05,
            "support": "At least one regime has at least 30 settled nonflat events in each half and each half raw one-sided exact-binomial p<=0.025, AND the symbol BH-adjusted q<=0.05.",
            "reporting": "Report every symbol and both regimes; no ranking or economic interpretation.",
        }
        or law.get("missing_data") != (
            "No forward fill, interpolation, resampling, or synthetic bars. Any timestamp delta other than exactly 300 seconds begins a new segment; event histories, regime windows, and outcomes cannot cross segment boundaries."
        )
        or law.get("duplicate_timestamps") != (
            "Collapse only rows with identical parsed OHLC and tick volume; any conflicting duplicate fails closed."
        )
        or law.get("no_parameter_search") is not True
    ):
        raise ValueError("freeze parameters differ from the implemented fixed law")
    if (
        freeze.get("accounting_effect", {}).get("economic_outcomes_opened") != 0
        or freeze.get("accounting_effect", {}).get("v2_attempts_consumed") != 0
        or freeze.get("safety", {}).get("protected_forward_opened") is not False
        or freeze.get("safety", {}).get("live_orders_authorized") is not False
        or freeze.get("interpretation_boundary", {}).get("economic_promotion_authorized") is not False
    ):
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


def split_contiguous(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not rows:
        return []
    segments = [[rows[0]]]
    for row in rows[1:]:
        delta = (row["timestamp"] - segments[-1][-1]["timestamp"]).total_seconds()
        if delta == M5_SECONDS:
            segments[-1].append(row)
        elif delta > 0:
            segments.append([row])
        else:
            raise ValueError("rows are not strictly chronological after canonicalization")
    return segments


def exact_binomial_greater(successes: int, observations: int) -> float:
    if observations < 0 or successes < 0 or successes > observations:
        raise ValueError("invalid binomial counts")
    if observations == 0:
        return 1.0
    return sum(math.comb(observations, value) for value in range(successes, observations + 1)) / (
        1 << observations
    )


def bh_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 1.0
    count = len(ordered)
    for rank in range(count, 0, -1):
        key, p_value = ordered[rank - 1]
        running = min(running, min(1.0, p_value * count / rank))
        adjusted[key] = running
    return adjusted


def _atr_at(segment: list[dict[str, Any]], end_index: int, period: int) -> float | None:
    if end_index < period:
        return None
    ranges = []
    for index in range(end_index - period + 1, end_index + 1):
        row = segment[index]
        previous_close = float(segment[index - 1]["close"])
        ranges.append(max(
            float(row["high"]) - float(row["low"]),
            abs(float(row["high"]) - previous_close),
            abs(float(row["low"]) - previous_close),
        ))
    return statistics.fmean(ranges)


def _event_context(segment: list[dict[str, Any]], index: int) -> str | None:
    current_atr_index = index - 1
    reference_start = index - 49
    if reference_start < 14:
        return None
    prior_atrs = [
        _atr_at(segment, atr_index, 14)
        for atr_index in range(reference_start, index - 1)
    ]
    current_atr = _atr_at(segment, current_atr_index, 14)
    if current_atr is None or len(prior_atrs) != 48 or any(value is None for value in prior_atrs):
        return None
    rank = sum(float(value) <= current_atr for value in prior_atrs) / 48
    if rank >= 0.80:
        return "HIGH_VOL_EXPANDING"
    if rank <= 0.20:
        return "LOW_VOL_COMPRESSED"
    return None


def _event_direction(segment: list[dict[str, Any]], index: int) -> int:
    prior = segment[index - 24:index]
    current = segment[index]
    if len(prior) != 24:
        return 0
    prior_median_range = statistics.median(
        float(row["high"]) - float(row["low"]) for row in prior
    )
    current_range = float(current["high"]) - float(current["low"])
    expanded = (
        current_range >= 1.5 * prior_median_range
        if prior_median_range > 0
        else current_range > 0
    )
    if not expanded:
        return 0
    if float(current["close"]) > max(float(row["high"]) for row in prior):
        return 1
    if float(current["close"]) < min(float(row["low"]) for row in prior):
        return -1
    return 0


def _summarize_context(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    nonflat = sorted(
        (row for row in outcomes if row["outcome"] != 0),
        key=lambda row: row["timestamp"],
    )
    half_index = len(nonflat) // 2
    halves = (nonflat[:half_index], nonflat[half_index:])
    half_summaries = []
    half_p_values = []
    for half in halves:
        continuations = sum(row["outcome"] == 1 for row in half)
        reversals = sum(row["outcome"] == -1 for row in half)
        p_value = exact_binomial_greater(continuations, len(half))
        half_p_values.append(p_value)
        half_summaries.append({
            "settled_nonflat_events": len(half),
            "continuation": continuations,
            "reversal": reversals,
            "continuation_fraction": continuations / len(half) if half else None,
            "one_sided_exact_binomial_p": p_value,
            "minimum_sample_size_pass": len(half) >= 30,
        })
    eligible = all(half["minimum_sample_size_pass"] for half in half_summaries)
    both_halves_pass = eligible and all(p_value <= 0.025 for p_value in half_p_values)
    settled = [row for row in outcomes if row["outcome"] is not None]
    return {
        "selected_events": len(outcomes),
        "settled_events": len(settled),
        "right_censored_events": len(outcomes) - len(settled),
        "flat_settled_events": sum(row["outcome"] == 0 for row in settled),
        "settled_nonflat_events": len(nonflat),
        "chronological_half_1": half_summaries[0],
        "chronological_half_2": half_summaries[1],
        "regime_p_value": max(half_p_values) if eligible else 1.0,
        "both_halves_pass": both_halves_pass,
    }


def evaluate_symbol(rows: list[dict[str, Any]]) -> dict[str, Any]:
    canonical, duplicates_removed = canonicalize_identical_duplicates(rows)
    segments = split_contiguous(canonical)
    context_outcomes: dict[str, list[dict[str, Any]]] = {context: [] for context in CONTEXTS}
    selected_events = 0
    unclassified_events = 0
    candidate_events = 0

    for segment_index, segment in enumerate(segments):
        last_selected_index: int | None = None
        for index in range(24, len(segment)):
            direction = _event_direction(segment, index)
            if direction == 0:
                continue
            candidate_events += 1
            if last_selected_index is not None and index - last_selected_index < 3:
                continue
            last_selected_index = index
            selected_events += 1
            context = _event_context(segment, index)
            if context is None:
                unclassified_events += 1
                continue
            future_index = index + 3
            if future_index >= len(segment):
                outcome = None
            else:
                directional_change = direction * (
                    float(segment[future_index]["close"]) - float(segment[index]["close"])
                )
                outcome = 1 if directional_change > 0 else (-1 if directional_change < 0 else 0)
            context_outcomes[context].append({
                "timestamp": segment[index]["timestamp"],
                "outcome": outcome,
                "segment_index": segment_index,
            })

    summaries = {
        context: _summarize_context(context_outcomes[context])
        for context in CONTEXTS
    }
    symbol_p_value = min(
        1.0,
        2.0 * min(summaries[context]["regime_p_value"] for context in CONTEXTS),
    )
    return {
        "rows": len(canonical),
        "identical_duplicate_rows_removed": duplicates_removed,
        "contiguous_segments": len(segments),
        "eligible_event_candidates": candidate_events,
        "selected_events": selected_events,
        "unclassified_events": unclassified_events,
        "contexts": summaries,
        "context_selection_adjusted_symbol_p_value": symbol_p_value,
    }


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
        timestamp = parse_utc(source["time_utc"])
        if timestamp < start or timestamp > end or timestamp >= protected_start:
            raise ValueError(f"{member}: row outside frozen development interval")
        if timestamp.second != 0 or timestamp.microsecond != 0 or timestamp.minute % 5:
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
        rows.append({
            "time_utc": source["time_utc"],
            "timestamp": timestamp,
            **values,
        })
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


def evaluate(
    freeze: dict[str, Any],
    development_zip: Path,
    replacement_zip: Path,
    registry_path: Path,
) -> dict[str, Any]:
    validate_freeze(freeze, registry_path)
    development_zip = Path(development_zip)
    replacement_zip = Path(replacement_zip)
    development_hash = sha256_file(development_zip)
    replacement_hash = sha256_file(replacement_zip)
    if development_hash != DEVELOPMENT_ZIP_SHA256:
        raise ValueError("development capture ZIP hash mismatch")
    if replacement_hash != REPLACEMENT_ZIP_SHA256:
        raise ValueError("replacement capture ZIP hash mismatch")

    results: dict[str, Any] = {}
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for symbol, symbol_id in EXPECTED_SYMBOLS:
            source = replacement if symbol_id in REPLACEMENT_IDS else development
            member = _find_member(source, symbol_id)
            results[symbol] = {
                "symbol_id": symbol_id,
                "source_member": member,
                **evaluate_symbol(_read_member(source, member, freeze)),
            }

    adjusted = bh_adjust({
        symbol: result["context_selection_adjusted_symbol_p_value"]
        for symbol, result in results.items()
    })
    supported_symbols = []
    for symbol, result in results.items():
        result["bh_adjusted_q"] = adjusted[symbol]
        passing_contexts = [
            context for context in CONTEXTS
            if result["contexts"][context]["both_halves_pass"]
        ]
        result["supported_contexts"] = passing_contexts
        result["supported_symbol"] = adjusted[symbol] <= 0.05 and bool(passing_contexts)
        if result["supported_symbol"]:
            supported_symbols.append(symbol)

    total_by_context = {
        context: {
            "selected_events": sum(row["contexts"][context]["selected_events"] for row in results.values()),
            "settled_events": sum(row["contexts"][context]["settled_events"] for row in results.values()),
            "continuation": sum(
                half["continuation"]
                for row in results.values()
                for half in (
                    row["contexts"][context]["chronological_half_1"],
                    row["contexts"][context]["chronological_half_2"],
                )
            ),
            "reversal": sum(
                half["reversal"]
                for row in results.values()
                for half in (
                    row["contexts"][context]["chronological_half_1"],
                    row["contexts"][context]["chronological_half_2"],
                )
            ),
            "flat_settled_events": sum(
                row["contexts"][context]["flat_settled_events"] for row in results.values()
            ),
        }
        for context in CONTEXTS
    }
    return {
        "schema": "mxm.greenfield.epoch29-regime-context-conditioned-structural-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "evidence_epoch": 29,
        "family": "REGIME_CONTEXT_CONDITIONED",
        "freeze_ref": FREEZE_REF,
        "implementation": {"version": VERSION},
        "freeze_sha256": sha256_file(Path(registry_path).with_name(Path(FREEZE_REF).name)),
        "input_attestation": {
            "registry_sha256": sha256_file(registry_path),
            "development_zip_sha256": development_hash,
            "replacement_zip_sha256": replacement_hash,
            "all_41_frozen_representatives_processed_exactly_once": len(results) == 41,
            "protected_forward_rows_read": 0,
        },
        "scope": {
            "representatives_processed": len(results),
            "ordered_representatives": [symbol for symbol, _ in EXPECTED_SYMBOLS],
            "structural_representatives_are_economically_equivalent": False,
        },
        "inference": {
            "per_half_raw_p_threshold": 0.025,
            "fdr_q": 0.05,
            "multiplicity": "BH_ACROSS_41_CONTEXT_SELECTION_ADJUSTED_SYMBOL_P_VALUES",
            "supported_symbols_count": len(supported_symbols),
            "supported_symbols": sorted(supported_symbols),
            "mechanism_family_closed": False,
        },
        "aggregate": total_by_context,
        "symbols": results,
        "interpretation_boundary": {
            "economic_promotion_authorized": False,
            "independent_confirmation": False,
            "internal_development_data_is_independent_confirmation": False,
            "mechanism_family_closed": False,
            "winner_selected": False,
            "result": "FROZEN_NON_ECONOMIC_DEVELOPMENT_STRUCTURAL_SCREEN_ONLY",
        },
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--registry", required=True)
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
