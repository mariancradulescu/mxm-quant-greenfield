import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.mean_reversion_magnitude_epoch36_screen import (
    _exact_positive_sign_p,
    _screen_rows,
    _split_inference,
    benjamini_hochberg,
    validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "research_v3/EPOCH36_MEAN_REVERSION_MAGNITUDE_PERSISTENCE_FRONTIER_FREEZE_V1.json"


def _rows(closes):
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    return [
        {
            "timestamp": start + timedelta(minutes=5 * index),
            "open": float(close),
            "high": float(close) + 0.1,
            "low": float(close) - 0.1,
            "close": float(close),
            "tick_volume": 1.0,
        }
        for index, close in enumerate(closes)
    ]


class Epoch36MeanReversionMagnitudeTests(unittest.TestCase):
    def test_freeze_binds_exact_accepted_proposal_and_fixed_magnitude_estimand(self):
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        registry = validate_freeze(freeze, ROOT)
        self.assertEqual(len(registry["representatives"]), 41)

        changed = copy.deepcopy(freeze)
        changed["preregistered_structural_law"]["extreme_z_threshold"] = 1.5
        with self.assertRaisesRegex(ValueError, "estimand or inference law"):
            validate_freeze(changed, ROOT)

    def test_unsigned_distance_contraction_is_positive_for_upper_and_lower_extremes(self):
        for extreme in (110.0, 90.0):
            rows = _rows([100.0] * 11 + [extreme] + [100.0] * 12)
            result = _screen_rows(rows, 1)
            self.assertEqual(result["event_candidates"], 1)
            self.assertEqual(result["eligible_events"], 1)
            self.assertGreater(
                result["daily_standardized_absolute_distance_contractions"]["2026-06-15"],
                0.0,
            )

    def test_future_close_changes_outcome_not_prior_event_admission(self):
        closes = [100.0] * 11 + [110.0] + [100.0] * 12
        original = _screen_rows(_rows(closes), 1)
        altered = list(closes)
        altered[23] = 120.0
        changed = _screen_rows(_rows(altered), 1)
        self.assertEqual(original["event_candidates"], 1)
        self.assertGreater(changed["event_candidates"], original["event_candidates"])
        self.assertLess(
            changed["daily_standardized_absolute_distance_contractions"]["2026-06-15"],
            0.0,
        )

    def test_noncontiguous_forward_window_is_excluded(self):
        rows = _rows([100.0] * 11 + [110.0] + [100.0] * 12)
        for row in rows[17:]:
            row["timestamp"] += timedelta(minutes=5)
        result = _screen_rows(rows, 1)
        self.assertEqual(result["event_candidates"], 1)
        self.assertEqual(result["eligible_events"], 0)
        self.assertEqual(result["excluded_events"]["incomplete_or_noncontiguous_forward_window"], 1)

    def test_only_first_eligible_event_per_utc_date_is_retained(self):
        closes = [100.0] * 11 + [110.0] + [100.0] * 11 + [110.0] + [100.0] * 12
        result = _screen_rows(_rows(closes), 1)
        self.assertEqual(result["event_candidates"], 2)
        self.assertEqual(result["eligible_events"], 1)
        self.assertEqual(result["excluded_events"]["duplicate_utc_date_event"], 1)

    def test_sign_test_omits_ties_and_halves_are_chronological(self):
        self.assertEqual(_exact_positive_sign_p([1.0, -1.0, 0.0]), 0.75)
        daily = {f"2026-07-{day:02d}": float(day - 11) for day in range(1, 23)}
        halves, sufficient = _split_inference(daily)
        self.assertTrue(sufficient)
        self.assertEqual((halves[0]["eligible_dates"], halves[1]["eligible_dates"]), (11, 11))
        self.assertLess(
            halves[0]["median_standardized_absolute_distance_contraction"],
            halves[1]["median_standardized_absolute_distance_contraction"],
        )

    def test_bh_includes_all_symbols_and_is_monotone(self):
        adjusted = benjamini_hochberg({"a": 0.001, "b": 0.01, "c": 0.04, "insufficient": 1.0})
        self.assertEqual(set(adjusted), {"a", "b", "c", "insufficient"})
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])
        self.assertEqual(adjusted["insufficient"], 1.0)


if __name__ == "__main__":
    unittest.main()
