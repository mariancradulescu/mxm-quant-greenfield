import unittest
from datetime import datetime, timedelta, timezone

from research_v3.breakout_volatility_event_availability_screen import (
    LOOKBACK_BARS,
    SOURCE_CAPTURE_SHA256,
    VOLATILITY_EXPANSION_RATIO,
    _screen_rows,
)


def _bar(index: int, open_: float, high: float, low: float, close: float):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (start + timedelta(minutes=5 * index), open_, high, low, close)


class BreakoutVolatilityEventAvailabilityTests(unittest.TestCase):
    def test_prospective_law_is_frozen(self):
        self.assertEqual(LOOKBACK_BARS, 24)
        self.assertEqual(VOLATILITY_EXPANSION_RATIO, 1.5)
        self.assertEqual(
            SOURCE_CAPTURE_SHA256,
            "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503",
        )

    def test_up_event_requires_breakout_and_expansion(self):
        rows = [_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(24)]
        rows.append(_bar(24, 101.0, 105.0, 100.0, 102.0))
        result = _screen_rows(rows)
        self.assertEqual(result["eligible_contiguous_windows"], 1)
        self.assertEqual(result["breakout_only_up"], 1)
        self.assertEqual(result["range_expansion_windows"], 1)
        self.assertEqual(result["event_up"], 1)
        self.assertEqual(result["events"], 1)

    def test_breakout_without_expansion_is_not_event(self):
        rows = [_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(24)]
        rows.append(_bar(24, 101.0, 102.1, 100.1, 102.05))
        result = _screen_rows(rows)
        self.assertEqual(result["breakout_only_up"], 1)
        self.assertEqual(result["range_expansion_windows"], 0)
        self.assertEqual(result["events"], 0)

    def test_gap_rejects_window(self):
        rows = [_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(25)]
        t, o, h, l, c = rows[12]
        rows[12] = (t + timedelta(minutes=5), o, h, l, c)
        result = _screen_rows(rows)
        self.assertEqual(result["eligible_contiguous_windows"], 0)


if __name__ == "__main__":
    unittest.main()
