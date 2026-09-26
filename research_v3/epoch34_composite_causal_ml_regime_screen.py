"""Prospectively frozen, non-economic Epoch34 conditional predictive-information screen."""
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "MXM_EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_STRUCTURAL_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_FRONTIER_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_de9da14ab5a5c49ceceaded07e20c776.json"
PROPOSAL_SHA256 = "af1e3d62b83f8265e92ebbdeec5d703fb524936dc08032a69fb651aac0ccb230"
REGISTRY_REF = "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
FEATURE_STORE_REF = "research_v3/BROKER_NATIVE_FRONTIER_FEATURE_STORE_EPOCH23_V1.json"
COVERAGE_REF = "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_STRUCTURAL_COVERAGE_EPOCH23_V1.json"
CURRENT_FRONTIER_REF = "research_v3/CURRENT_RESEARCH_FRONTIER_V1.json"
DEVELOPMENT_ACCEPTANCE_REF = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json"
REPLACEMENT_ACCEPTANCE_REF = "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json"
DEVELOPMENT_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
REPLACEMENT_IDS = frozenset({7427, 5352, 2924})
M5_SECONDS = 300
ATR_PERIOD = 14
RANK_LOOKBACK = 48
PERMUTATIONS = 999
MIN_TRAINING_OBSERVATIONS = 100
MIN_TRAINING_DATES = 10
MIN_OUTER_DATES_PER_HALF = 10
LEARNING_RATE = 0.05
STATE_NAMES = tuple(
    f"{vol}_{activity}_{session}"
    for vol in ("LOW_VOL", "HIGH_VOL")
    for activity in ("LOW_ACTIVITY", "HIGH_ACTIVITY")
    for session in ("NON_OVERLAP", "OVERLAP")
)
CSV_FIELDS = ["time_utc", "open", "high", "low", "close", "tick_volume"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp lacks timezone")
    return result.astimezone(timezone.utc)


def canonicalize_identical_duplicates(
    rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    found: dict[datetime, dict[str, Any]] = {}
    removed = 0
    for row in rows:
        old = found.get(row["timestamp"])
        if old is None:
            found[row["timestamp"]] = row
        elif any(old[field] != row[field] for field in ("open", "high", "low", "close", "tick_volume")):
            raise ValueError(f"conflicting duplicate at {row['time_utc']}")
        else:
            removed += 1
    return [found[key] for key in sorted(found)], removed


def _segments(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    result: list[list[dict[str, Any]]] = []
    for row in rows:
        if not result or (row["timestamp"] - result[-1][-1]["timestamp"]).total_seconds() != M5_SECONDS:
            result.append([row])
        else:
            result[-1].append(row)
    return result


def _true_range_mean(segment: list[dict[str, Any]], end: int) -> float | None:
    first = end - ATR_PERIOD + 1
    if first < 1:
        return None
    values = []
    for index in range(first, end + 1):
        previous_close = float(segment[index - 1]["close"])
        row = segment[index]
        values.append(max(
            float(row["high"]) - float(row["low"]),
            abs(float(row["high"]) - previous_close),
            abs(float(row["low"]) - previous_close),
        ))
    return statistics.fmean(values)


def _context(segment: list[dict[str, Any]], index: int) -> tuple[str, list[float]] | None:
    first_reference = index - RANK_LOOKBACK - 1
    if first_reference < ATR_PERIOD - 1:
        return None
    current_atr = _true_range_mean(segment, index - 1)
    prior_atrs = [_true_range_mean(segment, position)
                  for position in range(first_reference, index - 1)]
    prior_activity = [float(segment[position]["tick_volume"])
                      for position in range(first_reference, index - 1)]
    if current_atr is None or len(prior_atrs) != RANK_LOOKBACK or any(value is None for value in prior_atrs):
        return None
    vol_rank = sum(value <= current_atr for value in prior_atrs) / RANK_LOOKBACK
    activity_value = float(segment[index - 1]["tick_volume"])
    activity_rank = sum(value <= activity_value for value in prior_activity) / RANK_LOOKBACK
    vol_state = "LOW_VOL" if vol_rank <= 0.20 else "HIGH_VOL" if vol_rank >= 0.80 else None
    activity_state = (
        "LOW_ACTIVITY" if activity_rank <= 0.20
        else "HIGH_ACTIVITY" if activity_rank >= 0.80 else None
    )
    if vol_state is None or activity_state is None:
        return None
    overlap = "OVERLAP" if 13 <= segment[index]["timestamp"].hour <= 15 else "NON_OVERLAP"
    state = f"{vol_state}_{activity_state}_{overlap}"
    context = [1.0 if state == candidate else 0.0 for candidate in STATE_NAMES]
    return state, context


def _predictive_features(segment: list[dict[str, Any]], index: int) -> list[float] | None:
    if index < 12:
        return None
    returns = [
        math.log(float(segment[position]["close"]) / float(segment[position - 1]["close"]))
        for position in range(index - 12, index)
    ]
    scale = statistics.fmean(abs(value) for value in returns)
    normalized = [
        max(-10.0, min(10.0, returns[-offset] / scale)) if scale > 0 else 0.0
        for offset in (1, 2, 3)
    ]
    return [*normalized, scale]


def _sigmoid(value: float) -> float:
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def _probability(weights: list[float], features: list[float]) -> float:
    return _sigmoid(sum(weight * value for weight, value in zip(weights, features)))


def _update(weights: list[float], features: list[float], label: int) -> None:
    error = float(label > 0) - _probability(weights, features)
    for index, value in enumerate(features):
        weights[index] += LEARNING_RATE * error * value


def _model_inputs(
    segment: list[dict[str, Any]], index: int,
) -> tuple[list[float], list[float], str] | None:
    context = _context(segment, index)
    predictive = _predictive_features(segment, index)
    if context is None or predictive is None:
        return None
    state, state_features = context
    return [1.0, *state_features], [1.0, *state_features, *predictive], state


def _fit_models(
    rows: list[dict[str, Any]], cutoff: datetime,
) -> tuple[list[float], list[float], int, int]:
    baseline = [0.0] * (1 + len(STATE_NAMES))
    augmented = [0.0] * (1 + len(STATE_NAMES) + 4)
    observations = 0
    dates: set[str] = set()
    for segment in _segments(rows):
        for index in range(RANK_LOOKBACK + ATR_PERIOD, len(segment) - 1):
            if segment[index + 1]["timestamp"] >= cutoff:
                continue
            inputs = _model_inputs(segment, index)
            if inputs is None:
                continue
            change = float(segment[index + 1]["close"]) - float(segment[index]["close"])
            if change == 0:
                continue
            base_features, augmented_features, _ = inputs
            label = 1 if change > 0 else -1
            _update(baseline, base_features, label)
            _update(augmented, augmented_features, label)
            observations += 1
            dates.add(segment[index + 1]["timestamp"].date().isoformat())
    return baseline, augmented, observations, len(dates)


def _infer(daily: dict[str, list[float]], broker_symbol: str, half: str) -> dict[str, Any]:
    clusters = [statistics.fmean(values) for _, values in sorted(daily.items()) if values]
    eligible = len(clusters) >= MIN_OUTER_DATES_PER_HALF
    observed = statistics.fmean(clusters) if clusters else 0.0
    seed_text = f"MXM_EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_V1|{broker_symbol}|{half}"
    seed = int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:8], "big")
    rng = random.Random(seed)
    exceed = 0
    for _ in range(PERMUTATIONS):
        randomized = sum(value * (1 if rng.getrandbits(1) else -1) for value in clusters) / len(clusters) if clusters else 0.0
        if randomized >= observed:
            exceed += 1
    return {
        "distinct_utc_dates": len(clusters),
        "eligible": eligible,
        "mean_daily_brier_improvement": observed if eligible else None,
        "one_sided_sign_flip_p": (1 + exceed) / (1 + PERMUTATIONS) if eligible else 1.0,
    }


def evaluate_symbol(
    rows: list[dict[str, Any]], broker_symbol: str, symbol_id: int,
    cutoff: datetime,
) -> dict[str, Any]:
    rows, duplicates = canonicalize_identical_duplicates(rows)
    baseline, augmented, training_observations, training_dates = _fit_models(rows, cutoff)
    daily: dict[str, list[float]] = defaultdict(list)
    outer_observations = 0
    state_counts: dict[str, int] = defaultdict(int)
    for segment in _segments(rows):
        for index in range(RANK_LOOKBACK + ATR_PERIOD, len(segment) - 1):
            if segment[index]["timestamp"] < cutoff:
                continue
            inputs = _model_inputs(segment, index)
            if inputs is None:
                continue
            change = float(segment[index + 1]["close"]) - float(segment[index]["close"])
            if change == 0:
                continue
            base_features, augmented_features, state = inputs
            positive = change > 0
            base_probability = _probability(baseline, base_features)
            augmented_probability = _probability(augmented, augmented_features)
            outcome = float(positive)
            base_brier = (outcome - base_probability) ** 2
            augmented_brier = (outcome - augmented_probability) ** 2
            daily[segment[index]["timestamp"].date().isoformat()].append(base_brier - augmented_brier)
            state_counts[state] += 1
            outer_observations += 1
    dates = sorted(daily)
    midpoint = len(dates) // 2
    date_halves = (set(dates[:midpoint]), set(dates[midpoint:]))
    reports = []
    for label, selected_dates in zip(("CHRONOLOGICAL_HALF_1", "CHRONOLOGICAL_HALF_2"), date_halves):
        selected = {day: daily[day] for day in selected_dates}
        reports.append(_infer(selected, broker_symbol, label))
    training_eligible = (
        training_observations >= MIN_TRAINING_OBSERVATIONS
        and training_dates >= MIN_TRAINING_DATES
    )
    eligible = training_eligible and all(report["eligible"] for report in reports)
    raw_support = eligible and all(
        report["mean_daily_brier_improvement"] is not None
        and report["mean_daily_brier_improvement"] > 0
        and report["one_sided_sign_flip_p"] <= 0.05
        for report in reports
    )
    return {
        "symbol_id": symbol_id,
        "rows": len(rows),
        "identical_duplicate_rows_removed": duplicates,
        "contiguous_segments": len(_segments(rows)),
        "training_observations": training_observations,
        "training_utc_dates": training_dates,
        "training_minimum_pass": training_eligible,
        "outer_observations": outer_observations,
        "outer_utc_dates": len(dates),
        "regime_state_observations": dict(sorted(state_counts.items())),
        "chronological_half_1": reports[0],
        "chronological_half_2": reports[1],
        "max_half_p_value": (
            max(report["one_sided_sign_flip_p"] for report in reports)
            if training_eligible else 1.0
        ),
        "minimum_data_sufficiency_pass": eligible,
        "raw_incremental_structural_pass": raw_support,
    }


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    for index, (key, value) in enumerate(ordered):
        running = max(running, min(1.0, value * (len(ordered) - index)))
        adjusted[key] = running
    return adjusted


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def validate_freeze(freeze: dict[str, Any], root: Path) -> dict[str, Any]:
    if (freeze.get("schema") != "mxm.greenfield.epoch34-composite-causal-ml-regime-frontier-freeze.v1"
            or freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_EPOCH34_STRUCTURAL_SCREEN"):
        raise ValueError("unsupported or unfrozen Epoch34 authority")
    authority = freeze.get("authority", {})
    expected_hashes = {
        "current_frontier_sha256": "2e8cbe434a776d36ec494e7fbd642c36098400c38132cb57c734d6a60ab0f69b",
        "registry_sha256": "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3",
        "feature_store_sha256": "b92ad33bffad77f00b86933e1f552736485782e17fdea98fd0e84d1ab6dd117c",
        "coverage_sha256": "5cfb0662b12f1f42f8f5c503df64f42716dab98ba5729ab7e6eef75bce2c5dec",
        "development_zip_sha256": DEVELOPMENT_SHA256,
        "replacement_zip_sha256": REPLACEMENT_SHA256,
    }
    expected_refs = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "current_frontier_ref": CURRENT_FRONTIER_REF,
        "registry_ref": REGISTRY_REF,
        "feature_store_ref": FEATURE_STORE_REF,
        "coverage_ref": COVERAGE_REF,
        "development_acceptance_ref": DEVELOPMENT_ACCEPTANCE_REF,
        "replacement_acceptance_ref": REPLACEMENT_ACCEPTANCE_REF,
    }
    for field, expected in expected_refs.items():
        if authority.get(field) != expected:
            raise ValueError(f"Epoch34 authority reference mismatch: {field}")
    for field, expected in expected_hashes.items():
        if authority.get(field) != expected:
            raise ValueError(f"Epoch34 frozen authority hash mismatch: {field}")
    proposal = root / PROPOSAL_REF
    if not proposal.is_file() or sha256_file(proposal) != PROPOSAL_SHA256:
        raise ValueError("accepted proposal file-byte hash mismatch")
    registry_path = root / REGISTRY_REF
    current_frontier_path = root / CURRENT_FRONTIER_REF
    feature_path = root / FEATURE_STORE_REF
    coverage_path = root / COVERAGE_REF
    if (sha256_file(current_frontier_path) != authority["current_frontier_sha256"]
            or sha256_file(registry_path) != authority["registry_sha256"]
            or sha256_file(feature_path) != authority["feature_store_sha256"]
            or sha256_file(coverage_path) != authority["coverage_sha256"]):
        raise ValueError("frontier, feature-store, or coverage binding hash mismatch")
    current_frontier = _load_json(current_frontier_path)
    if (current_frontier.get("current_structural_registry_ref") != REGISTRY_REF
            or current_frontier.get("feature_store_ref") != FEATURE_STORE_REF
            or current_frontier.get("evidence_epoch") != 28):
        raise ValueError("Epoch34 authority no longer resolves through the bound current frontier")
    registry = _load_json(registry_path)
    coverage = _load_json(coverage_path)
    representatives = registry.get("representatives")
    if (not isinstance(representatives, list) or len(representatives) != 41
            or registry.get("counts", {}).get("representative_count") != 41):
        raise ValueError("Epoch34 requires the complete current set of 41 representatives")
    if (coverage.get("status") != "COMPLETE_NON_ECONOMIC_CURRENT_REPRESENTATIVE_COVERAGE_RESTORED"
            or coverage.get("current_representative_history_coverage", {}).get("status") != "PASS_41_OF_41"
            or coverage.get("current_representative_history_coverage", {}).get("total_current_representatives") != 41):
        raise ValueError("accepted-history coverage is not complete for all 41 representatives")
    if len({item.get("broker_symbol") for item in representatives}) != 41 or len({item.get("symbol_id") for item in representatives}) != 41:
        raise ValueError("current structural registry contains duplicate representatives")
    by_id = {int(item["symbol_id"]): item["broker_symbol"] for item in representatives}
    if not REPLACEMENT_IDS.issubset(by_id):
        raise ValueError("replacement archive IDs do not belong to the current frontier")
    proposal_doc = _load_json(proposal)
    decision = proposal_doc.get("decision", {})
    scope = decision.get("scope", {})
    if (decision.get("selected_action") != "Implement an Epoch34 composite causal-ML and regime-context structural screen."
            or scope.get("frontier") != "Use the complete current set of 41 structural representatives; require verified current accepted-history bindings and do not select a subgroup based on outcomes."
            or proposal_doc.get("data_policy", {}).get("new_market_data_requested") is not False):
        raise ValueError("accepted proposal semantics or data policy mismatch")
    development_acceptance = _load_json(root / DEVELOPMENT_ACCEPTANCE_REF)
    replacement_acceptance = _load_json(root / REPLACEMENT_ACCEPTANCE_REF)
    if development_acceptance.get("source", {}).get("zip_sha256") != DEVELOPMENT_SHA256:
        raise ValueError("development capture acceptance does not bind the frozen ZIP")
    if replacement_acceptance.get("capture_provenance", {}).get("returned_transport_zip_sha256") != REPLACEMENT_SHA256:
        raise ValueError("replacement capture acceptance does not bind the frozen ZIP")
    law = freeze.get("preregistered_structural_law", {})
    scope = freeze.get("scope", {})
    expected_interval = {
        "start_utc": "2026-06-15T00:00:00Z",
        "end_utc": "2026-09-13T23:59:59Z",
    }
    expected_context_states = list(STATE_NAMES)
    if (scope.get("frontier") != "ALL_41_CURRENT_STRUCTURAL_REPRESENTATIVES_EXACTLY_ONCE"
            or scope.get("representative_count") != 41
            or scope.get("resolution") != "M5"
            or scope.get("interval") != expected_interval
            or scope.get("training_cutoff_utc") != "2026-07-30T00:00:00Z"
            or scope.get("replacement_capture_symbol_ids") != [7427, 5352, 2924]):
        raise ValueError("Epoch34 frozen data and frontier scope mismatch")
    context_law = law.get("regime_context", {})
    model_law = law.get("paired_models", {})
    inference = law.get("inference", {})
    expected_training = (
        "Chronological prequential updates on eligible training observations only; "
        "emit each score before its label update. Freeze both weight vectors at the cutoff "
        "and never update during outer evaluation."
    )
    if (law.get("no_parameter_search") is not True or law.get("no_outer_refit") is not True
            or law.get("prior_epoch_results_are_not_inputs") is not True
            or law.get("internal_development_data_is_not_independent_confirmation") is not True
            or law.get("target") != "sign(close[t+1]-close[t]); zero labels excluded"
            or context_law.get("atr_period") != ATR_PERIOD
            or context_law.get("rank_lookback") != RANK_LOOKBACK
            or context_law.get("volatility_rank") != "ATR(t-1) ranked against the 48 prior valid ATR observations ending t-2 through t-49; <=0.20 LOW_VOL, >=0.80 HIGH_VOL, otherwise unclassified."
            or context_law.get("activity_rank") != "tick_volume(t-1) ranked against the 48 prior bars ending t-2 through t-49; <=0.20 LOW_ACTIVITY, >=0.80 HIGH_ACTIVITY, otherwise unclassified."
            or context_law.get("session_overlap") != "UTC hour 13 through 15 inclusive is OVERLAP; all other UTC hours are NON_OVERLAP."
            or context_law.get("context_states") != expected_context_states
            or context_law.get("unclassified_context") != "Exclude the observation from both models."
            or model_law.get("baseline") != "Online logistic regression with intercept and one-hot encoding of the eight frozen regime-context states."
            or model_law.get("augmented") != "Same logistic regression and context inputs plus lagged log returns at t-1, t-2, t-3 and mean absolute log return over the 12 bars ending t-1."
            or model_law.get("return_scaling") != "Divide each of the three lagged returns by the mean absolute return over the same 12-bar window; clip each ratio to [-10,10]. The fourth input is the unscaled mean absolute return."
            or model_law.get("learning_rate") != LEARNING_RATE
            or model_law.get("initial_weights") != "All zero."
            or model_law.get("training") != expected_training
            or model_law.get("prediction") != "Stable logistic probability of an up label."
            or inference.get("permutations") != PERMUTATIONS
            or inference.get("minimum_training_observations") != MIN_TRAINING_OBSERVATIONS
            or inference.get("minimum_training_utc_dates") != MIN_TRAINING_DATES
            or inference.get("minimum_outer_utc_dates_per_half") != MIN_OUTER_DATES_PER_HALF
            or inference.get("family_wise_error_rate") != 0.05
            or inference.get("multiplicity") != "HOLM_STEP_DOWN_FAMILY_WISE_ERROR_CONTROL_ACROSS_ALL_41_SYMBOL_MAX_HALF_P_VALUES"):
        raise ValueError("fixed Epoch34 model or inference law mismatch")
    if freeze.get("accounting_effect") != {
        "economic_outcomes_opened": 0, "v2_attempts_consumed": 0, "search_budget_change": 0,
    }:
        raise ValueError("Epoch34 economic accounting boundary violated")
    interpretation = freeze.get("interpretation_boundary", {})
    safety = freeze.get("safety", {})
    if (interpretation.get("economic_promotion_authorized") is not False
            or interpretation.get("protected_forward_opened") is not False
            or interpretation.get("independent_confirmation") is not False
            or interpretation.get("mechanism_family_closed") is not False
            or interpretation.get("winner_selected") is not False
            or interpretation.get("candidate_identity_created") is not False
            or safety.get("protected_forward_opened") is not False
            or safety.get("live_orders_authorized") is not False
            or safety.get("competition_start_authorized") is not False):
        raise ValueError("Epoch34 safety or interpretation boundary violated")
    return registry


def _read_member(archive: zipfile.ZipFile, member: str, interval: dict[str, str]) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(archive.read(member).decode("utf-8-sig")))
    if reader.fieldnames != CSV_FIELDS:
        raise ValueError(f"{member}: unexpected M5 CSV header")
    start, end = parse_utc(interval["start_utc"]), parse_utc(interval["end_utc"])
    rows = []
    for source in reader:
        timestamp = parse_utc(source["time_utc"])
        values = {field: float(source[field]) for field in CSV_FIELDS[1:]}
        if (not all(math.isfinite(value) for value in values.values())
                or min(values[field] for field in ("open", "high", "low", "close")) <= 0
                or values["tick_volume"] < 0
                or values["high"] < max(values["open"], values["close"], values["low"])
                or values["low"] > min(values["open"], values["close"], values["high"])
                or timestamp < start or timestamp > end):
            raise ValueError(f"{member}: invalid or out-of-scope market row")
        rows.append({"time_utc": source["time_utc"], "timestamp": timestamp, **values})
    if not rows:
        raise ValueError(f"{member}: empty series")
    return rows


