import json
import math
import random
import unittest
from pathlib import Path

from research_v3.relative_value_epoch24_diagnostic import (
    DiagnosticError,
    adf_stationarity,
    chronological_split,
    diagnose_pair,
    fit_development_hedge,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads(
    (ROOT / "research_v3/EPOCH24_RELATIVE_VALUE_DIAGNOSTIC_PLAN_V1.json").read_text()
)


def _synthetic_pair(n=600, seed=7):
    rng = random.Random(seed)
    log_right = [4.0]
    residual = 0.0
    rows = []
    for index in range(n):
        if index:
            log_right.append(log_right[-1] + rng.gauss(0.0, 0.008))
        residual = 0.45 * residual + rng.gauss(0.0, 0.006)
        log_left = 0.35 + 0.85 * log_right[-1] + residual
        rows.append(
            {
                "time_utc": f"2026-01-{1 + index // 100:02d}T{index % 24:02d}:00:00Z",
                "left_close": repr(math.exp(log_left)),
                "right_close": repr(math.exp(log_right[-1])),
            }
        )
    return {
        "symbols": ["AAA", "BBB"],
        "symbol_ids": [1, 2],
        "alignment": {
            "common_m5_timestamps": n,
            "left_rows": n,
            "right_rows": n,
            "left_only_rows": 0,
            "right_only_rows": 0,
            "forward_filled_rows": 0,
            "imputed_rows": 0,
        },
        "alignment_inventory_binding": {
            "expected_common_utc_dates": 60,
            "pair_inventory_reused_not_regenerated": True,
        },
        "comparability": {
            "status": "COMPARABLE",
            "comparable": True,
            "reasons": [],
            "quote_unit_inference_from_symbol_name": False,
        },
        "synchronized_closes": rows,
    }


class RelativeValueEpoch24DiagnosticTests(unittest.TestCase):
    def test_frozen_plan_is_non_economic_and_chronological(self):
        validate_plan(PLAN)
        split = chronological_split(500, PLAN)
        self.assertEqual(split["development"], (0, 300))
        self.assertEqual(split["validation"], (300, 400))
        self.assertEqual(split["holdout"], (400, 500))
        self.assertFalse(PLAN["time_split"]["holdout_refit"])
        self.assertFalse(PLAN["time_split"]["holdout_tuning"])
        self.assertFalse(PLAN["interpretation_boundary"]["pair_ranking"])
        self.assertFalse(PLAN["interpretation_boundary"]["returns_or_pnl"])

    def test_development_hedge_cannot_see_holdout_mutation(self):
        x = [float(i) for i in range(500)]
        y = [2.0 + 3.0 * value for value in x]
        base = fit_development_hedge(y, x, 300)
        y_mutated = list(y)
        x_mutated = list(x)
        for i in range(300, 500):
            y_mutated[i] = -100000.0 + i
            x_mutated[i] = 100000.0 - i
        changed = fit_development_hedge(y_mutated, x_mutated, 300)
        self.assertEqual(base, changed)
        self.assertAlmostEqual(base["intercept"], 2.0, places=10)
        self.assertAlmostEqual(base["beta"], 3.0, places=10)

    def test_stationary_fixture_has_deterministic_low_adf_p_value(self):
        rng = random.Random(11)
        series = []
        value = 0.0
        for _ in range(400):
            value = 0.35 * value + rng.gauss(0.0, 1.0)
            series.append(value)
        first = adf_stationarity(series, PLAN)
        second = adf_stationarity(series, PLAN)
        self.assertEqual(first, second)
        self.assertLessEqual(first["p_value"], PLAN["stationarity"]["alpha_development"])
        self.assertEqual(first["null_simulations"], 199)

    def test_pair_diagnostic_uses_frozen_holdout_and_opens_no_economics(self):
        result = diagnose_pair(_synthetic_pair(), PLAN)
        self.assertTrue(result["diagnostic_executed"])
        self.assertEqual(result["hedge"]["fit_end_exclusive"], 360)
        self.assertFalse(result["hedge"]["validation_refit"])
        self.assertFalse(result["hedge"]["holdout_refit"])
        self.assertIn("development", result["stationarity"])
        self.assertIn("holdout", result["stationarity"])
        self.assertEqual(result["economic_effect"]["economic_outcomes_opened"], 0)
        self.assertEqual(result["economic_effect"]["v2_attempts_consumed"], 0)
        self.assertFalse(result["economic_effect"]["returns_or_pnl_computed"])
        self.assertFalse(result["economic_effect"]["winning_pair_selected"])

    def test_noncomparable_pair_fails_before_statistical_execution(self):
        pair = _synthetic_pair()
        pair["comparability"] = {
            "status": "NOT_COMPARABLE_FAIL_CLOSED",
            "comparable": False,
            "reasons": ["QUOTE_UNIT_UNKNOWN_FAIL_CLOSED"],
        }
        result = diagnose_pair(pair, PLAN)
        self.assertFalse(result["diagnostic_executed"])
        self.assertEqual(result["classification"], "NOT_ADMISSIBLE_PRODUCT_COMPARABILITY")
        self.assertIn("QUOTE_UNIT_UNKNOWN_FAIL_CLOSED", result["failure_reasons"])

    def test_insufficient_alignment_fails_closed(self):
        pair = _synthetic_pair(n=299)
        result = diagnose_pair(pair, PLAN)
        self.assertFalse(result["diagnostic_executed"])
        self.assertEqual(result["classification"], "NOT_ADMISSIBLE_INSUFFICIENT_ALIGNMENT")

    def test_invalid_plan_cannot_enable_holdout_refit(self):
        changed = json.loads(json.dumps(PLAN))
        changed["time_split"]["holdout_refit"] = True
        with self.assertRaisesRegex(DiagnosticError, "holdout"):
            validate_plan(changed)


if __name__ == "__main__":
    unittest.main()
