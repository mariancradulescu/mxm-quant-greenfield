from __future__ import annotations

import json
import statistics
import zipfile
from pathlib import Path
from typing import Any

from research_v3.breakout_volatility_event_availability_screen import (
    EXPECTED_SERIES,
    LOOKBACK_BARS,
    RESOLUTION_SECONDS,
    SOURCE_CAPTURE_SHA256,
    VOLATILITY_EXPANSION_RATIO,
    BreakoutAvailabilityScreenError,
    _load_rows,
    _sha256_bytes,
    _sha256_file,
)

SOURCE_DECISION_REF = "research_v3/EPOCH15_BREAKOUT_15M_DIRECTIONAL_FOLLOWTHROUGH_DECISION_V1.json"
HORIZON_BARS = 3


class BreakoutFollowthroughScreenError(BreakoutAvailabilityScreenError):
    pass


def _event_direction(rows, index: int) -> int:
    window = rows[index - LOOKBACK_BARS:index + 1]
    if len(window) != LOOKBACK_BARS + 1:
        return 0
    if any(
        (window[pos][0] - window[pos - 1][0]).total_seconds() != RESOLUTION_SECONDS
        for pos in range(1, len(window))
    ):
        return 0
    prior = window[:-1]
    current = window[-1]
    prior_high = max(bar[2] for bar in prior)
    prior_low = min(bar[3] for bar in prior)
    prior_median_range = statistics.median(bar[2] - bar[3] for bar in prior)
    current_range = current[2] - current[3]
    is_expansion = (
        current_range >= VOLATILITY_EXPANSION_RATIO * prior_median_range
        if prior_median_range > 0
        else current_range > 0
    )
    if not is_expansion:
        return 0
    if current[4] > prior_high:
        return 1
    if current[4] < prior_low:
        return -1
    return 0


def _screen_rows_followthrough(rows) -> dict[str, Any]:
    events_detected = 0
    events_with_valid_followthrough = 0
    events_without_valid_followthrough = 0
    up_events = 0
    down_events = 0
    up_continuation = 0
    up_reversal = 0
    up_flat = 0
    down_continuation = 0
    down_reversal = 0
    down_flat = 0

    for index in range(LOOKBACK_BARS, len(rows)):
        direction = _event_direction(rows, index)
        if direction == 0:
            continue
        events_detected += 1
        if direction > 0:
            up_events += 1
        else:
            down_events += 1

        future_index = index + HORIZON_BARS
        if future_index >= len(rows):
            events_without_valid_followthrough += 1
            continue
        future_window = rows[index:future_index + 1]
        if any(
            (future_window[pos][0] - future_window[pos - 1][0]).total_seconds() != RESOLUTION_SECONDS
            for pos in range(1, len(future_window))
        ):
            events_without_valid_followthrough += 1
            continue

        events_with_valid_followthrough += 1
        delta = rows[future_index][4] - rows[index][4]
        if direction > 0:
            if delta > 0:
                up_continuation += 1
            elif delta < 0:
                up_reversal += 1
            else:
                up_flat += 1
        else:
            if delta < 0:
                down_continuation += 1
            elif delta > 0:
                down_reversal += 1
            else:
                down_flat += 1

    continuation = up_continuation + down_continuation
    reversal = up_reversal + down_reversal
    flat = up_flat + down_flat
    nonflat = continuation + reversal
    return {
        "events_detected": events_detected,
        "events_with_valid_followthrough": events_with_valid_followthrough,
        "events_without_valid_followthrough": events_without_valid_followthrough,
        "up_events": up_events,
        "down_events": down_events,
        "up_continuation": up_continuation,
        "up_reversal": up_reversal,
        "up_flat": up_flat,
        "down_continuation": down_continuation,
        "down_reversal": down_reversal,
        "down_flat": down_flat,
        "continuation": continuation,
        "reversal": reversal,
        "flat": flat,
        "continuation_fraction_nonflat": continuation / nonflat if nonflat else None,
    }


