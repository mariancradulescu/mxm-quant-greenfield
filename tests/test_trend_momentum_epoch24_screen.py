import unittest
from datetime import datetime, timedelta, timezone

from research_v3.trend_momentum_epoch24_screen import (
    bh_adjust,
    canonicalize_identical_duplicates,
    evaluate_symbol,
    exact_binomial_greater,
)


def row(i, close):
    timestamp=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=5*i)
    return {
        "time_utc":timestamp.isoformat().replace("+00:00","Z"),
        "timestamp":timestamp,
        "open":float(close),
        "high":float(close)+1.0,
        "low":float(close)-1.0,
        "close":float(close),
        "tick_volume":1.0,
    }


class Epoch24TrendMomentumScreenTests(unittest.TestCase):
    def test_exact_binomial_known_value(self):
        self.assertEqual(exact_binomial_greater(5,6), 0.109375)

    def test_bh_adjust_is_monotone_and_bounded(self):
        adjusted=bh_adjust({"a":0.001,"b":0.02,"c":0.9})
        self.assertLessEqual(adjusted["a"],adjusted["b"])
        self.assertLessEqual(adjusted["b"],adjusted["c"])
        self.assertTrue(all(0.0 <= value <= 1.0 for value in adjusted.values()))

    def test_identical_duplicate_is_collapsed_and_conflict_fails_closed(self):
        rows=[row(0,1),row(1,2)]
        rows.append(dict(rows[1]))
        canonical,removed=canonicalize_identical_duplicates(rows)
        self.assertEqual(len(canonical),2)
        self.assertEqual(removed,1)
        bad=dict(rows[1]); bad["close"]=99.0
        with self.assertRaisesRegex(ValueError,"conflicting duplicate"):
            canonicalize_identical_duplicates([rows[1],bad])

    def test_anchor_lattice_settlement_and_right_censor_are_causal(self):
        rows=[row(i,i+1) for i in range(37)]
        result=evaluate_symbol(rows,lookback=12,response=12,stride=12)
        self.assertEqual(result["admitted_anchors"],3)
        self.assertEqual(result["settled_anchors"],2)
        self.assertEqual(result["right_censored_future_response"],1)
        self.assertEqual(result["both_nonzero_settled"],2)
        self.assertEqual(result["continuation"],2)
        self.assertEqual(result["reversal"],0)


if __name__=="__main__":
    unittest.main()
