import hashlib
import json
import unittest
from pathlib import Path

from research_core_v3.v3_friction_capture import (
    coalesce_exact_windows,
    decode_delta_windows,
    local_geometry_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "research_core_v3/state/MAXT14_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V1.json"


class V3MaxT14FrictionCaptureTests(unittest.TestCase):
    def test_plan_binding_and_hard_boundaries(self):
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        binding = plan.pop("binding_sha256")
        raw = json.dumps(
            plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), binding)
        self.assertEqual(plan["selection"]["selected_regions"], 14)
        self.assertEqual(
            plan["selection"]["other_gross_regions_remaining_COST_UNRESOLVED"], 74
        )
        self.assertFalse(plan["broker_identity"]["orders"])
        self.assertFalse(plan["broker_identity"]["account_mutation"])
        self.assertFalse(plan["acquisition"]["protected_forward_opened"])
        self.assertFalse(plan["acquisition"]["fill_authority"])
        self.assertFalse(
            plan["freeze_gate"]["candidate_freeze_allowed_by_this_capture"]
        )

    def test_delta_decode_is_exact(self):
        self.assertEqual(
            decode_delta_windows([[1000, 32], [300, 40], [0, 10]]),
            [(1000, 1032), (1300, 1340), (1300, 1310)],
        )

    def test_transport_grouping_never_changes_exact_windows(self):
        source = [(1000, 1032), (1200, 1232), (700000, 700032)]
        blocks = coalesce_exact_windows(
            source, max_gap_ms=300000, max_block_span_ms=3600000
        )
        self.assertEqual(len(blocks), 2)
        recovered = [
            (w.start_ms, w.end_ms) for block in blocks for w in block.windows
        ]
        self.assertEqual(recovered, source)
        self.assertEqual(blocks[0].start_ms, 1000)
        self.assertEqual(blocks[0].end_ms, 1232)

    def test_real_frozen_scope_geometry_preflight(self):
        geometry = local_geometry_preflight(ROOT)
        self.assertEqual(geometry["symbols"], 14)
        self.assertEqual(geometry["exact_windows"], 691919)
        self.assertGreater(geometry["transport_blocks"], 0)
        self.assertLessEqual(
            geometry["transport_blocks"], geometry["exact_windows"]
        )
        self.assertEqual(
            geometry["base_bid_ask_requests_before_pagination"],
            2 * geometry["transport_blocks"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
