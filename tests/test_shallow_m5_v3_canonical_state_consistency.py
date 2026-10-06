from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

V4_STATE = ROOT / "research_core_v4/state/V4_STATE.json"
ADAPTIVE_CURRENT = ROOT / "adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json"
ADAPTIVE_AUTHORITY = ROOT / "adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json"
ACCEPTANCE_REL = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_ARM_GATE_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json"
ACCEPTANCE = ROOT / ACCEPTANCE_REL
ACCEPTANCE_SHA256 = "8e041389dc1344d7c2a004d9293a0b15a7242c097b3742cdcbf49c3a1ba27cd0"

NEXT = "PENDING_SEPARATE_REAL_SHALLOW_M5_V3_ARM_AUTHORIZATION"
HISTORICAL_PRE_V3 = (
    "PENDING_INDEPENDENT_FINAL_PREARM_AUDIT_OF_SHALLOW_M5_V2_"
    "PRODUCTION_ARCHITECTURE_V2_AND_REAL_GITHUB_PROVIDER_PREFLIGHT"
)

PRODUCTION_HASHES = {
    "research_core_v4/shallow_m5_support_v2_production_v2.py":
        "a1aa8ba8bd104639c2758bf4bc14096565e41c897bceda2d343e0ba68c840de7",
    ".github/workflows/breadth-first-shallow-m5-support-v2-production-v2.yml":
        "208b26c10b0b3f5750512d126b4fa5a33ffbaa4c085985a64c7ca23a0706e7af",
    "research_core_v4/shallow_m5_support_v2_production_v3.py":
        "c6897e3847cd88b1641f32e011d3b8b9f0397b8ef40c974db4f227b59978a0af",
    ".github/workflows/breadth-first-shallow-m5-support-v2-production-v3.yml":
        "2774bb2e43335589b89846bf745afef6bfd77ddd19be1bbf7b7d566c8c5d6ae1",
    "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_MACHINE_SIDE_PRODUCTION_ARCHITECTURE_FREEZE_V3.json":
        "769fd7d09c49ef0ac23675801239d5ee8e018e219e9c73d8ce4a8a584b381d84",
    "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_GITHUB_PROVIDER_PREFLIGHT_RESULT_V1.json":
        "58aba6b981e427e60e7e20550206c1de183a0f5e49ef59809735cb6baddc3153",
    "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PROVIDER_PREFLIGHT_ACCEPTANCE_AUTHORITY_V1.json":
        "c20a86896d839ad54b3c66597d797291d8244fd358555e692f20bbcf6170a00e",
}

ARM_RELS = (
    "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V1.json",
    "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V2.json",
    "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V3.json",
)


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    assert isinstance(value, dict)
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CanonicalV3OperationConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v4 = load(V4_STATE)
        cls.current = load(ADAPTIVE_CURRENT)
        cls.authority = load(ADAPTIVE_AUTHORITY)
        cls.acceptance = load(ACCEPTANCE)

    def test_three_canonical_operation_pointers_equal(self):
        self.assertEqual(self.v4["current_next_action_type"], self.v4["next_action"])
        self.assertEqual(self.v4["next_action"], self.current["next_action"])
        self.assertEqual(self.v4["next_action"], self.authority["next_action"])
        self.assertEqual(self.authority["current_operation"], self.authority["next_action"])
        self.assertEqual(self.v4["next_action"], NEXT)

    def test_current_authority_points_to_existing_acceptance_authority(self):
        self.assertEqual(self.v4["current_authority"], ACCEPTANCE_REL)
        self.assertTrue(ACCEPTANCE.is_file())

    def test_acceptance_authority_hash_matches_durable_state_bindings(self):
        self.assertEqual(sha256(ACCEPTANCE), ACCEPTANCE_SHA256)
        v4b = self.v4["shallow_m5_v2_current_operation"]
        cb = self.current["shallow_m5_v2_operational_rebind"]
        ab = self.authority["shallow_m5_v2_operational_rebind"]
        for binding in (v4b, cb, ab):
            self.assertEqual(binding["v3_gate_independent_acceptance_authority_ref"], ACCEPTANCE_REL)
            self.assertEqual(binding["v3_gate_independent_acceptance_authority_sha256"], ACCEPTANCE_SHA256)

    def test_historical_pre_v3_pointer_preserved(self):
        self.assertEqual(self.v4["historical_pre_architecture_v3_next_action"], HISTORICAL_PRE_V3)

    def test_independent_acceptance_binds_exact_accepted_gate(self):
        a = self.acceptance
        self.assertEqual(
            a["status"],
            "INDEPENDENTLY_ACCEPTED_MACHINE_ENFORCED_V3_ARM_GATE_READY_FOR_SEPARATE_REAL_ARM_GOVERNANCE",
        )
        self.assertEqual(a["exact_accepted_head"], "fff98dfdcb802703900c7952b2ee70063fe359d2")
        self.assertEqual(a["exact_head_validation"]["run_id"], 37501253462)
        self.assertEqual(a["exact_head_validation"]["job_id"], 112398534396)
        self.assertEqual(a["exact_head_validation"]["tests_passed"], 116)
        self.assertEqual(a["exact_head_validation"]["tests_failed"], 0)
        self.assertEqual(a["next_state"], NEXT)

    def test_exact_production_hash_preservation(self):
        for rel, expected in PRODUCTION_HASHES.items():
            with self.subTest(path=rel):
                self.assertEqual(sha256(ROOT / rel), expected)

    def test_zero_arm(self):
        for rel in ARM_RELS:
            with self.subTest(path=rel):
                self.assertFalse((ROOT / rel).exists())

    def test_zero_broker_and_history_at_accepted_audit_boundary(self):
        boundary = self.acceptance["audit_boundary"]
        self.assertIs(boundary["zero_arm_at_audit"], True)
        self.assertIs(boundary["zero_broker_contact_at_audit"], True)
        self.assertIs(boundary["zero_historical_request_at_audit"], True)

    def test_forward_and_confirmation_remain_closed(self):
        boundary = self.acceptance["audit_boundary"]
        self.assertIs(boundary["protected_forward_closed"], True)
        self.assertIs(boundary["confirmation_closed"], True)
        self.assertIs(self.v4["governance"]["protected_forward_opened"], False)
        self.assertIs(self.current["protected_forward_opened"], False)
        self.assertIs(self.authority["protected_forward_opened"], False)
        self.assertIs(self.authority["confirmation_opened"], False)

    def test_budget_and_historical_economics_unchanged(self):
        self.assertEqual(self.current["search_budget"]["total"], 84)
        self.assertEqual(self.current["search_budget"]["used"], 21)
        self.assertEqual(self.current["search_budget"]["remaining"], 63)
        self.assertEqual(self.current["search_budget"]["refunds"], 0)
        self.assertEqual(self.current["search_budget"]["economic_outcomes_opened"], 29)
        self.assertEqual(
            self.current["raw_result_sha256"],
            "be255fcfadbcf412a9d7b01238772dde4dc94fe5972cca4eb68006c4987de4e0",
        )


if __name__ == "__main__":
    unittest.main()
