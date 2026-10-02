"""Synthetic detector calibration engine for Research Core V4.

No broker access. No market outcomes. The simulator creates dependent weekly-cluster
response panels with volatility clustering and cross-symbol/cross-horizon dependence
to calibrate familywise error and power of the V4 discovery/selection architecture.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np

SEED = 20261002
WEEKS = 28
SYMBOLS = 6
HORIZONS = 4
HORIZON_RHO = 0.65
WEEK_AR1 = 0.25
COMMON_SYMBOL_WEIGHT = 0.30
LOGVOL_AR1 = 0.85
LOGVOL_LOADING = 0.22
EFFECT_SHAPE = np.array([0.5, 1.0, 0.75, 0.4], dtype=float)
EFFECT_GRID = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0]
TARGET_SE_REGIMES = [5.0, 10.0, 20.0]


def horizon_cholesky() -> np.ndarray:
    idx = np.arange(HORIZONS)
    corr = HORIZON_RHO ** np.abs(idx[:, None] - idx[None, :])
    return np.linalg.cholesky(corr)


def simulate(n: int, target_cluster_mean_se_bps: float, effect_bps: float, rng: np.random.Generator) -> np.ndarray:
    """Return [replicate, symbol, week, response_horizon] synthetic weekly responses."""
    L = horizon_cholesky()
    common = rng.normal(size=(n, WEEKS, HORIZONS)) @ L.T
    idio = rng.normal(size=(n, SYMBOLS, WEEKS, HORIZONS)) @ L.T
    innovations = COMMON_SYMBOL_WEIGHT * common[:, None, :, :] + np.sqrt(1.0 - COMMON_SYMBOL_WEIGHT**2) * idio

    y = np.empty_like(innovations)
    y[:, :, 0, :] = innovations[:, :, 0, :]
    week_scale = np.sqrt(1.0 - WEEK_AR1**2)
    for t in range(1, WEEKS):
        y[:, :, t, :] = WEEK_AR1 * y[:, :, t - 1, :] + week_scale * innovations[:, :, t, :]

    e = rng.normal(size=(n, WEEKS))
    lv = np.empty_like(e)
    lv[:, 0] = e[:, 0]
    lv_scale = np.sqrt(1.0 - LOGVOL_AR1**2)
    for t in range(1, WEEKS):
        lv[:, t] = LOGVOL_AR1 * lv[:, t - 1] + lv_scale * e[:, t]
    multiplier = np.exp(LOGVOL_LOADING * lv - LOGVOL_LOADING**2)
    y *= multiplier[:, None, :, None]

    # target_cluster_mean_se_bps is an interpretable nominal weekly-cluster mean SE scale.
    y *= float(target_cluster_mean_se_bps) * np.sqrt(WEEKS)
    if effect_bps:
        y[:, 0, :, :] += float(effect_bps) * EFFECT_SHAPE[None, None, :]
    return y


def t_statistics(y: np.ndarray) -> np.ndarray:
    mean = y.mean(axis=2)
    sd = y.std(axis=2, ddof=1)
    return mean / (sd / np.sqrt(WEEKS))


def empirical_family_p(local_max_t: np.ndarray, sorted_null_local_max_pool: np.ndarray) -> np.ndarray:
    flat = np.asarray(local_max_t)
    idx = np.searchsorted(sorted_null_local_max_pool, flat, side="left")
    ge = len(sorted_null_local_max_pool) - idx
    return (ge + 1.0) / (len(sorted_null_local_max_pool) + 1.0)


def holm_rejections(pvalues: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    n, m = pvalues.shape
    order = np.argsort(pvalues, axis=1)
    sorted_p = np.take_along_axis(pvalues, order, axis=1)
    thresholds = alpha / (m - np.arange(m))
    sequential = sorted_p <= thresholds[None, :]
    rejected_sorted = np.cumprod(sequential.astype(int), axis=1).astype(bool)
    rejected = np.zeros_like(rejected_sorted)
    rejected[np.arange(n)[:, None], order] = rejected_sorted
    return rejected


def temporal_stability(y: np.ndarray, selected_horizon: np.ndarray) -> np.ndarray:
    """Selected true-symbol horizon must be positive in >=3/4 chronological 7-week blocks."""
    n = y.shape[0]
    positive = []
    for block in range(4):
        block_mean = y[:, 0, block * 7 : (block + 1) * 7, :].mean(axis=1)
        positive.append(block_mean[np.arange(n), selected_horizon] > 0)
    return np.stack(positive, axis=1).sum(axis=1) >= 3


def connected_region_surrogate(t: np.ndarray) -> np.ndarray:
    """Diagnostic surrogate for an old generic 3-neighbor connected-region requirement."""
    z = 1.645
    return (
        ((t[:, 0, 0] > z) & (t[:, 0, 1] > z) & (t[:, 0, 2] > z))
        | ((t[:, 0, 1] > z) & (t[:, 0, 2] > z) & (t[:, 0, 3] > z))
    )


def evaluate(y: np.ndarray, null_pool: np.ndarray, local_threshold: float) -> dict[str, float]:
    t = t_statistics(y)
    local_max = t.max(axis=2)
    local_reject = local_max > local_threshold
    family_p = empirical_family_p(local_max, null_pool)
    holm = holm_rejections(family_p)
    selected = np.argmax(t[:, 0, :], axis=1)
    stability = temporal_stability(y, selected)
    old = connected_region_surrogate(t)
    return {
        "local_maxT": float(local_reject[:, 0].mean()),
        "holm6_selected_family": float(holm[:, 0].mean()),
        "local_maxT_plus_temporal_stability": float((local_reject[:, 0] & stability).mean()),
        "old_connected_region_surrogate": float(old.mean()),
        "any_of_6_local_without_selection_control": float(local_reject.any(axis=1).mean()),
        "holm6_global_any": float(holm.any(axis=1).mean()),
    }


def interpolate_mde(rows: list[dict], key: str, target: float):
    xs = [float(row["effect_bps"]) for row in rows]
    ys = [float(row[key]) for row in rows]
    for i, (x1, y1) in enumerate(zip(xs, ys)):
        if y1 >= target:
            if i == 0:
                return x1
            x0, y0 = xs[i - 1], ys[i - 1]
            if y1 == y0:
                return x1
            return x0 + (target - y0) * (x1 - x0) / (y1 - y0)
    return ">20"


def run_calibration(null_reps: int = 20000, positive_reps: int = 4000, negative_reps: int = 12000) -> dict:
    null = simulate(null_reps, 1.0, 0.0, np.random.default_rng(SEED))
    null_t = t_statistics(null)
    null_pool = np.sort(null_t.max(axis=2).ravel())
    threshold = float(np.quantile(null_pool, 0.95, method="higher"))

    negative = simulate(negative_reps, 1.0, 0.0, np.random.default_rng(SEED + 999))
    neg = evaluate(negative, null_pool, threshold)

    regimes = {}
    for se in TARGET_SE_REGIMES:
        rows = []
        for j, effect in enumerate(EFFECT_GRID):
            y = simulate(positive_reps, se, effect, np.random.default_rng(SEED + int(se) * 100 + j))
            m = evaluate(y, null_pool, threshold)
            rows.append({
                "effect_bps": effect,
                "local_maxT": m["local_maxT"],
                "holm6_selected_family": m["holm6_selected_family"],
                "local_maxT_plus_temporal_stability": m["local_maxT_plus_temporal_stability"],
                "old_connected_region_surrogate": m["old_connected_region_surrogate"],
            })
        mde = {}
        for key in ("local_maxT", "holm6_selected_family", "local_maxT_plus_temporal_stability", "old_connected_region_surrogate"):
            mde[key] = {
                "power_50pct_bps": interpolate_mde(rows, key, 0.50),
                "power_80pct_bps": interpolate_mde(rows, key, 0.80),
                "power_90pct_bps": interpolate_mde(rows, key, 0.90),
            }
        regimes[str(int(se))] = {"detection_probability_by_effect": rows, "mde": mde}

    return {
        "seed": SEED,
        "null_reps": null_reps,
        "positive_reps_per_effect_per_regime": positive_reps,
        "negative_control_reps": negative_reps,
        "local_maxT_95pct_threshold": threshold,
        "negative_control": neg,
        "noise_regimes": regimes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    result = run_calibration(
        null_reps=2000 if args.quick else 20000,
        positive_reps=400 if args.quick else 4000,
        negative_reps=1200 if args.quick else 12000,
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
