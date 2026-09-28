import json
import unittest
from pathlib import Path

from research_v3.mean_reversion_scope_power_preflight import (
    EFFECT_SCENARIOS,
    FREEZE_REF,
    LOOKBACKS,
    HORIZONS,
    THRESHOLDS,
    PreflightError,
    build_preflight,
    required_effective_dates,
    validate_freeze,
)

ROOT = Path(__file__).resolve().parents[1]


class MeanReversionScopePowerPreflightTests(unittest.TestCase):
    def test_freeze_binds_current_full_universe_and_design_without_outcomes(self):
        freeze = json.loads((ROOT / FREEZE_REF).read_text(encoding="utf-8"))
        validate_freeze(freeze, ROOT)
        self.assertEqual(
            freeze["authority"]["source_eligible_identity_set_sha256"],
            "e53dc4e58d4e0d37eca4f528e06d0866ad8ffe3f2bc64d35278ecc8ee9f52a65",
        )
        self.assertEqual(len(LOOKBACKS) * len(THRESHOLDS) * len(HORIZONS), 36)
        self.assertFalse(freeze["scope"]["structural_41_default_inferential_authority"])
        self.assertFalse(freeze["interpretation_boundary"]["economic_outcome_opened"])

    def test_power_sensitivity_uses_effective_independent_dates_and_increases_for_smaller_effects(self):
        required = [required_effective_dates(effect) for effect in EFFECT_SCENARIOS]
        self.assertGreater(required[0], required[1])
        self.assertGreater(required[1], required[2])
        self.assertGreater(required[2], 0)

    def test_preflight_does_not_claim_observed_power_or_select_a_panel(self):
        result = build_preflight(ROOT)
        self.assertEqual(result["status"], "COMPLETE_NON_ECONOMIC_SCOPE_AND_POWER_DESIGN_PREFLIGHT")
        self.assertEqual(result["scope"]["sampling_frame_size"], 1576)
        self.assertFalse(result["scope"]["symbol_subselection_performed"])
        self.assertFalse(result["design"]["power_sensitivity"]["achieved_power_estimated"])
        self.assertFalse(result["interpretation_boundary"]["economic_outcome_opened"])
        self.assertEqual(result["accounting_effect"]["v2_attempts_consumed"], 0)

    def test_freeze_rejects_changed_scope_or_unsafe_boundary(self):
        freeze = json.loads((ROOT / FREEZE_REF).read_text(encoding="utf-8"))
        freeze["design"]["coarse_parameter_regions"]["cell_count"] = 35
        with self.assertRaises(PreflightError):
            validate_freeze(freeze, ROOT)

        freeze = json.loads((ROOT / FREEZE_REF).read_text(encoding="utf-8"))
        freeze["interpretation_boundary"]["protected_forward_opened"] = True
        with self.assertRaises(PreflightError):
            validate_freeze(freeze, ROOT)


if __name__ == "__main__":
    unittest.main()
