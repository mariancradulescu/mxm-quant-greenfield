import unittest
from datetime import datetime, timedelta, timezone

from research_v3.breakout_volatility_30m_persistence_screen import (
    HORIZON_BARS,
    _event_direction,
    _screen_rows_persistence,
)


def _bar(index: int, open_: float, high: float, low: float, close: float):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (start + timedelta(minutes=5 * index), open_, high, low, close)


class BreakoutVolatility30mPersistenceTests(unittest.TestCase):
    def test_horizon_is_frozen_to_six_m5_bars(self):
        self.assertEqual(HORIZON_BARS, 6)

    def test_up_event_reversal_at_30m(self):
        rows = [_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(24)]
        rows.append(_bar(24, 101.0, 105.0, 100.0, 102.0))
        rows.extend([
            _bar(25, 102.0, 102.3, 101.7, 102.1),
            _bar(26, 102.1, 102.2, 101.7, 101.9),
            _bar(27, 101.9, 102.0, 101.5, 101.8),
            _bar(28, 101.8, 101.9, 101.3, 101.6),
            _bar(29, 101.6, 101.7, 101.1, 101.4),
            _bar(30, 101.4, 101.5, 100.8, 101.0),
        ])
        self.assertEqual(_event_direction(rows, 24), 1)
        result = _screen_rows_persistence(rows)
        self.assertEqual(result["events_detected"], 1)
        self.assertEqual(result["events_with_valid_followthrough"], 1)
        self.assertEqual(result["up_reversal"], 1)
        self.assertEqual(result["reversal"], 1)

    def test_gap_in_future_window_invalidates_followthrough(self):
        rows = [_bar(i, 100.0, 101.0, 99.0, 100.0) for i in range(24)]
        rows.append(_bar(24, 101.0, 105.0, 100.0, 102.0))
        rows.extend([_bar(i, 102.0, 102.4, 101.7, 102.1) for i in range(25,31)])
        t,o,h,l,c=rows[28]
        rows[28]=(t+timedelta(minutes=5),o,h,l,c)
        result=_screen_rows_persistence(rows)
        self.assertEqual(result["events_detected"],1)
        self.assertEqual(result["events_with_valid_followthrough"],0)
        self.assertEqual(result["events_without_valid_followthrough"],1)


if __name__=="__main__":
    unittest.main()
