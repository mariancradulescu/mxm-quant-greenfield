import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.mean_reversion_epoch47_wave01_coarse_parameter_region_scan import (
    ScanError,
    _date_effective_n,
    _power_scenarios,
    scan_symbol,
    validate_freeze,
)


def bars(closes, *, start=None, gap_after=None):
    start = start or datetime(2026, 1, 5, tzinfo=timezone.utc)
    rows = []
    for index, close in enumerate(closes):
        offset = index + (1 if gap_after is not None and index >= gap_after else 0)
        rows.append({
            "timestamp": start + timedelta(minutes=5 * offset),
            "close": float(close),
        })
    return rows


class MeanReversionEpoch47Wave01ScanTests(unittest.TestCase):
    def test_scan_records_every_frozen_cell_without_response_fields(self):
        result = scan_symbol(
            bars([1, 1, 2, 2, 2, 1, 1, 2, 1]),
            symbol="TEST",
            symbol_id=1,
            structural_stratum={"asset_class": "TEST"},
        )
        self.assertEqual(len(result), 12)
        self.assertEqual(
            {(row["lookback_bars"], row["absolute_standardized_deviation_threshold"]) for row in result},
            {(lookback, threshold) for lookback in (12, 24, 48, 96) for threshold in (1.0, 1.5, 2.0)},
        )
        prohibited = {"return", "pnl", "response", "winner", "post_event"}
        for row in result:
            self.assertFalse(prohibited.intersection(row))
            self.assertIn("per_utc_date_event_counts", row)
            self.assertIn("closed_form_power_estimates", row)

    def test_event_clusters_rearm_inside_band_and_direct_opposite_crossing_rearms(self):
        result = scan_symbol(
            bars([1, 1, 2, 2, 2, 1]),
            symbol="TEST",
            symbol_id=1,
            structural_stratum={},
            lookbacks=(3,),
            thresholds=(0.5,),
        )[0]
        self.assertEqual(result["eligible_contiguous_windows"], 3)
        self.assertEqual(result["reversal_event_count"], 2)
        self.assertEqual(result["per_utc_date_event_counts"][0]["event_count"], 2)

    def test_timestamp_gaps_are_not_bridged(self):
        result = scan_symbol(
            bars([1, 2, 3, 4, 5, 6], gap_after=4),
            symbol="TEST",
            symbol_id=1,
            structural_stratum={},
            lookbacks=(3,),
            thresholds=(1.0,),
        )[0]
        self.assertEqual(result["eligible_contiguous_windows"], 2)

    def test_effective_sample_and_power_are_bounded_and_monotonic(self):
        dates = {datetime(2026, 1, day).date(): 0 for day in range(1, 11)}
        self.assertEqual(_date_effective_n(dates)["effective_n"], 10.0)
        powers = [item["estimated_power"] for item in _power_scenarios(30)]
        self.assertGreater(powers[0], powers[1])
        self.assertGreater(powers[1], powers[2])

    def test_unsupported_or_unfrozen_authority_fails_closed(self):
        with self.assertRaises(ScanError):
            validate_freeze({}, Path("."))


if __name__ == "__main__":
    unittest.main()
