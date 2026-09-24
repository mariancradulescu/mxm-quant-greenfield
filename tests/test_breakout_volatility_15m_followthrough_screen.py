import unittest
from datetime import datetime, timedelta, timezone

from research_v3.breakout_volatility_15m_followthrough_screen import (
    HORIZON_BARS,
    _event_direction,
    _screen_rows_followthrough,
)


def _bar(index: int, open_: float, high: float, low: float, close: float):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (start + timedelta(minutes=5 * index), open_, high, low, close)


class BreakoutVolatility15mFollowthroughTests(unittest.TestCase):
    def test_horizon_is_frozen_to_three_m5_bars(self):
        self.assertEqual(HORIZON_BARS, 3)

    def test_up_event_continuation(self):
        rows = [_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(24)]
        rows.extend([
            _bar(24, 101.0, 105.0, 100.0, 102.0),
            _bar(25, 102.0, 102.2, 101.8, 102.1),
            _bar(26, 102.1, 102.4, 101.9, 102.2),
            _bar(27, 102.2, 103.2, 102.0, 103.0),
        ])
        self.assertEqual(_event_direction(rows, 24), 1)
        result = _screen_rows_followthrough(rows)
        self.assertEqual(result["events_detected"], 1)
        self.assertEqual(result["events_with_valid_followthrough"], 1)
        self.assertEqual(result["up_continuation"], 1)
        self.assertEqual(result["continuation"], 1)

    def test_future_gap_invalidates_followthrough_but_not_event(self):
        rows = [_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(24)]
        rows.extend([
            _bar(24, 101.0, 105.0, 100.0, 102.0),
            _bar(25, 102.0, 102.2, 101.8, 102.1),
            _bar(26, 102.1, 102.4, 101.9, 102.2),
            _bar(27, 102.2, 103.2, 102.0, 103.0),
        ])
        t, o, h, l, c = rows[26]
        rows[26] = (t + timedelta(minutes=5), o, h, l, c)
        result = _screen_rows_followthrough(rows)
        self.assertEqual(result["events_detected"], 1)
        self.assertEqual(result["events_with_valid_followthrough"], 0)
        self.assertEqual(result["events_without_valid_followthrough"], 1)


if __name__ == "__main__":
    unittest.main()
