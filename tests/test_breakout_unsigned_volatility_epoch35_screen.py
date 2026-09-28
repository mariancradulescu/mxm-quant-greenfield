import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.breakout_unsigned_volatility_epoch35_screen import (
    _exact_positive_sign_p,
    _screen_rows,
    _split_inference,
    benjamini_hochberg,
    validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "research_v3/EPOCH35_BREAKOUT_UNSIGNED_VOLATILITY_FRONTIER_FREEZE_V1.json"


def _rows(count=32, event_indices=()):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        close = 100.0 + 0.02 * index
        width = 0.3 if index in event_indices else 0.1
        timestamp = start + timedelta(minutes=5 * index)
        rows.append({
            "time_utc": timestamp.isoformat().replace("+00:00", "Z"),
            "timestamp": timestamp,
            "open": close,
            "high": close + width,
            "low": close - width,
            "close": close,
            "tick_volume": 1.0,
        })
    return rows


class Epoch35UnsignedVolatilityTests(unittest.TestCase):
    def test_freeze_binds_proposal_hash_full_panel_and_unsigned_estimand(self):
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        registry = validate_freeze(freeze, ROOT)
        self.assertEqual(len(registry["representatives"]), 41)
        changed = json.loads(json.dumps(freeze))
        changed["preregistered_structural_law"]["event_range_multiple"] = 1.5
        with self.assertRaisesRegex(ValueError, "event or inference law"):
            validate_freeze(changed, ROOT)

    def test_range_event_uses_only_twenty_prior_completed_bars(self):
        rows = _rows(event_indices={20})
        result = _screen_rows(rows, "TEST", 1)
        self.assertEqual(result["event_candidates"], 1)
        self.assertEqual(result["eligible_events"], 1)
        self.assertEqual(result["eligible_utc_dates"], ["2026-01-01"])
        self.assertFalse(result["minimum_data_sufficiency_pass"])

        altered_future = [dict(row) for row in rows]
        for row in altered_future[21:]:
            row["open"] += 10.0
            row["high"] += 10.0
            row["low"] += 10.0
            row["close"] += 10.0
        self.assertEqual(
            result["event_candidates"],
            _screen_rows(altered_future, "TEST", 1)["event_candidates"],
        )

    def test_first_complete_event_per_utc_date_is_retained(self):
        rows = _rows(event_indices={20, 23})
        result = _screen_rows(rows, "TEST", 1)
        self.assertEqual(result["event_candidates"], 2)
        self.assertEqual(result["eligible_events"], 1)
        self.assertEqual(result["excluded_events"]["duplicate_utc_date_event"], 1)

    def test_missing_and_noncontiguous_event_or_outcome_windows_fail_closed(self):
        missing_event_history = _rows(event_indices={20})
        for row in missing_event_history[18:]:
            row["timestamp"] += timedelta(minutes=5)
        self.assertEqual(_screen_rows(missing_event_history, "TEST", 1)["event_candidates"], 0)

        missing_forward = _rows(event_indices={20})
        for row in missing_forward[24:]:
            row["timestamp"] += timedelta(minutes=5)
        result = _screen_rows(missing_forward, "TEST", 1)
        self.assertEqual(result["event_candidates"], 1)
        self.assertEqual(result["eligible_events"], 0)
        self.assertEqual(result["excluded_events"]["incomplete_or_noncontiguous_outcome_window"], 1)

    def test_incomplete_forward_window_at_series_end_is_excluded(self):
        result = _screen_rows(_rows(count=21, event_indices={20}), "TEST", 1)
        self.assertEqual(result["event_candidates"], 1)
        self.assertEqual(result["eligible_events"], 0)
        self.assertFalse(result["minimum_data_sufficiency_pass"])

    def test_chronological_halves_and_minimum_sufficiency(self):
        daily = {f"2026-01-{day:02d}": float(day - 11) for day in range(1, 23)}
        reports, sufficient = _split_inference(daily)
        self.assertTrue(sufficient)
        self.assertEqual(reports[0]["eligible_dates"], 11)
        self.assertEqual(reports[1]["eligible_dates"], 11)
        self.assertEqual(reports[0]["label"], "CHRONOLOGICAL_HALF_1")
        self.assertLess(reports[0]["median_log_variance_ratio"], reports[1]["median_log_variance_ratio"])

        reports, sufficient = _split_inference(dict(list(daily.items())[:19]))
        self.assertFalse(sufficient)
        self.assertFalse(reports[0]["minimum_dates_pass"])
        self.assertEqual(reports[0]["one_sided_exact_sign_p"], 1.0)

    def test_exact_one_sided_sign_test_omits_ties(self):
        self.assertEqual(_exact_positive_sign_p([1.0, -1.0, 0.0]), 0.75)
        self.assertEqual(_exact_positive_sign_p([0.0, 0.0]), 1.0)
        self.assertAlmostEqual(_exact_positive_sign_p([1.0] * 10), 1 / 1024)

    def test_bh_adjustment_is_monotone_and_includes_all_family_members(self):
        adjusted = benjamini_hochberg({"a": 0.001, "b": 0.01, "c": 0.04, "d": 1.0})
        self.assertEqual(set(adjusted), {"a", "b", "c", "d"})
        self.assertAlmostEqual(adjusted["a"], 0.004)
        self.assertAlmostEqual(adjusted["b"], 0.02)
        self.assertAlmostEqual(adjusted["c"], 0.05333333333333334)
        self.assertEqual(adjusted["d"], 1.0)
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])
        self.assertLessEqual(adjusted["c"], adjusted["d"])


if __name__ == "__main__":
    unittest.main()
