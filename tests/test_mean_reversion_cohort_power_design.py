from __future__ import annotations

import unittest
import copy
from datetime import date, timedelta
from pathlib import Path

from research_v3.mean_reversion_cohort_power_design import (
    DesignError,
    audit_prior_scope_distinctness,
    build_power_preflight,
    dependence_adjusted_effective_sample_size,
    load_prior_freeze_scopes,
    required_effective_sample_size,
    select_outcome_blind_cohort,
)

ROOT = Path(__file__).resolve().parents[1]


class MeanReversionCohortPowerDesignTests(unittest.TestCase):
    def test_prior_comparison_uses_only_frozen_epoch25_and_epoch36_scopes(self):
        scopes = load_prior_freeze_scopes(ROOT)
        candidate = copy.deepcopy(scopes["EPOCH25"])
        candidate["lookback_bars"] = 24
        candidate["threshold"] = 1.5
        candidate["horizon_bars"] = 6
        audit = audit_prior_scope_distinctness(candidate, scopes)
        self.assertEqual(
            audit["comparisons"]["EPOCH25"]["classification"],
            "PARAMETERIZATION_ONLY",
        )
        self.assertFalse(audit["comparisons"]["EPOCH25"]["distinct_hypothesis_authorized"])
        self.assertFalse(audit["prior_results_read"])
        self.assertFalse(audit["distinct_hypothesis_authorized"])

    def test_structural_difference_is_reported_without_claiming_novelty(self):
        scopes = load_prior_freeze_scopes(ROOT)
        candidate = copy.deepcopy(scopes["EPOCH25"])
        candidate["response_estimand"]["measure"] = "A_DIFFERENT_PROSPECTIVE_ESTIMAND"
        audit = audit_prior_scope_distinctness(candidate, scopes)
        self.assertEqual(
            audit["comparisons"]["EPOCH25"]["classification"],
            "STRUCTURAL_DIFFERENCE_REQUIRES_PROSPECTIVE_JUDGMENT",
        )
        self.assertFalse(audit["distinct_hypothesis_authorized"])

    def test_outcome_blind_cohort_applies_frozen_rules_and_accounts_for_exclusions(self):
        rows = [
            {
                "symbol_id": 10,
                "current_entry_accessible": True,
                "both_direction_eur200_feasible": True,
                "post_exclusion_eligible": True,
                "data_completeness": 0.8,
                "capital_efficiency": 2.0,
            },
            {
                "symbol_id": 11,
                "current_entry_accessible": True,
                "both_direction_eur200_feasible": True,
                "post_exclusion_eligible": True,
                "data_completeness": 0.9,
                "capital_efficiency": 1.0,
            },
            {
                "symbol_id": 12,
                "current_entry_accessible": True,
                "both_direction_eur200_feasible": False,
                "post_exclusion_eligible": True,
                "data_completeness": 1.0,
                "capital_efficiency": 4.0,
            },
        ]
        policy = {
            "cohort_size": 1,
            "rationale": "Frozen outcome-blind sufficiency and capital-efficiency ranking.",
            "feature_fields": ["data_completeness", "capital_efficiency"],
            "filters": [
                {"field": "data_completeness", "operator": "gte", "value": 0.75}
            ],
            "ranking": [{"field": "data_completeness", "direction": "desc"}],
        }
        result = select_outcome_blind_cohort(rows, policy)
        self.assertEqual(result["selected_symbol_ids"], [11])
        self.assertTrue(result["selection_outcome_blind"])
        self.assertEqual(result["selected_identity_count"], 1)
        self.assertEqual(
            {row["symbol_id"] for row in result["exclusions"]}, {10, 12}
        )
        self.assertFalse(result["structural_representatives_substituted"])

    def test_cohort_rejects_outcome_features_and_unfrozen_fields(self):
        policy = {
            "cohort_size": 1,
            "rationale": "Rejected outcome-derived ranking.",
            "feature_fields": ["strategy_return"],
            "filters": [],
            "ranking": [{"field": "strategy_return", "direction": "desc"}],
        }
        with self.assertRaises(DesignError):
            select_outcome_blind_cohort([], policy)

    def test_effective_sample_size_and_planning_sensitivity_are_not_observed_power(self):
        dates = {
            date(2026, 1, 1) + timedelta(days=index): float(index >= 10)
            for index in range(20)
        }
        effective = dependence_adjusted_effective_sample_size(dates)
        self.assertEqual(effective["date_clusters"], 20)
        self.assertGreaterEqual(effective["effective_n"], 1)
        self.assertLess(effective["effective_n"], 20)
        self.assertFalse(effective["raw_bar_count_used_as_independent_n"])

        small_effect_n = required_effective_sample_size(
            0.2, hypothesis_count=4, target_power=0.8, familywise_alpha=0.05
        )
        large_effect_n = required_effective_sample_size(
            0.5, hypothesis_count=4, target_power=0.8, familywise_alpha=0.05
        )
        self.assertGreater(small_effect_n, large_effect_n)
        design = build_power_preflight(
            None,
            standardized_effect_scenarios=[0.2, 0.5],
            hypothesis_count=4,
            target_power=0.8,
            familywise_alpha=0.05,
        )
        self.assertEqual(design["status"], "NOT_ESTIMABLE_NO_ACCEPTED_DATE_LEVEL_PROXY")
        self.assertIsNone(design["effective_sample_size"])
        self.assertFalse(design["achieved_power_estimated"])
        self.assertFalse(design["strategy_outcomes_read"])

    def test_invalid_date_level_series_fails_closed(self):
        with self.assertRaises(DesignError):
            dependence_adjusted_effective_sample_size({date(2026, 1, 1): float("nan")})


if __name__ == "__main__":
    unittest.main()
