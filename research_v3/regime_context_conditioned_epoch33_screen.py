"""Fresh, frozen, non-economic regime-context structural screen for Epoch 33."""
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

VERSION = "MXM_EPOCH33_REGIME_CONTEXT_CONDITIONED_STRUCTURAL_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH33_REGIME_CONTEXT_CONDITIONED_FRONTIER_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_c84a5aabc6bdebb3bf038616d6868692.json"
PROPOSAL_SHA256 = "ce4a0590b0986ecbba9274d9183f97d524d9d242a170ada1e328c67ec37d7b4f"
REGISTRY_REF = "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
DEVELOPMENT_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
REPLACEMENT_IDS = frozenset({7427, 5352, 2924})
M5_SECONDS = 300
ATR_PERIOD = 14
RANK_LOOKBACK = 48
HORIZON = 3
SPACING = 3
MIN_HALF = 30
VOL_STATES = ("LOW_VOL", "HIGH_VOL")
ACTIVITY_STATES = ("LOW_ACTIVITY", "HIGH_ACTIVITY")
SESSION_STATES = ("NON_OVERLAP", "OVERLAP")
STATES = tuple(
    f"{vol}_{activity}_{session}"
    for vol in VOL_STATES
    for activity in ACTIVITY_STATES
    for session in SESSION_STATES
)
SYMBOLS = (
    ("VER.AT", 5268), ("GEM.AU", 3693), ("Lead", 2791),
    ("TRUMPUSD", 5562), ("NatGas", 251), ("USDCZK", 56),
    ("JPN225-F", 2917), ("EUBobl-F", 7290), ("SCI25", 150),
    ("NIO.US-24", 5479), ("XPDUSD", 95), ("WTOIL-PERP", 7393),
)


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
        elif any(old[field] != row[field] for field in
                 ("open", "high", "low", "close", "tick_volume")):
            raise ValueError(f"conflicting duplicate at {row['time_utc']}")
        else:
            removed += 1
    return [found[key] for key in sorted(found)], removed


def exact_binomial_greater(successes: int, observations: int) -> float:
    if observations < 0 or successes < 0 or successes > observations:
        raise ValueError("invalid binomial counts")
    if not observations:
        return 1.0
    return sum(math.comb(observations, value)
               for value in range(successes, observations + 1)) / (1 << observations)


