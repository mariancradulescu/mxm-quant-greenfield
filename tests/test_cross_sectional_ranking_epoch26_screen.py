from __future__ import annotations

import copy
import json
import random
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.cross_sectional_ranking_epoch26_screen import (
    BOOTSTRAP_RESAMPLES,
    EXPECTED_SYMBOLS,
    _symbol_anchors,
    _block_indices,
    _rank_percentiles,
    benjamini_yekutieli,
    evaluate_symbol_daily_scores,
    validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]


class Epoch26CrossSectionalRankingScreenTests(unittest.TestCase):
    @staticmethod
    def _rows(count: int, *, start: datetime, offset: int = 0):
        return [
            {
                "timestamp": start + timedelta(seconds=300 * index),
                "close": float(100 + index + offset),
            }
            for index in range(count)
        ]

    def test_freeze_binds_exact_current_41_representative_scope(self):
        freeze = json.loads(
            (ROOT / "research_v3/EPOCH26_CROSS_SECTIONAL_RANKING_FRONTIER_FREEZE_V1.json").read_text()
        )
        validate_freeze(freeze)
        symbols = tuple(
            (item["broker_symbol"], item["symbol_id"])
            for item in freeze["scope"]["representatives"]
        )
        self.assertEqual(symbols, EXPECTED_SYMBOLS)
        self.assertEqual(len(set(symbols)), 41)

        changed = copy.deepcopy(freeze)
        changed["preregistered_structural_law"]["inference"]["block_length_days"] = 1
        with self.assertRaisesRegex(ValueError, "fixed implemented law"):
            validate_freeze(changed)

    def test_average_tie_percentile_ranks_are_bounded_and_deterministic(self):
        ranks = _rank_percentiles({"a": 1.0, "b": 1.0, "c": 3.0, "d": 4.0})
        self.assertEqual(ranks, {"a": 1 / 6, "b": 1 / 6, "c": 2 / 3, "d": 1.0})
        self.assertTrue(all(0 <= value <= 1 for value in ranks.values()))

    def test_anchor_windows_do_not_cross_gaps_and_censor_incomplete_future(self):
        start = datetime(2026, 6, 15, tzinfo=timezone.utc)
        first = self._rows(37, start=start)
        second = self._rows(
            25,
            start=start + timedelta(seconds=300 * 38),
            offset=100,
        )
        anchors, admitted, censored = _symbol_anchors(first + second)
        self.assertEqual((admitted, censored), (5, 2))
        self.assertEqual(len(anchors), 3)
        self.assertTrue(
            all(anchor["timestamp"] < second[0]["timestamp"] for anchor in anchors[:2])
        )

    def test_by_adjustment_covers_complete_dependent_test_family(self):
        adjusted = benjamini_yekutieli({"a": 0.001, "b": 0.02, "c": 0.9})
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])
        self.assertEqual(set(adjusted), {"a", "b", "c"})
        self.assertTrue(all(0 <= value <= 1 for value in adjusted.values()))

    def test_block_bootstrap_is_reproducible_and_insufficient_data_fails_closed(self):
        rng = random.Random(260926)
        indices = [
            _block_indices(30, rng)
            for _ in range(BOOTSTRAP_RESAMPLES)
        ]
        self.assertEqual(len(indices), 5000)
        self.assertTrue(all(len(sample) == 30 for sample in indices))
        self.assertEqual(
            evaluate_symbol_daily_scores([0.1, None, -0.1], indices)["one_sided_block_bootstrap_p"],
            1.0,
        )
        self.assertFalse(
            evaluate_symbol_daily_scores([0.1, None, -0.1], indices)["minimum_sample_size_pass"]
        )


if __name__ == "__main__":
    unittest.main()
