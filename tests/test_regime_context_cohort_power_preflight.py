from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from research_v3.regime_context_cohort_power_preflight import (
    PreflightError,
    build_from_authorities,
    build_preflight,
)

ROOT = Path(__file__).resolve().parents[1]


class RegimeContextCohortPowerPreflightTests(unittest.TestCase):
    def test_current_accepted_authorities_fail_closed_without_inferential_cohort(self):
        result = build_preflight(ROOT)
        self.assertEqual(result["sampling_frame"]["eligible_identity_count"], 1576)
        self.assertIsNone(result["sampling_frame"]["selected_inferential_identity_count"])
        self.assertFalse(result["sampling_frame"]["structural_41_used_as_inferential_universe"])
        self.assertEqual(
            result["accepted_data_coverage"]["identities_with_verified_m5_bars"], 45
        )
        self.assertEqual(
            result["power_preflight"]["status"],
            "NOT_ESTIMABLE_FROM_ACCEPTED_FULL_FRAME_DATA",
        )
        self.assertEqual(
            result["decision"]["status"],
            "DATA_INSUFFICIENT_FOR_PROSPECTIVE_INFERENTIAL_COHORT_SELECTION",
        )
        self.assertFalse(result["interpretation_boundary"]["relative_value_alignment_inventory_recomputed"])
        self.assertEqual(result["accounting_effect"]["economic_outcomes_opened"], 0)

    def test_mismatched_full_frame_inventory_fails_closed(self):
        feasibility = json.loads(
            (ROOT / "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json")
            .read_text(encoding="utf-8")
        )
        peer = json.loads(
            (ROOT / "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json").read_text(
                encoding="utf-8"
            )
        )
        regime = json.loads(
            (ROOT / "evidence/REGIME_CONTEXT_DATA_SUFFICIENCY_AUDIT_V1.json").read_text(
                encoding="utf-8"
            )
        )
        inventory = json.loads(
            (ROOT / "evidence/EPOCH40_MEAN_REVERSION_STAGE1_TRIAGE_RESULT_V1.json").read_text(
                encoding="utf-8"
            )
        )
        changed = copy.deepcopy(inventory)
        changed["identities"].pop()
        with self.assertRaises(PreflightError):
            build_from_authorities(feasibility, peer, regime, changed)

    def test_structural_audit_cannot_be_promoted_to_a_full_frame_power_sample(self):
        feasibility = json.loads(
            (ROOT / "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json")
            .read_text(encoding="utf-8")
        )
        peer = json.loads(
            (ROOT / "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json").read_text(
                encoding="utf-8"
            )
        )
        regime = json.loads(
            (ROOT / "evidence/REGIME_CONTEXT_DATA_SUFFICIENCY_AUDIT_V1.json").read_text(
                encoding="utf-8"
            )
        )
        inventory = json.loads(
            (ROOT / "evidence/EPOCH40_MEAN_REVERSION_STAGE1_TRIAGE_RESULT_V1.json").read_text(
                encoding="utf-8"
            )
        )
        regime["scope"]["representative_count"] = 1576
        with self.assertRaises(PreflightError):
            build_from_authorities(feasibility, peer, regime, inventory)

    def test_deterministic_operation_preserves_later_semantic_data_scope_step(self):
        operation = json.loads(
            (
                ROOT
                / "research_v3/EPOCH41_REGIME_CONTEXT_COHORT_POWER_PREFLIGHT_DETERMINISTIC_OPERATION_V1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            operation["execution_policy"]["exact_head_green_required_before_execution"], True
        )
        self.assertFalse(operation["execution_policy"]["new_semantic_judgment_required"])
        self.assertEqual(
            operation["next_status"],
            "FRESH_GENERAL_AI_REASONING_REQUIRED_FOR_MINIMAL_REGIME_CONTEXT_DATA_SCOPE",
        )


if __name__ == "__main__":
    unittest.main()