def execute(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    observed_sha = _sha256_file(source)
    if observed_sha != SOURCE_CAPTURE_SHA256:
        raise BreakoutFollowthroughScreenError(
            f"capture hash mismatch: expected {SOURCE_CAPTURE_SHA256}, observed {observed_sha}"
        )

    with zipfile.ZipFile(source) as archive:
        manifest = json.loads(archive.read("capture_manifest.json"))
        complete = [
            item for item in manifest.get("series", [])
            if item.get("capture_status") == "SERIES_CAPTURE_COMPLETE"
        ]
        if len(complete) != EXPECTED_SERIES:
            raise BreakoutFollowthroughScreenError(
                f"expected {EXPECTED_SERIES} complete series, observed {len(complete)}"
            )
        if manifest.get("resolution") != "M5":
            raise BreakoutFollowthroughScreenError("capture resolution is not M5")
        if manifest.get("protected_evidence_opened") is not False:
            raise BreakoutFollowthroughScreenError("protected evidence flag is not false")
        if manifest.get("economic_outcomes_opened") != 0:
            raise BreakoutFollowthroughScreenError("capture already records economic outcomes")

        per_symbol: dict[str, Any] = {}
        total_rows = 0
        for item in complete:
            symbol = item["broker_symbol"]
            raw = archive.read(item["file"])
            if _sha256_bytes(raw) != item.get("sha256"):
                raise BreakoutFollowthroughScreenError(f"{symbol}: manifest file hash mismatch")
            rows = _load_rows(raw, symbol)
            if len(rows) != item.get("row_count"):
                raise BreakoutFollowthroughScreenError(f"{symbol}: manifest row count mismatch")
            if item.get("synthetic_fill") is not False or item.get("forward_fill") is not False:
                raise BreakoutFollowthroughScreenError(f"{symbol}: synthetic/forward fill forbidden")
            result = _screen_rows_followthrough(rows)
            result["rows"] = len(rows)
            per_symbol[symbol] = result
            total_rows += len(rows)

    additive = [
        "events_detected", "events_with_valid_followthrough", "events_without_valid_followthrough",
        "up_events", "down_events", "up_continuation", "up_reversal", "up_flat",
        "down_continuation", "down_reversal", "down_flat", "continuation", "reversal", "flat",
    ]
    aggregate = {key: sum(v[key] for v in per_symbol.values()) for key in additive}
    aggregate["symbols"] = len(per_symbol)
    aggregate["rows"] = total_rows
    nonflat = aggregate["continuation"] + aggregate["reversal"]
    aggregate["continuation_fraction_nonflat"] = (
        aggregate["continuation"] / nonflat if nonflat else None
    )

    return {
        "schema": "mxm.greenfield.breakout-volatility-15m-directional-followthrough.v1",
        "status": "COMPLETE_NON_ECONOMIC_BREAKOUT_15M_DIRECTIONAL_FOLLOWTHROUGH_SCREEN",
        "source_capture_sha256": SOURCE_CAPTURE_SHA256,
        "source_decision_ref": SOURCE_DECISION_REF,
        "resolution": "M5",
        "frozen_law": {
            "event_lookback_bars": LOOKBACK_BARS,
            "event_volatility_expansion_ratio": VOLATILITY_EXPANSION_RATIO,
            "followthrough_horizon_bars": HORIZON_BARS,
            "followthrough_horizon": "15m",
            "parameter_variation": "NONE",
        },
        "per_symbol": per_symbol,
        "aggregate": aggregate,
        "interpretation_boundary": (
            "Directional continuation/reversal counts only. No magnitude, returns, PnL, costs, "
            "ranking, promotion, inferential rejection, economic identity, family closure, "
            "outer, or protected-forward evidence."
        ),
        "economic_effect": {
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "search_budget_change": 0,
        },
        "broader_universe_status": "OPEN_1578_ELIGIBLE_POST_EXCLUSION_FRONTIER_CANDIDATES",
        "family_exhaustion_claimed": False,
    }
