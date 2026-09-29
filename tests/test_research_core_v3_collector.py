from __future__ import annotations

import json
import unittest
from pathlib import Path

from research_core_v3.collector import (
    AUTHORITATIVE_FRONTIER,
    EXPECTED_ACCEPTED_IDENTITY_EXCLUSION,
    EXPECTED_COHORTS,
    EXPECTED_FRESH_EPOCH46_REPRESENTATIVES,
    EXPECTED_LEGACY_SINGLETON_COHORTS,
    EPOCH45_AUDIT_REL,
    EPOCH46_PLAN_REL,
    _accepted_epoch45_ids,
    build_wave0_plan,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]


class ResearchCoreV3CollectorTest(unittest.TestCase):
    def test_wave0_reproduces_epoch46_and_covers_all_41_cohorts(self):
        plan = build_wave0_plan(ROOT)
        self.assertTrue(validate_plan(plan))
        self.assertEqual(plan["authoritative_frontier"], AUTHORITATIVE_FRONTIER)
        self.assertEqual(plan["structural_cohort_count"], EXPECTED_COHORTS)
        self.assertEqual(len(plan["symbols"]), EXPECTED_COHORTS)
        self.assertEqual(len({x["symbol_id"] for x in plan["symbols"]}), EXPECTED_COHORTS)
        self.assertEqual(len({x["peer_candidate_cohort_id"] for x in plan["symbols"]}), EXPECTED_COHORTS)

        fresh = [
            x
            for x in plan["symbols"]
            if x["selection_role"] == "FRESH_EPOCH46_COMPATIBLE_REPRESENTATIVE"
        ]
        singleton = [
            x
            for x in plan["symbols"]
            if x["selection_role"] == "LEGACY_SINGLETON_RECAPTURE_FOR_REPO_BYTE_MATERIALIZATION"
        ]
        self.assertEqual(len(fresh), EXPECTED_FRESH_EPOCH46_REPRESENTATIVES)
        self.assertEqual(len(singleton), EXPECTED_LEGACY_SINGLETON_COHORTS)

        accepted_epoch46 = json.loads((ROOT / EPOCH46_PLAN_REL).read_text(encoding="utf-8"))
        expected = {
            (int(x["symbol_id"]), str(x["broker_symbol"]))
            for x in accepted_epoch46["symbols"]
        }
        actual = {(int(x["symbol_id"]), str(x["broker_symbol"])) for x in fresh}
        self.assertEqual(actual, expected)

    def test_selection_is_outcome_blind_and_protected_forward_closed(self):
        plan = build_wave0_plan(ROOT)
        law = plan["selection_law"]
        self.assertFalse(law["market_outcomes_used"])
        self.assertFalse(law["winner_identity_used"])
        self.assertFalse(plan["protected_forward_opened"])
        self.assertEqual(plan["economic_outcomes_opened"], 0)
        self.assertFalse(plan["strategy_returns_computed"])
        self.assertFalse(plan["pnl_computed"])
        self.assertFalse(plan["winner_selection_performed"])
        self.assertTrue(plan["capture_law"]["read_only"])
        self.assertFalse(plan["capture_law"]["orders_permitted"])
        self.assertFalse(plan["capture_law"]["account_mutation_permitted"])
        self.assertFalse(plan["capture_law"]["synthetic_fill_permitted"])
        self.assertFalse(plan["capture_law"]["forward_fill_permitted"])

    def test_epoch45_exclusion_is_exact_45(self):
        audit = json.loads((ROOT / EPOCH45_AUDIT_REL).read_text(encoding="utf-8"))
        accepted = _accepted_epoch45_ids(audit)
        self.assertEqual(len(accepted), EXPECTED_ACCEPTED_IDENTITY_EXCLUSION)


if __name__ == "__main__":
    unittest.main()
