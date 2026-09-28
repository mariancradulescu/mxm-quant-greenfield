from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from research_v3.mean_reversion_hypothesis_power_preflight import (
    FREEZE_REF,
    PreflightError,
    build_preflight,
)

ROOT = Path(__file__).resolve().parents[1]


class MeanReversionHypothesisPowerPreflightTests(unittest.TestCase):
    def test_preflight_freezes_distinct_design_without_opening_response_statistics(self):
        result = build_preflight(ROOT)
        self.assertEqual(
            result["status"], "COMPLETE_NON_ECONOMIC_HYPOTHESIS_AND_POWER_PREFLIGHT"
        )
        self.assertEqual(result["sampling_frame"]["eligible_identity_count"], 1576)
        self.assertIsNone(result["sampling_frame"]["selected_inferential_cohort"])
        self.assertFalse(
            result["sampling_frame"]["structural_41_used_as_inferential_universe"]
        )
        self.assertEqual(
            result["accepted_data_coverage"]["bounded_inventory_verified_m5_identities"],
            45,
        )
        self.assertIn(
            "no absence claim",
            result["accepted_data_coverage"]["other_accepted_capture_scopes"],
        )
        self.assertFalse(result["power_preflight"]["achieved_power_estimated"])
        self.assertFalse(result["power_preflight"]["response_statistics_computed"])
        self.assertFalse(result["novelty_audit"]["prior_results_read"])
        self.assertFalse(result["novelty_audit"]["response_statistic_evaluated"])
        self.assertFalse(result["data_boundary"]["new_market_data_requested"])
        self.assertFalse(
            result["temporal_boundary"]["future_response_evaluation_authorized_in_this_phase"]
        )
        self.assertEqual(result["accounting_effect"]["economic_outcomes_opened"], 0)

    def test_hypothesis_is_structurally_distinct_from_both_prior_freezes(self):
        result = build_preflight(ROOT)
        comparisons = result["novelty_audit"]["comparisons"]
        self.assertEqual(set(comparisons), {"EPOCH25", "EPOCH36"})
        for comparison in comparisons.values():
            self.assertEqual(
                comparison["classification"],
                "STRUCTURAL_DIFFERENCE_REQUIRES_PROSPECTIVE_JUDGMENT",
            )
            self.assertFalse(comparison["distinct_hypothesis_authorized"])

    def test_freeze_rejects_inferential_substitution_or_unauthorized_cohort(self):
        freeze = json.loads((ROOT / FREEZE_REF).read_text(encoding="utf-8"))
        changed = copy.deepcopy(freeze)
        changed["scope"]["structural_41_default_inferential_authority"] = True
        with self.assertRaises(PreflightError):
            from research_v3.mean_reversion_hypothesis_power_preflight import _validate_freeze

            _validate_freeze(ROOT, changed)

        changed = copy.deepcopy(freeze)
        changed["scope"]["selected_cohort"] = [1, 2, 3]
        with self.assertRaises(PreflightError):
            from research_v3.mean_reversion_hypothesis_power_preflight import _validate_freeze

            _validate_freeze(ROOT, changed)

    def test_power_scenarios_are_planning_only_and_respect_multiplicity(self):
        scenarios = build_preflight(ROOT)["power_preflight"]["planning_sensitivity"]
        required = [
            item["required_effective_independent_clusters"] for item in scenarios
        ]
        self.assertEqual([item["hypothesis_count"] for item in scenarios], [36] * 3)
        self.assertGreater(required[0], required[1])
        self.assertGreater(required[1], required[2])
        self.assertTrue(
            all(
                item["interpretation"]
                == "PLANNING_SENSITIVITY_ONLY_NOT_AN_ECONOMIC_THRESHOLD"
                for item in scenarios
            )
        )


if __name__ == "__main__":
    unittest.main()
