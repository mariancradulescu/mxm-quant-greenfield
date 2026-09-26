"""Fixed, causal, non-economic predictive-state screen for Epoch 31."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import zipfile
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "MXM_EPOCH31_CAUSAL_STATE_V1"
FREEZE_REF = "research_v3/EPOCH31_CAUSAL_ML_PREDICTIVE_STATE_FRONTIER_FREEZE_V1.json"
REGISTRY_REF = "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
M5_SECONDS = 300
SPLIT = datetime(2026, 7, 30, tzinfo=timezone.utc)
IDS = frozenset({7427, 5352, 2924})
PERMUTATIONS = 999


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


def canonicalize_identical_duplicates(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
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


def _features(segment: list[dict[str, Any]], index: int) -> list[float] | None:
    if index < 13:
        return None
    returns = [math.log(segment[i]["close"] / segment[i - 1]["close"]) for i in range(index - 12, index)]
    return [returns[-1], returns[-2], returns[-3], sum(abs(value) for value in returns) / 12.0]


def _sigmoid(value: float) -> float:
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def evaluate_symbol(rows: list[dict[str, Any]], broker_symbol: str, split: datetime = SPLIT) -> dict[str, Any]:
    rows, duplicates = canonicalize_identical_duplicates(rows)
    daily: dict[str, list[float]] = defaultdict(list)
    predictions = 0
    for segment in _segments(rows):
        weights = [0.0] * 5
        for index in range(13, len(segment) - 1):
            features = _features(segment, index)
            if features is None:
                continue
            label_delta = segment[index + 1]["close"] - segment[index]["close"]
            if label_delta == 0:
                continue
            label = 1.0 if label_delta > 0 else -1.0
            vector = [1.0, *features]
            score = 2.0 * _sigmoid(sum(a * b for a, b in zip(weights, vector))) - 1.0
            daily[segment[index]["timestamp"].date().isoformat()].append(label * score)
            probability = (score + 1.0) / 2.0
            error = (1.0 if label > 0 else 0.0) - probability
            for position, value in enumerate(vector):
                weights[position] += 0.05 * error * value
            predictions += 1
    first = {day: values for day, values in daily.items() if day < split.date().isoformat()}
    second = {day: values for day, values in daily.items() if day >= split.date().isoformat()}
    halves = {"first": _infer(first, broker_symbol, "CHRONOLOGICAL_HALF_1"),
              "second": _infer(second, broker_symbol, "CHRONOLOGICAL_HALF_2")}
    return {"rows": len(rows), "identical_duplicate_rows_removed": duplicates,
            "contiguous_segments": len(_segments(rows)), "predictions": predictions,
            "first_half": halves["first"], "second_half": halves["second"],
            "raw_structural_pass": all(item["eligible"] and item["p_value"] <= 0.05 for item in halves.values()),
            "symbol_p_value": max(item["p_value"] for item in halves.values()) if all(item["eligible"] for item in halves.values()) else 1.0}


def _infer(daily: dict[str, list[float]], symbol: str, label: str) -> dict[str, Any]:
    clusters = [sum(values) / len(values) for _, values in sorted(daily.items()) if values]
    eligible = len(clusters) >= 10
    observed = sum(clusters) / len(clusters) if clusters else 0.0
    seed = int.from_bytes(hashlib.sha256(f"MXM_EPOCH31_CAUSAL_STATE_V1|{symbol}|{label}".encode()).digest()[:8], "big")
    rng, exceed = random.Random(seed), 0
    for _ in range(PERMUTATIONS):
        if clusters and sum(value * (1 if rng.getrandbits(1) else -1) for value in clusters) / len(clusters) >= observed:
            exceed += 1
    return {"distinct_utc_dates": len(clusters), "eligible": eligible, "mean_daily_cluster_score": observed if eligible else None,
            "p_value": (1 + exceed) / (1 + PERMUTATIONS) if eligible else 1.0}


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    running = 0.0
    result = {}
    for index, (key, value) in enumerate(ordered):
        running = max(running, min(1.0, value * (len(ordered) - index)))
        result[key] = running
    return result


def _read_member(archive: zipfile.ZipFile, member: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(archive.read(member).decode("utf-8-sig")))
    fields = ["time_utc", "open", "high", "low", "close", "tick_volume"]
    if reader.fieldnames != fields:
        raise ValueError(f"{member}: unexpected M5 CSV header")
    rows = []
    for source in reader:
        timestamp = parse_utc(source["time_utc"])
        values = {field: float(source[field]) for field in fields[1:]}
        if not all(math.isfinite(value) for value in values.values()) or values["close"] <= 0:
            raise ValueError(f"{member}: invalid numeric row")
        rows.append({"time_utc": source["time_utc"], "timestamp": timestamp, **values})
    if not rows:
        raise ValueError(f"{member}: empty series")
    return rows


def validate_freeze(freeze: dict[str, Any], registry_path: Path) -> None:
    if freeze.get("schema") != "mxm.greenfield.epoch31-causal-ml-predictive-state-frontier-freeze.v1" or freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_EPOCH31_STRUCTURAL_SCREEN":
        raise ValueError("unsupported or unfrozen Epoch31 freeze")
    if freeze["authority"]["accepted_proposal_ref"] != "research_v3/ai_director/proposals/AUTO_reason_4ec73c5c88ac21bf41d985c0dfa36a54.json" or freeze["authority"]["accepted_proposal_file_sha256"] != "a9b90c0e48bfddae5c57642822dd7c31826c5013a966f6a5db6a9ff3eb0eb0e4":
        raise ValueError("accepted proposal file hash mismatch")
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    if sha256_file(Path(registry_path)) != freeze["authority"]["registry_sha256"]:
        raise ValueError("structural registry hash mismatch")
    proposal = Path(registry_path).parent.parent / freeze["authority"]["accepted_proposal_ref"]
    if sha256_file(proposal) != freeze["authority"]["accepted_proposal_file_sha256"]:
        raise ValueError("accepted proposal file hash mismatch")
    representatives = freeze.get("scope", {}).get("representative_count")
    if representatives != 41 or len(registry.get("representatives", [])) != 41:
        raise ValueError("freeze must bind all 41 representatives")
    law = freeze["preregistered_structural_law"]
    if law["learning_rate"] != 0.05 or law["warmup_bars"] != 13 or law["inference"]["permutations"] != 999 or law["no_parameter_search"] is not True:
        raise ValueError("fixed causal law mismatch")
    if freeze["accounting_effect"] != {"economic_outcomes_opened": 0, "v2_attempts_consumed": 0, "search_budget_change": 0}:
        raise ValueError("economic accounting boundary violated")
    if freeze["interpretation_boundary"]["economic_promotion_authorized"] or freeze["interpretation_boundary"]["protected_forward_opened"]:
        raise ValueError("interpretation boundary violated")


def evaluate(freeze: dict[str, Any], development_zip: Path, replacement_zip: Path, registry_path: Path) -> dict[str, Any]:
    validate_freeze(freeze, registry_path)
    if sha256_file(development_zip) != freeze["authority"]["development_zip_sha256"] or sha256_file(replacement_zip) != freeze["authority"]["replacement_zip_sha256"]:
        raise ValueError("capture ZIP hash mismatch")
    results = {}
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for item in json.loads(Path(registry_path).read_text(encoding="utf-8"))["representatives"]:
            symbol, symbol_id = item["broker_symbol"], int(item["symbol_id"])
            archive = replacement if symbol_id in IDS else development
            matches = [name for name in archive.namelist() if name.startswith(f"raw/{symbol_id}_") and name.endswith("_M5.csv")]
            if len(matches) != 1:
                raise ValueError(f"expected one M5 member for {symbol_id}")
            results[symbol] = {"symbol_id": symbol_id, **evaluate_symbol(_read_member(archive, matches[0]), symbol)}
    adjusted = holm_adjust({symbol: result["symbol_p_value"] for symbol, result in results.items()})
    for symbol, result in results.items():
        result["holm_adjusted_p"] = adjusted[symbol]
        result["supported"] = result["raw_structural_pass"] and adjusted[symbol] <= 0.05
    return {"schema": "mxm.greenfield.epoch31-causal-ml-predictive-state-structural-result.v1", "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
            "evidence_epoch": 31, "family": "CAUSAL_ML_PREDICTIVE_OR_STATE_MODEL", "freeze_ref": FREEZE_REF,
            "implementation": {"version": VERSION}, "scope": {"representatives_processed": len(results), "all_41_processed_exactly_once": len(results) == 41, "representatives_are_economic_equivalents": False},
            "input_attestation": {"registry_sha256": sha256_file(registry_path),
                                  "development_zip_sha256": sha256_file(development_zip),
                                  "replacement_zip_sha256": sha256_file(replacement_zip),
                                  "protected_forward_rows_read": 0},
            "inference": {"multiplicity": "HOLM_ACROSS_41_SYMBOL_P_VALUES", "family_wise_error_rate": 0.05, "mechanism_family_closed": False},
            "symbols": results,
            "interpretation_boundary": {"result": "FROZEN_NON_ECONOMIC_DEVELOPMENT_STRUCTURAL_SCREEN_ONLY",
                                        "economic_promotion_authorized": False, "independent_confirmation": False,
                                        "mechanism_family_closed": False, "winner_selected": False},
            "accounting_effect": {"v2_attempts_consumed": 0, "economic_outcomes_opened": 0, "search_budget_change": 0},
            "safety": {"protected_forward_opened": False, "live_orders_authorized": False, "competition_start_authorized": False}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--development-zip", required=True)
    parser.add_argument("--replacement-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    freeze_path = Path(args.freeze)
    result = evaluate(
        json.loads(freeze_path.read_text(encoding="utf-8")),
        Path(args.development_zip),
        Path(args.replacement_zip),
        Path(args.registry),
    )
    result["freeze_sha256"] = sha256_file(freeze_path)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
