import hashlib
import json
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from research_core_v3.v3_friction_winner_screen import (
    winner_screen_geometry_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "research_core_v3/state/WINNER_FIRST_FRICTION_ACQUISITION_PLAN_V1.json"
DESIGN = ROOT / "research_core_v3/state/WINNER_FIRST_FRICTION_SCREEN_PLAN_V1.json"
FREEZE = ROOT / "research_core_v3/state/WINNER_FIRST_FRICTION_SAMPLING_FREEZE_V1.json"


def binding_ok(path: Path) -> bool:
    d = json.loads(path.read_text(encoding="utf-8"))
    expected = d.pop("binding_sha256")
    raw = json.dumps(
        d, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest() == expected


class WinnerFirstFrictionTests(unittest.TestCase):
    def test_frozen_bindings_and_scope(self):
        self.assertTrue(binding_ok(PLAN))
        self.assertTrue(binding_ok(DESIGN))
        self.assertTrue(binding_ok(FREEZE))
        p = json.loads(PLAN.read_text(encoding="utf-8"))
        d = json.loads(DESIGN.read_text(encoding="utf-8"))
        f = json.loads(FREEZE.read_text(encoding="utf-8"))
        self.assertEqual(len(p["targets"]), 56)
        self.assertEqual(p["selection"]["selected_symbols"], 56)
        self.assertEqual(p["selection"]["selected_regions"], 57)
        self.assertEqual(d["scope"]["screen_symbols"], 56)
        self.assertEqual(d["scope"]["screen_regions"], 57)
        self.assertEqual(f["screen_symbols"], 56)
        self.assertEqual(f["screen_regions"], 57)
        self.assertFalse(f["outcomes_used_for_membership"])
        self.assertFalse(f["protected_forward_opened"])
        self.assertEqual(f["candidate_frozen_count"], 0)

    def test_targets_are_unique_symbols_and_tsla_carries_two_regions(self):
        p = json.loads(PLAN.read_text(encoding="utf-8"))
        symbols = [x["symbol"] for x in p["targets"]]
        self.assertEqual(len(symbols), len(set(symbols)))
        self.assertNotIn("CRM.US-24", symbols)
        self.assertNotIn("AMD.US-24", symbols)
        self.assertNotIn("XTZUSD", symbols)
        tsla = next(x for x in p["targets"] if x["symbol"] == "TSLA.US-24")
        self.assertEqual(len(tsla["regions"]), 2)
        self.assertEqual(
            sum(len(x["regions"]) for x in p["targets"]),
            57,
        )

    def test_sampling_uses_at_most_two_strata_per_month_and_three_windows_per_hour(self):
        f = json.loads(FREEZE.read_text(encoding="utf-8"))
        for symbol, meta in f["sampling"].items():
            by_month = Counter(
                x["month"] for x in meta["selected_strata"].values()
            )
            self.assertTrue(all(v <= 2 for v in by_month.values()), symbol)
            for item in meta["selected_strata"].values():
                self.assertLessEqual(len(item["selected_windows"]), 3)
                self.assertGreater(len(item["selected_windows"]), 0)
        self.assertLessEqual(
            f["sampled_exact_windows"], 3 * f["sampled_hours"]
        )

    def test_real_geometry_is_bounded_and_has_no_stage0(self):
        g = winner_screen_geometry_preflight(ROOT)
        self.assertEqual(g["screen_symbols"], 56)
        self.assertEqual(g["screen_regions"], 57)
        self.assertEqual(g["reference_exact_windows"], 2623050)
        self.assertLessEqual(g["sampled_hours"], 56 * 26)
        self.assertLessEqual(
            g["sampled_exact_windows"], 3 * g["sampled_hours"]
        )
        self.assertEqual(
            g["base_bid_ask_requests_before_pagination"],
            2 * g["sampled_hours"],
        )
        self.assertTrue(g["stage0_benchmark_skipped"])
        self.assertFalse(g["automatic_additional_acquisition"])

    def test_design_forbids_promotion_and_candidate_freeze(self):
        d = json.loads(DESIGN.read_text(encoding="utf-8"))
        self.assertTrue(d["screen_metrics"]["no_promotion_from_screen"])
        self.assertTrue(
            d["screen_metrics"]["no_candidate_freeze_from_screen"]
        )
        self.assertTrue(d["transport"]["stage0_benchmark_skipped"])
        self.assertFalse(d["scope"]["protected_forward_opened"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
