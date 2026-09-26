from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "MXM_EPOCH25_MEAN_REVERSION_STRUCTURAL_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH25_MEAN_REVERSION_FRONTIER_FREEZE_V1.json"
DEVELOPMENT_ZIP_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_ZIP_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
M5_SECONDS = 300
WINDOW_BARS = 12
RESPONSE_BARS = 12
ANCHOR_STRIDE_BARS = 12
Z_THRESHOLD = 2.0
FDR_Q = 0.05
MINIMUM_PER_HALF = 30
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


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_freeze(freeze: dict[str, Any]) -> None:
    if freeze.get("schema") != "mxm.greenfield.epoch25-mean-reversion-frontier-freeze.v1":
        raise ValueError("unsupported mean-reversion freeze schema")
    if freeze.get("status") != "FROZEN_BEFORE_MEAN_REVERSION_STRUCTURAL_OUTCOME":
        raise ValueError("mean-reversion law is not prospectively frozen")
    authority = freeze["authority"]
    if authority.get("accepted_proposal_hash") != "840428cfc8fd3acaccc9fd85df4f802c7c66e0c45c299fdc4aee9abd1ce28c1c":
        raise ValueError("freeze is not bound to the accepted proposal")
    if authority.get("development_zip_sha256") != DEVELOPMENT_ZIP_SHA256:
        raise ValueError("development capture binding differs from accepted authority")
    if authority.get("replacement_zip_sha256") != REPLACEMENT_ZIP_SHA256:
        raise ValueError("replacement capture binding differs from accepted authority")
    scope = freeze["scope"]
    if (
        scope.get("resolution") != "M5"
        or scope.get("interval") != {
            "start_utc": "2026-06-15T00:00:00Z",
            "end_utc": "2026-09-13T23:59:59Z",
        }
        or scope.get("protected_forward_start") != "2026-09-17T12:02:58Z"
        or scope.get("representatives_are_not_economically_equivalent") is not True
    ):
        raise ValueError("freeze scope differs from accepted development authority")
    observed = tuple(
        (str(item["broker_symbol"]), int(item["symbol_id"]))
        for item in scope["representatives"]
    )
    if observed != EXPECTED_SYMBOLS or len(set(observed)) != 41:
        raise ValueError("freeze must contain the exact 41 current representatives in authority order")
    if int(scope.get("representative_count", 0)) != 41:
        raise ValueError("freeze representative count is not 41")
    if set(map(int, scope["replacement_capture_symbol_ids"])) != REPLACEMENT_IDS:
        raise ValueError("replacement capture symbol scope is not exact")
    law = freeze["preregistered_structural_law"]
    signal = law["signal"]
    response = law["response"]
    inference = law["inference"]
    if (
        int(signal["window_bars"]) != WINDOW_BARS
        or signal.get("window_includes_signal_bar") is not True
        or signal.get("center") != "ARITHMETIC_MEAN_OF_THE_12_CLOSES_ENDING_AT_SIGNAL_BAR"
        or signal.get("scale") != "POPULATION_STANDARD_DEVIATION_OF_THE_SAME_12_CLOSES"
        or float(signal["threshold"]) != Z_THRESHOLD
        or signal.get("signal_rule") != (
            "If scale is zero, emit no signal. Otherwise z=(signal_close-center)/scale; "
            "z>=2.0 signals SHORT, z<=-2.0 signals LONG, and all other values emit no signal."
        )
        or signal.get("timing") != (
            "Signal is evaluated only after the current M5 bar is complete; it uses that bar "
            "and the immediately preceding 11 exact contiguous M5 closes."
        )
        or int(response["bars"]) != RESPONSE_BARS
        or int(response["horizon_minutes"]) != 60
        or int(law["anchor_stride_bars"]) != ANCHOR_STRIDE_BARS
        or law.get("missing_data") != (
            "No forward fill, interpolation, resampling, or synthetic bars. A timestamp delta "
            "other than exactly 300 seconds starts a new segment; no response may cross a segment boundary."
        )
        or law.get("censoring") != (
            "Every admitted signal remains counted. If the next 12 exact M5 bars are not observed "
            "in the same segment, classify it RIGHT_CENSORED_FUTURE_RESPONSE and exclude it from settled-outcome statistics."
        )
        or int(inference["minimum_settled_nonflat_signals_per_chronological_half"]) != MINIMUM_PER_HALF
        or float(inference["fdr_q"]) != FDR_Q
        or inference.get("multiplicity") != "BENJAMINI_HOCHBERG_FDR_ACROSS_ALL_41_REPRESENTATIVES"
        or inference.get("per_symbol_test") != "ONE_SIDED_EXACT_BINOMIAL_SUCCESS_VS_0_5_ON_SETTLED_NONFLAT_SIGNALS"
        or inference.get("stability") != (
            "Combined success fraction and each chronological-half success fraction must be strictly greater than 0.5."
        )
        or law.get("no_parameter_search") is not True
    ):
        raise ValueError("freeze parameters differ from the implemented fixed law")
    if (
        freeze.get("family") != "MEAN_REVERSION"
        or freeze.get("accounting_effect", {}).get("economic_outcomes_opened") != 0
        or freeze.get("accounting_effect", {}).get("v2_attempts_consumed") != 0
        or freeze.get("safety", {}).get("protected_forward_opened") is not False
        or freeze.get("safety", {}).get("live_orders_authorized") is not False
    ):
        raise ValueError("freeze crosses a prohibited economic or safety boundary")


