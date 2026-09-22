import unittest
from pathlib import Path

from discovery.accounting import assert_current_state_matches_repository, derive_current_accounting
from discovery.persistence import build_post_outcome_plan
from m6.tier1_candidate_replay import _prior_finite_window

ROOT=Path(__file__).resolve().parents[1]


class CurrentAccountingIntegrityTests(unittest.TestCase):
    def test_live_accounting_is_derived_not_hard_coded(self):
        d=assert_current_state_matches_repository(ROOT)
        self.assertEqual(d["v2_search_budget_remaining"],d["v2_search_budget"]-d["v2_attempts_used"])
        self.assertEqual(d["global_attempts_seen"],d["legacy_prior_attempts"]+d["v2_attempts_used"])
        self.assertEqual(d["v2_attempts_used"],len(d["evaluated_candidate_ids"]))

    def test_c012_prior_window_excludes_current_observation(self):
        values=[float(i) for i in range(522)] + [10_000_000.0]
        prior=_prior_finite_window(values,522,520)
        self.assertEqual(len(prior),520)
        self.assertNotIn(10_000_000.0,prior)
        self.assertEqual(prior[0],2.0)
        self.assertEqual(prior[-1],521.0)

    def test_duplicate_persistence_is_idempotent(self):
        import json
        result=json.loads((ROOT/"discovery/results/V2-C023_STAGE_A_V1.json").read_text())
        plan=build_post_outcome_plan(
            ROOT,result=result,result_relpath="discovery/results/V2-C023_STAGE_A_V1.json",
            timestamp_utc="2026-09-22T13:05:00Z",
        )
        self.assertEqual(plan["status"],"IDEMPOTENT_ALREADY_RECORDED")


if __name__=="__main__":
    unittest.main(verbosity=2)
