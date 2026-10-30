"""No-secret source-first one-year time support and missingness regression tests."""
import datetime as dt
import tempfile
from pathlib import Path
import unittest
from . import long_calendar_source_reception_20261030 as m

def clock_at(day='2026-08-24T00:00:00+00:00'):
    return int(dt.datetime.fromisoformat(day).timestamp())

class VerifiedCalendarSeparation(unittest.TestCase):
    def test_authoritative_145_annual_vs_1576_four_weeks(self):
        x=m.accepted_catalog()
        self.assertEqual(x['source_year']['identities'],145)
        self.assertEqual(x['source_year']['m5_rows'],11406418)
        self.assertEqual(x['source_year']['distinct_asset_classes'],10)
        self.assertEqual(x['mid_horizon_13week']['identities_original'],40)
        self.assertEqual(x['short_horizon']['identities'],1576)
        self.assertEqual(x['short_horizon']['m5_rows'],3355389)
        self.assertFalse(x['source_year']['per_identity_exact_weekly_coverage_proven'])
        self.assertFalse(x['account']['current_per_identity_20260925_recheck_proven'])
        self.assertFalse(x['research_boundaries']['reserved_confirmation_opened'])
        self.assertTrue(x['no_closed_strategy_reexecution'])

    def test_actual_weekly_source_not_bar_count(self):
        a=clock_at()
        times=[a+i*300 for i in range(120)]
        x=m.exact_clock(times)
        self.assertEqual(list(x),['2026-W35'])
        self.assertEqual(x['2026-W35']['causal_12bar_features'],109)
        self.assertEqual(x['2026-W35']['future_8bar_observable'],101)
        self.assertEqual(x['2026-W35']['future_8bar_missing'],8)

    def test_missing_interior_does_not_fabricate_causal_support(self):
        a=clock_at()
        times=[a+i*300 for i in range(120) if i not in (40,41)]
        x=m.exact_clock(times)['2026-W35']
        self.assertLess(x['causal_12bar_features'],109)
        self.assertLess(x['future_8bar_observable'],101)

    def test_observed_weekend_crypto_bars_are_eligible(self):
        # Weekends may be genuinely traded by an accepted broker crypto CFD.
        a=clock_at('2026-08-29T00:00:00+00:00')
        x=m.exact_clock([a+i*300 for i in range(120)])
        self.assertEqual(list(x),['2026-W35'])
        self.assertEqual(x['2026-W35']['causal_12bar_features'],109)
        self.assertEqual(x['2026-W35']['future_8bar_observable'],101)
        self.assertEqual(x['2026-W35']['future_8bar_missing'],8)

    def test_real_sunday_to_monday_cross_week_history_is_not_discarded(self):
        a=clock_at('2026-08-30T23:00:00+00:00')
        x=m.exact_clock([a+i*300 for i in range(25)])
        self.assertEqual(x['2026-W35']['causal_12bar_features'],1)
        self.assertEqual(x['2026-W36']['causal_12bar_features'],13)
        self.assertEqual(x['2026-W36']['future_8bar_observable'],5)

    def test_absent_weekend_not_interpolated_into_forex_session(self):
        friday=clock_at('2026-08-28T00:00:00+00:00')
        monday=clock_at('2026-08-31T00:00:00+00:00')
        times=[friday+i*300 for i in range(15)]+[monday+i*300 for i in range(15)]
        x=m.exact_clock(times)
        self.assertEqual({w:v['causal_12bar_features'] for w,v in x.items()},
                         {'2026-W35':4,'2026-W36':4})
        self.assertEqual(sum(v['future_8bar_observable'] for v in x.values()),0)

    def test_distinct_weeks_not_identity_multiplication(self):
        a=clock_at()
        b=clock_at('2026-08-31T00:00:00+00:00')
        x=m.exact_clock([a+i*300 for i in range(65)]+[b+i*300 for i in range(65)])
        self.assertEqual(list(x),['2026-W35','2026-W36'])
        self.assertNotEqual(len(x),130)

    def test_duplicate_and_offgrid_fail_closed(self):
        a=clock_at()
        with self.assertRaisesRegex(ValueError,'DUPLICATES'):
            m.exact_clock([a,a])
        with self.assertRaisesRegex(ValueError,'FIVE_MINUTE_GRID'):
            m.exact_clock([a+3])

    def test_missing_original_is_not_verified_archive(self):
        with self.assertRaisesRegex(ValueError,'TWO_ORIGINAL_INPUT_BUNDLES'):
            m.exact_archive([])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'not_an_original.zip';path.write_bytes(b'not accepted')
            with self.assertRaisesRegex(ValueError,'ORIGINAL_ARCHIVE_SHA256'):
                m.exact_archive([path,path])

if __name__=='__main__':unittest.main()
