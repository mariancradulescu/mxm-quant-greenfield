"""Read-only adaptive cross-family triage for the accepted M5 development capture.

This module assesses chronology, coverage, cadence, and observable data surfaces.
It deliberately does not calculate returns, PnL, strategy outcomes, or promotion
statistics. The capture is an accepted external artifact, so validation is bound
to its acceptance hash and frozen plan rather than to a repository-local copy.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ACCEPTANCE_REL = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json"
PLAN_REL = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_PLAN_V1.json"
ACCEPTED_STATUS = "ACCEPTED_COMPLETE_NON_ECONOMIC_DEVELOPMENT_CAPTURE"
M5_SECONDS = 300
BREAKOUT_HISTORY_BARS = 12
FAMILIES = (
    ("TREND_MOMENTUM", "TIME_SERIES", ("ordered_ohlc", "sufficient_history")),
    ("MEAN_REVERSION", "TIME_SERIES", ("ordered_ohlc", "sufficient_history")),
    ("BREAKOUT_VOLATILITY_EXPANSION", "TIME_SERIES", ("ordered_ohlc", "sufficient_history")),
    ("CARRY_TERM_STRUCTURE", "RELATIVE_VALUE", ("term_structure_metadata",)),
    ("SEASONALITY_SESSION_TIME", "TIME_SERIES", ("ordered_timestamps", "sufficient_history")),
    ("RELATIVE_VALUE_COINTEGRATION", "RELATIVE_VALUE", ("multiple_symbols", "aligned_timestamps")),
    ("CROSS_SECTIONAL_RANKING", "CROSS_SECTIONAL", ("multiple_symbols", "aligned_timestamps")),
    ("CROSS_MARKET_LEAD_LAG", "CROSS_MARKET", ("multiple_symbols", "aligned_timestamps")),
    ("REGIME_CONTEXT_CONDITIONED", "TIME_SERIES", ("ordered_ohlc", "sufficient_history")),
    ("CAUSAL_ML_PREDICTIVE_OR_STATE_MODEL", "TIME_SERIES", ("ordered_ohlc", "sufficient_history")),
)

UNIVARIATE_FAMILIES = (
    "BREAKOUT_VOLATILITY_EXPANSION",
    "CAUSAL_ML_PREDICTIVE_OR_STATE_MODEL",
    "MEAN_REVERSION",
    "REGIME_CONTEXT_CONDITIONED",
    "SEASONALITY_SESSION_TIME",
    "TREND_MOMENTUM",
)


class TriageError(ValueError):
    """Raised when the accepted development artifact cannot be screened safely."""


def _read_gate_series(raw: bytes, start: datetime, end: datetime) -> dict[str, Any]:
    """Return availability-only diagnostics; no price transformation is performed."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    expected = ("time_utc", "open", "high", "low", "close", "tick_volume")
    if tuple(reader.fieldnames or ()) != expected:
        raise TriageError("univariate gate requires single-price OHLC and tick volume")
    timestamps: list[datetime] = []
    for row in reader:
        timestamp = _utc(str(row["time_utc"]))
        if not start <= timestamp <= end:
            raise TriageError("series contains a row outside the frozen interval")
        try:
            values = [float(row[key]) for key in expected[1:]]
        except (KeyError, TypeError, ValueError) as exc:
            raise TriageError("series contains a non-numeric OHLCV field") from exc
        if not all(value == value and abs(value) != float("inf") for value in values):
            raise TriageError("series contains a non-finite OHLCV field")
        if values[1] < max(values[0], values[3]) or values[2] > min(values[0], values[3]):
            raise TriageError("series contains an invalid OHLC invariant")
        timestamps.append(timestamp)
    if any(left >= right for left, right in zip(timestamps, timestamps[1:])):
        raise TriageError("series timestamps are not strictly increasing")
    gaps = [int((right - left).total_seconds()) for left, right in zip(timestamps, timestamps[1:])]
    observed = set(timestamps)
    expected_slots = (
        int((timestamps[-1] - timestamps[0]).total_seconds() // M5_SECONDS) + 1
        if timestamps else 0
    )
    return {
        "rows": len(timestamps),
        "first_utc": timestamps[0].isoformat().replace("+00:00", "Z") if timestamps else None,
        "last_utc": timestamps[-1].isoformat().replace("+00:00", "Z") if timestamps else None,
        "chronology_valid": True,
        "duplicate_timestamps": 0,
        "off_cadence_intervals": sum(gap % M5_SECONDS != 0 for gap in gaps),
        "missing_m5_slots_between_bounds": max(0, expected_slots - len(observed)),
        "largest_gap_seconds": max(gaps, default=0),
        "active_dates": len({timestamp.date().isoformat() for timestamp in timestamps}),
        "utc_hour_buckets": sorted({timestamp.hour for timestamp in timestamps}),
        "weekday_buckets": sorted({timestamp.weekday() for timestamp in timestamps}),
        "causal_observation_pairs": max(0, len(timestamps) - 1),
    }


def run_univariate_structural_gate(
    zip_path: str | Path,
    *,
    repository_root: str | Path = ".",
    accepted_sha256: str | None = None,
) -> dict[str, Any]:
    """Run the accepted 40-symbol structural gate without economic evaluation."""
    root = Path(repository_root)
    acceptance = _load_json(root, ACCEPTANCE_REL)
    plan = _load_json(root, PLAN_REL)
    if acceptance.get("status") != ACCEPTED_STATUS:
        raise TriageError("development capture acceptance is not complete")
    expected_sha = accepted_sha256 or str((acceptance.get("source") or {}).get("zip_sha256") or "")
    observed_sha = _sha256(Path(zip_path))
    if not expected_sha or observed_sha != expected_sha:
        raise TriageError("development ZIP hash does not match accepted capture")
    if plan.get("resolution") != "M5":
        raise TriageError("univariate gate requires M5 capture")
    interval = plan.get("interval") or {}
    start, end = _utc(str(interval["start_utc"])), _utc(str(interval["end_utc"]))
    symbols = {str(item["broker_symbol"]): item for item in plan.get("symbols") or []}
    if len(symbols) != 40:
        raise TriageError("univariate gate requires the exact accepted 40-symbol capture")
    with zipfile.ZipFile(zip_path) as archive:
        try:
            manifest = json.loads(archive.read("capture_manifest.json"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise TriageError("capture manifest is missing or invalid") from exc
        if manifest.get("plan_sha256") != plan.get("plan_sha256"):
            raise TriageError("capture manifest plan hash mismatch")
        if manifest.get("economic_outcomes_opened") != 0 or manifest.get("v2_attempts_consumed") != 0:
            raise TriageError("capture manifest is economically contaminated")
        manifest_rows = _manifest_series(manifest)
        if set(manifest_rows) != set(symbols):
            raise TriageError("capture series set does not match frozen development plan")
        diagnostics = {
            symbol: _read_gate_series(archive.read(str(item["file"])), start, end)
            for symbol, item in sorted(manifest_rows.items())
        }

    family_requirements = {
        family: (
            ("ordered_ohlc", "minimum_history", "causal_observation_pairs")
            if family != "SEASONALITY_SESSION_TIME"
            else ("ordered_timestamps", "minimum_history", "session_coverage")
        )
        for family in UNIVARIATE_FAMILIES
    }
    capabilities = {
        "ordered_ohlc": any(row["rows"] > 0 for row in diagnostics.values()),
        "ordered_timestamps": any(row["rows"] > 0 for row in diagnostics.values()),
        "minimum_history": all(row["rows"] >= 288 for row in diagnostics.values()),
        "causal_observation_pairs": all(row["causal_observation_pairs"] > 0 for row in diagnostics.values()),
        "session_coverage": all(bool(row["utc_hour_buckets"]) for row in diagnostics.values()),
    }
    matrix = []
    for family in UNIVARIATE_FAMILIES:
        requirements = family_requirements[family]
        missing = [item for item in requirements if not capabilities[item]]
        event_availability = {
            symbol: {
                "available": row["causal_observation_pairs"] > 0,
                "observed_event_count": row["causal_observation_pairs"],
            }
            for symbol, row in diagnostics.items()
        }
        matrix.append({
            "family": family,
            "requirements": list(requirements),
            "satisfied_requirements": [item for item in requirements if item not in missing],
            "missing_prerequisites": missing,
            "event_availability": {
                "eligible_symbol_count": sum(
                    item["available"] for item in event_availability.values()
                ),
                "per_symbol": event_availability,
            },
            "data_sufficiency": "SUFFICIENT" if not missing else "INSUFFICIENT",
            "economic_evaluation": "NOT_PERFORMED",
        })
    eligible = [row["family"] for row in matrix if not row["missing_prerequisites"]]
    return {
        "schema": "mxm.greenfield.broker-native-univariate-structural-gate.v1",
        "status": "COMPLETE_NON_ECONOMIC_UNIVARIATE_STRUCTURAL_GATE",
        "source": {
            "acceptance_ref": ACCEPTANCE_REL,
            "plan_ref": PLAN_REL,
            "zip_sha256": observed_sha,
            "resolution": "M5",
            "symbols_screened": len(diagnostics),
        },
        "scope": {
            "families": list(UNIVARIATE_FAMILIES),
            "rows_read": sum(row["rows"] for row in diagnostics.values()),
            "per_symbol": diagnostics,
            "capabilities": capabilities,
        },
        "family_prerequisite_matrix": matrix,
        "prospective_recommendation": {
            "kind": "SMALLEST_MECHANISM_SPECIFIC_OUTER",
            "eligible_families": eligible,
            "additional_authenticated_data_required": False,
            "selection_basis": "non-economic prerequisite coverage and observed chronology/session availability",
            "economic_identity_authorized": False,
        },
        "economic_effect": {
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "returns_or_pnl_computed": False,
            "promotion_claimed": False,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "parameter_mining": False,
        },
    }


def _breakout_event_diagnostics(
    raw: bytes, start: datetime, end: datetime
) -> dict[str, Any]:
    """Evaluate one fixed causal breakout/volatility-expansion event law.

    An event is admitted at bar t only when the immediately preceding
    BREAKOUT_HISTORY_BARS bars are observed at the expected M5 cadence and
    bar t breaks their high or low while its range exceeds their mean range.
    This is an availability screen only; it does not assign direction or
    evaluate a subsequent response.
    """
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    expected = ("time_utc", "open", "high", "low", "close", "tick_volume")
    if tuple(reader.fieldnames or ()) != expected:
        raise TriageError("breakout gate requires single-price OHLC and tick volume")
    bars: list[tuple[datetime, float, float, float, float]] = []
    for row in reader:
        timestamp = _utc(str(row["time_utc"]))
        if not start <= timestamp <= end:
            raise TriageError("series contains a row outside the frozen interval")
        try:
            open_, high, low, close = (
                float(row[key]) for key in ("open", "high", "low", "close")
            )
            float(row["tick_volume"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TriageError("series contains a non-numeric OHLCV field") from exc
        values = (open_, high, low, close)
        if not all(value == value and abs(value) != float("inf") for value in values):
            raise TriageError("series contains a non-finite OHLC field")
        if high < max(open_, close) or low > min(open_, close) or low > high:
            raise TriageError("series contains an invalid OHLC invariant")
        bars.append((timestamp, open_, high, low, close))
    if any(left >= right for left, right in zip((bar[0] for bar in bars), (bar[0] for bar in bars[1:]))):
        raise TriageError("series timestamps are not strictly increasing")

    missing_history = 0
    eligible_bars = 0
    events = 0
    event_timestamps: list[datetime] = []
    for index in range(BREAKOUT_HISTORY_BARS, len(bars)):
        history = bars[index - BREAKOUT_HISTORY_BARS:index]
        current = bars[index]
        if any(
            (right[0] - left[0]).total_seconds() != M5_SECONDS
            for left, right in zip(history, history[1:])
        ) or (current[0] - history[-1][0]).total_seconds() != M5_SECONDS:
            missing_history += 1
            continue
        eligible_bars += 1
        prior_high = max(bar[2] for bar in history)
        prior_low = min(bar[3] for bar in history)
        prior_mean_range = sum(bar[2] - bar[3] for bar in history) / len(history)
        current_range = current[2] - current[3]
        if (current[2] > prior_high or current[3] < prior_low) and current_range > prior_mean_range:
            events += 1
            event_timestamps.append(current[0])
    spacings = [
        int((right - left).total_seconds() // M5_SECONDS)
        for left, right in zip(event_timestamps, event_timestamps[1:])
    ]
    return {
        "rows": len(bars),
        "first_utc": bars[0][0].isoformat().replace("+00:00", "Z") if bars else None,
        "last_utc": bars[-1][0].isoformat().replace("+00:00", "Z") if bars else None,
        "minimum_history_bars": BREAKOUT_HISTORY_BARS,
        "eligible_bars": eligible_bars,
        "missing_history_exclusions": missing_history,
        "event_count": events,
        "event_timestamps_utc": [
            timestamp.isoformat().replace("+00:00", "Z") for timestamp in event_timestamps
        ],
        "event_spacing_m5": spacings,
        "event_clustering": {
            "adjacent_event_pairs": sum(spacing == 1 for spacing in spacings),
            "minimum_spacing_m5": min(spacings, default=None),
            "maximum_spacing_m5": max(spacings, default=None),
        },
        "chronology_valid": True,
        "economic_evaluation": "NOT_PERFORMED",
    }


def run_breakout_event_availability_gate(
    zip_path: str | Path,
    *,
    repository_root: str | Path = ".",
    accepted_sha256: str | None = None,
) -> dict[str, Any]:
    """Run the accepted 40-symbol causal breakout availability gate."""
    root = Path(repository_root)
    acceptance = _load_json(root, ACCEPTANCE_REL)
    plan = _load_json(root, PLAN_REL)
    if acceptance.get("status") != ACCEPTED_STATUS:
        raise TriageError("development capture acceptance is not complete")
    expected_sha = accepted_sha256 or str((acceptance.get("source") or {}).get("zip_sha256") or "")
    observed_sha = _sha256(Path(zip_path))
    if not expected_sha or observed_sha != expected_sha:
        raise TriageError("development ZIP hash does not match accepted capture")
    if plan.get("resolution") != "M5":
        raise TriageError("breakout gate requires M5 capture")
    interval = plan.get("interval") or {}
    start, end = _utc(str(interval["start_utc"])), _utc(str(interval["end_utc"]))
    symbols = {str(item["broker_symbol"]): item for item in plan.get("symbols") or []}
    if len(symbols) != 40:
        raise TriageError("breakout gate requires the exact accepted 40-symbol capture")
    with zipfile.ZipFile(zip_path) as archive:
        try:
            manifest = json.loads(archive.read("capture_manifest.json"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise TriageError("capture manifest is missing or invalid") from exc
        if manifest.get("plan_sha256") != plan.get("plan_sha256"):
            raise TriageError("capture manifest plan hash mismatch")
        if manifest.get("economic_outcomes_opened") != 0 or manifest.get("v2_attempts_consumed") != 0:
            raise TriageError("capture manifest is economically contaminated")
        manifest_rows = _manifest_series(manifest)
        if set(manifest_rows) != set(symbols):
            raise TriageError("capture series set does not match frozen development plan")
        diagnostics = {
            symbol: _breakout_event_diagnostics(archive.read(str(item["file"])), start, end)
            for symbol, item in sorted(manifest_rows.items())
        }
    eligible = [
        symbol for symbol, value in diagnostics.items() if value["event_count"] > 0
    ]
    return {
        "schema": "mxm.greenfield.broker-native-breakout-event-availability-gate.v1",
        "status": "COMPLETE_NON_ECONOMIC_BREAKOUT_EVENT_AVAILABILITY_GATE",
        "source": {
            "acceptance_ref": ACCEPTANCE_REL,
            "plan_ref": PLAN_REL,
            "zip_sha256": observed_sha,
            "resolution": "M5",
            "symbols_screened": len(diagnostics),
        },
        "scope": {
            "family": "BREAKOUT_VOLATILITY_EXPANSION",
            "event_law": {
                "history_bars": BREAKOUT_HISTORY_BARS,
                "breakout": "current high above prior rolling high or current low below prior rolling low",
                "volatility_expansion": "current high-low range above prior rolling mean range",
                "causal_observation_rule": "all prior history bars and current bar must be observed at consecutive M5 cadence",
            },
            "rows_read": sum(value["rows"] for value in diagnostics.values()),
            "per_symbol": diagnostics,
        },
        "prospective_recommendation": {
            "kind": "PROSPECTIVE_MECHANISM_SPECIFICATION_IF_EVENT_AVAILABILITY_SUFFICIENT",
            "eligible_symbol_count": len(eligible),
            "eligible_symbols": eligible,
            "additional_authenticated_data_required": False,
            "economic_identity_authorized": False,
            "family_exhaustion_claimed": False,
        },
        "economic_effect": {
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "returns_or_pnl_computed": False,
            "promotion_claimed": False,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "parameter_mining": False,
        },
    }


def select_primary_family(
    triage: Mapping[str, Any],
    preferred_family_order: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    """Select one executable structural family without evaluating economics.

    The preference order is supplied by the accepted AI decision rather than
    inferred from returns or from a finite next-action dispatch table.
    """
    if triage.get("status") != "COMPLETE_NON_ECONOMIC_ADAPTIVE_TRIAGE":
        raise TriageError("primary-family selection requires complete adaptive triage")
    selection = triage.get("adaptive_selection")
    ranking = triage.get("family_ranking")
    if not isinstance(selection, Mapping) or not isinstance(ranking, list):
        raise TriageError("adaptive triage is missing family selection diagnostics")
    selected = selection.get("selected_families")
    if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
        raise TriageError("adaptive triage has malformed selected families")
    order = tuple(preferred_family_order)
    if not order or len(set(order)) != len(order):
        raise TriageError("preferred family order must be non-empty and unique")
    ranking_by_family: dict[str, Mapping[str, Any]] = {}
    for row in ranking:
        if not isinstance(row, Mapping) or not isinstance(row.get("family"), str):
            raise TriageError("adaptive triage has malformed family ranking")
        ranking_by_family[row["family"]] = row
    for family in order:
        if family not in selected:
            continue
        row = ranking_by_family.get(family)
        if row is None or row.get("missing_prerequisites"):
            continue
        return {
            "primary_family": family,
            "selection_basis": "accepted_preference_order_over_non_economic_prerequisite_sufficiency",
            "candidate_families": list(selected),
            "economic_evaluation": "NOT_PERFORMED",
            "mechanism_family_closure_claimed": False,
        }
    raise TriageError("no preferred family satisfies the accepted non-economic prerequisites")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TriageError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise TriageError("timestamps must include UTC offset")
    return parsed.astimezone(timezone.utc)


def _load_json(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TriageError(f"cannot load authority: {relative}") from exc
    if not isinstance(value, dict):
        raise TriageError(f"authority is not an object: {relative}")
    return value


def _manifest_series(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in manifest.get("series") or []:
        if not isinstance(item, Mapping):
            raise TriageError("manifest contains a malformed series")
        symbol = str(item.get("broker_symbol") or "")
        filename = str(item.get("file") or "")
        if not symbol or not filename or symbol in result:
            raise TriageError("manifest contains duplicate or incomplete series")
        result[symbol] = item
    return result


def _series_structure(raw: bytes, start: datetime, end: datetime) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    if tuple(reader.fieldnames or ()) != (
        "time_utc", "open", "high", "low", "close", "tick_volume"
    ):
        raise TriageError("development series must contain single-price OHLC and tick volume")
    timestamps: list[datetime] = []
    rows = 0
    for row in reader:
        timestamp = _utc(str(row["time_utc"]))
        if not start <= timestamp <= end:
            raise TriageError("series contains a row outside the frozen interval")
        try:
            values = [float(row[key]) for key in ("open", "high", "low", "close", "tick_volume")]
        except (KeyError, TypeError, ValueError) as exc:
            raise TriageError("series contains a non-numeric OHLCV field") from exc
        if not all(value == value and abs(value) != float("inf") for value in values):
            raise TriageError("series contains a non-finite OHLCV field")
        if values[1] < max(values[0], values[3]) or values[2] > min(values[0], values[3]):
            raise TriageError("series contains an invalid OHLC invariant")
        timestamps.append(timestamp)
        rows += 1
    if any(left >= right for left, right in zip(timestamps, timestamps[1:])):
        raise TriageError("series timestamps are not strictly increasing")
    gaps = [int((right - left).total_seconds()) for left, right in zip(timestamps, timestamps[1:])]
    return {
        "rows": rows,
        "first_utc": timestamps[0].isoformat().replace("+00:00", "Z") if timestamps else None,
        "last_utc": timestamps[-1].isoformat().replace("+00:00", "Z") if timestamps else None,
        "duplicate_timestamps": 0,
        "off_cadence_intervals": sum(gap != M5_SECONDS for gap in gaps),
        "largest_gap_seconds": max(gaps, default=0),
        "utc_hour_buckets": sorted({timestamp.hour for timestamp in timestamps}),
    }


def run_triage(
    zip_path: str | Path,
    *,
    repository_root: str | Path = ".",
    accepted_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate and triage one exact accepted development capture."""
    root = Path(repository_root)
    acceptance = _load_json(root, ACCEPTANCE_REL)
    plan = _load_json(root, PLAN_REL)
    if acceptance.get("status") != ACCEPTED_STATUS:
        raise TriageError("development capture acceptance is not complete")
    expected_sha = accepted_sha256 or str((acceptance.get("source") or {}).get("zip_sha256") or "")
    observed_sha = _sha256(Path(zip_path))
    if not expected_sha or observed_sha != expected_sha:
        raise TriageError("development ZIP hash does not match accepted capture")
    interval = plan.get("interval") or {}
    start, end = _utc(str(interval["start_utc"])), _utc(str(interval["end_utc"]))
    symbols = {str(item["broker_symbol"]): item for item in plan.get("symbols") or []}
    if not symbols:
        raise TriageError("frozen development plan has no symbols")
    with zipfile.ZipFile(zip_path) as archive:
        try:
            manifest = json.loads(archive.read("capture_manifest.json"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise TriageError("capture manifest is missing or invalid") from exc
        if manifest.get("plan_sha256") != plan.get("plan_sha256"):
            raise TriageError("capture manifest plan hash mismatch")
        if manifest.get("economic_outcomes_opened") != 0 or manifest.get("v2_attempts_consumed") != 0:
            raise TriageError("capture manifest is economically contaminated")
        manifest_rows = _manifest_series(manifest)
        if set(manifest_rows) != set(symbols):
            raise TriageError("capture series set does not match frozen development plan")
        diagnostics: dict[str, dict[str, Any]] = {}
        for symbol, item in sorted(manifest_rows.items()):
            diagnostics[symbol] = _series_structure(archive.read(str(item["file"])), start, end)

    complete = [symbol for symbol, value in diagnostics.items() if value["rows"] > 0]
    aligned = len(complete) >= 2 and all(
        diagnostics[symbol]["first_utc"] == diagnostics[complete[0]]["first_utc"]
        and diagnostics[symbol]["last_utc"] == diagnostics[complete[0]]["last_utc"]
        for symbol in complete
    )
    capabilities = {
        "ordered_ohlc": bool(complete),
        "ordered_timestamps": bool(complete),
        "sufficient_history": bool(complete) and all(
            diagnostics[symbol]["rows"] >= 288 for symbol in complete
        ),
        "multiple_symbols": len(complete) >= 2,
        "aligned_timestamps": aligned,
        "term_structure_metadata": False,
    }
    ranked = []
    for family, structure, requirements in FAMILIES:
        satisfied = [requirement for requirement in requirements if capabilities[requirement]]
        missing = [requirement for requirement in requirements if not capabilities[requirement]]
        ranked.append({
            "family": family,
            "structure": structure,
            "requirements": list(requirements),
            "satisfied_requirements": satisfied,
            "missing_prerequisites": missing,
            "data_sufficiency": "SUFFICIENT_FOR_NON_ECONOMIC_TRIAGE" if not missing else "INSUFFICIENT",
            "economic_evaluation": "NOT_PERFORMED",
        })
    ranked.sort(key=lambda row: (-len(row["satisfied_requirements"]), row["family"]))
    selected = [row["family"] for row in ranked if not row["missing_prerequisites"]]
    return {
        "schema": "mxm.greenfield.broker-native-adaptive-cross-family-triage.v1",
        "status": "COMPLETE_NON_ECONOMIC_ADAPTIVE_TRIAGE",
        "source": {
            "acceptance_ref": ACCEPTANCE_REL,
            "plan_ref": PLAN_REL,
            "zip_sha256": observed_sha,
            "resolution": "M5",
            "symbols_screened": len(diagnostics),
        },
        "scope": {
            "rows_read": sum(value["rows"] for value in diagnostics.values()),
            "series_with_rows": len(complete),
            "aligned_series": aligned,
            "capabilities": capabilities,
            "per_symbol": diagnostics,
        },
        "family_ranking": ranked,
        "adaptive_selection": {
            "selected_families": selected,
            "selection_basis": "causal ordering, history sufficiency, cross-symbol alignment, and declared data prerequisites",
            "fixed_family_or_parameter_grid": False,
            "new_market_data_required": False,
        },
        "economic_effect": {
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "pnl_or_returns_computed": False,
            "promotion_claimed": False,
        },
    }
