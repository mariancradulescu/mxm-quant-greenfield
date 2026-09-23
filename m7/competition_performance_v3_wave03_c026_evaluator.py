from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.schema import validate_result
from m7.competition_performance_v3_wave02_evaluator import (
    CAP,
    COST_SHA,
    END,
    PREFIX,
    START,
    evaluate as base_evaluate,
    load_rows,
    open_capture,
    sha256_file,
)

VERSION = "MXM_PERFORMANCE_RESEARCH_V3_WAVE03_C026_EVALUATOR_V1"
CANDIDATE_ID = "V2-C026"
CANDIDATE_SPEC_HASH = "41880f453efd363da860024e8f9b7b299bd14b9f2367156779f3f193f9abc9e9"
BASE_EVALUATOR_GIT_BLOB_SHA1 = "cfc1feabf0b8b251940d3e7b17f01d915bdc214a"
BOUNDARY_HOURS = (0, 8, 14, 21)
TRAINING_DAYS = 28
MIN_EXAMPLES = 5
CONFIDENCE_SE = 1.0
N = 1000.0


class Wave03IntegrityError(ValueError):
    pass


def next_boundary(t):
    if t.minute != 0 or t.second != 0 or t.microsecond != 0 or t.hour not in BOUNDARY_HOURS:
        raise Wave03IntegrityError("not an exact frozen UTC segment boundary")
    if t.hour == 0:
        return t.replace(hour=8)
    if t.hour == 8:
        return t.replace(hour=14)
    if t.hour == 14:
        return t.replace(hour=21)
    return (t + timedelta(days=1)).replace(hour=0)


def segment_name(t):
    return {0:"SEG_00_08", 8:"SEG_08_14", 14:"SEG_14_21", 21:"SEG_21_00"}[t.hour]


def build_symbol_trades(rows, symbol, cost_fraction):
    by_time = {r["t"]: r for r in rows}
    segments = []
    for r in rows:
        t = r["t"]
        if t < START or t >= END or t.minute != 0 or t.hour not in BOUNDARY_HOURS:
            continue
        x = next_boundary(t)
        xr = by_time.get(x)
        if xr is None or x > END:
            continue
        if r["o"] <= 0:
            raise Wave03IntegrityError(symbol + " non-positive entry open")
        segments.append({
            "entry": t,
            "exit": x,
            "segment": segment_name(t),
            "p": r["o"],
            "q": xr["o"],
            "ret": xr["o"] / r["o"] - 1.0,
        })

    history = defaultdict(list)
    trades = []
    diagnostics = {"eligible_segments":0, "trained_segments":0, "cost_hurdle_passes":0}
    for seg in segments:
        diagnostics["eligible_segments"] += 1
        cutoff = seg["entry"] - timedelta(days=TRAINING_DAYS)
        prior = [
            x for x in history[seg["segment"]]
            if x["exit"] < seg["entry"] and x["entry"] >= cutoff
        ]
        if len(prior) >= MIN_EXAMPLES:
            diagnostics["trained_segments"] += 1
            vals = [x["ret"] for x in prior]
            mean = statistics.mean(vals)
            se = statistics.stdev(vals) / math.sqrt(len(vals))
            lower_abs_edge = abs(mean) - CONFIDENCE_SE * se
            if mean != 0 and lower_abs_edge > cost_fraction:
                diagnostics["cost_hurdle_passes"] += 1
                trades.append({
                    "cid": CANDIDATE_ID,
                    "s": symbol,
                    "d": "LONG" if mean > 0 else "SHORT",
                    "e": seg["entry"],
                    "x": seg["exit"],
                    "p": seg["p"],
                    "q": seg["q"],
                    "costf": cost_fraction,
                    "meta": {
                        "segment": seg["segment"],
                        "train_n": len(vals),
                        "mean": mean,
                        "se": se,
                        "lower_abs_edge": lower_abs_edge,
                    },
                })
        history[seg["segment"]].append(seg)
    return trades, diagnostics


def execute_wave(root, capture_zip):
    root = Path(root)
    acceptance = json.loads((root / "data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json").read_text(encoding="utf-8"))
    cost_doc = json.loads((root / "evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json").read_text(encoding="utf-8"))
    wave = json.loads((root / "research_v3/WAVE_03_PRE_OUTCOME_FREEZE_V1.json").read_text(encoding="utf-8"))
    spec = json.loads((root / "discovery/candidates/V2-C026.json").read_text(encoding="utf-8"))

    verify_spec_hash(spec)
    if spec["spec_hash"] != CANDIDATE_SPEC_HASH or wave["candidate_spec_hashes"][CANDIDATE_ID] != CANDIDATE_SPEC_HASH:
        raise Wave03IntegrityError("C026 spec binding drift")
    if sha256_file(root / "evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json") != COST_SHA:
        raise Wave03IntegrityError("cost authority SHA mismatch")
    if wave["capture"]["sha256"] != CAP or wave["cost_authority"]["sha256"] != COST_SHA:
        raise Wave03IntegrityError("Wave03 evidence binding drift")

    z = open_capture(Path(capture_zip), acceptance)
    rows_by_symbol = {s: load_rows(z, s) for s in acceptance["selected_markets"]}
    costs = {s: v["roundtrip_cost_fraction"] for s, v in cost_doc["symbols"].items()}

    trades = []
    diagnostics = {}
    for symbol, rows in rows_by_symbol.items():
        ts, diag = build_symbol_trades(rows, symbol, costs[symbol])
        trades.extend(ts)
        diagnostics[symbol] = diag

    if not trades:
        raise Wave03IntegrityError("C026 produced no economic events under frozen semantics")

    result = base_evaluate(CANDIDATE_ID, spec, trades, COST_SHA)
    result["implementation_validity"] = {
        "state": "VALID",
        "reason": "Frozen C026 causal session-time evaluator and accepted V6/cost integrity gates passed.",
    }
    result["metrics"]["regime_contribution"] = {
        "state": "NOT_APPLICABLE",
        "reason": "C026 UTC liquidity-segment identity is part of the prospectively frozen signal, not post-outcome regime binning.",
    }
    result["provenance"]["evaluator"] = {
        "version": VERSION,
        "sha256": sha256_file(__file__),
    }
    result["result_hash"] = compute_result_hash(result)
    validate_result(result)
    return result, diagnostics