def evaluate(
    freeze: dict[str, Any], development_zip: Path, replacement_zip: Path,
    root: Path,
) -> dict[str, Any]:
    registry = validate_freeze(freeze, root)
    if sha256_file(development_zip) != DEVELOPMENT_SHA256 or sha256_file(replacement_zip) != REPLACEMENT_SHA256:
        raise ValueError("accepted capture ZIP hash mismatch")
    interval = freeze["scope"]["interval"]
    cutoff = parse_utc(freeze["scope"]["training_cutoff_utc"])
    results: dict[str, Any] = {}
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for item in registry["representatives"]:
            symbol, symbol_id = str(item["broker_symbol"]), int(item["symbol_id"])
            archive = replacement if symbol_id in REPLACEMENT_IDS else development
            matches = [
                name for name in archive.namelist()
                if name.startswith(f"raw/{symbol_id}_") and name.endswith("_M5.csv")
            ]
            if len(matches) != 1:
                raise ValueError(f"expected exactly one accepted M5 member for {symbol} ({symbol_id})")
            result = evaluate_symbol(_read_member(archive, matches[0], interval), symbol, symbol_id, cutoff)
            results[symbol] = result
    if len(results) != 41:
        raise ValueError("Epoch34 did not process all 41 current representatives")
    adjusted = holm_adjust({symbol: result["max_half_p_value"] for symbol, result in results.items()})
    for symbol, result in results.items():
        result["holm_adjusted_p"] = adjusted[symbol]
        result["supported_incremental_information"] = (
            result["raw_incremental_structural_pass"] and adjusted[symbol] <= 0.05
        )
    return {
        "schema": "mxm.greenfield.epoch34-composite-causal-ml-regime-structural-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "evidence_epoch": 34,
        "family": "CAUSAL_ML_PREDICTIVE_OR_STATE_MODEL_CONDITIONAL_ON_REGIME_CONTEXT",
        "freeze_ref": FREEZE_REF,
        "implementation": {"version": VERSION},
        "scope": {
            "representatives_processed": len(results),
            "all_41_processed_exactly_once": len(results) == 41,
            "representatives_are_economic_equivalents": False,
        },
        "input_attestation": {
            "registry_sha256": sha256_file(root / REGISTRY_REF),
            "current_frontier_sha256": sha256_file(root / CURRENT_FRONTIER_REF),
            "feature_store_sha256": sha256_file(root / FEATURE_STORE_REF),
            "coverage_sha256": sha256_file(root / COVERAGE_REF),
            "proposal_file_sha256": sha256_file(root / PROPOSAL_REF),
            "development_zip_sha256": sha256_file(development_zip),
            "replacement_zip_sha256": sha256_file(replacement_zip),
            "protected_forward_rows_read": 0,
            "prior_epoch_screen_results_used_as_inputs": False,
        },
        "inference": {
            "multiplicity": "HOLM_ACROSS_41_SYMBOL_MAX_HALF_P_VALUES",
            "family_wise_error_rate": 0.05,
            "mechanism_family_closed": False,
        },
        "symbols": results,
        "interpretation_boundary": {
            "result": "FROZEN_NON_ECONOMIC_DEVELOPMENT_STRUCTURAL_INCREMENTAL_INFORMATION_SCREEN_ONLY",
            "economic_promotion_authorized": False,
            "independent_confirmation": False,
            "internal_development_data_is_independent_confirmation": False,
            "mechanism_family_closed": False,
            "winner_selected": False,
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
    parser.add_argument("--root", default=".")
    parser.add_argument("--freeze", default=FREEZE_REF)
    parser.add_argument("--development-zip", required=True)
    parser.add_argument("--replacement-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    root = Path(args.root)
    freeze_path = root / args.freeze
    result = evaluate(
        _load_json(freeze_path),
        Path(args.development_zip),
        Path(args.replacement_zip),
        root,
    )
    result["freeze_sha256"] = sha256_file(freeze_path)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
