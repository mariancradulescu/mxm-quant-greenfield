from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEXT = "PENDING_SEPARATE_REAL_SHALLOW_M5_V4_ARM_AUTHORIZATION"
AUTH_REF = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V4_PREARM_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json"
AUTH_SHA = "3eaf659a9f57eba539fc564a78c1c2edd71cb5a8656b84d62df33c6d008c2508"

HASHES = {
    "research_core_v4/shallow_m5_support_v2_boundary_v4.py":
        "7f148effd792052e367ce892781123fedc8d9083bfbad27ec9cf8065c48eef52",
    "research_core_v4/shallow_m5_support_v2_production_v4.py":
        "8b7b94d3856160936af61c1a533188b972479e069a6c368fe7f5eeb9af2fcd75",
    ".github/workflows/breadth-first-shallow-m5-support-v2-production-v4.yml":
        "c332c53d375deaf6d409791a330dbbc47c367406df2ed39cc11c72046fd37f60",
    "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_MACHINE_SIDE_PRODUCTION_ARCHITECTURE_FREEZE_V4.json":
        "2df4e2ac5010e81e12cda0cfae462b1a788427c2f2cb1364021a983913addd17",
    "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_BOUNDARY_FORENSIC_RESULT_V1.json":
        "5ff5ee46fe9b5483cfe11077abcabdcd77f50b4f3a4df5329a73e19b80bb013b",
    "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_V3_BOUNDARY_FORENSIC_RESULT_AUTHORITY_V1.json":
        "00e1a23b958ca6da0d0f58e71ad4a7be8245a221d4586ae78d9360438bbf336e",
    AUTH_REF: AUTH_SHA,
}


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


class V4CanonicalStateConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v4 = load("research_core_v4/state/V4_STATE.json")
        cls.cur = load("adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json")
        cls.auth = load("adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json")
        cls.acceptance = load(AUTH_REF)
        cls.blocks = [
            cls.v4["shallow_m5_v2_current_operation"],
            cls.cur["shallow_m5_v2_operational_rebind"],
            cls.auth["shallow_m5_v2_operational_rebind"],
        ]

    def test_01_all_current_operation_pointers_equal(self):
        self.assertEqual(self.v4["current_next_action_type"], NEXT)
        self.assertEqual(self.v4["next_action"], NEXT)
        self.assertEqual(self.cur["next_action"], NEXT)
        self.assertEqual(self.auth["next_action"], NEXT)
        self.assertEqual(self.auth["current_operation"], NEXT)

    def test_02_current_authority_is_v4_acceptance(self):
        self.assertEqual(self.v4["current_authority"], AUTH_REF)
        self.assertTrue((ROOT / AUTH_REF).is_file())
        self.assertEqual(sha(AUTH_REF), AUTH_SHA)

    def test_03_acceptance_authority_exact_validation_binding(self):
        self.assertEqual(
            self.acceptance["status"],
            "INDEPENDENTLY_ACCEPTED_LOWER_BOUNDARY_CORRECTED_V4_PREARM_READY_FOR_SEPARATE_REAL_ARM_GOVERNANCE",
        )
        self.assertEqual(self.acceptance["accepted_head"], "079848fe50841ade2913ef10ac985dae2b9344b0")
        proof = self.acceptance["exact_head_validation"]
        self.assertEqual(proof["run_id"], 37534443385)
        self.assertEqual(proof["job_id"], 112511710360)
        self.assertEqual(proof["tests_passed"], 19)
        self.assertEqual(proof["tests_failed"], 0)
        self.assertEqual(proof["conclusion"], "success")

    def test_04_acceptance_sha_durably_bound_all_states(self):
        for block in self.blocks:
            self.assertEqual(block["v4_prearm_independent_acceptance_authority_ref"], AUTH_REF)
            self.assertEqual(block["v4_prearm_independent_acceptance_authority_sha256"], AUTH_SHA)

    def test_05_active_arm_false_historical_v3_arm_true_all_states(self):
        for block in self.blocks:
            self.assertIs(block["active_capture_ARM_present"], False)
            self.assertIs(block["historical_failed_V3_ARM_present"], True)
            self.assertIs(block["arm_present"], False)
            self.assertEqual(block["arm_present_semantics"], "ACTIVE_CAPTURE_ARM_PRESENT")
            self.assertIs(block["v4_arm_present"], False)

    def test_06_active_release_false_historical_v3_release_true_all_states(self):
        for block in self.blocks:
            self.assertIs(block["active_capture_release_present"], False)
            self.assertIs(block["historical_failed_V3_release_present"], True)
            self.assertIs(block["v4_release_present"], False)

    def test_07_zero_v4_arm_file(self):
        self.assertFalse(
            (ROOT / "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_PRODUCTION_ARM_V4.json").exists()
        )

    def test_08_exact_v4_and_forensic_hashes_unchanged(self):
        for rel, expected in HASHES.items():
            self.assertEqual(sha(rel), expected, rel)

    def test_09_authority_binds_exact_response_and_pagination_laws(self):
        response = self.acceptance["accepted_lower_boundary_normalization_law"]
        self.assertEqual(response["lower_open_lt_from"], "DISCARD_BEFORE_PRICE_OR_VOLUME_DECODE")
        self.assertEqual(response["inside_from_to_inclusive"], "DECODE_USING_EXISTING_EXACT_V2_DECODER")
        self.assertEqual(response["open_gt_current_to"], "FAIL_CLOSED")
        self.assertEqual(response["open_at_or_after_protected_forward"], "FAIL_CLOSED")
        pagination = self.acceptance["accepted_raw_geometry_pagination_law"]
        self.assertEqual(pagination["count_basis"], "RAW_RESPONSE_COUNT")
        self.assertEqual(pagination["cursor_basis"], "RAW_MIN_OPEN_TIMESTAMP")
        self.assertEqual(pagination["page_cap"], 3)
        self.assertEqual(pagination["retries_after_initial"], 2)
        self.assertEqual(pagination["rate_limit_rps"], 4)
        self.assertEqual(pagination["requested_count"], 5000)

    def test_10_acceptance_boundary_is_not_armed_or_executed(self):
        boundary = self.acceptance["arm_readiness_boundary"]
        self.assertIs(boundary["active_v4_arm_present"], False)
        self.assertIs(boundary["active_v4_release_present"], False)
        self.assertEqual(boundary["v4_production_run_count"], 0)
        self.assertIs(boundary["protected_forward_opened"], False)
        self.assertIs(boundary["confirmation_opened"], False)
        self.assertEqual(boundary["next_state"], NEXT)


if __name__ == "__main__":
    unittest.main()
