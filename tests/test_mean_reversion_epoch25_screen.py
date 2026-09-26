import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.mean_reversion_epoch25_screen import (
    EXPECTED_SYMBOLS,
    bh_adjust,
    canonicalize_identical_duplicates,
    evaluate_symbol,
    exact_binomial_greater,
    signal_direction,
    validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]


def _row(index: int, close: float, *, offset_minutes: int = 0):
    timestamp = datetime(2026, 6, 15, tzinfo=timezone.utc) + timedelta(
        minutes=5 * index + offset_minutes
    )
    return {
        "time_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "timestamp": timestamp,
        "open": float(close),
        "high": float(close) + 1.0,
        "low": float(close) - 1.0,
        "close": float(close),
        "tick_volume": 1.0,
    }


class Epoch25MeanReversionScreenTests(unittest.TestCase):
    def test_prospective_freeze_matches_exact_current_representatives(self):
        freeze = json.loads(
            (ROOT / "research_v3/EPOCH25_MEAN_REVERSION_FRONTIER_FREEZE_V1.json").read_text()
        )
        validate_freeze(freeze)
        symbols = tuple(
            (item["broker_symbol"], item["symbol_id"])
            for item in freeze["scope"]["representatives"]
        )
        self.assertEqual(symbols, EXPECTED_SYMBOLS)
        self.assertEqual(len(symbols), 41)

        changed = copy.deepcopy(freeze)
        changed["preregistered_structural_law"]["signal"]["threshold"] = 1.5
        with self.assertRaisesRegex(ValueError, "fixed law"):
            validate_freeze(changed)

    def test_exact_binomial_and_bh_adjustment(self):
        self.assertEqual(exact_binomial_greater(5, 6), 0.109375)
        adjusted = bh_adjust({"a": 0.001, "b": 0.02, "c": 0.9})
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])
        self.assertTrue(all(0.0 <= value <= 1.0 for value in adjusted.values()))

    def test_signal_uses_only_completed_window_and_is_directional(self):
        above = [_row(i, 100.0) for i in range(11)] + [_row(11, 110.0)]
        below = [_row(i, 100.0) for i in range(11)] + [_row(11, 90.0)]
        self.assertEqual(signal_direction(above), -1)
        self.assertEqual(signal_direction(below), 1)
        self.assertEqual(signal_direction([_row(i, 100.0) for i in range(12)]), 0)
        altered_future = above + [_row(i, 1.0) for i in range(12, 24)]
        self.assertEqual(signal_direction(altered_future[:12]), -1)
        canonical, removed = canonicalize_identical_duplicates(above + [dict(above[-1])])
        self.assertEqual((len(canonical), removed), (12, 1))

    def test_reversion_outcome_and_right_censor_are_reported(self):
        rows = [_row(i, 100.0) for i in range(11)] + [_row(11, 110.0)]
        rows.extend(_row(i, 110.0 - i) for i in range(12, 24))
        result = evaluate_symbol(rows)
        self.assertGreaterEqual(result["admitted_signals"], 1)
        self.assertEqual(result["successes"], 1)
        self.assertEqual(result["failures"], 0)

        censored = evaluate_symbol(rows[:23])
        self.assertEqual(censored["right_censored_future_response"], 1)
        self.assertEqual(censored["settled_signals"], 0)

    def test_gaps_block_future_settlement_and_duplicate_conflicts_fail_closed(self):
        rows = [_row(i, 100.0) for i in range(11)] + [_row(11, 110.0)]
        rows.extend(_row(i, 109.0 - i, offset_minutes=5 if i >= 15 else 0) for i in range(12, 24))
        result = evaluate_symbol(rows)
        self.assertEqual(result["right_censored_future_response"], 1)
        self.assertGreater(result["contiguous_segments"], 1)

        duplicate = dict(rows[0])
        duplicate["close"] = 101.0
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            canonicalize_identical_duplicates([rows[0], duplicate])

    def test_flat_response_is_separate_from_nonflat_test_denominator(self):
        rows = [_row(i, 100.0) for i in range(11)] + [_row(11, 110.0)]
        rows.extend(_row(i, 110.0) for i in range(12, 24))
        result = evaluate_symbol(rows)
        self.assertEqual(result["flat_settled_signals"], 1)
        self.assertEqual(result["settled_nonflat_signals"], 0)
        self.assertEqual(result["one_sided_exact_binomial_p"], 1.0)


if __name__ == "__main__":
    unittest.main()
