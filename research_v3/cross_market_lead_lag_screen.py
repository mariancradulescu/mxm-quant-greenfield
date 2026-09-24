"""Deterministic, non-economic one-bar cross-market lead-lag screen."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SOURCE_CAPTURE_SHA256 = "36de60e2991bec99596b5b11da43efe3d62dafa8747c043a25c394fd3f9a4d49"
SOURCE_CAPTURE_REF = "evidence/CROSSALIGN_FOUR_SYMBOL_M5_CAPTURE_ACCEPTANCE_V1.json"
PLAN_REF = "data/CROSSALIGN_FOUR_SYMBOL_M5_CAPTURE_PLAN_V1.json"
SYMBOLS = ("AUDJPY", "AUS200", "Brent-F", "BCHUSD")
INTERVAL = {
    "start_utc": "2026-07-20T00:00:00Z",
    "end_utc": "2026-09-13T23:59:59Z",
}
M5 = timedelta(minutes=5)


class LeadLagScreenError(ValueError):
    pass


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _direction(open_: float, close: float) -> int:
    if close > open_:
        return 1
    if close < open_:
        return -1
    return 0


def _read_series(raw: bytes, symbol: str) -> dict[datetime, tuple[float, float]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    expected = ("timestamp_utc", "open", "high", "low", "close", "tick_volume")
    if tuple(reader.fieldnames or ()) != expected:
        raise LeadLagScreenError(f"{symbol}: single-price trendbar fields are required")
    rows: dict[datetime, tuple[float, float]] = {}
    previous: datetime | None = None
    for row in reader:
        try:
            timestamp = _utc(str(row["timestamp_utc"]))
            values = tuple(float(row[key]) for key in expected[1:])
        except (KeyError, TypeError, ValueError) as exc:
            raise LeadLagScreenError(f"{symbol}: invalid numeric or timestamp field") from exc
        if previous is not None and timestamp <= previous:
            raise LeadLagScreenError(f"{symbol}: timestamps are not strictly increasing")
        if not all(math.isfinite(value) for value in values):
            raise LeadLagScreenError(f"{symbol}: non-finite trendbar field")
        open_, high, low, close, _volume = values
        if high < max(open_, close) or low > min(open_, close):
            raise LeadLagScreenError(f"{symbol}: invalid OHLC invariant")
        if timestamp in rows:
            raise LeadLagScreenError(f"{symbol}: duplicate timestamp")
        rows[timestamp] = (open_, close)
        previous = timestamp
    if not rows:
        raise LeadLagScreenError(f"{symbol}: empty series")
    return rows


def _load_capture(path: str | Path) -> tuple[dict[str, dict[datetime, tuple[float, float]]], dict[str, Any]]:
    path = Path(path)
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != SOURCE_CAPTURE_SHA256:
        raise LeadLagScreenError("capture ZIP hash does not match accepted CROSSALIGN bytes")
    with zipfile.ZipFile(path) as archive:
        try:
            manifest = json.loads(archive.read("MXM_CROSSALIGN_FOUR_SYMBOL_M5_NON_ECONOMIC_V1/capture_manifest.json"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise LeadLagScreenError("accepted capture manifest is missing or invalid") from exc
        if manifest.get("economic_outcomes_opened") != 0 or manifest.get("v2_attempts_consumed") != 0:
            raise LeadLagScreenError("capture is economically contaminated")
        if manifest.get("resolution") != "M5" or manifest.get("requested_interval") != INTERVAL:
            raise LeadLagScreenError("capture resolution or interval is not the accepted scope")
        series: dict[str, dict[datetime, tuple[float, float]]] = {}
        for item in manifest.get("series") or []:
            symbol = str(item.get("broker_symbol"))
            if symbol in SYMBOLS and item.get("capture_status") == "SERIES_CAPTURE_COMPLETE":
                rel = str(item["file"])
                series[symbol] = _read_series(
                    archive.read("MXM_CROSSALIGN_FOUR_SYMBOL_M5_NON_ECONOMIC_V1/" + rel),
                    symbol,
                )
        if set(series) != set(SYMBOLS):
            raise LeadLagScreenError("capture does not contain the exact four accepted series")
    return series, {"capture_sha256": observed, "manifest": manifest}


def _wilson_interval(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, centre - radius), min(1.0, centre + radius)]


def execute(path: str | Path, *, expected_common_timestamps: int = 9539,
            expected_pairs: int = 9455) -> dict[str, Any]:
    series, metadata = _load_capture(path)
    common = set.intersection(*(set(rows) for rows in series.values()))
    ordered = sorted(common)
    pairs = [
        (timestamp, timestamp + M5)
        for timestamp in ordered
        if timestamp + M5 in common
    ]
    if len(common) != expected_common_timestamps or len(pairs) != expected_pairs:
        raise LeadLagScreenError("accepted capture alignment counts do not match the frozen scope")
    segments: list[list[tuple[datetime, datetime]]] = []
    for pair in pairs:
        if not segments or pair[0] != segments[-1][-1][1]:
            segments.append([])
        segments[-1].append(pair)

    pair_results: dict[str, Any] = {}
    for source in SYMBOLS:
        for target in SYMBOLS:
            if source == target:
                continue
            counts: Counter[str] = Counter()
            segment_counts: list[dict[str, Any]] = []
            for segment in segments:
                local: Counter[str] = Counter()
                for timestamp, following in segment:
                    source_direction = _direction(*series[source][timestamp])
                    target_direction = _direction(*series[target][following])
                    key = f"{source_direction},{target_direction}"
                    counts[key] += 1
                    local[key] += 1
                segment_counts.append({
                    "start_utc": segment[0][0].isoformat().replace("+00:00", "Z"),
                    "end_utc": segment[-1][1].isoformat().replace("+00:00", "Z"),
                    "pairs": len(segment),
                    "direction_contingency": dict(sorted(local.items())),
                })
            same = counts.get("1,1", 0) + counts.get("-1,-1", 0)
            nonzero = sum(value for key, value in counts.items()
                          if key.split(",") != ["0", "0"])
            pair_results[f"{source}|{target}"] = {
                "source": source,
                "target": target,
                "pairs": sum(counts.values()),
                "direction_contingency": dict(sorted(counts.items())),
                "same_direction_fraction_nonzero": same / nonzero if nonzero else None,
                "same_direction_fraction_95ci": _wilson_interval(same, nonzero),
                "contiguous_segments": segment_counts,
            }
    result = {
        "schema": "mxm.greenfield.cross-market-lead-lag-one-bar-screen.v1",
        "status": "COMPLETE_NON_ECONOMIC_CROSS_MARKET_SCREEN",
        "source_capture_ref": SOURCE_CAPTURE_REF,
        "source_capture_sha256": metadata["capture_sha256"],
        "plan_ref": PLAN_REF,
        "symbols": list(SYMBOLS),
        "resolution": "M5",
        "interval": INTERVAL,
        "observation_law": "At each strictly consecutive common pair, compare source bar direction (close versus open) at t with target bar direction at t+5m; gaps and missing bars are excluded.",
        "pairs": len(pairs),
        "common_timestamps": len(common),
        "contiguous_valid_segments": len(segments),
        "ordered_pair_reports": pair_results,
        "interpretation_boundary": "Descriptive association only; no causality, returns, costs, PnL, ranking, promotion, or economic outcome.",
        "economic_effect": {"economic_outcomes_opened": 0, "v2_attempts_consumed": 0},
        "safety": {"protected_forward_opened": False, "live_orders_authorized": False},
    }
    return result
