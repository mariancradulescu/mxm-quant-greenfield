"""Outcome-blind MEAN_REVERSION Stage-1 scan on accepted Epoch46 Wave01 data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any

from research_v3.regime_context_data_sufficiency_audit import _effective_n

VERSION = "MXM_EPOCH47_MEAN_REVERSION_WAVE01_COARSE_PARAMETER_REGION_SCAN_V1"
FREEZE_REF = "research_v3/EPOCH47_MEAN_REVERSION_WAVE01_COARSE_PARAMETER_REGION_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_ba723215ff1cce105447e4c95e4443e4.json"
PROPOSAL_SHA256 = "6f889d8f2a49412621a00f6194f23b830b02ce5be36c234d1010291db28d7a22"
PROPOSAL_HASH = "453d0ddb418b21ae72107222f5219aea323161e7f37e4bdb65d7f963184f2edc"
CAPTURE_ACCEPTANCE_REF = "evidence/EPOCH46_OUTCOME_BLIND_M5_WAVE_01_CAPTURE_ACCEPTANCE_V1.json"
CAPTURE_ACCEPTANCE_SHA256 = "8e51c69485332dc70ea9ab6985d8e33866c8733ddee77e3f339ecc82adfb7128"
DATA_SUFFICIENCY_REF = "evidence/EPOCH46_OUTCOME_BLIND_M5_WAVE_01_DATA_SUFFICIENCY_V1.json"
DATA_SUFFICIENCY_SHA256 = "9059e19f380e5b993d21b87edf88ddb66dc667377e16164acdd33a43e8183666"
PLAN_REF = "data/EPOCH46_OUTCOME_BLIND_M5_ACQUISITION_WAVE_01_PLAN_V1.json"
PLAN_SHA256 = "70706ee9c04fb262cf38be8c6cbd0fd7450c91e6d870e5c5f80c9301724ae247"
CAPTURE_ZIP_SHA256 = "bfdfcba4e70c699fa3719e15e01ed4f7a4542d7ed0e7439fd836133ab80d1ac1"
CAPTURE_PAYLOAD_SHA256 = "0305ca9d194300d28efde5b21aced13557e986d8d5476e3202ba66c8476774e2"
RESULT_REF = "evidence/EPOCH47_MEAN_REVERSION_WAVE01_COARSE_PARAMETER_REGION_SCAN_V1.json"
LOOKBACKS = (12, 24, 48, 96)
THRESHOLDS = (1.0, 1.5, 2.0)
EFFECT_SCENARIOS = (0.5, 0.3, 0.2)
POWER_ALPHA = 0.05 / 36
TARGET_POWER = 0.8
M5_SECONDS = 300
START_UTC = datetime(2025, 12, 15, tzinfo=timezone.utc)
END_UTC = datetime(2026, 3, 15, 23, 59, 59, tzinfo=timezone.utc)
ZERO_HISTORY_SYMBOL = "AMD.US-PERP"


class ScanError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_plan_sha256(plan: dict[str, Any]) -> str:
    canonical = {key: value for key, value in plan.items() if key != "plan_sha256"}
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _sha256(encoded)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScanError(f"required authority is missing or unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ScanError(f"required authority must be a JSON object: {path}")
    return value


def _require_authority_hash(root: Path, ref: str, expected: str) -> dict[str, Any]:
    path = root / ref
    if not path.is_file() or _file_sha256(path) != expected:
        raise ScanError(f"accepted authority file-byte hash mismatch: {ref}")
    return _read_json(path)


def validate_freeze(freeze: dict[str, Any], root: Path) -> tuple[dict[str, Any], ...]:
    if (
        freeze.get("schema") != "mxm.greenfield.epoch47-mean-reversion-wave01-coarse-region-freeze.v1"
        or freeze.get("status") != "PROSPECTIVELY_FROZEN_NON_ECONOMIC_STAGE1_COARSE_PARAMETER_REGION_SCAN"
        or freeze.get("evidence_epoch") != 45
        or freeze.get("family") != "MEAN_REVERSION"
    ):
        raise ScanError("unsupported or unfrozen Epoch47 scan authority")

    authority = freeze.get("authority") or {}
    expected_authority = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "accepted_proposal_file_sha256": PROPOSAL_SHA256,
        "accepted_proposal_hash": PROPOSAL_HASH,
        "accepted_proposal_id": "AI_reason_ba723215ff1cce105447e4c95e4443e4_EPOCH47_MEAN_REVERSION_WAVE01_COARSE_REGION_FREEZE",
        "capture_acceptance_ref": CAPTURE_ACCEPTANCE_REF,
        "capture_acceptance_file_sha256": CAPTURE_ACCEPTANCE_SHA256,
        "data_sufficiency_ref": DATA_SUFFICIENCY_REF,
        "data_sufficiency_file_sha256": DATA_SUFFICIENCY_SHA256,
        "capture_plan_ref": PLAN_REF,
        "capture_plan_sha256": PLAN_SHA256,
        "accepted_capture_outer_zip_sha256": CAPTURE_ZIP_SHA256,
        "accepted_capture_canonical_payload_sha256": CAPTURE_PAYLOAD_SHA256,
    }
    if any(authority.get(key) != value for key, value in expected_authority.items()):
        raise ScanError("freeze does not bind the exact accepted proposal and capture authorities")
    if freeze.get("parameter_grid") != {
        "absolute_standardized_deviation_thresholds": list(THRESHOLDS),
        "lookback_bars": list(LOOKBACKS),
        "cell_count": len(THRESHOLDS) * len(LOOKBACKS),
        "record_every_symbol_cell": True,
        "winner_only_logging": False,
        "grid_source_ref": DATA_SUFFICIENCY_REF,
    }:
        raise ScanError("frozen coarse parameter grid differs from accepted data-sufficiency authority")
    expected_event_law = {
        "resolution": "M5",
        "window": "For each exact-contiguous lookback window ending at a completed bar, calculate z=(close_t - arithmetic_mean(window_closes))/population_standard_deviation(window_closes).",
        "eligibility": "A window is eligible only when all lookback M5 bars are present, timestamps are exactly 300 seconds apart, prices are finite and positive, and population standard deviation is positive.",
        "event": "Count the first threshold crossing from the neutral band as one reversal excursion; do not count further bars while z remains in that tail. Returning inside the threshold rearms the next excursion. A direct crossing into the opposite tail starts a new excursion.",
        "availability_denominator": "All eligible nonzero-scale exact-contiguous windows for that symbol and cell.",
        "date_cluster": "UTC calendar date of the first threshold-crossing bar; retain zero-event dates that contain eligible windows.",
        "missing_data": "Never fill, interpolate, resample, forward-fill, or bridge a timestamp gap; reset the excursion state at every gap.",
        "prohibited": [
            "post-event directional or return response",
            "strategy return or PnL",
            "candidate or winner selection",
            "protected-forward evidence",
        ],
    }
    expected_dependence = {
        "independence_unit": "UTC date clusters of outcome-blind reversal event counts",
        "effective_sample_size_method": "Initial-positive-sequence calendar-date autocorrelation adjustment; truncate at the first nonpositive lag, cap lag at 30 days, and bound effective_n to [1, date_clusters] when date_clusters is nonzero.",
        "standardized_effect_scenarios": [0.5, 0.3, 0.2],
        "target_power": 0.8,
        "familywise_alpha": 0.05,
        "power_hypothesis_count": 36,
        "power_alpha": "One-sided Bonferroni alpha=0.05/36, matching the accepted Wave01 data-sufficiency planning design.",
        "power_formula": "Normal approximation: Phi(effect*sqrt(effective_n)-Phi_inverse(1-alpha)); planning diagnostic only, not an observed response or inferential result.",
    }
    if freeze.get("event_law") != expected_event_law or freeze.get("dependence_and_power") != expected_dependence:
        raise ScanError("frozen event, dependence, or power law changed")

    proposal = _require_authority_hash(root, PROPOSAL_REF, PROPOSAL_SHA256)
    capture = _require_authority_hash(root, CAPTURE_ACCEPTANCE_REF, CAPTURE_ACCEPTANCE_SHA256)
    sufficiency = _require_authority_hash(root, DATA_SUFFICIENCY_REF, DATA_SUFFICIENCY_SHA256)
    plan = _read_json(root / PLAN_REF)
    decision = proposal.get("decision") or {}
    proposal_scope = (proposal.get("next_research_state") or {}).get("implementation_scope") or {}
    if (
        proposal.get("proposal_id") != expected_authority["accepted_proposal_id"]
        or proposal.get("proposal_hash") not in (None, expected_authority["accepted_proposal_hash"])
        or decision.get("selected_mechanism_family") != "MEAN_REVERSION"
        or decision.get("stage") != "PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1/STAGE_1_COARSE_MECHANISM_REGION_SCAN"
        or proposal_scope.get("next_action") != "IMPLEMENT_AND_RUN_MEAN_REVERSION_EPOCH47_WAVE01_COARSE_PARAMETER_REGION_SCAN"
        or capture.get("status") != "ACCEPTED_HASH_VERIFIED_OUTCOME_BLIND_DEVELOPMENT_CAPTURE_WITH_ONE_ZERO_HISTORY_IDENTITY"
        or sufficiency.get("status") != "SUFFICIENT_FOR_FRESH_EXPLORATORY_SYMBOL_MECHANISM_PARAMETER_REGION_DISCOVERY_NOT_CONFIRMATION"
        or plan.get("plan_sha256") != PLAN_SHA256
        or _canonical_plan_sha256(plan) != PLAN_SHA256
        or plan.get("resolution") != "M5"
        or capture.get("source_capture_bundle", {}).get("outer_zip_sha256") != CAPTURE_ZIP_SHA256
        or capture.get("source_capture_bundle", {}).get("canonical_payload_sha256") != CAPTURE_PAYLOAD_SHA256
        or capture.get("source_capture_bundle", {}).get("plan_sha256") != PLAN_SHA256
        or sufficiency.get("mean_reversion_preregistered_grid_event_density", {}).get("lookback_bars") != list(LOOKBACKS)
        or sufficiency.get("mean_reversion_preregistered_grid_event_density", {}).get(
            "absolute_standardized_deviation_thresholds"
        ) != list(THRESHOLDS)
        or sufficiency.get("power_planning", {}).get("hypothesis_count") != 36
        or sufficiency.get("power_planning", {}).get("target_power") != TARGET_POWER
        or sufficiency.get("power_planning", {}).get("familywise_alpha") != 0.05
    ):
        raise ScanError("accepted proposal, capture, data sufficiency, or plan scope is inconsistent")

    capture_scope = capture.get("frozen_scope") or {}
    interval = plan.get("interval") or {}
    if (
        capture_scope.get("resolution") != "M5"
        or capture_scope.get("start_utc") != "2025-12-15T00:00:00Z"
        or capture_scope.get("end_utc") != "2026-03-15T23:59:59Z"
        or capture_scope.get("requested_identity_count") != 34
        or interval.get("start_utc") != "2025-12-15T00:00:00Z"
        or interval.get("end_utc") != "2026-03-15T23:59:59Z"
        or len(plan.get("symbols") or []) != 34
        or freeze.get("scope", {}).get("requested_identity_count") != 34
        or freeze.get("scope", {}).get("identities_with_accepted_rows") != 33
        or freeze.get("scope", {}).get("authentic_zero_history_identity") != ZERO_HISTORY_SYMBOL
    ):
        raise ScanError("accepted development cohort or interval differs from frozen scan scope")
    for section in (freeze.get("interpretation_boundary") or {}, freeze.get("safety") or {}):
        if any(value is True for key, value in section.items() if isinstance(value, bool)):
            raise ScanError("freeze crosses an economic or protected-data boundary")
    scope = freeze.get("scope") or {}
    if (
        scope.get("structural_41_default_inferential_authority") is not False
        or scope.get("protected_forward_opened") is not False
        or scope.get("zero_history_is_not_negative_evidence") is not True
        or scope.get("cohort_role") != "DEVELOPMENT_ONLY_MECHANISM_SPECIFIC_DISCOVERY"
    ):
        raise ScanError("frozen sampling-frame interpretation is unsafe")
    if freeze.get("accounting_effect") != {
        "economic_outcomes_opened": 0,
        "v2_attempts_consumed": 0,
        "search_budget_change": 0,
    }:
        raise ScanError("freeze declares an unauthorized accounting effect")
    if freeze.get("event_law", {}).get("prohibited") != [
        "post-event directional or return response",
        "strategy return or PnL",
        "candidate or winner selection",
        "protected-forward evidence",
    ]:
        raise ScanError("frozen interpretation boundary is incomplete")
    return capture, sufficiency, plan


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScanError(f"invalid bar timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ScanError("bar timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _normalize_symbol(symbol: str) -> str:
    return symbol.replace(".", "_").replace("-", "_")


def _read_capture_series(
    archive: zipfile.ZipFile,
    symbol: dict[str, Any],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    symbol_id = int(symbol["symbol_id"])
    name = str(symbol["broker_symbol"])
    matches = [
        member for member in archive.namelist()
        if member.startswith(f"raw/{symbol_id}_") and member.endswith("_M5.csv")
    ]
    if len(matches) != 1 or _normalize_symbol(name) not in matches[0]:
        raise ScanError(f"exact accepted root M5 file missing or ambiguous: {name}/{symbol_id}")
    try:
        decoded = archive.read(matches[0]).decode("utf-8-sig")
    except (UnicodeDecodeError, KeyError) as exc:
        raise ScanError(f"accepted M5 CSV cannot be read: {name}") from exc
    reader = csv.DictReader(io.StringIO(decoded))
    required = {"time_utc", "open", "high", "low", "close", "tick_volume"}
    if not required.issubset(reader.fieldnames or ()):
        raise ScanError(f"accepted M5 CSV fields are incomplete: {name}")
    rows = []
    previous: datetime | None = None
    for raw in reader:
        stamp = _parse_time(raw["time_utc"])
        if stamp < start or stamp > end or int(stamp.timestamp()) % M5_SECONDS:
            raise ScanError(f"off-interval or off-grid M5 timestamp: {name} {raw['time_utc']}")
        if previous is not None and stamp <= previous:
            raise ScanError(f"duplicate or nonmonotonic M5 timestamp: {name} {raw['time_utc']}")
        previous = stamp
        try:
            values = {field: float(raw[field]) for field in ("open", "high", "low", "close", "tick_volume")}
        except (TypeError, ValueError) as exc:
            raise ScanError(f"invalid numeric M5 value: {name} {raw['time_utc']}") from exc
        if (
            not all(math.isfinite(value) for value in values.values())
            or min(values[field] for field in ("open", "high", "low", "close")) <= 0
            or values["tick_volume"] < 0
            or values["low"] > min(values["open"], values["close"])
            or values["high"] < max(values["open"], values["close"])
        ):
            raise ScanError(f"invalid OHLC or tick-volume invariant: {name} {raw['time_utc']}")
        rows.append({"timestamp": stamp, "close": values["close"]})
    return rows


def _date_effective_n(date_counts: dict[date, int]) -> dict[str, Any]:
    return _effective_n(date_counts)


def _power_scenarios(effective_n: float) -> list[dict[str, Any]]:
    scenarios = []
    normal = NormalDist()
    critical = normal.inv_cdf(1.0 - POWER_ALPHA)
    for effect in EFFECT_SCENARIOS:
        power = (
            normal.cdf(effect * math.sqrt(effective_n) - critical)
            if effective_n > 0 else 0.0
        )
        scenarios.append({
            "standardized_effect": effect,
            "estimated_power": round(power, 10),
            "target_power": TARGET_POWER,
            "one_sided_bonferroni_alpha": POWER_ALPHA,
            "interpretation": "CLOSED_FORM_PLANNING_ESTIMATE_ONLY_NOT_OBSERVED_RESPONSE_OR_INFERENCE",
        })
    return scenarios


def scan_symbol(
    rows: list[dict[str, Any]],
    *,
    symbol: str,
    symbol_id: int,
    structural_stratum: dict[str, Any],
    lookbacks: tuple[int, ...] = LOOKBACKS,
    thresholds: tuple[float, ...] = THRESHOLDS,
) -> list[dict[str, Any]]:
    """Compute every outcome-blind cell; input prices are never read after event time."""
    results = []
    for lookback in lookbacks:
        for threshold in thresholds:
            eligible = 0
            events = 0
            armed = True
            prior_tail = 0
            daily_counts: dict[date, int] = {}
            window: list[dict[str, Any]] = []
            for row in rows:
                if window and (row["timestamp"] - window[-1]["timestamp"]).total_seconds() != M5_SECONDS:
                    window.clear()
                    armed = True
                    prior_tail = 0
                window.append(row)
                if len(window) > lookback:
                    window.pop(0)
                if len(window) != lookback:
                    continue
                closes = [item["close"] for item in window]
                center = statistics.fmean(closes)
                scale = statistics.pstdev(closes)
                if scale <= 0:
                    continue
                eligible += 1
                day = row["timestamp"].date()
                daily_counts.setdefault(day, 0)
                z_score = (closes[-1] - center) / scale
                tail = 1 if z_score >= threshold else -1 if z_score <= -threshold else 0
                if tail == 0:
                    armed = True
                    prior_tail = 0
                elif armed or (prior_tail and tail != prior_tail):
                    events += 1
                    daily_counts[day] = daily_counts.get(day, 0) + 1
                    armed = False
                    prior_tail = tail
                elif tail:
                    prior_tail = tail

            dependence = _date_effective_n(daily_counts)
            results.append({
                "symbol_id": symbol_id,
                "broker_symbol": symbol,
                "structural_stratum": structural_stratum,
                "lookback_bars": lookback,
                "absolute_standardized_deviation_threshold": threshold,
                "eligible_contiguous_windows": eligible,
                "reversal_event_count": events,
                "event_availability_rate": (events / eligible) if eligible else None,
                "per_utc_date_event_counts": [
                    {"date_utc": day.isoformat(), "event_count": count}
                    for day, count in sorted(daily_counts.items())
                ],
                "date_cluster_count": dependence["date_clusters"],
                "dependence_adjusted_effective_date_clusters": dependence["effective_n"],
                "positive_autocorrelation_lags": dependence["positive_autocorrelation_lags"],
                "closed_form_power_estimates": _power_scenarios(dependence["effective_n"]),
            })
    return results


def _validate_payload(
    archive: zipfile.ZipFile,
    symbols: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        payload = json.loads(archive.read("EPOCH46_CAPTURE_PAYLOAD.json"))
        manifest = json.loads(archive.read("CAPTURE_MANIFEST.json"))
    except (KeyError, json.JSONDecodeError) as exc:
        raise ScanError("accepted capture payload or identity manifest is missing or invalid") from exc
    if (
        payload.get("schema") != "mxm.greenfield.epoch46-outcome-blind-m5-capture-bundle.v1"
        or payload.get("status") != "M5_OUTCOME_BLIND_WAVE_01_CAPTURE_COMPLETE"
        or payload.get("plan_sha256") != PLAN_SHA256
        or payload.get("resolution") != "M5"
        or payload.get("protected_evidence_opened") is not False
        or payload.get("economic_outcomes_opened") != 0
        or payload.get("strategy_returns_computed") is not False
        or payload.get("pnl_computed") is not False
        or manifest.get("schema") != "mxm.greenfield.capture-manifest.v1"
        or manifest.get("account_fingerprint") != "b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636"
        or (manifest.get("sha256_per_canonical_payload") or {}).get("EPOCH46_CAPTURE_PAYLOAD.json")
        != CAPTURE_PAYLOAD_SHA256
    ):
        raise ScanError("capture payload or manifest violates accepted non-economic authority")
    payload_series = payload.get("series") or []
    by_id = {int(item["symbol_id"]): item for item in payload_series}
    requested = {int(item["symbol_id"]) for item in symbols}
    if len(by_id) != 34 or set(by_id) != requested:
        raise ScanError("capture payload identity set differs from the frozen 34-symbol cohort")
    return by_id


def build_scan(root: str | Path, capture_zip: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    freeze = _read_json(repository / FREEZE_REF)
    capture_acceptance, sufficiency, plan = validate_freeze(freeze, repository)
    path = Path(capture_zip)
    if not path.is_file() or _file_sha256(path) != CAPTURE_ZIP_SHA256:
        raise ScanError("Epoch46 accepted capture ZIP hash mismatch")
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ScanError("accepted Epoch46 capture is not a valid ZIP archive") from exc
    with archive:
        if archive.testzip() is not None:
            raise ScanError("accepted capture ZIP CRC validation failed")
        payload_series = _validate_payload(archive, plan["symbols"])
        names = [str(item["broker_symbol"]) for item in plan["symbols"]]
        ids = [int(item["symbol_id"]) for item in plan["symbols"]]
        if len(set(names)) != 34 or len(set(ids)) != 34:
            raise ScanError("frozen capture plan contains duplicate identities")
        checksums = archive.read("CHECKSUMS.sha256").decode("utf-8").splitlines()
        for line in checksums:
            digest, member = line.split("  ", 1)
            if member not in archive.namelist() or _sha256(archive.read(member)) != digest:
                raise ScanError(f"capture internal checksum mismatch: {member}")
        cells = []
        zero_rows = []
        start, end = START_UTC, END_UTC
        for identity in plan["symbols"]:
            symbol = str(identity["broker_symbol"])
            rows = _read_capture_series(archive, identity, start, end)
            item = payload_series[int(identity["symbol_id"])]
            if item.get("broker_symbol") != symbol or int(item.get("row_count", -1)) != len(rows):
                raise ScanError(f"payload and canonical CSV row counts do not reconcile: {symbol}")
            if not rows:
                zero_rows.append(symbol)
                continue
            cells.extend(scan_symbol(
                rows,
                symbol=symbol,
                symbol_id=int(identity["symbol_id"]),
                structural_stratum=identity["structural_stratum"],
            ))
        if set(zero_rows) != {ZERO_HISTORY_SYMBOL}:
            raise ScanError("authentic zero-history identity differs from accepted capture")
        if len(cells) != 33 * len(LOOKBACKS) * len(THRESHOLDS):
            raise ScanError("scan did not persist every required nonempty symbol-cell probe")

    return {
        "schema": "mxm.greenfield.epoch47-mean-reversion-wave01-coarse-parameter-region-scan.v1",
        "status": "COMPLETE_NON_ECONOMIC_MEAN_REVERSION_COARSE_PARAMETER_REGION_SCAN",
        "evidence_epoch": 46,
        "research_sequence_label": "EPOCH47",
        "family": "MEAN_REVERSION",
        "implementation": {"version": VERSION, "freeze_ref": FREEZE_REF},
        "source_authority": {
            "accepted_proposal_ref": PROPOSAL_REF,
            "accepted_proposal_file_sha256": PROPOSAL_SHA256,
            "capture_acceptance_ref": CAPTURE_ACCEPTANCE_REF,
            "capture_acceptance_file_sha256": CAPTURE_ACCEPTANCE_SHA256,
            "data_sufficiency_ref": DATA_SUFFICIENCY_REF,
            "data_sufficiency_file_sha256": DATA_SUFFICIENCY_SHA256,
            "capture_plan_ref": PLAN_REF,
            "capture_plan_sha256": PLAN_SHA256,
            "capture_outer_zip_sha256": CAPTURE_ZIP_SHA256,
            "capture_canonical_payload_sha256": CAPTURE_PAYLOAD_SHA256,
        },
        "scope": {
            "resolution": "M5",
            "interval_utc": {"start": "2025-12-15T00:00:00Z", "end": "2026-03-15T23:59:59Z"},
            "requested_identity_count": 34,
            "identities_scanned": 33,
            "authentic_zero_history_identities": [ZERO_HISTORY_SYMBOL],
            "total_m5_rows": (capture_acceptance.get("integrity_validation") or {}).get("total_m5_rows"),
            "development_only": True,
            "not_independent_confirmation": True,
        },
        "grid": {
            "lookback_bars": list(LOOKBACKS),
            "absolute_standardized_deviation_thresholds": list(THRESHOLDS),
            "cells_per_symbol": 12,
            "symbol_cell_records": len(cells),
            "all_probes_recorded": True,
            "winner_selection_performed": False,
        },
        "symbols": cells,
        "interpretation_boundary": {
            "event_availability_only": True,
            "post_event_directional_or_return_response_computed": False,
            "strategy_returns_computed": False,
            "pnl_computed": False,
            "economic_outcome_opened": False,
            "candidate_economic_identity_created": False,
            "winner_cell_or_symbol_selected": False,
            "protected_forward_opened": False,
            "independent_confirmation_claimed": False,
            "mechanism_family_closed": False,
            "economic_promotion_authorized": False,
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
        "later_step": {
            "stage": "PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1/STAGE_2_ROBUST_REGION_IDENTIFICATION",
            "requires_subsequent_proposal": True,
            "broad_neighborhoods_preferred": True,
            "isolated_single_cell_winners_rejected": True,
            "stage3_refinement_performed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--capture-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(RESULT_REF))
    args = parser.parse_args(argv)
    result = build_scan(args.root, args.capture_zip)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "scanned_symbols": result["scope"]["identities_scanned"],
        "symbol_cell_records": result["grid"]["symbol_cell_records"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
