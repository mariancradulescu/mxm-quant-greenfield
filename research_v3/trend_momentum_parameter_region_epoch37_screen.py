"""Prospectively frozen, non-economic TREND_MOMENTUM coarse parameter-region scan.

This module evaluates every predeclared grid cell on the seven accepted 13-week
M5 development series. It reports a structural directional-response surface only:
no costs, PnL, candidate identity, protected-forward data, or economic outcome.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "MXM_EPOCH37_TREND_MOMENTUM_COARSE_PARAMETER_REGION_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH37_TREND_MOMENTUM_PARAMETER_REGION_FRONTIER_FREEZE_V1.json"
RESULT_REF = "evidence/EPOCH38_TREND_MOMENTUM_COARSE_PARAMETER_REGION_RESULT_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_85a6da387ad291b1ccdb81cefe0718b6.json"
PROPOSAL_ID = "AI_TREND_MOMENTUM_FX_CRYPTO_METALS_COARSE_PARAMETER_SCAN_V1"
PROPOSAL_HASH = "71333910d8382a45e46d7d4dd71282731ae9043eb0474977344b9142c116471e"
PROPOSAL_REGISTRY_REF = "research_v3/ai_director/PROPOSAL_REGISTRY_V1.json"
DEVELOPMENT_ACCEPTANCE_REF = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json"
DEVELOPMENT_PLAN_SHA256 = "b29e6f95dcd1adc3374f71124628388df7e235829fc019d31b1183166b9c7d6a"
DEVELOPMENT_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_ACCEPTANCE_REF = "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json"
REPLACEMENT_PLAN_SHA256 = "a573cbcf19897c50f9ae2ad971dc308529578604c583d57d2e836906b0c25b5f"
REPLACEMENT_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
REGISTRY_REF = "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
PARAMETER_GOVERNOR_REF = "research_v3/PARAMETER_DISCOVERY_AND_ROBUSTNESS_GOVERNOR_V1.json"
MULTI_FRONTIER_GOVERNOR_REF = "research_v3/MULTI_FRONTIER_DISCOVERY_GOVERNOR_V1.json"
COVERAGE_LEDGER_REF = "research_v3/DISCOVERY_COVERAGE_LEDGER_V1.json"
START_UTC = "2026-06-15T00:00:00Z"
END_UTC = "2026-09-13T23:59:59Z"
LOOKBACKS = [12, 24, 48, 96, 192]
THRESHOLDS = [0.5, 1.0, 1.5, 2.0]
HOLDS = {"15m": 3, "1h": 12, "4h": 48, "1d": 288}
TARGETS = [
    ("JPYX", 146, "Currency Index (Spot)"),
    ("ZARJPY", 98, "Forex (Spot)"),
    ("USDCLP", 2759, "Forex (Spot)"),
    ("USDBRL", 2755, "Forex (Spot)"),
    ("USDCZK", 56, "Forex (Spot)"),
    ("TRUMPUSD", 5562, "Crypto Currency (Spot)"),
    ("XPDUSD", 95, "Metals (Spot)"),
]
REPLACEMENT_IDS = {7427, 5352, 2924}
MIN_EFFECTIVE_DAYS = 10
MIN_HALF_DAYS = 5
NEIGHBOR_SUPPORT_FRACTION = 0.75
CROSS_SYMBOL_MIN_SYMBOLS = 4
CROSS_SYMBOL_MIN_ASSET_CLASSES = 2
M5_SECONDS = 300
MECHANISM_LAW = {
    "signal": "At each completed M5 bar inside an exact-contiguous segment, compute log(close_t/close_t-lookback) divided by population standard deviation of the lookback one-bar log returns times sqrt(lookback). Admit a trend event when absolute normalized momentum is at least the frozen threshold; direction is its sign.",
    "exit": "Starting after the event bar, exit at the first bar where normalized momentum using the same frozen lookback crosses zero to the opposite sign, or at the frozen hold horizon, whichever occurs first. A horizon crossing a segment boundary is right-censored and not repaired.",
    "effect_size": "For each settled event compute direction * log(exit_close/event_close) * 10000 basis points. Aggregate within UTC date first, then report the arithmetic mean of daily directional responses as the cell effect size.",
    "effective_independence": "UTC date is the dependence unit: all settled event responses for one cell and UTC date are averaged before effect size, uncertainty, or chronological-half diagnostics. Effective independent sample size is the number of UTC dates with a settled daily response.",
    "uncertainty": "Sample standard error across daily directional responses and a descriptive 1.96*SE interval half-width; no confirmatory p-value or economic inference is opened.",
    "missing_data": "No fill, interpolation, resampling, or synthetic bars. Any timestamp gap greater than 300 seconds starts a new segment. Any event whose required forward horizon crosses a segment boundary is right-censored.",
}
ROBUSTNESS_LAW = {
    "local_support": "effect_size > 0, at least 10 effective UTC days, at least 5 effective UTC days in each chronological half, and both chronological-half effect sizes > 0",
    "direct_neighborhood": "Cells differing by exactly one adjacent frozen grid step on exactly one parameter axis are direct neighbors.",
    "broad_local_neighborhood_support": "local_support plus at least three direct neighbors, at least 75% directly adjacent cells locally supported, and positive median adjacent effect size",
    "cross_symbol_support": ">=4 of 7 symbols locally supported at the exact parameter cell and support spans >=2 asset classes",
    "robust_region": "A connected direct-adjacent component of cross-symbol-supported parameter cells containing >=3 cells and varying in >=2 parameter dimensions.",
    "single_symbol_proxy_boundary": "A single-symbol asset-class proxy cannot by itself establish asset-class robustness.",
}


class TrendMomentumScanError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrendMomentumScanError(f"{path}: expected JSON object")
    return value


def parse_utc(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _target_dicts() -> list[dict[str, Any]]:
    return [{"symbol": s, "symbol_id": i, "asset_class": a} for s, i, a in TARGETS]


def validate_freeze(freeze: dict[str, Any], root: Path) -> dict[str, Any]:
    if (freeze.get("schema") != "mxm.greenfield.epoch37-trend-momentum-parameter-region-freeze.v1"
            or freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_TREND_MOMENTUM_COARSE_PARAMETER_REGION_SCAN"
            or freeze.get("evidence_epoch") != 37
            or freeze.get("family") != "TREND_MOMENTUM"
            or freeze.get("stage") != "PARAMETER_DISCOVERY_STAGE_1_COARSE_MECHANISM_REGION_SCAN"):
        raise TrendMomentumScanError("unsupported or unfrozen TREND parameter-region authority")

    authority = freeze.get("authority") or {}
    exact_authority = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "accepted_proposal_hash": PROPOSAL_HASH,
        "proposal_registry_ref": PROPOSAL_REGISTRY_REF,
        "development_acceptance_ref": DEVELOPMENT_ACCEPTANCE_REF,
        "development_capture_plan_sha256": DEVELOPMENT_PLAN_SHA256,
        "development_zip_sha256": DEVELOPMENT_SHA256,
        "replacement_acceptance_ref": REPLACEMENT_ACCEPTANCE_REF,
        "replacement_capture_plan_sha256": REPLACEMENT_PLAN_SHA256,
        "replacement_zip_sha256": REPLACEMENT_SHA256,
        "registry_ref": REGISTRY_REF,
        "parameter_governor_ref": PARAMETER_GOVERNOR_REF,
        "multi_frontier_governor_ref": MULTI_FRONTIER_GOVERNOR_REF,
        "coverage_ledger_ref": COVERAGE_LEDGER_REF,
    }
    if authority != exact_authority:
        raise TrendMomentumScanError("accepted proposal or capture authority binding mismatch")

    proposal = _load_json(root / PROPOSAL_REF)
    if proposal.get("proposal_id") != PROPOSAL_ID or sha256_bytes(canonical_bytes(proposal)) != PROPOSAL_HASH:
        raise TrendMomentumScanError("accepted proposal hash mismatch")
    registry_doc = _load_json(root / PROPOSAL_REGISTRY_REF)
    if not any(
        row.get("proposal_id") == PROPOSAL_ID
        and row.get("proposal_hash") == PROPOSAL_HASH
        and row.get("proposal_ref") == PROPOSAL_REF
        and row.get("economic_outcome_opened") is False
        and int(row.get("v2_attempt_consumed") or 0) == 0
        for row in registry_doc.get("accepted", [])
    ):
        raise TrendMomentumScanError("proposal is not accepted in canonical registry")

    development = _load_json(root / DEVELOPMENT_ACCEPTANCE_REF)
    source = development.get("source") or {}
    validation = development.get("validation") or {}
    if (development.get("status") != "ACCEPTED_COMPLETE_NON_ECONOMIC_DEVELOPMENT_CAPTURE"
            or source.get("zip_sha256") != DEVELOPMENT_SHA256
            or source.get("plan_sha256") != DEVELOPMENT_PLAN_SHA256
            or source.get("external_name") != "MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip"
            or validation.get("series_complete") != 40
            or validation.get("duplicate_timestamps_total") != 0
            or validation.get("out_of_interval_rows") != 0
            or validation.get("protected_forward_rows") != 0
            or development.get("interval") != {"start_utc": START_UTC, "end_utc": END_UTC, "resolution": "M5"}):
        raise TrendMomentumScanError("accepted development capture authority/hash mismatch")

    replacement = _load_json(root / REPLACEMENT_ACCEPTANCE_REF)
    if (replacement.get("status") != "ACCEPTED_AFTER_DETERMINISTIC_CANONICALIZATION_OF_IDENTICAL_DUPLICATES"
            or replacement.get("source_plan_sha256") != REPLACEMENT_PLAN_SHA256
            or (replacement.get("capture_provenance") or {}).get("returned_transport_zip_sha256") != REPLACEMENT_SHA256
            or (replacement.get("canonicalization_repair") or {}).get("conflicting_duplicate_timestamps") != 0
            or (replacement.get("canonicalization_repair") or {}).get("protected_forward_rows") != 0):
        raise TrendMomentumScanError("accepted replacement capture authority/hash mismatch")

    structural = _load_json(root / REGISTRY_REF)
    rows = structural.get("representatives") or []
    by_symbol = {row.get("broker_symbol"): row for row in rows}
    expected = _target_dicts()
    for target in expected:
        row = by_symbol.get(target["symbol"])
        if (not row or int(row.get("symbol_id", -1)) != target["symbol_id"]
                or (row.get("signature") or [None])[0] != target["asset_class"]
                or row.get("has_13w_history") is not True):
            raise TrendMomentumScanError(f"target symbol registry binding mismatch: {target['symbol']}")
        if target["symbol_id"] in REPLACEMENT_IDS:
            raise TrendMomentumScanError("coarse TREND target unexpectedly routes through replacement archive")

    scope = freeze.get("scope") or {}
    if (scope.get("symbols") != expected
            or scope.get("resolution") != "M5"
            or scope.get("interval") != {"start_utc": START_UTC, "end_utc": END_UTC}
            or scope.get("data_source") != "DEVELOPMENT_ARCHIVE_ONLY_FOR_THE_SEVEN_FROZEN_SYMBOLS"
            or scope.get("structural_41_are_economic_equivalents") is not False
            or scope.get("eligible_frontier_remains_open") != 1576):
        raise TrendMomentumScanError("wrong symbol set or frozen data scope")

    grid = freeze.get("parameter_grid") or {}
    if (grid.get("lookback_bars_M5") != LOOKBACKS
            or grid.get("momentum_threshold_zscore") != THRESHOLDS
            or grid.get("hold_horizon") != list(HOLDS)
            or grid.get("cells_per_symbol") != 80
            or grid.get("record_every_probe") is not True
            or grid.get("winner_only_logging") is not False):
        raise TrendMomentumScanError("wrong parameter grid")

    if freeze.get("mechanism_law") != MECHANISM_LAW or freeze.get("robustness_law") != ROBUSTNESS_LAW:
        raise TrendMomentumScanError("frozen mechanism or robustness law mismatch")

    boundaries = freeze.get("boundaries") or {}
    required_false = [
        "protected_or_forward_evidence_used", "economic_outcome_opened", "v2_attempt_consumed",
        "candidate_identity_opened", "mechanism_family_closed", "asset_class_closed",
    ]
    if any(boundaries.get(key) is not False for key in required_false):
        raise TrendMomentumScanError("frozen non-economic boundary mismatch")
    return structural


def _canonicalize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ts: dict[datetime, dict[str, Any]] = {}
    for row in rows:
        ts = row["timestamp"]
        prior = by_ts.get(ts)
        if prior is None:
            by_ts[ts] = row
            continue
        if any(prior[field] != row[field] for field in ("open", "high", "low", "close", "tick_volume")):
            raise TrendMomentumScanError(f"duplicate conflicting bars at {row['time_utc']}")
    return [by_ts[k] for k in sorted(by_ts)]


def _segments(rows: list[dict[str, Any]]) -> tuple[list[list[dict[str, Any]]], int, int]:
    if not rows:
        return [], 0, 0
    segments = [[rows[0]]]
    gap_count = 0
    implied_missing_bars = 0
    for row in rows[1:]:
        delta = int((row["timestamp"] - segments[-1][-1]["timestamp"]).total_seconds())
        if delta == M5_SECONDS:
            segments[-1].append(row)
        elif delta > M5_SECONDS:
            gap_count += 1
            implied_missing_bars += max(0, delta // M5_SECONDS - 1)
            segments.append([row])
        else:
            raise TrendMomentumScanError("non-increasing timestamp after canonicalization")
    return segments, gap_count, implied_missing_bars


def _read_symbol(zf: zipfile.ZipFile, symbol_id: int, symbol: str) -> list[dict[str, Any]]:
    matches = [n for n in zf.namelist() if n.startswith(f"raw/{symbol_id}_") and n.endswith("_M5.csv")]
    if len(matches) != 1 or symbol.replace(".", "_").replace("-", "_") not in matches[0]:
        raise TrendMomentumScanError(f"exact root M5 member missing or ambiguous for {symbol}/{symbol_id}: {matches}")
    reader = csv.DictReader(zf.read(matches[0]).decode("utf-8-sig").splitlines())
    out = []
    start, end = parse_utc(START_UTC), parse_utc(END_UTC)
    for raw in reader:
        ts = parse_utc(raw["time_utc"])
        if ts < start or ts > end:
            raise TrendMomentumScanError(f"future/protected or out-of-interval data: {symbol} {raw['time_utc']}")
        vals = {k: float(raw[k]) for k in ("open", "high", "low", "close")}
        if not all(math.isfinite(v) and v > 0 for v in vals.values()):
            raise TrendMomentumScanError(f"invalid OHLC: {symbol} {raw['time_utc']}")
        if vals["high"] < max(vals["open"], vals["close"]) or vals["low"] > min(vals["open"], vals["close"]):
            raise TrendMomentumScanError(f"OHLC invariant failure: {symbol} {raw['time_utc']}")
        out.append({
            "time_utc": raw["time_utc"], "timestamp": ts,
            **vals, "tick_volume": float(raw.get("tick_volume") or 0.0),
        })
    return _canonicalize(out)


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _uncertainty(values: list[float]) -> dict[str, Any]:
    if len(values) < 2:
        return {"standard_error_bps": None, "ci95_half_width_bps": None}
    se = statistics.stdev(values) / math.sqrt(len(values))
    return {"standard_error_bps": se, "ci95_half_width_bps": 1.96 * se}


def _precompute_signals(segments: list[list[dict[str, Any]]], lookback: int) -> list[tuple[list[float], list[float | None]]]:
    out = []
    for segment in segments:
        closes = [float(r["close"]) for r in segment]
        zs: list[float | None] = [None] * len(closes)
        rets = [0.0] + [math.log(closes[i] / closes[i-1]) for i in range(1, len(closes))]
        ps = [0.0]; ps2 = [0.0]
        for r in rets[1:]:
            ps.append(ps[-1] + r); ps2.append(ps2[-1] + r*r)
        for i in range(lookback, len(closes)):
            lo = i - lookback
            total = ps[i] - ps[lo]
            total2 = ps2[i] - ps2[lo]
            mean = total / lookback
            vol = math.sqrt(max(0.0, total2 / lookback - mean * mean))
            if vol > 0.0 and math.isfinite(vol):
                zs[i] = math.log(closes[i] / closes[i-lookback]) / (vol * math.sqrt(lookback))
        out.append((closes, zs))
    return out


def _evaluate_cell(segments: list[list[dict[str, Any]]], lookback: int, threshold: float, hold_bars: int,
                   signal_cache: list[tuple[list[float], list[float | None]]] | None = None) -> dict[str, Any]:
    eligible_signal_bars = triggered = settled = right_censored = opposite_exit = fixed_exit = 0
    daily: dict[str, list[float]] = {}
    cache = signal_cache if signal_cache is not None else _precompute_signals(segments, lookback)
    for segment, (closes, zs) in zip(segments, cache):
        for i in range(lookback, len(segment)):
            z = zs[i]
            if z is None:
                continue
            eligible_signal_bars += 1
            if abs(z) < threshold:
                continue
            triggered += 1
            direction = 1 if z > 0 else -1
            if i + hold_bars >= len(segment):
                right_censored += 1
                continue
            exit_index = i + hold_bars
            used_opposite = False
            for j in range(i + 1, i + hold_bars + 1):
                zj = zs[j]
                if zj is not None and direction * zj <= 0.0:
                    exit_index = j
                    used_opposite = True
                    break
            signed_bps = direction * math.log(closes[exit_index] / closes[i]) * 10000.0
            day = segment[i]["timestamp"].date().isoformat()
            daily.setdefault(day, []).append(signed_bps)
            settled += 1
            opposite_exit += int(used_opposite)
            fixed_exit += int(not used_opposite)
    daily_effects = {d: statistics.fmean(v) for d, v in sorted(daily.items())}
    vals = list(daily_effects.values())
    split = len(vals) // 2
    h1, h2 = vals[:split], vals[split:]
    h1_mean, h2_mean = _mean(h1), _mean(h2)
    same_positive = h1_mean is not None and h2_mean is not None and h1_mean > 0 and h2_mean > 0
    same_sign = h1_mean is not None and h2_mean is not None and h1_mean * h2_mean > 0
    effect = _mean(vals)
    return {
        "effect_size": effect,
        "effect_size_unit": "MEAN_DAILY_DIRECTIONAL_LOG_PRICE_RESPONSE_BPS",
        "uncertainty": _uncertainty(vals),
        "effective_independent_sample_size": len(vals),
        "event_density": triggered / eligible_signal_bars if eligible_signal_bars else 0.0,
        "chronological_half_stability": {
            "half_1_effect_size_bps": h1_mean, "half_2_effect_size_bps": h2_mean,
            "half_1_effective_days": len(h1), "half_2_effective_days": len(h2),
            "same_sign": same_sign, "both_positive": same_positive,
        },
        "censoring": {
            "triggered_events": triggered, "settled_events": settled, "right_censored_events": right_censored,
            "opposite_sign_crossing_exits": opposite_exit, "fixed_horizon_exits": fixed_exit,
        },
        "coverage": {
            "eligible_signal_bars": eligible_signal_bars,
            "settled_over_triggered": settled / triggered if triggered else 0.0,
            "active_effective_utc_days": len(vals),
        },
        "daily_effects_bps": daily_effects,
        "local_support": bool(effect is not None and effect > 0 and len(vals) >= MIN_EFFECTIVE_DAYS
                              and len(h1) >= MIN_HALF_DAYS and len(h2) >= MIN_HALF_DAYS and same_positive),
    }


def _key(lb: int, threshold: float, hold: str) -> str:
    return f"L{lb}_Z{threshold:g}_H{hold}"


def _neighbor_keys(lb: int, th: float, hold: str) -> list[str]:
    li, ti, hi = LOOKBACKS.index(lb), THRESHOLDS.index(th), list(HOLDS).index(hold)
    out = []
    for axis, idx, values in ((0, li, LOOKBACKS), (1, ti, THRESHOLDS), (2, hi, list(HOLDS))):
        for d in (-1, 1):
            ni = idx + d
            if 0 <= ni < len(values):
                nlb, nth, nh = lb, th, hold
                if axis == 0: nlb = values[ni]
                elif axis == 1: nth = values[ni]
                else: nh = values[ni]
                out.append(_key(int(nlb), float(nth), str(nh)))
    return out


def _attach_neighborhoods(cells: dict[str, dict[str, Any]]) -> None:
    for cell in cells.values():
        neighbors = [cells[k] for k in _neighbor_keys(cell["lookback"], cell["momentum_threshold_zscore"], cell["hold_horizon"])]
        supported = [n for n in neighbors if n["local_support"]]
        effects = [n["effect_size"] for n in neighbors if n["effect_size"] is not None]
        fraction = len(supported) / len(neighbors) if neighbors else 0.0
        cell["robust_neighborhood_metrics"] = {
            "direct_adjacent_cells": len(neighbors), "adjacent_supported_cells": len(supported),
            "adjacent_support_fraction": fraction,
            "median_adjacent_effect_size_bps": statistics.median(effects) if effects else None,
            "broad_local_neighborhood_support": bool(
                cell["local_support"] and len(neighbors) >= 3 and fraction >= NEIGHBOR_SUPPORT_FRACTION
                and effects and statistics.median(effects) > 0),
        }


def _cross_symbol_regions(symbols: dict[str, dict[str, Any]]) -> dict[str, Any]:
    params = []
    for lb in LOOKBACKS:
        for th in THRESHOLDS:
            for hold in HOLDS:
                k = _key(lb, th, hold)
                rows = [(s, d["asset_class"], d["cells"][k]) for s, d in symbols.items()]
                supported = [(s, a, c) for s, a, c in rows if c["local_support"]]
                assets = sorted(set(a for _, a, _ in supported))
                effects = [c["effect_size"] for _, _, c in rows if c["effect_size"] is not None]
                params.append({
                    "key": k, "lookback": lb, "momentum_threshold_zscore": th, "hold_horizon": hold,
                    "supported_symbol_count": len(supported), "supported_symbols": [s for s, _, _ in supported],
                    "supported_asset_classes": assets, "asset_class_count": len(assets),
                    "median_effect_size_bps": statistics.median(effects) if effects else None,
                    "cross_symbol_support": len(supported) >= CROSS_SYMBOL_MIN_SYMBOLS and len(assets) >= CROSS_SYMBOL_MIN_ASSET_CLASSES,
                })
    by_key = {p["key"]: p for p in params}
    qualifying = {p["key"] for p in params if p["cross_symbol_support"]}
    seen = set(); components = []
    for start in sorted(qualifying):
        if start in seen: continue
        stack = [start]; comp = []
        while stack:
            k = stack.pop()
            if k in seen or k not in qualifying: continue
            seen.add(k); comp.append(k)
            p = by_key[k]
            for nk in _neighbor_keys(p["lookback"], p["momentum_threshold_zscore"], p["hold_horizon"]):
                if nk in qualifying and nk not in seen: stack.append(nk)
        if comp:
            dims = {
                "lookbacks": sorted({by_key[k]["lookback"] for k in comp}),
                "thresholds": sorted({by_key[k]["momentum_threshold_zscore"] for k in comp}),
                "holds": [h for h in HOLDS if h in {by_key[k]["hold_horizon"] for k in comp}],
            }
            varied = sum(len(v) > 1 for v in dims.values())
            components.append({"cells": sorted(comp), "cell_count": len(comp), **dims,
                               "broad_robust_region": len(comp) >= 3 and varied >= 2})
    robust = [c for c in components if c["broad_robust_region"]]
    return {
        "per_parameter_cell": params, "connected_cross_symbol_support_components": components,
        "robust_regions": robust, "robust_region_count": len(robust),
        "criterion": {
            "cell_cross_symbol_support": f">={CROSS_SYMBOL_MIN_SYMBOLS}/7 locally supported symbols across >={CROSS_SYMBOL_MIN_ASSET_CLASSES} asset classes",
            "robust_region": "connected direct-adjacent component with >=3 cells varying in >=2 parameter dimensions",
        },
    }


def evaluate_symbol_rows(rows: list[dict[str, Any]], symbol: str, symbol_id: int, asset_class: str) -> dict[str, Any]:
    rows = _canonicalize(rows)
    segments, gaps, missing = _segments(rows)
    cells: dict[str, dict[str, Any]] = {}
    for lb in LOOKBACKS:
        signal_cache = _precompute_signals(segments, lb)
        for th in THRESHOLDS:
            for hold, bars in HOLDS.items():
                cell = _evaluate_cell(segments, lb, th, bars, signal_cache)
                cell.update({
                    "symbol": symbol, "asset_class": asset_class, "lookback": lb,
                    "momentum_threshold_zscore": th, "hold_horizon": hold,
                    "missingness": {
                        "observed_rows": len(rows), "contiguous_segments": len(segments), "gap_count": gaps,
                        "implied_nontrading_or_missing_M5_slots_between_segments": missing,
                        "fill_or_interpolation_used": False,
                    },
                })
                cells[_key(lb, th, hold)] = cell
    if len(cells) != 80:
        raise TrendMomentumScanError(f"not all 80 parameter cells emitted for {symbol}")
    _attach_neighborhoods(cells)
    return {"symbol_id": symbol_id, "asset_class": asset_class, "rows": len(rows),
            "cells": cells, "cells_emitted": len(cells)}


def evaluate(freeze: dict[str, Any], development_zip: Path, root: Path) -> dict[str, Any]:
    validate_freeze(freeze, root)
    if sha256_file(development_zip) != DEVELOPMENT_SHA256:
        raise TrendMomentumScanError("accepted development ZIP hash mismatch")
    symbols: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(development_zip) as zf:
        for symbol, symbol_id, asset_class in TARGETS:
            symbols[symbol] = evaluate_symbol_rows(_read_symbol(zf, symbol_id, symbol), symbol, symbol_id, asset_class)
    cross = _cross_symbol_regions(symbols)
    asset_coverage: dict[str, Any] = {}
    for _, _, asset in TARGETS:
        asset_coverage.setdefault(asset, {"symbols": [], "cells": 0})
    for symbol, data in symbols.items():
        row = asset_coverage[data["asset_class"]]
        row["symbols"].append(symbol); row["cells"] += len(data["cells"])
    return {
        "schema": "mxm.greenfield.epoch38-trend-momentum-coarse-parameter-region-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_PARAMETER_RESPONSE_SURFACE",
        "authorizing_evidence_epoch": 37, "evidence_epoch": 38, "family": "TREND_MOMENTUM",
        "stage": "PARAMETER_DISCOVERY_STAGE_1_COARSE_MECHANISM_REGION_SCAN",
        "freeze_ref": FREEZE_REF, "implementation": {"version": VERSION},
        "input_attestation": {
            "proposal_hash": PROPOSAL_HASH, "development_capture_plan_sha256": DEVELOPMENT_PLAN_SHA256,
            "development_zip_sha256": sha256_file(development_zip),
            "replacement_capture_plan_sha256": REPLACEMENT_PLAN_SHA256,
            "replacement_zip_sha256": REPLACEMENT_SHA256,
            "replacement_archive_used_for_target_symbols": False,
            "protected_forward_rows_read": 0, "new_market_data_acquired": False,
        },
        "scope": {
            "symbols_processed": len(symbols), "parameter_cells_per_symbol": 80,
            "parameter_cells_evaluated": sum(d["cells_emitted"] for d in symbols.values()),
            "eligible_frontier_remains_open": 1576, "structural_41_are_economic_equivalents": False,
        },
        "asset_class_coverage": asset_coverage, "symbols": symbols, "cross_symbol_robustness": cross,
        "interpretation_boundary": {
            "local_seven_symbol_coarse_proxy_only": True, "family_closure_authorized": False,
            "asset_class_closure_authorized": False, "full_1576_frontier_substituted": False,
            "independent_confirmation": False, "economic_promotion_authorized": False,
            "candidate_identity_created": False, "winner_selected": False, "protected_forward_opened": False,
        },
        "accounting_effect": {"economic_outcomes_opened": 0, "v2_attempts_consumed": 0, "search_budget_change": 0},
        "safety": {"protected_forward_opened": False, "live_orders_authorized": False, "competition_start_authorized": False},
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=VERSION)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--development-zip", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args(argv)
    root = a.root.resolve()
    archive = a.development_zip or root / "research_v3/runtime_v2_inputs/MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip"
    result = evaluate(_load_json(root / FREEZE_REF), archive, root)
    result["freeze_sha256"] = sha256_file(root / FREEZE_REF)
    output = a.output or root / RESULT_REF
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "result_ref": str(output),
                      "parameter_cells_evaluated": result["scope"]["parameter_cells_evaluated"],
                      "robust_region_count": result["cross_symbol_robustness"]["robust_region_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
