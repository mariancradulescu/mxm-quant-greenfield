import copy
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.causal_ml_predictive_state_epoch31_screen import (
    canonicalize_identical_duplicates, evaluate_symbol, holm_adjust, validate_freeze
)
import json

ROOT = Path(__file__).resolve().parents[1]


class Epoch31CausalStateTests(unittest.TestCase):
    def test_freeze_is_fixed_and_non_economic(self):
        freeze = json.loads((ROOT / "research_v3/EPOCH31_CAUSAL_ML_PREDICTIVE_STATE_FRONTIER_FREEZE_V1.json").read_text())
        validate_freeze(freeze, ROOT / "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json")
        altered = copy.deepcopy(freeze)
        altered["preregistered_structural_law"]["learning_rate"] = 0.1
        with self.assertRaises(ValueError):
            validate_freeze(altered, ROOT / "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json")

    def test_duplicate_conflict_fails_and_holm_is_bounded(self):
        row = {"timestamp": datetime(2026, 6, 15, tzinfo=timezone.utc), "time_utc": "x",
               "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "tick_volume": 1.0}
        canonical, removed = canonicalize_identical_duplicates([row, dict(row)])
        self.assertEqual((len(canonical), removed), (1, 1))
        with self.assertRaises(ValueError):
            canonicalize_identical_duplicates([row, dict(row, close=2.0)])
        adjusted = holm_adjust({"a": 0.001, "b": 0.02, "c": 0.9})
        self.assertTrue(all(0 <= value <= 1 for value in adjusted.values()))

    def test_walk_forward_is_ineligible_without_ten_daily_clusters(self):
        start = datetime(2026, 6, 15, tzinfo=timezone.utc)
        rows = []
        for index in range(16):
            timestamp = start + timedelta(minutes=5 * index)
            rows.append({"timestamp": timestamp, "time_utc": timestamp.isoformat(), "open": 100 + index,
                         "high": 101 + index, "low": 99 + index, "close": 100 + index, "tick_volume": 1.0})
        result = evaluate_symbol(rows, "TEST")
        self.assertFalse(result["first_half"]["eligible"])
        self.assertEqual(result["symbol_p_value"], 1.0)
