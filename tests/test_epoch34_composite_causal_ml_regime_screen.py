import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.epoch34_composite_causal_ml_regime_screen import (
    STATE_NAMES,
    canonicalize_identical_duplicates,
    evaluate_symbol,
    holm_adjust,
    validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "research_v3/EPOCH34_COMPOSITE_CAUSAL_ML_REGIME_FRONTIER_FREEZE_V1.json"


def _row(index, base):
    timestamp = base + timedelta(minutes=5 * index)
    close = 100.0 + index * 0.01
    return {
        "time_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "timestamp": timestamp,
        "open": close,
        "high": close + 0.1 + (index % 7) * 0.01,
        "low": close - 0.1,
        "close": close,
        "tick_volume": float(index % 5),
    }


class Epoch34CompositeCausalRegimeTests(unittest.TestCase):
    def test_freeze_binds_exact_accepted_proposal_full_frontier_and_fixed_law(self):
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        registry = validate_freeze(freeze, ROOT)
        self.assertEqual(len(registry["representatives"]), 41)
        altered = copy.deepcopy(freeze)
        altered["preregistered_structural_law"]["paired_models"]["learning_rate"] = 0.1
        with self.assertRaisesRegex(ValueError, "fixed"):
            validate_freeze(altered, ROOT)

    def test_duplicate_conflicts_fail_and_holm_is_monotone_and_bounded(self):
        timestamp = datetime(2026, 6, 15, tzinfo=timezone.utc)
        row = {
            "time_utc": "2026-06-15T00:00:00Z",
            "timestamp": timestamp,
            "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "tick_volume": 2.0,
        }
        collapsed, removed = canonicalize_identical_duplicates([row, dict(row)])
        self.assertEqual((len(collapsed), removed), (1, 1))
        with self.assertRaisesRegex(ValueError, "conflicting"):
            canonicalize_identical_duplicates([row, dict(row, close=1.6)])
        adjusted = holm_adjust({"a": 0.001, "b": 0.02, "c": 0.9})
        self.assertTrue(all(0.0 <= value <= 1.0 for value in adjusted.values()))
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertEqual(set(STATE_NAMES), {
            f"{vol}_{activity}_{session}"
            for vol in ("LOW_VOL", "HIGH_VOL")
            for activity in ("LOW_ACTIVITY", "HIGH_ACTIVITY")
            for session in ("NON_OVERLAP", "OVERLAP")
        })

    def test_test_period_labels_do_not_change_frozen_training_models(self):
        from research_v3.epoch34_composite_causal_ml_regime_screen import _fit_models

        start = datetime(2026, 6, 15, tzinfo=timezone.utc)
        cutoff = datetime(2026, 7, 30, tzinfo=timezone.utc)
        rows = []
        for day in range(50):
            base = start + timedelta(days=day)
            rows.extend(_row(index, base) for index in range(64))
        changed = [dict(row) for row in rows]
        for row in changed:
            if row["timestamp"] >= cutoff:
                row["close"] *= 1.7
                row["high"] = row["close"] + 0.1
                row["low"] = row["close"] - 0.1
        first = _fit_models(rows, cutoff)
        second = _fit_models(changed, cutoff)
        self.assertEqual(first, second)

    def test_predictive_features_stop_at_previous_bar(self):
        from research_v3.epoch34_composite_causal_ml_regime_screen import _predictive_features

        start = datetime(2026, 6, 15, tzinfo=timezone.utc)
        rows = [_row(index, start) for index in range(80)]
        original = _predictive_features(rows, 70)
        changed = [dict(row) for row in rows]
        changed[70]["close"] *= 2.0
        self.assertEqual(original, _predictive_features(changed, 70))

    def test_screen_reports_ineligible_halves_without_claiming_support(self):
        start = datetime(2026, 6, 15, tzinfo=timezone.utc)
        rows = [_row(index, start) for index in range(80)]
        result = evaluate_symbol(rows, "TEST", 1, datetime(2026, 7, 30, tzinfo=timezone.utc))
        self.assertFalse(result["minimum_data_sufficiency_pass"])
        self.assertFalse(result["raw_incremental_structural_pass"])
        self.assertEqual(result["max_half_p_value"], 1.0)


if __name__ == "__main__":
    unittest.main()
