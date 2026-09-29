from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from research_v3.mean_reversion_power_aware_discovery import (
    DiscoveryError,
    build_from_authorities,
    build_preflight,
)

ROOT = Path(__file__).resolve().parents[1]


def _authorities():
    return (
        json.loads(
            (ROOT / "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json")
            .read_text(encoding="utf-8")
        ),
        json.loads(
            (ROOT / "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json").read_text(
                encoding="utf-8"
            )
        ),
        json.loads(
            (ROOT / "evidence/EPOCH40_MEAN_REVERSION_STAGE1_TRIAGE_RESULT_V1.json").read_text(
                encoding="utf-8"
            )
        ),
        json.loads(
            (ROOT / "evidence/EPOCH42_MEAN_REVERSION_COHORT_POWER_PREFLIGHT_V1.json").read_text(
                encoding="utf-8"
            )
        ),
        json.loads(
            (ROOT / "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json")
            .read_text(encoding="utf-8")
        ),
    )


class MeanReversionPowerAwareDiscoveryTests(unittest.TestCase):
    def test_current_authorities_preserve_full_frame_and_fail_closed_on_inference(self):
        result = build_preflight(ROOT)
        self.assertEqual(result["sampling_frame"]["eligible_identity_count"], 1576)
        self.assertIsNone(result["sampling_frame"]["selected_inferential_cohort"])
        self.assertFalse(result["sampling_frame"]["structural_41_used_as_inferential_universe"])
        self.assertEqual(
            result["accepted_data_coverage"][
                "identities_with_verified_m5_bars_in_bounded_inventory"
            ],
            45,
        )
        self.assertEqual(
            result["accepted_data_coverage"][
                "accepted_history_identities_in_persisted_candidate_index"
            ],
            42,
        )
        self.assertFalse(result["accepted_data_coverage"]["absence_claim_for_other_capture_scopes"])
        self.assertEqual(
            result["accepted_data_coverage"]["outcome_blind_feature_coverage"]["denominator"],
            1576,
        )
        self.assertGreater(
            result["accepted_data_coverage"]["outcome_blind_feature_coverage"][
                "identities_with_feature"
            ]["realized_volatility_opportunity_proxy"],
            0,
        )
        self.assertLessEqual(
            result["accepted_data_coverage"]["outcome_blind_feature_coverage"][
                "identities_with_feature"
            ]["realized_volatility_opportunity_proxy"],
            45,
        )
        self.assertTrue(
            result["accepted_data_coverage"]["accepted_external_capture"][
                "bytes_external_to_git_are_transport_materialization_not_new_acquisition"
            ]
        )
        self.assertFalse(
            result["accepted_data_coverage"]["accepted_external_capture"][
                "this_interval_disjoint_from_epoch25_epoch36_response_window"
            ]
        )
        self.assertFalse(result["power_preflight"]["achieved_power_estimated"])
        self.assertFalse(result["power_preflight"]["epoch42_diagnostic_rerun"])
        self.assertFalse(result["interpretation_boundary"]["relative_value_alignment_inventory_recomputed"])
        self.assertEqual(result["accounting_effect"]["economic_outcomes_opened"], 0)

    def test_full_frame_identity_mismatch_fails_closed(self):
        feasibility, peer, inventory, epoch42, capture = _authorities()
        changed = copy.deepcopy(inventory)
        changed["identities"].pop()
        with self.assertRaises(DiscoveryError):
            build_from_authorities(feasibility, peer, changed, epoch42, capture)

    def test_structural_representatives_cannot_become_the_inferential_frame(self):
        feasibility, peer, inventory, epoch42, capture = _authorities()
        changed = copy.deepcopy(peer)
        changed["identities"] = changed["identities"][:41]
        with self.assertRaises(DiscoveryError):
            build_from_authorities(feasibility, changed, inventory, epoch42, capture)

    def test_unknown_completeness_and_missing_event_dependence_are_not_imputed(self):
        feasibility, peer, inventory, epoch42, capture = _authorities()
        result = build_from_authorities(feasibility, peer, inventory, epoch42, capture)
        self.assertEqual(
            result["accepted_data_coverage"]["schedule_adjusted_completeness_auditable_identities"],
            0,
        )
        self.assertEqual(
            result["accepted_data_coverage"]["identities_with_event_cluster_and_effective_sample_support"],
            0,
        )
        self.assertIsNone(result["power_preflight"]["observed_effective_sample_size"])

    def test_deterministic_operation_preserves_later_data_scope_judgment(self):
        operation = json.loads(
            (
                ROOT
                / "research_v3/EPOCH43_MEAN_REVERSION_POWER_AWARE_DISCOVERY_DETERMINISTIC_OPERATION_V1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(operation["execution_policy"]["new_semantic_judgment_required"])
        self.assertTrue(operation["execution_policy"]["exact_head_green_required_before_execution"])
        self.assertEqual(
            operation["next_reasoning_action"],
            "AUDIT_EXACT_ACCEPTED_MEAN_REVERSION_CAPTURE_SCOPES_AND_PROSPECTIVELY_DEFINE_ANY_MINIMAL_DISJOINT_DATA_INCREMENT",
        )


if __name__ == "__main__":
    unittest.main()
