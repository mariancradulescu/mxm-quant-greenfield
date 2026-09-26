"""Prospectively frozen, non-economic linked-pair structural screen."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import random
import zipfile
from collections import defaultdict
from pathlib import Path

from research_v3.causal_ml_predictive_state_epoch31_screen import (
    _read_member, canonicalize_identical_duplicates, holm_adjust, sha256_file,
)

FREEZE_REF = "research_v3/EPOCH32_RELATIVE_VALUE_PAIR_STRUCTURE_FRONTIER_FREEZE_V1.json"
REGISTRY_REF = "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
VERSION = "MXM_EPOCH32_LINKED_PAIR_STRUCTURE_V1"
REPLACEMENT_IDS = frozenset({7427, 5352, 2924})


def validate_freeze(root: Path, freeze: dict) -> None:
    if freeze.get("schema") != "mxm.greenfield.epoch32-relative-value-pair-structure-freeze.v1" or freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_EPOCH32_STRUCTURAL_SCREEN":
        raise ValueError("unsupported or unfrozen pair law")
    authority = freeze["authority"]
    for ref, key in ((authority["accepted_proposal_ref"], "accepted_proposal_file_sha256"),
                     (REGISTRY_REF, "registry_sha256")):
        if sha256_file(root / ref) != authority[key]:
            raise ValueError(f"authority hash mismatch: {ref}")
    law = freeze["law"]
    if (law["pair_linkage"] != "SAME_BROKER_ASSET_CLASS_SIGNATURE_0_ONLY"
            or law["split"] != "CHRONOLOGICAL_50_25_25_BY_SHARED_TIMESTAMP"
            or law["no_parameter_search"] is not True
            or law["no_refit_in_test_partitions"] is not True
            or law["no_selection_by_prior_epoch24_outcome"] is not True):
        raise ValueError("structural law drift")
    if freeze["accounting_effect"] != {"economic_outcomes_opened": 0, "v2_attempts_consumed": 0, "search_budget_change": 0}:
        raise ValueError("economic accounting boundary")
    if any(freeze["interpretation_boundary"][key] for key in ("economic_promotion_authorized", "protected_forward_opened", "independent_confirmation")):
        raise ValueError("protected or confirmatory boundary")


def linked_pairs(representatives: list[dict]) -> list[tuple[dict, dict]]:
    ordered = sorted(representatives, key=lambda item: item["broker_symbol"])
    if len(ordered) != 41 or len({row["broker_symbol"] for row in ordered}) != 41:
        raise ValueError("expected 41 distinct representatives")
    return [(left, right) for i, left in enumerate(ordered) for right in ordered[i+1:]
            if left["signature"][0] == right["signature"][0]]


def _fit_development(rows: list[tuple]) -> tuple[float, float] | None:
    xs = [math.log(row[1]) for row in rows]
    ys = [math.log(row[2]) for row in rows]
    mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
    denominator = sum((x-mx)**2 for x in xs)
    if denominator <= 1e-16:
        return None
    beta = sum((x-mx)*(y-my) for x, y in zip(xs, ys))/denominator
    return beta, my-beta*mx


def _test_partition(rows: list[tuple], beta: float, intercept: float, pair_id: str, label: str, law: dict) -> dict:
    by_day: dict[str, list[float]] = defaultdict(list)
    contiguous = 0
    for prev, curr in zip(rows, rows[1:]):
        if (curr[0]-prev[0]).total_seconds() != 300:
            continue
        prev_resid = math.log(prev[2])-intercept-beta*math.log(prev[1])
        curr_resid = math.log(curr[2])-intercept-beta*math.log(curr[1])
        score = -prev_resid*(curr_resid-prev_resid)/(abs(prev_resid)+1e-12)
        if math.isfinite(score):
            by_day[prev[0].date().isoformat()].append(score)
            contiguous += 1
    clusters = [sum(scores)/len(scores) for _, scores in sorted(by_day.items())]
    eligible = (contiguous >= law["minimum_contiguous_transitions_per_partition"]
                and len(clusters) >= law["minimum_distinct_utc_days_per_test_partition"])
    if not eligible:
        return {"eligible": False, "contiguous_transitions": contiguous,
                "distinct_utc_days": len(clusters), "mean_daily_score": None, "p_value": 1.0}
    observed = sum(clusters)/len(clusters)
    seed = int.from_bytes(hashlib.sha256(f"{VERSION}|{pair_id}|{label}".encode()).digest()[:8], "big")
    rng = random.Random(seed)
    exceed = sum(sum(v*(1 if rng.getrandbits(1) else -1) for v in clusters)/len(clusters) >= observed
                 for _ in range(999))
    return {"eligible": True, "contiguous_transitions": contiguous,
            "distinct_utc_days": len(clusters), "mean_daily_score": observed,
            "p_value": (1+exceed)/1000}


def screen_pair(left_rows: list[dict], right_rows: list[dict], pair_id: str, law: dict) -> dict:
    left, left_duplicates = canonicalize_identical_duplicates(left_rows)
    right, right_duplicates = canonicalize_identical_duplicates(right_rows)
    a = {row["timestamp"]: row["close"] for row in left}
    b = {row["timestamp"]: row["close"] for row in right}
    timestamps = sorted(a.keys() & b.keys())
    aligned = [(t, a[t], b[t]) for t in timestamps]
    n = len(aligned)
    cut1, cut2 = n//2, (3*n)//4
    output = {"aligned_rows": n, "identical_duplicate_rows_removed": left_duplicates+right_duplicates,
              "partition_rows": [cut1, cut2-cut1, n-cut2]}
    if cut1 < 3 or cut2-cut1 < 2 or n-cut2 < 2:
        return {**output, "eligible": False, "reason": "INSUFFICIENT_ALIGNED_HISTORY", "pair_p_value": 1.0}
    fit = _fit_development(aligned[:cut1])
    if fit is None:
        return {**output, "eligible": False, "reason": "DEGENERATE_DEVELOPMENT_FIT", "pair_p_value": 1.0}
    beta, intercept = fit
    validation = _test_partition(aligned[cut1:cut2], beta, intercept, pair_id, "VALIDATION", law)
    holdout = _test_partition(aligned[cut2:], beta, intercept, pair_id, "INTERNAL_HOLDOUT", law)
    eligible = validation["eligible"] and holdout["eligible"]
    return {**output, "eligible": eligible, "development_beta": beta,
            "development_intercept": intercept, "validation": validation,
            "internal_holdout": holdout,
            "raw_structural_pass": eligible and validation["p_value"] <= .05 and holdout["p_value"] <= .05,
            "pair_p_value": max(validation["p_value"], holdout["p_value"]) if eligible else 1.0}


def evaluate(root: Path, development_zip: Path, replacement_zip: Path) -> dict:
    freeze = json.loads((root/FREEZE_REF).read_text())
    validate_freeze(root, freeze)
    for path, field in ((development_zip, "development_zip_sha256"), (replacement_zip, "replacement_zip_sha256")):
        if sha256_file(path) != freeze["authority"][field]:
            raise ValueError("accepted capture ZIP hash mismatch")
    representatives = json.loads((root/REGISTRY_REF).read_text())["representatives"]
    pairs = linked_pairs(representatives)
    required = {int(row["symbol_id"]) for pair in pairs for row in pair}
    series = {}
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for symbol_id in required:
            archive = replacement if symbol_id in REPLACEMENT_IDS else development
            matches = [name for name in archive.namelist() if name.startswith(f"raw/{symbol_id}_") and name.endswith("_M5.csv")]
            if len(matches) != 1:
                raise ValueError(f"expected one M5 member for {symbol_id}")
            series[symbol_id] = _read_member(archive, matches[0])
    results = {}
    for left, right in pairs:
        pair_id = left["broker_symbol"]+"|"+right["broker_symbol"]
        results[pair_id] = {"broker_symbols": [left["broker_symbol"],right["broker_symbol"]],
                            "symbol_ids": [left["symbol_id"],right["symbol_id"]],
                            "asset_class": left["signature"][0],
                            **screen_pair(series[int(left["symbol_id"])],series[int(right["symbol_id"])],pair_id,freeze["law"])}
    adjusted = holm_adjust({key: row["pair_p_value"] for key, row in results.items()})
    for key, row in results.items():
        row["holm_adjusted_p"] = adjusted[key]
        row["supported"] = bool(row.get("raw_structural_pass") and adjusted[key] <= .05)
    return {"schema":"mxm.greenfield.epoch32-relative-value-pair-structure-result.v1",
            "status":"COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT", "evidence_epoch":32,
            "family":"RELATIVE_VALUE_COINTEGRATION", "freeze_ref":FREEZE_REF,
            "freeze_sha256":sha256_file(root/FREEZE_REF), "implementation":{"version":VERSION},
            "scope":{"representatives_considered":41,"linked_pairs_predeclared":len(pairs),
                     "pairs_processed":len(results),"pair_linkage":"SAME_BROKER_ASSET_CLASS_SIGNATURE_0_ONLY"},
            "input_attestation":{"registry_sha256":sha256_file(root/REGISTRY_REF),
                                 "development_zip_sha256":sha256_file(development_zip),
                                 "replacement_zip_sha256":sha256_file(replacement_zip),
                                 "protected_forward_rows_read":0},
            "inference":{"multiplicity":"HOLM_ACROSS_ALL_PREDECLARED_LINKED_PAIRS",
                         "family_wise_error_rate":.05,"mechanism_family_closed":False},
            "pairs":results,
            "interpretation_boundary":{"result":"FROZEN_NON_ECONOMIC_DEVELOPMENT_STRUCTURAL_SCREEN_ONLY",
                "economic_promotion_authorized":False,"independent_confirmation":False,
                "mechanism_family_closed":False,"winner_selected":False},
            "accounting_effect":{"v2_attempts_consumed":0,"economic_outcomes_opened":0,"search_budget_change":0},
            "safety":{"protected_forward_opened":False,"live_orders_authorized":False,"competition_start_authorized":False}}


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=Path("."))
    parser.add_argument("--development-zip",type=Path,required=True)
    parser.add_argument("--replacement-zip",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=evaluate(args.root,args.development_zip,args.replacement_zip)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n")


if __name__=="__main__": main()