def bh_adjust(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    result: dict[str, float] = {}
    running = 1.0
    for rank in range(len(ordered), 0, -1):
        key, value = ordered[rank - 1]
        running = min(running, min(1.0, value * len(ordered) / rank))
        result[key] = running
    return result


def _segments(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    result: list[list[dict[str, Any]]] = []
    for row in rows:
        if not result or (row["timestamp"] - result[-1][-1]["timestamp"]).total_seconds() != M5_SECONDS:
            result.append([row])
        else:
            result[-1].append(row)
    return result


def _atr(segment: list[dict[str, Any]], end: int) -> float | None:
    if end < ATR_PERIOD:
        return None
    values = []
    for index in range(end - ATR_PERIOD + 1, end + 1):
        previous = float(segment[index - 1]["close"])
        row = segment[index]
        values.append(max(float(row["high"]) - float(row["low"]),
                          abs(float(row["high"]) - previous),
                          abs(float(row["low"]) - previous)))
    return statistics.fmean(values)


def _ranked_state(segment: list[dict[str, Any]], index: int) -> str | None:
    current_index = index - 1
    first = index - RANK_LOOKBACK
    if first < ATR_PERIOD:
        return None
    current_atr = _atr(segment, current_index)
    atrs = [_atr(segment, item) for item in range(first, index - 1)]
    activity = [float(segment[item]["tick_volume"])
                for item in range(first, index - 1)]
    if current_atr is None or len(atrs) != RANK_LOOKBACK or any(value is None for value in atrs):
        return None
    vol_rank = sum(value <= current_atr for value in atrs) / RANK_LOOKBACK
    activity_rank = sum(value <= float(segment[current_index]["tick_volume"])
                        for value in activity) / RANK_LOOKBACK
    vol = "HIGH_VOL" if vol_rank >= 0.80 else "LOW_VOL" if vol_rank <= 0.20 else None
    active = ("HIGH_ACTIVITY" if activity_rank >= 0.80
              else "LOW_ACTIVITY" if activity_rank <= 0.20 else None)
    if vol is None or active is None:
        return None
    timestamp = segment[index]["timestamp"]
    overlap = "OVERLAP" if 13 <= timestamp.hour < 16 else "NON_OVERLAP"
    return f"{vol}_{active}_{overlap}"


def _summary(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [row for row in outcomes if row["outcome"] is not None]
    nonflat = [row for row in settled if row["outcome"] != 0]
    midpoint = len(nonflat) // 2
    halves = (nonflat[:midpoint], nonflat[midpoint:])
    reports = []
    p_values = []
    for half in halves:
        continuation = sum(row["outcome"] == 1 for row in half)
        p_value = exact_binomial_greater(continuation, len(half))
        p_values.append(p_value)
        reports.append({
            "settled_nonflat_events": len(half),
            "continuation": continuation,
            "reversal": sum(row["outcome"] == -1 for row in half),
            "continuation_fraction": continuation / len(half) if half else None,
            "one_sided_exact_binomial_p": p_value,
            "minimum_sample_size_pass": len(half) >= MIN_HALF,
        })
    eligible = all(report["minimum_sample_size_pass"] for report in reports)
    return {
        "selected_events": len(outcomes),
        "settled_events": len(settled),
        "right_censored_events": len(outcomes) - len(settled),
        "flat_settled_events": sum(row["outcome"] == 0 for row in settled),
        "settled_nonflat_events": len(nonflat),
        "chronological_half_1": reports[0],
        "chronological_half_2": reports[1],
        "state_p_value": max(p_values) if eligible else 1.0,
        "both_halves_pass": eligible and all(value <= 0.025 for value in p_values),
    }


def evaluate_symbol(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows, duplicates = canonicalize_identical_duplicates(rows)
    outcomes = {state: [] for state in STATES}
    selected = unclassified = candidates = 0
    for segment_index, segment in enumerate(_segments(rows)):
        last_selected: int | None = None
        for index in range(4, len(segment)):
            direction = 1 if segment[index - 1]["close"] > segment[index - 4]["close"] else -1 if segment[index - 1]["close"] < segment[index - 4]["close"] else 0
            if not direction:
                continue
            candidates += 1
            if last_selected is not None and index - last_selected < SPACING:
                continue
            last_selected = index
            selected += 1
            state = _ranked_state(segment, index)
            if state is None:
                unclassified += 1
                continue
            future = index + HORIZON
            outcome = None
            if future < len(segment):
                change = direction * (float(segment[future]["close"]) - float(segment[index]["close"]))
                outcome = 1 if change > 0 else -1 if change < 0 else 0
            outcomes[state].append({"timestamp": segment[index]["timestamp"],
                                    "outcome": outcome, "segment_index": segment_index})
    reports = {state: _summary(values) for state, values in outcomes.items()}
    state_p = {state: report["state_p_value"] for state, report in reports.items()}
    return {
        "rows": len(rows), "identical_duplicate_rows_removed": duplicates,
        "contiguous_segments": len(_segments(rows)), "eligible_directional_candidates": candidates,
        "selected_events": selected, "unclassified_events": unclassified,
        "states": reports, "context_selection_adjusted_symbol_p_value":
            min(1.0, len(STATES) * min(state_p.values())),
    }


def validate_freeze(freeze: dict[str, Any], registry_path: Path) -> None:
    if freeze.get("schema") != "mxm.greenfield.epoch33-regime-context-conditioned-frontier-freeze.v1" or freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_EPOCH33_STRUCTURAL_SCREEN":
        raise ValueError("unsupported or unfrozen Epoch33 freeze")
    authority = freeze.get("authority", {})
    proposal = Path(registry_path).parents[1] / PROPOSAL_REF
    if (authority.get("accepted_proposal_ref") != PROPOSAL_REF or
            authority.get("accepted_proposal_file_sha256") != PROPOSAL_SHA256 or
            sha256_file(proposal) != PROPOSAL_SHA256 or
            sha256_file(registry_path) != authority.get("registry_sha256")):
        raise ValueError("accepted proposal or registry hash mismatch")
    law = freeze["preregistered_structural_law"]
    if (law["atr_period"] != ATR_PERIOD or law["rank_lookback"] != RANK_LOOKBACK or
            law["horizon_bars"] != HORIZON or law["minimum_nonflat_events_per_half"] != MIN_HALF or
            law["no_parameter_search"] is not True or tuple(law["states"]) != STATES):
        raise ValueError("fixed Epoch33 law mismatch")
    if freeze["scope"]["symbols"] != [symbol for symbol, _ in SYMBOLS]:
        raise ValueError("freeze symbol scope mismatch")
    if freeze["accounting_effect"] != {"economic_outcomes_opened": 0, "v2_attempts_consumed": 0, "search_budget_change": 0}:
        raise ValueError("economic accounting boundary violated")
    if freeze["safety"]["protected_forward_opened"] or freeze["safety"]["live_orders_authorized"]:
        raise ValueError("safety boundary violated")


def _read_member(archive: zipfile.ZipFile, member: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(archive.read(member).decode("utf-8-sig")))
    fields = ["time_utc", "open", "high", "low", "close", "tick_volume"]
    if reader.fieldnames != fields:
        raise ValueError(f"{member}: unexpected M5 CSV header")
    rows = []
    for source in reader:
        timestamp = parse_utc(source["time_utc"])
        values = {field: float(source[field]) for field in fields[1:]}
        if not all(math.isfinite(value) for value in values.values()) or values["close"] <= 0 or values["tick_volume"] < 0:
            raise ValueError(f"{member}: invalid numeric row")
        rows.append({"time_utc": source["time_utc"], "timestamp": timestamp, **values})
    if not rows:
        raise ValueError(f"{member}: empty series")
    return rows


def evaluate(freeze: dict[str, Any], development_zip: Path, replacement_zip: Path, registry_path: Path) -> dict[str, Any]:
    validate_freeze(freeze, registry_path)
    if sha256_file(development_zip) != DEVELOPMENT_SHA256 or sha256_file(replacement_zip) != REPLACEMENT_SHA256:
        raise ValueError("accepted capture ZIP hash mismatch")
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    results = {}
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for symbol, symbol_id in SYMBOLS:
            archive = replacement if symbol_id in REPLACEMENT_IDS else development
            matches = [name for name in archive.namelist() if name.startswith(f"raw/{symbol_id}_") and name.endswith("_M5.csv")]
            if len(matches) != 1:
                raise ValueError(f"expected exactly one accepted M5 member for {symbol}")
            results[symbol] = {"symbol_id": symbol_id, **evaluate_symbol(_read_member(archive, matches[0]))}
    adjusted = bh_adjust({symbol: result["context_selection_adjusted_symbol_p_value"] for symbol, result in results.items()})
    for symbol, result in results.items():
        result["bh_adjusted_q"] = adjusted[symbol]
        result["supported_states"] = [state for state in STATES if result["states"][state]["both_halves_pass"]]
        result["supported_symbol"] = bool(result["supported_states"]) and adjusted[symbol] <= 0.05
    return {
        "schema": "mxm.greenfield.epoch33-regime-context-conditioned-structural-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT", "evidence_epoch": 33,
        "family": "REGIME_CONTEXT_CONDITIONED", "freeze_ref": FREEZE_REF,
        "implementation": {"version": VERSION},
        "scope": {"symbols": list(symbol for symbol, _ in SYMBOLS), "representatives_processed": len(results), "economic_equivalence": False},
        "input_attestation": {"registry_sha256": sha256_file(registry_path), "development_zip_sha256": sha256_file(development_zip), "protected_forward_rows_read": 0},
        "inference": {"multiplicity": "BH_ACROSS_12_SYMBOL_P_VALUES", "fdr_q": 0.05, "mechanism_family_closed": False},
        "symbols": results,
        "interpretation_boundary": {"result": "FROZEN_NON_ECONOMIC_STRUCTURAL_SCREEN_ONLY", "economic_promotion_authorized": False, "independent_confirmation": False, "mechanism_family_closed": False, "winner_selected": False},
        "accounting_effect": {"economic_outcomes_opened": 0, "v2_attempts_consumed": 0, "search_budget_change": 0},
        "safety": {"protected_forward_opened": False, "live_orders_authorized": False, "competition_start_authorized": False},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--freeze", required=True); parser.add_argument("--registry", required=True)
    parser.add_argument("--development-zip", required=True); parser.add_argument("--replacement-zip", required=True)
    parser.add_argument("--output", required=True); args = parser.parse_args(argv)
    result = evaluate(json.loads(Path(args.freeze).read_text(encoding="utf-8")), Path(args.development_zip), Path(args.replacement_zip), Path(args.registry))
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
