import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_v3.regime_context_conditioned_epoch33_screen import (
    STATES, bh_adjust, canonicalize_identical_duplicates, evaluate_symbol, validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "research_v3/EPOCH33_REGIME_CONTEXT_CONDITIONED_FRONTIER_FREEZE_V1.json"
REGISTRY = ROOT / "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"


def row(index, close=100.0):
    timestamp = datetime(2026, 6, 15, tzinfo=timezone.utc) + timedelta(minutes=5 * index)
    return {"time_utc": timestamp.isoformat().replace("+00:00", "Z"), "timestamp": timestamp,
            "open": close, "high": close + 0.5, "low": close - 0.5,
            "close": close, "tick_volume": 1.0}


class Epoch33RegimeScreenTests(unittest.TestCase):
    def test_freeze_binds_exact_proposal_and_fixed_state_law(self):
        freeze = json.loads(FREEZE.read_text())
        validate_freeze(freeze, REGISTRY)
        altered = copy.deepcopy(freeze)
        altered["preregistered_structural_law"]["rank_lookback"] = 24
        with self.assertRaisesRegex(ValueError, "fixed"):
            validate_freeze(altered, REGISTRY)

    def test_duplicate_policy_and_bh_are_bounded(self):
        original = row(0)
        self.assertEqual(canonicalize_identical_duplicates([original, dict(original)])[1], 1)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            canonicalize_identical_duplicates([original, dict(original, close=101.0)])
        adjusted = bh_adjust({"a": 0.001, "b": 0.02, "c": 0.9})
        self.assertEqual(set(adjusted), {"a", "b", "c"})
        self.assertTrue(all(0.0 <= value <= 1.0 for value in adjusted.values()))

    def test_state_reports_are_fixed_and_censor_future_crossing(self):
        result = evaluate_symbol([row(index) for index in range(70)])
        self.assertEqual(tuple(result["states"]), STATES)
        self.assertGreaterEqual(result["selected_events"], 0)
        gap = [row(index) for index in range(70)]
        for index in range(65, 70):
            gap[index]["timestamp"] += timedelta(minutes=5)
            gap[index]["time_utc"] = gap[index]["timestamp"].isoformat().replace("+00:00", "Z")
        self.assertGreater(evaluate_symbol(gap)["contiguous_segments"], 1)


if __name__ == "__main__":
    unittest.main()
