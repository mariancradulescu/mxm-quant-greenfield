import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.regime_context_conditioned_epoch29_screen import (
    bh_adjust,
    canonicalize_identical_duplicates,
    evaluate_symbol,
    exact_binomial_greater,
    validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "research_v3/EPOCH29_REGIME_CONTEXT_CONDITIONED_FRONTIER_FREEZE_V1.json"
REGISTRY_PATH = ROOT / "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"


def _row(index: int, *, close: float = 100.0, high: float = 100.5, low: float = 99.5):
    timestamp = datetime(2026, 6, 15, tzinfo=timezone.utc) + timedelta(minutes=5 * index)
    return {
        "time_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "timestamp": timestamp,
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": 1.0,
    }


def _rows_with_event(*, count: int = 68, gap_before: int | None = None):
    rows = [_row(index) for index in range(count)]
    rows[64] = _row(64, close=102.0, high=102.5, low=100.5)
    rows[65] = _row(65, close=102.0, high=102.5, low=101.5)
    rows[66] = _row(66, close=102.0, high=102.5, low=101.5)
    if count > 67:
        rows[67] = _row(67, close=103.0, high=103.5, low=102.5)
    if gap_before is not None:
        for index in range(gap_before, count):
            rows[index]["timestamp"] += timedelta(minutes=5)
            rows[index]["time_utc"] = rows[index]["timestamp"].isoformat().replace("+00:00", "Z")
    return rows


class Epoch29RegimeContextScreenTests(unittest.TestCase):
    def test_freeze_binds_exact_current_frontier_and_fixed_law(self):
        freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        validate_freeze(freeze, REGISTRY_PATH)

        altered = copy.deepcopy(freeze)
        altered["preregistered_structural_law"]["inference"]["fdr_q"] = 0.10
        with self.assertRaisesRegex(ValueError, "fixed law"):
            validate_freeze(altered, REGISTRY_PATH)

    def test_exact_binomial_and_bh_adjustment_are_bounded(self):
        self.assertEqual(exact_binomial_greater(5, 6), 0.109375)
        adjusted = bh_adjust({"a": 0.001, "b": 0.02, "c": 0.9})
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])
        self.assertTrue(all(0.0 <= value <= 1.0 for value in adjusted.values()))

    def test_duplicate_rows_collapse_only_when_identical(self):
        rows = [_row(0), _row(1)]
        canonical, removed = canonicalize_identical_duplicates(rows + [dict(rows[1])])
        self.assertEqual((len(canonical), removed), (2, 1))
        conflict = dict(rows[1], close=101.0)
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            canonicalize_identical_duplicates([rows[1], conflict])

    def test_regime_is_lagged_and_event_outcome_uses_three_future_bars(self):
        result = evaluate_symbol(_rows_with_event())
        self.assertEqual(result["selected_events"], 1)
        self.assertEqual(result["unclassified_events"], 0)
        high = result["contexts"]["HIGH_VOL_EXPANDING"]
        self.assertEqual(high["selected_events"], 1)
        self.assertEqual(high["settled_events"], 1)
        self.assertEqual(high["chronological_half_1"]["continuation"], 0)
        self.assertEqual(high["chronological_half_2"]["continuation"], 1)
        self.assertEqual(result["contexts"]["LOW_VOL_COMPRESSED"]["selected_events"], 0)

    def test_right_censoring_and_timestamp_gaps_block_outcome_crossing(self):
        censored = evaluate_symbol(_rows_with_event(count=67))
        high = censored["contexts"]["HIGH_VOL_EXPANDING"]
        self.assertEqual(high["right_censored_events"], 1)
        self.assertEqual(high["settled_events"], 0)

        across_gap = evaluate_symbol(_rows_with_event(gap_before=65))
        self.assertGreater(across_gap["contiguous_segments"], 1)
        self.assertEqual(
            across_gap["contexts"]["HIGH_VOL_EXPANDING"]["right_censored_events"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
