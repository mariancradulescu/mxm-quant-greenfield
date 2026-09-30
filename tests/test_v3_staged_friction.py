import hashlib
import json
import math
import unittest
from pathlib import Path

from m6.cost_evidence import DecodedTick
from research_core_v3.v3_friction_staged import (
    benchmark_anchor_hours,
    build_reference_strata,
    freeze_sampling_for_symbol,
    merge_paginated_tick_pages_chronological,
    staged_death_bound,
    staged_geometry_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "research_core_v3/state/STAGED_FRICTION_ACQUISITION_PLAN_V1.json"
BUILDER = ROOT / "tools/build_v3_maxt14_friction_capture_package.py"
STAGED = ROOT / "research_core_v3/v3_friction_staged.py"


class V3StagedFrictionTests(unittest.TestCase):
    def test_design_binding_and_scientific_boundaries(self):
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
        self.assertFalse(d["principles"]["current_spread_substitution"])
        self.assertFalse(d["sequential_rule"]["favorable_early_stop"])
        self.assertFalse(d["storage"]["raw_tick_values_written_to_disk"])
        self.assertEqual(d["stage0_benchmark"]["planned_base_probes"], 252)

    def test_sampling_freeze_is_deterministic_and_cumulative(self):
        hour = 3_600_000
        scope = {
            "windows": [
                (hour * h + 1000, hour * h + 33000)
                for h in range(24 * 40)
            ]
        }
        strata = build_reference_strata(scope)
        a = freeze_sampling_for_symbol(
            "SYN", strata, seed="seed", stage_counts=[1, 2, 4, 8]
        )
        b = freeze_sampling_for_symbol(
            "SYN", strata, seed="seed", stage_counts=[1, 2, 4, 8]
        )
        self.assertEqual(a, b)
        total = sum(v["reference_windows"] for v in a.values())
        self.assertEqual(total, len(scope["windows"]))
        for meta in a.values():
            self.assertEqual(
                meta["stage_hour_counts"],
                sorted(meta["stage_hour_counts"]),
            )
            self.assertLessEqual(
                meta["stage_hour_counts"][-1], meta["reference_hours"]
            )

    def test_benchmark_anchors_are_transport_only_density_probes(self):
        hour = 3_600_000
        scope = {"windows": []}
        for h, count in enumerate([1, 2, 3, 7, 11, 20, 30, 40]):
            for j in range(count):
                start = h * hour + j * 1000
                scope["windows"].append((start, start + 32000))
        strata = build_reference_strata(scope)
        anchors = benchmark_anchor_hours(strata)
        self.assertEqual(len(anchors), 3)
        self.assertEqual(len(set(anchors)), 3)

    def test_paginated_tick_pages_are_merged_globally_chronological(self):
        # cTrader returns each page newest-range first, while each decoded page
        # is normalized oldest-first. The older second page must be prepended.
        newest_page = [
            DecodedTick(3000, 103),
            DecodedTick(4000, 104),
        ]
        older_page = [
            DecodedTick(1000, 101),
            DecodedTick(2000, 102),
            DecodedTick(3000, 103),  # inclusive pagination overlap
        ]
        merged, duplicates = merge_paginated_tick_pages_chronological(
            [newest_page, older_page]
        )
        self.assertEqual(
            [x.timestamp_ms for x in merged],
            [1000, 2000, 3000, 4000],
        )
        self.assertEqual(
            [x.raw_tick for x in merged],
            [101, 102, 103, 104],
        )
        self.assertEqual(duplicates, 1)

    def test_paginated_tick_merge_preserves_distinct_same_ms_states(self):
        newest_page = [
            DecodedTick(3000, 104),
            DecodedTick(4000, 105),
        ]
        older_page = [
            DecodedTick(2000, 102),
            DecodedTick(3000, 103),
        ]
        merged, duplicates = merge_paginated_tick_pages_chronological(
            [newest_page, older_page]
        )
        self.assertEqual(
            [(x.timestamp_ms, x.raw_tick) for x in merged],
            [(2000, 102), (3000, 103), (3000, 104), (4000, 105)],
        )
        self.assertEqual(duplicates, 0)

    def test_death_bound_is_conservative_and_monotone(self):
        meta = {
            "A": {
                "reference_hours": 10,
                "reference_windows": 20,
                "max_windows_per_hour": 2,
            },
            "B": {
                "reference_hours": 10,
                "reference_windows": 20,
                "max_windows_per_hour": 2,
            },
        }
        low = staged_death_bound(
            gross_bps=1.0,
            total_reference_windows=40,
            strata_meta=meta,
            sampled_cluster_totals={"A": [0.0, 0.0], "B": [0.0, 0.0]},
            alpha=0.001,
        )
        high = staged_death_bound(
            gross_bps=1.0,
            total_reference_windows=40,
            strata_meta=meta,
            sampled_cluster_totals={"A": [4.0, 4.0], "B": [4.0, 4.0]},
            alpha=0.001,
        )
        self.assertEqual(low["lower_bound_bps"], 0.0)
        self.assertGreater(
            high["estimate_clipped_bps"], low["estimate_clipped_bps"]
        )
        self.assertGreaterEqual(
            high["lower_bound_bps"], low["lower_bound_bps"]
        )
        self.assertTrue(math.isfinite(high["half_width_bps"]))

    def test_real_staged_geometry_is_exact_and_bounded(self):
        g = staged_geometry_preflight(ROOT)
        self.assertEqual(g["reference_exact_windows"], 691919)
        self.assertEqual(g["stage0_base_probes"], 252)
        first = g["stages"][0]["by_transport_span_minutes"]
        last = g["stages"][-1]["by_transport_span_minutes"]
        self.assertEqual(first["60"]["sampled_exact_windows"], 5977)
        self.assertEqual(first["60"]["base_bid_ask_requests_before_pagination"], 1456)
        self.assertEqual(first["15"]["base_bid_ask_requests_before_pagination"], 5620)
        self.assertEqual(first["5"]["base_bid_ask_requests_before_pagination"], 11954)
        self.assertEqual(last["60"]["sampled_exact_windows"], 47256)
        self.assertEqual(last["60"]["base_bid_ask_requests_before_pagination"], 11648)
        self.assertEqual(last["15"]["base_bid_ask_requests_before_pagination"], 44848)
        self.assertEqual(last["5"]["base_bid_ask_requests_before_pagination"], 94512)

    def test_staged_package_excludes_exhaustive_entrypoint_and_raw_tick_csv(self):
        builder = BUILDER.read_text(encoding="utf-8")
        staged = STAGED.read_text(encoding="utf-8")
        self.assertIn("V3_MAXT14_FRICTION_STAGE_RUN.py", builder)
        self.assertNotIn('"V3_MAXT14_FRICTION_CAPTURE_RUN.py"', builder)
        self.assertNotIn("tick_csv_bytes", staged)
        self.assertNotIn("canonical_tick_rows", staged)
        self.assertIn("raw_tick_values_written_to_disk", staged)


if __name__ == "__main__":
    unittest.main(verbosity=2)
