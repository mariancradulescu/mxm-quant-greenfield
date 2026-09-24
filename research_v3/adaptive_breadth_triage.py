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


class TriageError(ValueError):
    """Raised when the accepted development artifact cannot be screened safely."""


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
