import hashlib
import json
import math
import unittest
from pathlib import Path

from research_core_v3.v3_friction_global_triage import (
    freeze_global_triage_sampling,
    global_death_bound,
    global_triage_geometry_preflight,
)
from research_core_v3.v3_friction_staged import build_reference_strata

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "research_core_v3/state/GLOBAL_FRICTION_TRIAGE_PLAN_V1.json"
BUILDER = ROOT / "tools/build_v3_global_friction_triage_package.py"


class V3GlobalFrictionTriageTests(unittest.TestCase):
    def test_design_binding_and_scope_are_frozen(self):
        d = json.loads(DESIGN.read_text(encoding="utf-8"))
        binding = d.pop("binding_sha256")
        raw = json.dumps(
            d, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), binding)
        self.assertEqual(d["scope"]["corrected_development_cells"], 7975)
        self.assertEqual(d["scope"]["gross_robust_regions"], 88)
        self.assertEqual(d["scope"]["priority_regions"], 14)
        self.assertEqual(d["scope"]["other_gross_regions_cost_unresolved"], 74)
        self.assertEqual(d["scope"]["authoritative_frontier"], 1576)
        self.assertEqual(d["scope"]["full_reference_exact_windows"], 691919)
        self.assertFalse(d["scope"]["protected_forward_opened"])
        self.assertEqual(d["scope"]["candidate_frozen_count"], 0)
        self.assertEqual(d["initial_global_triage"]["campaign_looks"], 1)
        self.assertFalse(
            d["initial_global_triage"]["automatic_additional_acquisition"]
        )
        self.assertEqual(
            d["stage0_benchmark"]["probe_spans_minutes"], [1, 5, 15, 60, 180]
        )
        self.assertEqual(d["stage0_benchmark"]["planned_base_probes"], 420)
        self.assertFalse(d["storage"]["raw_tick_values_written_to_disk"])
        self.assertEqual(d["storage"]["hard_first_bundle_cap_bytes"], 67108864)

    def test_sampling_is_deterministic_and_sparse(self):
        hour = 3_600_000
        scope = {"windows": []}
        for h in range(24 * 40):
            for j in range(7):
                start = hour * h + j * 10_000
                scope["windows"].append((start, start + 32_000))
        strata = build_reference_strata(scope)
        a = freeze_global_triage_sampling(
            "SYN",
            strata,
            seed="seed",
            hours_per_stratum=1,
            windows_per_hour=3,
        )
        b = freeze_global_triage_sampling(
            "SYN",
            strata,
            seed="seed",
            hours_per_stratum=1,
            windows_per_hour=3,
        )
        self.assertEqual(a, b)
        self.assertEqual(
            sum(v["reference_windows"] for v in a.values()),
            len(scope["windows"]),
        )
        for meta in a.values():
            self.assertLessEqual(len(meta["selected_hour_start_ms"]), 1)
            self.assertLessEqual(meta["sampled_exact_windows"], 3)
            for ids in meta["selected_window_indices_by_hour"].values():
                self.assertLessEqual(len(ids), 3)
                self.assertEqual(len(ids), len(set(ids)))

    def test_sparse_death_bound_is_conservative(self):
        meta = {
            "A": {
                "reference_hours": 10,
                "reference_windows": 100,
                "max_windows_per_hour": 10,
                "proxy_max_windows_per_hour": 3,
            },
            "B": {
                "reference_hours": 10,
                "reference_windows": 100,
                "max_windows_per_hour": 10,
                "proxy_max_windows_per_hour": 3,
            },
        }
        low = global_death_bound(
            gross_bps=1.0,
            total_reference_windows=200,
            strata_meta=meta,
            sampled_cluster_totals={"A": [0.0], "B": [0.0]},
            alpha=0.001,
        )
        high = global_death_bound(
            gross_bps=1.0,
            total_reference_windows=200,
            strata_meta=meta,
            sampled_cluster_totals={"A": [6.0], "B": [6.0]},
            alpha=0.001,
        )
        self.assertEqual(low["lower_bound_bps"], 0.0)
        self.assertGreater(
            high["estimate_clipped_proxy_bps"],
            low["estimate_clipped_proxy_bps"],
        )
        self.assertTrue(math.isfinite(high["half_width_bps"]))

    def test_real_geometry_is_one_global_bounded_campaign(self):
        g = global_triage_geometry_preflight(ROOT)
        self.assertEqual(g["reference_exact_windows"], 691919)
        self.assertEqual(g["stage0_base_probes"], 420)
        self.assertEqual(g["campaign_looks"], 1)
        self.assertFalse(g["automatic_additional_acquisition"])
        self.assertGreater(g["sampled_hours"], 0)
        self.assertGreater(g["sampled_exact_windows"], 0)
        self.assertLessEqual(
            g["sampled_exact_windows"], 3 * g["sampled_hours"]
        )
        by_span = g["by_transport_span_minutes"]
        self.assertEqual(
            by_span["60"]["base_bid_ask_requests_before_pagination"],
            2 * g["sampled_hours"],
        )
        self.assertEqual(
            by_span["180"]["base_bid_ask_requests_before_pagination"],
            by_span["60"]["base_bid_ask_requests_before_pagination"],
        )
        self.assertLessEqual(
            by_span["60"]["base_bid_ask_requests_before_pagination"],
            by_span["1"]["base_bid_ask_requests_before_pagination"],
        )
        lo, hi = g["total_base_request_range_before_pagination"]
        self.assertLessEqual(lo, hi)
        self.assertGreaterEqual(lo, 420)

    def test_v7_package_is_distinct_from_v5_and_v6_entrypoints(self):
        builder = BUILDER.read_text(encoding="utf-8")
        self.assertIn("V3_MAXT14_GLOBAL_FRICTION_TRIAGE_RUN.py", builder)
        self.assertIn("GLOBAL_FRICTION_TRIAGE_PLAN_V1.json", builder)
        self.assertNotIn('"V3_MAXT14_FRICTION_CAPTURE_RUN.py"', builder)
        self.assertNotIn('"V3_MAXT14_FRICTION_STAGE_RUN.py"', builder)


if __name__ == "__main__":
    unittest.main(verbosity=2)
