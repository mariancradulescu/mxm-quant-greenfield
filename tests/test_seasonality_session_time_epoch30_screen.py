import copy
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from research_v3.seasonality_session_time_epoch30_screen import (
    _daily_profiles,
    _evaluate_half,
    canonicalize_identical_duplicates,
    evaluate_symbol,
    holm_adjust,
    validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "research_v3/EPOCH30_SEASONALITY_SESSION_TIME_FRONTIER_FREEZE_V1.json"
REGISTRY_PATH = ROOT / "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
COVERAGE_PATH = ROOT / "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_STRUCTURAL_COVERAGE_EPOCH23_V1.json"


def _row(timestamp: datetime, close: float):
    return {
        "time_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "timestamp": timestamp,
        "open": close,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "tick_volume": 1.0,
    }


class Epoch30SeasonalitySessionTimeTests(unittest.TestCase):
    def test_freeze_binds_all_current_representatives_and_fixed_law(self):
        freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        validate_freeze(freeze, REGISTRY_PATH, COVERAGE_PATH)
        self.assertEqual(len(freeze["scope"]["representatives"]), 41)
        self.assertEqual(freeze["scope"]["replacement_capture_symbol_ids"], [7427, 5352, 2924])

        altered = copy.deepcopy(freeze)
        altered["preregistered_structural_law"]["clock"]["timezone"] = "BROKER_LOCAL"
        with self.assertRaisesRegex(ValueError, "fixed law"):
            validate_freeze(altered, REGISTRY_PATH, COVERAGE_PATH)

    def test_identical_duplicates_collapse_and_conflicts_fail_closed(self):
        timestamp = datetime(2026, 6, 15, tzinfo=timezone.utc)
        row = _row(timestamp, 100.0)
        canonical, removed = canonicalize_identical_duplicates([row, dict(row)])
        self.assertEqual((len(canonical), removed), (1, 1))

        conflict = dict(row, close=101.0)
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            canonicalize_identical_duplicates([row, conflict])

    def test_holm_adjustment_is_monotone_and_bounded(self):
        adjusted = holm_adjust({"a": 0.001, "b": 0.02, "c": 0.9})
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])
        self.assertTrue(all(0.0 <= value <= 1.0 for value in adjusted.values()))

    def test_timestamp_gaps_prevent_cross_segment_observations(self):
        start = datetime(2026, 6, 15, 23, 50, tzinfo=timezone.utc)
        rows = [
            _row(start, 100.0),
            _row(start + timedelta(minutes=5), 101.0),
            _row(start + timedelta(minutes=10), 102.0),
            _row(start + timedelta(minutes=15), 103.0),
            _row(start + timedelta(minutes=25), 104.0),
        ]
        profiles, zero_dates, segments, observations = _daily_profiles(rows)
        self.assertEqual(segments, 2)
        self.assertEqual(zero_dates, 0)
        self.assertEqual(observations, 3)
        self.assertEqual(profiles, [
            (date(2026, 6, 15), {23: 1.0}),
            (date(2026, 6, 16), {0: 1.0}),
        ])

    def test_randomization_is_deterministic_and_clock_peak_is_structural(self):
        profiles = [
            {0: 0.5, 6: 0.5, 12: 2.5, 18: 0.5}
            for _ in range(20)
        ]
        first = _evaluate_half(profiles, "TEST", "CHRONOLOGICAL_HALF_1")
        repeated = _evaluate_half(profiles, "TEST", "CHRONOLOGICAL_HALF_1")
        self.assertEqual(first["randomization_p_value"], repeated["randomization_p_value"])
        self.assertEqual(first["unique_peak_utc_hour"], 12)
        self.assertGreaterEqual(first["primary_statistic_activity_cv"], 0.10)
        self.assertLessEqual(first["randomization_p_value"], 0.05)

    def test_ineligible_symbol_does_not_claim_clock_support(self):
        rows = [
            _row(datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc), 100.0),
            _row(datetime(2026, 6, 15, 0, 5, tzinfo=timezone.utc), 101.0),
        ]
        result = evaluate_symbol(
            rows, "TEST", datetime(2026, 7, 30, tzinfo=timezone.utc)
        )
        self.assertFalse(result["first_half"]["eligible"])
        self.assertFalse(result["raw_structural_pass"])
        self.assertEqual(result["symbol_p_value"], 1.0)


if __name__ == "__main__":
    unittest.main()
