"""Fabricated-only parity checks for the unchanged frozen 3-lag coupling law."""
import math
import unittest
from datetime import datetime, timezone
from research_core_v4.existing1576_data_first_v1.coupling_response_kernel_v1 import directions, response

START = int(datetime(2026, 8, 20, tzinfo=timezone.utc).timestamp())
END = START + 28 * 86400
T = START + 7200
LAGS = (0, 300, 900)


def fabricated():
    out = {}
    for step in range(60):
        ts = START + step * 300
        out[ts] = {
            "timestamp": ts, "available_at": ts + 300,
            "open": 100.0, "high": 102.0, "low": 99.0,
            "close": 101.0, "tick_volume": 1,
        }
    return out


class TestFrozenKernelScientificParity(unittest.TestCase):
    def test_complete_known_positive_pair_all_lags(self):
        bars = fabricated()
        for lag in LAGS:
            with self.subTest(lag=lag):
                (a, b), label = directions(bars, T, lag)
                self.assertEqual(((a, b), label), ((1, 1), "SUPPORTED"))
                ret, rlabel = response(bars, T, lag, T + 3600 + lag, END)
                self.assertEqual((ret, rlabel), (0.0, "SUPPORTED"))

    def test_known_incremental_disagreement_on_same_support(self):
        bars = fabricated()
        for ts in (T-300, T-600, T-1200):
            bars[ts] = {**bars[ts], "open": 101.0, "close": 100.0}
        for lag in LAGS:
            with self.subTest(lag=lag):
                pair, label = directions(bars, T, lag)
                self.assertEqual((pair, label), ((1, -1), "SUPPORTED"))
                y, rlabel = response(bars, T, lag, T+3600+lag, END)
                self.assertEqual(rlabel, "SUPPORTED")
                self.assertAlmostEqual(y, math.log(101/100))
                self.assertAlmostEqual((pair[0]-pair[1])*y*10000, 20000*math.log(101/100))

    def test_zero_activity_abstains(self):
        bars = fabricated()
        for ts in range(T-3600, T, 300):
            bars[ts]["tick_volume"] = 0
        self.assertEqual(directions(bars, T, 0), (None, "ZERO_ACTIVITY"))

    def test_zero_baseline_abstains_on_common_pair(self):
        bars = fabricated()
        bars[T-300]["open"] = bars[T-300]["close"]
        self.assertEqual(directions(bars, T, 0), (None, "COMMON_ZERO_DIRECTION_ABSTENTION"))

    def test_missing_feature_and_label_not_imputed(self):
        bars = fabricated()
        del bars[T-3600]
        self.assertEqual(directions(bars, T, 0), (None, "FEATURE_GAP"))
        bars = fabricated()
        del bars[T+3300]
        self.assertEqual(response(bars, T, 0, T+3600, END), (None, "LABEL_GAP"))

    def test_late_receipt_is_not_silently_filled(self):
        bars = fabricated()
        bars[T-300]["available_at"] = T+1
        self.assertEqual(directions(bars, T, 0), (None, "FEATURE_RECEIPT"))

    def test_maturity_and_calendar_censor(self):
        bars = fabricated()
        with self.assertRaisesRegex(ValueError, "LABEL_NOT_MATURE"):
            response(bars, T, 300, T+3600+299, END)
        self.assertEqual(response(bars, END-3600, 300, END, END), (None, "DOMAIN_CENSOR"))

    def test_invalid_price_and_volume_reject_not_corrected(self):
        bars = fabricated()
        bars[T-300]["high"] = 0.0
        with self.assertRaisesRegex(ValueError, "INVALID_OHLC"):
            directions(bars, T, 0)
        bars = fabricated()
        bars[T-300]["tick_volume"] = -1
        with self.assertRaisesRegex(ValueError, "INVALID_VOLUME"):
            directions(bars, T, 0)

    def test_nonfinite_reject(self):
        bars = fabricated()
        bars[T-300]["close"] = float("nan")
        with self.assertRaisesRegex(ValueError, "NONFINITE_OHLC"):
            directions(bars, T, 0)

    def test_early_prefix_and_offgrid_reject(self):
        bars = fabricated()
        self.assertEqual(directions(bars, START, 0), (None, "FEATURE_GAP"))
        with self.assertRaisesRegex(ValueError, "DECISION_GRID"):
            directions(bars, T+300, 0)


if __name__ == "__main__":
    unittest.main()
