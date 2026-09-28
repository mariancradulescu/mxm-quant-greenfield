"""Outcome-blind coverage and temporal-sufficiency audit of accepted M5 inputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "MXM_REGIME_CONTEXT_DATA_SUFFICIENCY_AUDIT_V1"
FREEZE_REF = "research_v3/REGIME_CONTEXT_DATA_SUFFICIENCY_AUDIT_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_88b3d8ac3e0ad746ff188958465fbd36.json"
PROPOSAL_SHA256 = "20db9e7dcc5e3ff2ac4746f7fa81c82ded1598a2ab2bca078c266a037359a62e"
REGISTRY_REF = "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
REGISTRY_SHA256 = "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3"
DEVELOPMENT_ACCEPTANCE_REF = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json"
DEVELOPMENT_PLAN_REF = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_PLAN_V1.json"
DEVELOPMENT_PLAN_SHA256 = "b29e6f95dcd1adc3374f71124628388df7e235829fc019d31b1183166b9c7d6a"
DEVELOPMENT_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_ACCEPTANCE_REF = "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json"
REPLACEMENT_PLAN_REF = "data/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_PLAN_EPOCH22_V1.json"
REPLACEMENT_PLAN_SHA256 = "a573cbcf19897c50f9ae2ad971dc308529578604c583d57d2e836906b0c25b5f"
REPLACEMENT_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
START_UTC = datetime(2026, 6, 15, tzinfo=timezone.utc)
END_UTC = datetime(2026, 9, 13, 23, 59, 59, tzinfo=timezone.utc)
PROTECTED_START = datetime(2026, 9, 17, 12, 2, 58, tzinfo=timezone.utc)
BAR_SECONDS = 300
ATR_PERIOD = 14
RANK_LOOKBACK = 48
SESSION_OVERLAP_START_UTC = 13
SESSION_OVERLAP_END_UTC = 16
FIELDS = ("time_utc", "open", "high", "low", "close", "tick_volume")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp lacks timezone")
    return parsed.astimezone(timezone.utc)


def _same_bar(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(left[key] == right[key] for key in ("open", "high", "low", "close", "tick_volume"))


def canonicalize_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    result: list[dict[str, Any]] = []
    duplicates = 0
    previous: datetime | None = None
    for row in rows:
        timestamp = row["timestamp"]
        if previous is not None and timestamp < previous:
            raise ValueError("timestamps are not strictly ordered")
        if result and timestamp == result[-1]["timestamp"]:
            if not _same_bar(result[-1], row):
                raise ValueError(f"conflicting duplicate at {row['time_utc']}")
            duplicates += 1
            continue
        result.append(row)
        previous = timestamp
    return result, duplicates


def read_series(
    archive: zipfile.ZipFile,
    symbol_id: int,
    canonicalize_capture_order: bool = False,
) -> list[dict[str, Any]]:
    matches = [
        name for name in archive.namelist()
        if name.startswith(f"raw/{symbol_id}_") and name.endswith("_M5.csv")
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one accepted M5 series for symbol id {symbol_id}")
    reader = csv.DictReader(io.StringIO(archive.read(matches[0]).decode("utf-8-sig")))
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError(f"{matches[0]}: unexpected M5 CSV header")
    rows = []
    for source in reader:
        timestamp = parse_utc(source["time_utc"])
        if timestamp >= PROTECTED_START:
            raise ValueError("protected-forward timestamp encountered")
        if not START_UTC <= timestamp <= END_UTC:
            raise ValueError("out-of-interval timestamp encountered")
        values = {field: float(source[field]) for field in FIELDS[1:]}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("non-finite M5 value")
        if (values["low"] <= 0 or values["close"] <= 0 or
                values["high"] < max(values["open"], values["close"], values["low"]) or
                values["low"] > min(values["open"], values["close"]) or
                values["tick_volume"] < 0):
            raise ValueError("invalid OHLC or tick-volume row")
        rows.append({"time_utc": source["time_utc"], "timestamp": timestamp, **values})
    if not rows:
        raise ValueError(f"{matches[0]}: empty accepted series")
    if canonicalize_capture_order:
        rows.sort(key=lambda row: row["timestamp"])
    return rows


def _atr(values: list[float], index: int) -> float | None:
    if index < ATR_PERIOD - 1:
        return None
    return statistics.fmean(values[index - ATR_PERIOD + 1:index + 1])


def _rank(value: float, references: list[float]) -> float:
    return sum(reference <= value for reference in references) / len(references)


def _classify_segment(segment: list[dict[str, Any]]) -> list[tuple[str | None, str]]:
    true_ranges = []
    for position, row in enumerate(segment):
        if position == 0:
            true_ranges.append(float(row["high"]) - float(row["low"]))
        else:
            prior_close = float(segment[position - 1]["close"])
            true_ranges.append(max(
                float(row["high"]) - float(row["low"]),
                abs(float(row["high"]) - prior_close),
                abs(float(row["low"]) - prior_close),
            ))
    atr_values = [_atr(true_ranges, position) for position in range(len(segment))]
    states: list[tuple[str | None, str]] = [(None, "INSUFFICIENT_HISTORY")] * len(segment)
    for index in range(len(segment)):
        current = index - 1
        first_reference = index - RANK_LOOKBACK - 1
        if first_reference < ATR_PERIOD - 1:
            continue
        current_atr = atr_values[current]
        references = atr_values[first_reference:current]
        activity = [float(segment[position]["tick_volume"])
                    for position in range(first_reference, current)]
        if current_atr is None or len(references) != RANK_LOOKBACK or len(activity) != RANK_LOOKBACK:
            continue
        if any(value is None for value in references):
            continue
        vol_rank = _rank(current_atr, [float(value) for value in references])
        activity_rank = _rank(float(segment[current]["tick_volume"]), activity)
        vol = "HIGH_VOL" if vol_rank >= 0.8 else "LOW_VOL" if vol_rank <= 0.2 else None
        active = ("HIGH_ACTIVITY" if activity_rank >= 0.8
                  else "LOW_ACTIVITY" if activity_rank <= 0.2 else None)
        if vol is None or active is None:
            states[index] = (None, "MIDDLE_VOLATILITY_OR_ACTIVITY_RANK")
            continue
        timestamp = segment[index]["timestamp"]
        session = ("OVERLAP" if SESSION_OVERLAP_START_UTC <= timestamp.hour < SESSION_OVERLAP_END_UTC
                   else "NON_OVERLAP")
        states[index] = (f"{vol}_{active}_{session}", "CLASSIFIED")
    return states


def _segments(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    segments: list[list[dict[str, Any]]] = []
    for row in rows:
        if (not segments or
                (row["timestamp"] - segments[-1][-1]["timestamp"]).total_seconds() != BAR_SECONDS):
            segments.append([row])
        else:
            segments[-1].append(row)
    return segments


def _effective_n(series: dict[date, float]) -> dict[str, Any]:
    ordered = sorted(series.items())
    n = len(ordered)
    if n < 2:
        return {"date_clusters": n, "effective_n": float(n), "positive_autocorrelation_lags": 0}
    mean = statistics.fmean(value for _, value in ordered)
    variance = sum((value - mean) ** 2 for _, value in ordered)
    if variance == 0:
        return {"date_clusters": n, "effective_n": float(n), "positive_autocorrelation_lags": 0}
    by_date = dict(ordered)
    first, last = ordered[0][0], ordered[-1][0]
    max_lag = min(30, (last - first).days)
    tau = 1.0
    positive_lags = 0
    for lag in range(1, max_lag + 1):
        covariance = 0.0
        pairs = 0
        for day, value in ordered:
            later = day + timedelta(days=lag)
            if later in by_date:
                covariance += (value - mean) * (by_date[later] - mean)
                pairs += 1
        if pairs < 2:
            break
        rho = covariance / variance
        if rho <= 0:
            break
        tau += 2 * rho
        positive_lags += 1
    return {
        "date_clusters": n,
        "effective_n": max(1.0, min(float(n), n / tau)),
        "positive_autocorrelation_lags": positive_lags,
    }


def _sensitivity(effective_n: float) -> dict[str, Any]:
    return {
        "standardized_mean_shift_at_80pct_power_two_sided_alpha_0_05": (
            2.8016 / math.sqrt(effective_n) if effective_n > 0 else None
        ),
        "interpretation": "normal-approximation planning sensitivity only; not an inference or outcome effect",
    }


def audit_symbol(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows, duplicates = canonicalize_rows(rows)
    segments = _segments(rows)
    state_bars: Counter[str] = Counter()
    date_state_bars: dict[str, Counter[date]] = defaultdict(Counter)
    state_spells: Counter[str] = Counter()
    state_spell_dates: dict[str, set[date]] = defaultdict(set)
    unclassified_reasons: Counter[str] = Counter()
    daily_context: dict[date, int] = Counter()
    daily_rows: Counter[date] = Counter()
    overlap_rows = 0
    missing_intervals: list[float] = []
    for row in rows:
        day = row["timestamp"].date()
        daily_rows[day] += 1
        if SESSION_OVERLAP_START_UTC <= row["timestamp"].hour < SESSION_OVERLAP_END_UTC:
            overlap_rows += 1
    for previous, current in zip(rows, rows[1:]):
        delta = (current["timestamp"] - previous["timestamp"]).total_seconds()
        if delta != BAR_SECONDS:
            missing_intervals.append(delta)
    for segment in segments:
        previous_state: str | None = None
        for index, (row, (state, reason)) in enumerate(zip(segment, _classify_segment(segment))):
            if state is None:
                unclassified_reasons[reason] += 1
                previous_state = None
                continue
            day = row["timestamp"].date()
            state_bars[state] += 1
            date_state_bars[state][day] += 1
            daily_context[day] += 1
            if state != previous_state:
                state_spells[state] += 1
                state_spell_dates[state].add(day)
            previous_state = state
    observed_dates = {
        day for state_dates in date_state_bars.values() for day in state_dates
    }
    states = {}
    for vol in ("LOW_VOL", "HIGH_VOL"):
        for activity in ("LOW_ACTIVITY", "HIGH_ACTIVITY"):
            for session in ("NON_OVERLAP", "OVERLAP"):
                name = f"{vol}_{activity}_{session}"
                daily = {
                    day: date_state_bars[name].get(day, 0) / sum(
                        state_date_counts.get(day, 0)
                        for state_date_counts in date_state_bars.values()
                    )
                    for day in observed_dates
                }
                sample = _effective_n(daily)
                states[name] = {
                    "context_observations": state_bars[name],
                    "utc_date_clusters": len(date_state_bars[name]),
                    "effective_n_basis_utc_dates": sample["date_clusters"],
                    "effective_date_clusters": sample["effective_n"],
                    "positive_autocorrelation_lags": sample["positive_autocorrelation_lags"],
                    "contiguous_context_spell_clusters": state_spells[name],
                    "context_spell_utc_date_clusters": len(state_spell_dates[name]),
                    "detectable_effect_sensitivity": _sensitivity(sample["effective_n"]),
                }
    context_dates = {
        day: daily_context.get(day, 0) / row_count
        for day, row_count in daily_rows.items()
    }
    effective = _effective_n(context_dates)
    return {
        "m5_rows": len(rows),
        "identical_duplicate_rows_removed": duplicates,
        "first_timestamp_utc": rows[0]["timestamp"].isoformat().replace("+00:00", "Z"),
        "last_timestamp_utc": rows[-1]["timestamp"].isoformat().replace("+00:00", "Z"),
        "contiguous_segments": len(segments),
        "timestamp_gap_count": len(missing_intervals),
        "timestamp_gap_seconds": {
            "maximum_interval": max(missing_intervals) if missing_intervals else 0,
            "sum_of_noncontiguous_intervals": sum(missing_intervals) if missing_intervals else 0,
        },
        "context_classified_observations": sum(state_bars.values()),
        "context_unclassified_observations": len(rows) - sum(state_bars.values()),
        "context_unclassified_reasons": dict(sorted(unclassified_reasons.items())),
        "context_date_clusters": effective["date_clusters"],
        "context_effective_date_clusters": effective["effective_n"],
        "schedule_overlap_proxy_observations": overlap_rows,
        "schedule_overlap_proxy_fraction": overlap_rows / len(rows),
        "states": states,
    }


def _schedule_key(representative: dict[str, Any]) -> tuple[str, str, bool]:
    signature = representative["signature"]
    return signature[2], signature[3], signature[4]


def _archive_series(
    archive: zipfile.ZipFile,
    representative: dict[str, Any],
    canonicalize_capture_order: bool,
) -> list[dict[str, Any]]:
    return read_series(
        archive,
        int(representative["symbol_id"]),
        canonicalize_capture_order=canonicalize_capture_order,
    )


def validate_inputs(freeze: dict[str, Any], registry_path: Path, development_zip: Path,
                    replacement_zip: Path) -> list[dict[str, Any]]:
    if freeze.get("schema") != "mxm.greenfield.regime-context-data-sufficiency-freeze.v1":
        raise ValueError("unsupported audit freeze")
    if freeze.get("status") != "PROSPECTIVELY_FROZEN_NON_ECONOMIC_AUDIT":
        raise ValueError("audit freeze is not prospective")
    authority = freeze.get("authority", {})
    if (authority.get("accepted_proposal_ref") != PROPOSAL_REF or
            authority.get("accepted_proposal_file_sha256") != PROPOSAL_SHA256 or
            authority.get("structural_registry_ref") != REGISTRY_REF or
            authority.get("structural_registry_sha256") != REGISTRY_SHA256 or
            authority.get("development_acceptance_ref") != DEVELOPMENT_ACCEPTANCE_REF or
            authority.get("development_capture_plan_ref") != DEVELOPMENT_PLAN_REF or
            authority.get("development_capture_plan_sha256") != DEVELOPMENT_PLAN_SHA256 or
            authority.get("development_capture_sha256") != DEVELOPMENT_SHA256 or
            authority.get("replacement_acceptance_ref") != REPLACEMENT_ACCEPTANCE_REF or
            authority.get("replacement_capture_plan_ref") != REPLACEMENT_PLAN_REF or
            authority.get("replacement_capture_plan_sha256") != REPLACEMENT_PLAN_SHA256 or
            authority.get("replacement_capture_sha256") != REPLACEMENT_SHA256):
        raise ValueError("freeze authority does not match accepted evidence")
    expected_scope = {
        "resolution": "M5",
        "interval": {
            "start_utc": "2026-06-15T00:00:00Z",
            "end_utc": "2026-09-13T23:59:59Z",
        },
        "protected_forward_start_utc": "2026-09-17T12:02:58Z",
        "representative_count": 41,
        "structural_coverage_only": True,
        "structural_representatives_are_economic_equivalents": False,
    }
    scope = freeze.get("scope", {})
    if any(scope.get(key) != value for key, value in expected_scope.items()):
        raise ValueError("freeze scope mismatch")
    if scope.get("registry_ref") != REGISTRY_REF:
        raise ValueError("freeze registry reference mismatch")
    expected_data = {
        "development_zip_filename": "MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip",
        "replacement_zip_filename": "MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip",
        "replacement_symbol_ids": [7427, 5352, 2924],
        "each_representative_processed_once": True,
        "no_new_market_data_requested": True,
    }
    if freeze.get("data") != expected_data:
        raise ValueError("freeze replacement capture scope mismatch")
    expected_context_law = {
        "true_range": "MAX(HIGH-LOW,ABS(HIGH-PREVIOUS_CLOSE),ABS(LOW-PREVIOUS_CLOSE))",
        "volatility": "ATR is the arithmetic mean of 14 true ranges; classify bar t from ATR(t-1) ranked against ATR(t-49) through ATR(t-2).",
        "activity": "Classify bar t from tick_volume(t-1) ranked against tick_volume(t-49) through tick_volume(t-2).",
        "rank": "COUNT(reference<=current)/48; ranks <=0.20 are LOW, >=0.80 are HIGH, and the middle is unclassified.",
        "session_overlap_proxy": "UTC event/bar hour 13 through 15 is OVERLAP; all other hours are NON_OVERLAP. This is a proxy only, not a claim about observed broker session schedules.",
        "continuity": "No fill, interpolation, or resampling. A timestamp delta other than exactly 300 seconds begins a new segment and context windows restart.",
        "duplicates": "Collapse identical timestamp rows only when OHLC and tick volume match; conflicting duplicates fail closed.",
    }
    if freeze.get("context_law") != expected_context_law:
        raise ValueError("freeze context feature law mismatch")
    expected_audit_law = {
        "report": [
            "Observed and context-classified rows, explicit unclassified warmup/middle-state rows, exact common timestamps, and timestamp gaps.",
            "Eight context-state counts, UTC date clusters, contiguous context-spell clusters, and serial-dependence-adjusted date effective sample sizes.",
            "Session-overlap proxy coverage, never presented as observed broker schedule truth.",
            "Pooled sensitivity only within the same broker coverage bucket, session-region signature, and weekend-capability tuple; equal symbol weight within UTC date."
        ],
        "effective_sample_size": "For daily state-prevalence series, estimate calendar-day autocorrelation through lag 30, stop at the first non-positive lag, and calculate n/(1+2*sum(positive autocorrelations)), bounded to [1,n]. Missing calendar dates are not imputed and contribute no autocorrelation pair.",
        "detectable_effect_sensitivity": "Report the normal-approximation one-sample standardized mean shift (z_0.975+z_0.80)/sqrt(n_eff), using 2.8016 in the numerator. Planning sensitivity only; no tests, outcomes, or inferential claims.",
        "pooled_units_are_descriptive_only": True,
    }
    if freeze.get("audit_law") != expected_audit_law:
        raise ValueError("freeze audit law mismatch")
    if freeze.get("accounting_effect") != {
        "economic_outcomes_opened": 0,
        "v2_attempts_consumed": 0,
        "search_budget_change": 0,
    }:
        raise ValueError("freeze accounting boundary violated")
    prohibitions = freeze.get("prohibitions", {})
    expected_prohibitions = {
        "strategy_events_computed": False,
        "strategy_returns_or_pnl_computed": False,
        "prior_epoch29_epoch33_epoch34_diagnostics_retested": False,
        "independent_confirmation_claimed": False,
        "internal_development_data_is_independent_confirmation": False,
        "economic_promotion_authorized": False,
        "candidate_identity_created": False,
        "protected_forward_opened": False,
        "live_orders_authorized": False,
    }
    if prohibitions != expected_prohibitions:
        raise ValueError("freeze prohibition boundary violated")
    if sha256_file(Path(registry_path)) != REGISTRY_SHA256:
        raise ValueError("structural registry hash mismatch")
    root = Path(registry_path).parents[1]
    proposal = root / PROPOSAL_REF
    if sha256_file(proposal) != PROPOSAL_SHA256:
        raise ValueError("accepted proposal file-byte hash mismatch")
    if sha256_file(root / DEVELOPMENT_PLAN_REF) != DEVELOPMENT_PLAN_SHA256:
        raise ValueError("accepted development capture plan hash mismatch")
    if sha256_file(root / REPLACEMENT_PLAN_REF) != REPLACEMENT_PLAN_SHA256:
        raise ValueError("accepted replacement capture plan hash mismatch")
    development_acceptance = json.loads((root / DEVELOPMENT_ACCEPTANCE_REF).read_text(encoding="utf-8"))
    if (development_acceptance.get("status") != "ACCEPTED_COMPLETE_NON_ECONOMIC_DEVELOPMENT_CAPTURE" or
            development_acceptance.get("source", {}).get("zip_sha256") != DEVELOPMENT_SHA256 or
            development_acceptance.get("source", {}).get("plan_sha256") != DEVELOPMENT_PLAN_SHA256 or
            development_acceptance.get("interval", {}).get("resolution") != "M5" or
            development_acceptance.get("interval", {}).get("start_utc") != "2026-06-15T00:00:00Z" or
            development_acceptance.get("interval", {}).get("end_utc") != "2026-09-13T23:59:59Z" or
            development_acceptance.get("validation", {}).get("series_complete") !=
            development_acceptance.get("validation", {}).get("series_planned") or
            development_acceptance.get("validation", {}).get("protected_forward_rows") != 0 or
            development_acceptance.get("safety", {}).get("protected_evidence_opened") is not False or
            development_acceptance.get("safety", {}).get("economic_outcomes_opened") != 0 or
            development_acceptance.get("safety", {}).get("v2_attempts_consumed") != 0):
        raise ValueError("accepted development capture scope or completion mismatch")
    replacement_acceptance = json.loads((root / REPLACEMENT_ACCEPTANCE_REF).read_text(encoding="utf-8"))
    replacement_scope = replacement_acceptance.get("frozen_scope_validation", {})
    replacement_safety = replacement_acceptance.get("canonicalization_repair", {})
    if (replacement_acceptance.get("status") !=
            "ACCEPTED_AFTER_DETERMINISTIC_CANONICALIZATION_OF_IDENTICAL_DUPLICATES" or
            replacement_acceptance.get("source_plan_sha256") != REPLACEMENT_PLAN_SHA256 or
            replacement_acceptance.get("capture_provenance", {}).get("returned_transport_zip_sha256") !=
            REPLACEMENT_SHA256 or
            replacement_scope.get("exact_symbol_ids") != [7427, 5352, 2924] or
            replacement_scope.get("resolution") != "M5" or
            replacement_scope.get("requested_interval") != {
                "start_utc": "2026-06-15T00:00:00Z",
                "end_utc": "2026-09-13T23:59:59Z",
            } or replacement_safety.get("recapture_required") is not False or
            replacement_safety.get("protected_forward_rows") != 0 or
            replacement_acceptance.get("safety", {}).get("protected_evidence_opened") is not False or
            replacement_acceptance.get("accounting_effect", {}).get("economic_outcomes") != 0 or
            replacement_acceptance.get("accounting_effect", {}).get("v2_attempts") != 0):
        raise ValueError("accepted replacement capture scope or safety mismatch")
    if sha256_file(Path(development_zip)) != DEVELOPMENT_SHA256:
        raise ValueError("accepted development capture hash mismatch")
    if sha256_file(Path(replacement_zip)) != REPLACEMENT_SHA256:
        raise ValueError("accepted replacement capture hash mismatch")
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    representatives = registry.get("representatives")
    if not isinstance(representatives, list) or len(representatives) != 41:
        raise ValueError("expected the complete 41-representative structural panel")
    frozen_ids = freeze.get("scope", {}).get("symbol_ids")
    registry_ids = [int(item["symbol_id"]) for item in representatives]
    if (frozen_ids != registry_ids or len(set(registry_ids)) != len(registry_ids) or
            len({item["broker_symbol"] for item in representatives}) != len(representatives)):
        raise ValueError("freeze and current accepted representative scope differ")
    return representatives


def evaluate(freeze: dict[str, Any], registry_path: Path, development_zip: Path,
             replacement_zip: Path) -> dict[str, Any]:
    representatives = validate_inputs(freeze, registry_path, development_zip, replacement_zip)
    replacement_ids = set(freeze["data"]["replacement_symbol_ids"])
    by_symbol: dict[str, dict[str, Any]] = {}
    timestamp_sets: dict[str, set[datetime]] = {}
    pooled_members: dict[tuple[str, str, bool], list[tuple[str, list[dict[str, Any]]]]] = defaultdict(list)
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for representative in representatives:
            symbol = representative["broker_symbol"]
            symbol_id = int(representative["symbol_id"])
            archive = replacement if symbol_id in replacement_ids else development
            rows = _archive_series(archive, representative, symbol_id in replacement_ids)
            report = audit_symbol(rows)
            by_symbol[symbol] = {"symbol_id": symbol_id, **report}
            timestamp_sets[symbol] = {row["timestamp"] for row in rows}
            pooled_members[_schedule_key(representative)].append((symbol, rows))
    common_timestamps = set.intersection(*timestamp_sets.values()) if timestamp_sets else set()
    pooled = []
    for (coverage, regions, weekend), members in sorted(pooled_members.items()):
        if len(members) < 2:
            continue
        daily_by_state: dict[str, dict[date, list[float]]] = defaultdict(lambda: defaultdict(list))
        all_group_dates: set[date] = set()
        for _, rows in members:
            member_daily: dict[date, Counter[str]] = defaultdict(Counter)
            for segment in _segments(rows):
                for index, (row, (state, _)) in enumerate(zip(segment, _classify_segment(segment))):
                    if state is not None:
                        member_daily[row["timestamp"].date()][state] += 1
            for day, counts in member_daily.items():
                total = sum(counts.values())
                all_group_dates.add(day)
                for state in (
                    f"{vol}_{activity}_{session}"
                    for vol in ("LOW_VOL", "HIGH_VOL")
                    for activity in ("LOW_ACTIVITY", "HIGH_ACTIVITY")
                    for session in ("NON_OVERLAP", "OVERLAP")
                ):
                    daily_by_state[state][day].append(counts.get(state, 0) / total)
        state_reports = {}
        for state, date_values in sorted(daily_by_state.items()):
            equally_weighted_daily = {
                day: statistics.fmean(date_values.get(day, [0.0]))
                for day in all_group_dates
            }
            sample = _effective_n(equally_weighted_daily)
            state_reports[state] = {
                "observed_utc_date_clusters": sample["date_clusters"],
                "effective_date_clusters": sample["effective_n"],
                "positive_autocorrelation_lags": sample["positive_autocorrelation_lags"],
                "detectable_effect_sensitivity": _sensitivity(sample["effective_n"]),
            }
        pooled.append({
            "schedule_compatibility_key": {
                "coverage_bucket": coverage,
                "session_regions": regions,
                "weekend_capable": weekend,
            },
            "symbols": [symbol for symbol, _ in members],
            "symbol_count": len(members),
            "pooled_unit": "UTC_DATE_WITH_EQUAL_SYMBOL_WEIGHT; DEVELOPMENT_COVERAGE_ONLY",
            "states": state_reports,
        })
    return {
        "schema": "mxm.greenfield.regime-context-data-sufficiency-audit.v1",
        "status": "COMPLETE_NON_ECONOMIC_DATA_SUFFICIENCY_AUDIT",
        "implementation": {"version": VERSION},
        "evidence_epoch": 39,
        "freeze_ref": FREEZE_REF,
        "scope": {
            "representative_count": len(representatives),
            "resolution": "M5",
            "interval": {
                "start_utc": START_UTC.isoformat().replace("+00:00", "Z"),
                "end_utc": END_UTC.isoformat().replace("+00:00", "Z"),
            },
            "structural_representatives_are_economic_equivalents": False,
            "role": "STRUCTURAL_COVERAGE_ONLY",
        },
        "input_attestation": {
            "proposal_file_sha256": PROPOSAL_SHA256,
            "registry_sha256": sha256_file(registry_path),
            "development_acceptance_ref": DEVELOPMENT_ACCEPTANCE_REF,
            "development_plan_ref": DEVELOPMENT_PLAN_REF,
            "development_zip_sha256": sha256_file(development_zip),
            "replacement_acceptance_ref": REPLACEMENT_ACCEPTANCE_REF,
            "replacement_plan_ref": REPLACEMENT_PLAN_REF,
            "replacement_zip_sha256": sha256_file(replacement_zip),
            "protected_forward_rows_read": 0,
            "all_41_representatives_processed_exactly_once": len(by_symbol) == 41,
        },
        "cross_symbol_alignment": {
            "common_exact_utc_m5_timestamps": len(common_timestamps),
            "union_exact_utc_m5_timestamps": len(set.union(*timestamp_sets.values())) if timestamp_sets else 0,
            "missingness_policy": "OBSERVED_ROWS_ONLY; NO_EXPECTED_CALENDAR_FILL, FORWARD_FILL, OR RESAMPLING",
        },
        "schedule_overlap": {
            "definition": "UTC hour 13 through 15 overlap proxy inherited from the accepted Epoch33 context specification",
            "observed_broker_schedule_claim": False,
            "per_symbol_observation_counts": {
                symbol: {
                    "overlap_proxy": sum(
                        1 for timestamp in timestamp_sets[symbol]
                        if SESSION_OVERLAP_START_UTC <= timestamp.hour < SESSION_OVERLAP_END_UTC
                    ),
                    "outside_overlap_proxy": sum(
                        1 for timestamp in timestamp_sets[symbol]
                        if not SESSION_OVERLAP_START_UTC <= timestamp.hour < SESSION_OVERLAP_END_UTC
                    ),
                }
                for symbol in by_symbol
            },
        },
        "symbols": by_symbol,
        "schedule_compatible_pooled_units": pooled,
        "interpretation_boundary": {
            "descriptive_development_input_audit_only": True,
            "strategy_events_or_returns_computed": False,
            "prior_epoch29_epoch33_epoch34_diagnostics_retested": False,
            "independent_confirmation": False,
            "economic_promotion_authorized": False,
            "mechanism_family_closed": False,
            "candidate_identity_created": False,
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
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--development-zip", required=True)
    parser.add_argument("--replacement-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = evaluate(
        json.loads(Path(args.freeze).read_text(encoding="utf-8")),
        Path(args.registry),
        Path(args.development_zip),
        Path(args.replacement_zip),
    )
    result["freeze_sha256"] = sha256_file(Path(args.freeze))
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
