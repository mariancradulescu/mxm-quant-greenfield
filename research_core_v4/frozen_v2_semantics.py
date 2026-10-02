from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Sequence

import numpy as np

STATE_ORDER = {"LOW": 0, "HIGH": 1}


def select_leaf_index(
    adjusted_p: Sequence[float],
    observed_t: Sequence[float],
    leaf_meta: Sequence[tuple[str, int]],
) -> int:
    """Frozen V2 selector: p asc, t desc, horizon asc, LOW before HIGH."""
    if not (len(adjusted_p) == len(observed_t) == len(leaf_meta)):
        raise ValueError("selector inputs must have equal length")
    if not adjusted_p:
        raise ValueError("no leaves")
    for state, horizon in leaf_meta:
        if state not in STATE_ORDER:
            raise ValueError(f"invalid volatility state: {state}")
        if int(horizon) <= 0:
            raise ValueError("invalid horizon")
    def key(i: int):
        p = float(adjusted_p[i])
        t = float(observed_t[i])
        if not math.isfinite(p):
            p = 1.0
        t_key = -t if math.isfinite(t) else float("inf")
        state, horizon = leaf_meta[i]
        return (p, t_key, int(horizon), STATE_ORDER[state])
    return min(range(len(adjusted_p)), key=key)


def paired_arm_symbol_week(
    units: Iterable[object],
    arm: str,
) -> dict[tuple[str, str, str, str, int], float]:
    """Equal-weight available directions inside each paired symbol-week leaf."""
    if arm not in ("FULL", "BASELINE"):
        raise ValueError("arm must be FULL or BASELINE")
    grouped: dict[tuple[str, str, str, str, int], list[float]] = defaultdict(list)
    attr = "full_mean" if arm == "FULL" else "baseline_mean"
    for u in units:
        key = (u.context, u.symbol, u.week_key, u.vol_state, int(u.horizon))
        grouped[key].append(float(getattr(u, attr)))
    return {k: float(np.mean(v)) for k, v in grouped.items()}


def paired_arm_context_week(
    units: Iterable[object],
    arm: str,
    min_symbols: int,
) -> dict[tuple[str, str, str, int], float]:
    """Equal-weight valid symbols inside each context-week leaf."""
    sw = paired_arm_symbol_week(units, arm)
    grouped: dict[tuple[str, str, str, int], list[float]] = defaultdict(list)
    for (ctx, sym, week, state, horizon), value in sw.items():
        grouped[(ctx, week, state, horizon)].append(float(value))
    return {
        k: float(np.mean(v))
        for k, v in grouped.items()
        if len(v) >= int(min_symbols)
    }


def paired_arm_hierarchical_mean(
    units: Iterable[object],
    arm: str,
    min_symbols: int,
) -> float | None:
    """Mean across the fixed valid context-week geometry after equal direction/symbol weighting."""
    cw = paired_arm_context_week(units, arm, min_symbols)
    if not cw:
        return None
    return float(np.mean(list(cw.values())))


def canonical_json_bytes(obj: object) -> bytes:
    import json
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
