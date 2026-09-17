import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from m2.broker_semantics import state_counts, validate_registry
from m2.economic_core import (
    Bar,
    Event,
    completed_bar_index,
    decision_time_for_bar,
    hold_exit_index,
    next_valid_entry_index,
    normalize_volume,
    order_events,
    settle_round_trip,
    swap_boundary_count,
)

UTC = timezone.utc
T0 = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


def bar(index, start_hour, *, session_open=True):
    start = T0 + timedelta(hours=start_hour)
    return Bar(index, start, start + timedelta(hours=1), D("100"), D("101"), D("99"), D("100.5"), session_open)


class M2SyntheticFixtures(unittest.TestCase):
    # F01 completed-bar causality
    def test_f01_completed_bar_causality(self):
        bars = [bar(0, 0), bar(1, 1)]
        self.assertEqual(completed_bar_index(bars, T0 + timedelta(hours=1, minutes=30)), 0)

    # F02 decision timing
    def test_f02_decision_timing(self):
        b = bar(0, 0)
        self.assertEqual(decision_time_for_bar(b), T0 + timedelta(hours=1))
        self.assertIsNone(completed_bar_index([b], T0 + timedelta(minutes=59, seconds=59)))
        self.assertEqual(completed_bar_index([b], T0 + timedelta(hours=1)), 0)

    # F03 next-valid entry / market-closed delay
    def test_f03_next_valid_entry(self):
        bars = [bar(0, 0), bar(1, 1, session_open=False), bar(2, 2, session_open=True)]
        self.assertEqual(next_valid_entry_index(bars, 0), 2)

    # F04 entry/exit indexing
    def test_f04_entry_exit_indexing(self):
        bars = [bar(10, 0), bar(11, 1), bar(12, 2), bar(13, 3)]
        entry = next_valid_entry_index(bars, 10)
        self.assertEqual(entry, 11)
        self.assertEqual(hold_exit_index(bars, entry, 2), 12)

    # F05 long/short PnL sign
    def test_f05_long_short_pnl_sign(self):
        kwargs = dict(
            volume=D("1"), entry_mid=D("100"), exit_mid=D("102"), spread=D("0"),
            commission_per_unit_per_side_quote=D("0"), contract_multiplier=D("1"),
            entry_time=T0, exit_time=T0 + timedelta(hours=1), rollover_times=[],
            swap_per_unit_per_boundary_quote=D("0"), quote_to_account_rate=D("1"),
        )
        self.assertEqual(settle_round_trip(direction="LONG", **kwargs).net_account, D("2"))
        self.assertEqual(settle_round_trip(direction="SHORT", **kwargs).net_account, D("-2"))

    # F06 volume normalization
    def test_f06_volume_normalization(self):
        self.assertEqual(normalize_volume(D("0.037"), D("0.01"), D("0.01")), D("0.03"))
        self.assertIsNone(normalize_volume(D("0.009"), D("0.01"), D("0.01")))
        self.assertEqual(normalize_volume(D("0.27"), D("0.01"), D("0.01"), D("0.20")), D("0.20"))

    # F07 commission
    def test_f07_commission(self):
        r = settle_round_trip(
            direction="LONG", volume=D("3"), entry_mid=D("100"), exit_mid=D("100"), spread=D("0"),
            commission_per_unit_per_side_quote=D("0.25"), contract_multiplier=D("1"),
            entry_time=T0, exit_time=T0 + timedelta(hours=1), rollover_times=[],
            swap_per_unit_per_boundary_quote=D("0"), quote_to_account_rate=D("1"),
        )
        self.assertEqual(r.commission_quote, D("1.50"))
        self.assertEqual(r.net_quote, D("-1.50"))

    # F08 spread
    def test_f08_spread(self):
        r = settle_round_trip(
            direction="LONG", volume=D("2"), entry_mid=D("100"), exit_mid=D("100"), spread=D("0.4"),
            commission_per_unit_per_side_quote=D("0"), contract_multiplier=D("1"),
            entry_time=T0, exit_time=T0 + timedelta(hours=1), rollover_times=[],
            swap_per_unit_per_boundary_quote=D("0"), quote_to_account_rate=D("1"),
        )
        self.assertEqual(r.entry_fill, D("100.2"))
        self.assertEqual(r.exit_fill, D("99.8"))
        self.assertEqual(r.spread_cost_quote, D("0.8"))
        self.assertEqual(r.net_quote, D("-0.8"))

    # F09 swap boundary handling
    def test_f09_swap_boundary_handling(self):
        boundaries = [T0, T0 + timedelta(hours=24), T0 + timedelta(hours=48)]
        self.assertEqual(swap_boundary_count(T0, T0 + timedelta(hours=48), boundaries), 2)
        r = settle_round_trip(
            direction="LONG", volume=D("2"), entry_mid=D("100"), exit_mid=D("100"), spread=D("0"),
            commission_per_unit_per_side_quote=D("0"), contract_multiplier=D("1"),
            entry_time=T0, exit_time=T0 + timedelta(hours=48), rollover_times=boundaries,
            swap_per_unit_per_boundary_quote=D("-0.10"), quote_to_account_rate=D("1"),
        )
        self.assertEqual(r.swap_boundaries, 2)
        self.assertEqual(r.swap_quote, D("-0.40"))

    # F10 currency conversion
    def test_f10_currency_conversion(self):
        r = settle_round_trip(
            direction="LONG", volume=D("1"), entry_mid=D("100"), exit_mid=D("110"), spread=D("0"),
            commission_per_unit_per_side_quote=D("0"), contract_multiplier=D("1"),
            entry_time=T0, exit_time=T0 + timedelta(hours=1), rollover_times=[],
            swap_per_unit_per_boundary_quote=D("0"), quote_to_account_rate=D("0.5"),
        )
        self.assertEqual(r.net_quote, D("10"))
        self.assertEqual(r.net_account, D("5.0"))

    # F11 hold termination
    def test_f11_hold_termination(self):
        bars = [bar(0, 0), bar(1, 1), bar(2, 2), bar(3, 3)]
        self.assertEqual(hold_exit_index(bars, 1, 3), 3)
        self.assertIsNone(hold_exit_index(bars, 2, 3))

    # F12 same-timestamp ordering
    def test_f12_same_timestamp_ordering(self):
        t = T0 + timedelta(hours=1)
        events = [
            Event(t, "ENTRY"), Event(t, "DECISION"), Event(t, "EXIT"),
            Event(t, "BAR_CLOSE"), Event(t, "BROKER_STATE"),
        ]
        self.assertEqual([e.kind for e in order_events(events)], [
            "BROKER_STATE", "BAR_CLOSE", "EXIT", "DECISION", "ENTRY"
        ])

    # F13 missing-bar/session behavior + semantic registry integrity
    def test_f13_missing_bar_session_behavior(self):
        bars = [bar(0, 0), bar(3, 3, session_open=False), bar(7, 7, session_open=True)]
        self.assertEqual(next_valid_entry_index(bars, 0), 7)
        self.assertEqual(hold_exit_index(bars, 7, 1), 7)
        self.assertTrue(validate_registry())
        self.assertEqual(state_counts(), {"VERIFIED": 7, "CONSERVATIVE_BOUND": 0, "UNRESOLVED": 8})


if __name__ == "__main__":
    unittest.main(verbosity=2)