def exact_binomial_greater(successes: int, observations: int) -> float:
    if observations < 0 or successes < 0 or successes > observations:
        raise ValueError("invalid binomial counts")
    if observations == 0:
        return 1.0
    return sum(
        math.comb(observations, value)
        for value in range(successes, observations + 1)
    ) / (2 ** observations)


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


def canonicalize_identical_duplicates(
    rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    by_timestamp: dict[datetime, dict[str, Any]] = {}
    removed = 0
    for row in rows:
        timestamp = row["timestamp"]
        previous = by_timestamp.get(timestamp)
        if previous is None:
            by_timestamp[timestamp] = row
            continue
        if any(previous[field] != row[field] for field in ("open", "high", "low", "close", "tick_volume")):
            raise ValueError(f"conflicting duplicate at {row['time_utc']}")
        removed += 1
    canonical = [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]
    return canonical, removed


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
            raise ValueError("rows are not strictly chronological")
    return segments


def signal_direction(window: list[dict[str, Any]]) -> int:
    if len(window) != WINDOW_BARS:
        raise ValueError("signal window must contain exactly 12 bars")
    closes = [float(row["close"]) for row in window]
    scale = statistics.pstdev(closes)
    if scale == 0.0:
        return 0
    z_score = (closes[-1] - statistics.fmean(closes)) / scale
    if z_score >= Z_THRESHOLD:
        return -1
    if z_score <= -Z_THRESHOLD:
        return 1
    return 0


def evaluate_symbol(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows, duplicates_removed = canonicalize_identical_duplicates(rows)
    segments = split_contiguous(rows)
    admitted: list[dict[str, Any]] = []
    for segment in segments:
        for index in range(WINDOW_BARS - 1, len(segment), ANCHOR_STRIDE_BARS):
            direction = signal_direction(segment[index - WINDOW_BARS + 1:index + 1])
            if direction == 0:
                continue
            record: dict[str, Any] = {
                "timestamp": segment[index]["timestamp"],
                "settled": False,
                "outcome": None,
            }
            future_index = index + RESPONSE_BARS
            if future_index < len(segment):
                response = direction * (
                    float(segment[future_index]["close"]) - float(segment[index]["close"])
                )
                record["settled"] = True
                record["outcome"] = 1 if response > 0 else (-1 if response < 0 else 0)
            admitted.append(record)

    settled = sorted(
        (record for record in admitted if record["settled"]),
        key=lambda record: record["timestamp"],
    )
    nonflat = [record for record in settled if record["outcome"] != 0]
    half_index = len(nonflat) // 2
    halves = (nonflat[:half_index], nonflat[half_index:])
    successes = sum(record["outcome"] == 1 for record in nonflat)
    failures = sum(record["outcome"] == -1 for record in nonflat)
    flat = sum(record["outcome"] == 0 for record in settled)

    def half_summary(half: list[dict[str, Any]]) -> dict[str, Any]:
        half_successes = sum(record["outcome"] == 1 for record in half)
        return {
            "settled_nonflat_signals": len(half),
            "successes": half_successes,
            "failures": len(half) - half_successes,
            "success_fraction": half_successes / len(half) if half else None,
        }

    return {
        "rows": len(rows),
        "identical_duplicate_rows_removed": duplicates_removed,
        "contiguous_segments": len(segments),
        "admitted_signals": len(admitted),
        "settled_signals": len(settled),
        "right_censored_future_response": sum(not record["settled"] for record in admitted),
        "flat_settled_signals": flat,
        "settled_nonflat_signals": len(nonflat),
        "successes": successes,
        "failures": failures,
        "success_fraction": successes / len(nonflat) if nonflat else None,
        "one_sided_exact_binomial_p": exact_binomial_greater(successes, len(nonflat)),
        "chronological_half_1": half_summary(halves[0]),
        "chronological_half_2": half_summary(halves[1]),
    }


def _read_member(archive: zipfile.ZipFile, member: str, freeze: dict[str, Any]) -> list[dict[str, Any]]:
    start = _parse_utc(freeze["scope"]["interval"]["start_utc"])
    end = _parse_utc(freeze["scope"]["interval"]["end_utc"])
    protected = _parse_utc(freeze["scope"]["protected_forward_start"])
    text = archive.read(member).decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    expected_fields = ["time_utc", "open", "high", "low", "close", "tick_volume"]
    if reader.fieldnames != expected_fields:
        raise ValueError(f"{member}: unexpected M5 CSV header")
    rows = []
    for source in reader:
        timestamp = _parse_utc(source["time_utc"])
        if timestamp < start or timestamp > end or timestamp >= protected:
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
            min(values["open"], values["high"], values["low"], values["close"]) <= 0
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
) -> dict[str, Any]:
    validate_freeze(freeze)
    development_zip = Path(development_zip)
    replacement_zip = Path(replacement_zip)
    development_hash = _sha256_file(development_zip)
    replacement_hash = _sha256_file(replacement_zip)
    if development_hash != DEVELOPMENT_ZIP_SHA256:
        raise ValueError("development capture ZIP hash mismatch")
    if replacement_hash != REPLACEMENT_ZIP_SHA256:
        raise ValueError("replacement capture ZIP hash mismatch")

    results: dict[str, Any] = {}
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for symbol, symbol_id in EXPECTED_SYMBOLS:
            source = replacement if symbol_id in REPLACEMENT_IDS else development
            member = _find_member(source, symbol_id)
            row_result = evaluate_symbol(_read_member(source, member, freeze))
            results[symbol] = {
                "symbol_id": symbol_id,
                "source_member": member,
                **row_result,
            }

    adjusted = bh_adjust({
        symbol: result["one_sided_exact_binomial_p"]
        for symbol, result in results.items()
    })
    supported = []
    for symbol, result in results.items():
        result["bh_adjusted_q"] = adjusted[symbol]
        half1 = result["chronological_half_1"]
        half2 = result["chronological_half_2"]
        result["minimum_evidence_pass"] = (
            half1["settled_nonflat_signals"] >= MINIMUM_PER_HALF
            and half2["settled_nonflat_signals"] >= MINIMUM_PER_HALF
        )
        result["stability_pass"] = (
            result["success_fraction"] is not None
            and result["success_fraction"] > 0.5
            and half1["success_fraction"] is not None
            and half1["success_fraction"] > 0.5
            and half2["success_fraction"] is not None
            and half2["success_fraction"] > 0.5
        )
        result["structural_support"] = (
            result["bh_adjusted_q"] <= FDR_Q
            and result["minimum_evidence_pass"]
            and result["stability_pass"]
        )
        if result["structural_support"]:
            supported.append(symbol)

    return {
        "schema": "mxm.greenfield.epoch25-mean-reversion-structural-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "evidence_epoch": 25,
        "family": "MEAN_REVERSION",
        "freeze_ref": FREEZE_REF,
        "implementation": {"version": VERSION},
        "source_artifacts": {
            "development_zip_sha256": development_hash,
            "replacement_zip_sha256": replacement_hash,
        },
        "scope": {
            "representatives": len(results),
            "all_frozen_representatives_processed_exactly_once": tuple(results) == tuple(
                symbol for symbol, _ in EXPECTED_SYMBOLS
            ),
        },
        "inference": {
            "fdr_q": FDR_Q,
            "minimum_settled_nonflat_signals_per_chronological_half": MINIMUM_PER_HALF,
            "supported_symbols_count": len(supported),
            "supported_symbols": sorted(supported),
        },
        "symbols": results,
        "aggregate": {
            "admitted_signals": sum(result["admitted_signals"] for result in results.values()),
            "settled_signals": sum(result["settled_signals"] for result in results.values()),
            "right_censored_future_response": sum(
                result["right_censored_future_response"] for result in results.values()
            ),
            "settled_nonflat_signals": sum(
                result["settled_nonflat_signals"] for result in results.values()
            ),
            "successes": sum(result["successes"] for result in results.values()),
            "failures": sum(result["failures"] for result in results.values()),
            "flat_settled_signals": sum(result["flat_settled_signals"] for result in results.values()),
        },
        "interpretation_boundary": {
            "economic_promotion_authorized": False,
            "mechanism_family_closed": False,
            "winner_selected": False,
            "internal_development_data_is_independent_confirmation": False,
            "result": "NON_ECONOMIC_DEVELOPMENT_STRUCTURAL_SCREEN_ONLY",
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
    parser.add_argument("--development-zip", required=True)
    parser.add_argument("--replacement-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    freeze = json.loads(Path(args.freeze).read_text(encoding="utf-8"))
    result = evaluate(freeze, Path(args.development_zip), Path(args.replacement_zip))
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
