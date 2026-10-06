from __future__ import annotations

import json
import unittest
from pathlib import Path

from research_core_v4 import shallow_m5_support_v2 as m


class ShallowM5V2FinalFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_committed_digits_map_is_exact_regeneration(self):
        path = self.root / "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_SYMBOL_DIGITS_MAP.json"
        committed = json.loads(path.read_bytes())
        regenerated = m.build_digits_map(self.root)
        self.assertEqual(committed, regenerated)
        self.assertEqual(len(committed["entries"]), 1576)
        self.assertEqual(
            committed["digits_map_sha256"],
            "4657c1cea348479afa198b005ae1da3b3f788fb2b33bd2c35f07034bfba2ce7a",
        )
        self.assertEqual(
            m.sha256_bytes(path.read_bytes()),
            "2a8f29795ba49f3a79e96fb2bf9cf6d7f2e5f880d736cd7ba4726ff729feab4a",
        )

    def test_preserved_v1_is_byte_immutable(self):
        path = self.root / "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V1_PREARM_FREEZE.json"
        self.assertEqual(
            m.sha256_bytes(path.read_bytes()),
            "837ee83306a587088a64852956a97da1f3099d7680d6fc01f8da015f6904f208",
        )

    def test_corrected_freeze_binds_protocol_decoder_and_bounds(self):
        path = self.root / "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PREARM_PROTOCOL_DECODER_FREEZE.json"
        freeze = json.loads(path.read_bytes())
        self.assertEqual(
            freeze["status"],
            "PENDING_INDEPENDENT_AUDIT_OF_CORRECTED_BREADTH_FIRST_SHALLOW_M5_SUPPORT_V1_PREARM_PROTOCOL_AND_DECODER_BEFORE_ANY_ARM",
        )
        self.assertFalse(freeze["versioning"]["preserved_v1_mutated"])
        self.assertFalse(freeze["versioning"]["v1_structural_foundation_accepted_but_armable"])
        self.assertEqual(
            freeze["protocol_authority"]["upstream_commit"],
            m.OFFICIAL_PROTO_COMMIT,
        )
        self.assertEqual(
            freeze["symbol_digits_map"]["digits_map_sha256"],
            "4657c1cea348479afa198b005ae1da3b3f788fb2b33bd2c35f07034bfba2ce7a",
        )
        self.assertEqual(
            freeze["finite_pagination_and_wire_bound"]["logical_identity_segment_count"],
            6304,
        )
        self.assertEqual(
            freeze["finite_pagination_and_wire_bound"]["maximum_page_request_count"],
            18912,
        )
        self.assertEqual(
            freeze["finite_pagination_and_wire_bound"]["maximum_wire_attempts_per_page"],
            3,
        )
        self.assertEqual(
            freeze["finite_pagination_and_wire_bound"]["true_absolute_maximum_wire_attempts"],
            56736,
        )

    def test_final_stop_guards_remain_closed(self):
        freeze = json.loads(
            (
                self.root
                / "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PREARM_PROTOCOL_DECODER_FREEZE.json"
            ).read_bytes()
        )
        stop = freeze["required_stop"]
        self.assertFalse(stop["arm_present"])
        self.assertFalse(stop["broker_contact"])
        self.assertEqual(stop["historical_requests_sent"], 0)
        self.assertFalse(stop["credentials_used"])
        self.assertEqual(stop["economic_outcomes_opened_this_task"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
