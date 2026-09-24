from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

SOURCE_CAPTURE_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
SOURCE_ACCEPTANCE_REF = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json"
SOURCE_DECISION_REF = "research_v3/EPOCH14_BREAKOUT_VOLATILITY_EVENT_AVAILABILITY_DECISION_V1.json"
LOOKBACK_BARS = 24
VOLATILITY_EXPANSION_RATIO = 1.5
EXPECTED_SERIES = 40
RESOLUTION_SECONDS = 300


class BreakoutAvailabilityScreenError(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_rows(raw: bytes, symbol: str) -> list[tuple[datetime, float, float, float, float]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    required = {"time_utc", "open", "high", "low", "close"}
    if not required.issubset(reader.fieldnames or []):
        raise BreakoutAvailabilityScreenError(f"{symbol}: required OHLC columns missing")
    rows: list[tuple[datetime, float, float, float, float]] = []
    previous: datetime | None = None
    for row in reader:
        timestamp = _parse_utc(row["time_utc"])
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        if high < max(open_, close) or low > min(open_, close) or high < low:
            raise BreakoutAvailabilityScreenError(f"{symbol}: OHLC invariant failure")
        if previous is not None and timestamp <= previous:
            raise BreakoutAvailabilityScreenError(f"{symbol}: timestamps are not strictly increasing")
        previous = timestamp
        rows.append((timestamp, open_, high, low, close))
    return rows


def _screen_rows(rows: list[tuple[datetime, float, float, float, float]]) -> dict[str, Any]:
    eligible = 0
    breakout_up = 0
    breakout_down = 0
    expansion = 0
    event_up = 0
    event_down = 0

    for index in range(LOOKBACK_BARS, len(rows)):
        window = rows[index - LOOKBACK_BARS:index + 1]
        if any(
            (window[pos][0] - window[pos - 1][0]).total_seconds() != RESOLUTION_SECONDS
            for pos in range(1, len(window))
        ):
            continue

        eligible += 1
        prior = window[:-1]
        current = window[-1]
        prior_high = max(bar[2] for bar in prior)
        prior_low = min(bar[3] for bar in prior)
        prior_ranges = [bar[2] - bar[3] for bar in prior]
        prior_median_range = statistics.median(prior_ranges)
        current_range = current[2] - current[3]

        is_up = current[4] > prior_high
        is_down = current[4] < prior_low
        if is_up:
            breakout_up += 1
        if is_down:
            breakout_down += 1

        is_expansion = (
            current_range >= VOLATILITY_EXPANSION_RATIO * prior_median_range
            if prior_median_range > 0
            else current_range > 0
        )
        if is_expansion:
            expansion += 1
        if is_up and is_expansion:
            event_up += 1
        if is_down and is_expansion:
            event_down += 1

    events = event_up + event_down
    return {
        "eligible_contiguous_windows": eligible,
        "breakout_only_up": breakout_up,
        "breakout_only_down": breakout_down,
        "range_expansion_windows": expansion,
        "event_up": event_up,
        "event_down": event_down,
        "events": events,
        "event_availability_rate": events / eligible if eligible else None,
    }


def execute(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    observed_sha = _sha256_file(source)
    if observed_sha != SOURCE_CAPTURE_SHA256:
        raise BreakoutAvailabilityScreenError(
            f"capture hash mismatch: expected {SOURCE_CAPTURE_SHA256}, observed {observed_sha}"
        )

    with zipfile.ZipFile(source) as archive:
        try:
            manifest = json.loads(archive.read("capture_manifest.json"))
        except KeyError as exc:
            raise BreakoutAvailabilityScreenError("top-level capture_manifest.json missing") from exc

        if manifest.get("resolution") != "M5":
            raise BreakoutAvailabilityScreenError("capture resolution is not M5")
        if manifest.get("protected_evidence_opened") is not False:
            raise BreakoutAvailabilityScreenError("protected evidence flag is not false")
        if manifest.get("economic_outcomes_opened") != 0:
            raise BreakoutAvailabilityScreenError("capture already records economic outcomes")

        complete = [
            item for item in manifest.get("series", [])
            if item.get("capture_status") == "SERIES_CAPTURE_COMPLETE"
        ]
        if len(complete) != EXPECTED_SERIES:
            raise BreakoutAvailabilityScreenError(
                f"expected {EXPECTED_SERIES} complete series, observed {len(complete)}"
            )

        per_symbol: dict[str, Any] = {}
        total_rows = 0
        for item in complete:
            symbol = item["broker_symbol"]
            raw = archive.read(item["file"])
            if _sha256_bytes(raw) != item.get("sha256"):
                raise BreakoutAvailabilityScreenError(f"{symbol}: manifest file hash mismatch")
            rows = _load_rows(raw, symbol)
            if len(rows) != item.get("row_count"):
                raise BreakoutAvailabilityScreenError(f"{symbol}: manifest row count mismatch")
            if item.get("synthetic_fill") is not False or item.get("forward_fill") is not False:
                raise BreakoutAvailabilityScreenError(f"{symbol}: synthetic/forward fill forbidden")
            result = _screen_rows(rows)
            result["rows"] = len(rows)
            per_symbol[symbol] = result
            total_rows += len(rows)

    aggregate = {
        "symbols": len(per_symbol),
        "rows": total_rows,
        "eligible_contiguous_windows": sum(v["eligible_contiguous_windows"] for v in per_symbol.values()),
        "breakout_only_up": sum(v["breakout_only_up"] for v in per_symbol.values()),
        "breakout_only_down": sum(v["breakout_only_down"] for v in per_symbol.values()),
        "range_expansion_windows": sum(v["range_expansion_windows"] for v in per_symbol.values()),
        "event_up": sum(v["event_up"] for v in per_symbol.values()),
        "event_down": sum(v["event_down"] for v in per_symbol.values()),
        "events": sum(v["events"] for v in per_symbol.values()),
    }
    aggregate["event_availability_rate"] = (
        aggregate["events"] / aggregate["eligible_contiguous_windows"]
        if aggregate["eligible_contiguous_windows"] else None
    )

    return {
        "schema": "mxm.greenfield.breakout-volatility-event-availability-screen.v1",
        "status": "COMPLETE_NON_ECONOMIC_BREAKOUT_VOLATILITY_EVENT_AVAILABILITY_SCREEN",
        "source_capture_ref": SOURCE_ACCEPTANCE_REF,
        "source_capture_sha256": SOURCE_CAPTURE_SHA256,
        "source_decision_ref": SOURCE_DECISION_REF,
        "resolution": "M5",
        "prospective_event_law": {
            "lookback_bars": LOOKBACK_BARS,
            "lookback_duration": "2h at M5",
            "volatility_expansion_ratio": VOLATILITY_EXPANSION_RATIO,
            "breakout_up": "close_t > max(high) over preceding 24 consecutive bars",
            "breakout_down": "close_t < min(low) over preceding 24 consecutive bars",
            "range_reference": "median(high-low) over preceding 24 consecutive bars",
            "gap_policy": "reject any 25-bar window containing a non-300-second interval",
            "parameter_variation": "NONE",
        },
        "per_symbol": per_symbol,
        "aggregate": aggregate,
        "interpretation_boundary": (
            "Event availability only. No post-event returns, PnL, costs, ranking, promotion, "
            "inferential rejection, economic identity, family closure, outer, or protected-forward evidence."
        ),
        "economic_effect": {
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "search_budget_change": 0,
        },
        "broader_universe_status": "OPEN_1578_ELIGIBLE_POST_EXCLUSION_FRONTIER_CANDIDATES",
        "family_exhaustion_claimed": False,
    }
