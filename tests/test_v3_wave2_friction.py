import hashlib
import json
import unittest
from pathlib import Path

from research_core_v3.v3_friction_global_triage import (
    expand_within_hour_cluster_total,
    global_death_bound,
    global_triage_geometry_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "research_core_v3/state/WAVE2_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V1.json"
DESIGN = ROOT / "research_core_v3/state/WAVE2_GLOBAL_FRICTION_TRIAGE_PLAN_V1.json"


def _binding(path: Path) -> tuple[dict, str]:
    d = json.loads(path.read_text(encoding="utf-8"))
    binding = d.pop("binding_sha256")
    raw = json.dumps(
        d, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return d, hashlib.sha256(raw).hexdigest(), binding


class V3Wave2FrictionTests(unittest.TestCase):
    def test_plan_and_design_bindings_are_exact(self):
        p, got_p, want_p = _binding(PLAN)
        d, got_d, want_d = _binding(DESIGN)
        self.assertEqual(got_p, want_p)
        self.assertEqual(got_d, want_d)
        self.assertEqual(len(p["targets"]), 14)
        self.assertEqual(p["selection"]["selected_exact_quote_windows"], 747620)
        self.assertEqual(
            d["death_rule"]["estimator_mode"],
            "TWO_STAGE_INCLUSION_WEIGHTED_WITHIN_SELECTED_HOUR",
        )
        self.assertEqual(d["initial_global_triage"]["campaign_looks"], 1)
        self.assertFalse(d["initial_global_triage"]["automatic_additional_acquisition"])
        self.assertFalse(d["scope"]["protected_forward_opened"])

    def test_within_hour_inclusion_weighting_restores_reference_total_scale(self):
        self.assertEqual(
            expand_within_hour_cluster_total(
                6.0,
                reference_window_count=12,
                sampled_window_count=3,
            ),
            24.0,
        )
        with self.assertRaises(Exception):
            expand_within_hour_cluster_total(
                1.0,
                reference_window_count=2,
                sampled_window_count=3,
            )

    def test_corrected_bound_can_cross_death_threshold(self):
        gross = 1.0
        meta = {}
        totals = {}
        for i in range(52):
            key = f"S{i}"
            meta[key] = {
                "reference_hours": 100,
                "reference_windows": 1200,
                "max_windows_per_hour": 12,
                "proxy_max_windows_per_hour": 12,
            }
            totals[key] = [24.0]
        result = global_death_bound(
            gross_bps=gross,
            total_reference_windows=52 * 1200,
            strata_meta=meta,
            sampled_cluster_totals=totals,
            alpha=0.01 / 14,
        )
        self.assertGreater(result["lower_bound_bps"], gross)

    def test_wave2_real_geometry_is_bounded_and_global(self):
        g = global_triage_geometry_preflight(
            ROOT,
            plan_rel="research_core_v3/state/WAVE2_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V1.json",
            design_rel="research_core_v3/state/WAVE2_GLOBAL_FRICTION_TRIAGE_PLAN_V1.json",
        )
        self.assertEqual(g["reference_exact_windows"], 747620)
        self.assertEqual(g["stage0_base_probes"], 364)
        self.assertEqual(g["campaign_looks"], 1)
        self.assertFalse(g["automatic_additional_acquisition"])
        self.assertEqual(
            g["estimator_mode"],
            "TWO_STAGE_INCLUSION_WEIGHTED_WITHIN_SELECTED_HOUR",
        )
        self.assertGreater(g["sampled_hours"], 0)
        self.assertGreater(g["sampled_exact_windows"], 0)
        self.assertLessEqual(g["sampled_exact_windows"], 3 * g["sampled_hours"])
        lo, hi = g["total_base_request_range_before_pagination"]
        self.assertGreaterEqual(lo, 364)
        self.assertLessEqual(lo, hi)


if __name__ == "__main__":
    unittest.main(verbosity=2)
