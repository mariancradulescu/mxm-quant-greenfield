"""Non-economic readback acceptance. Opens ONLY existing Git-tracked JSON."""
import copy
import tempfile
from pathlib import Path
import unittest
from .portfolio_delivery_gate import (load_originals, diagnose, extract, RESULTS, HARD21,
                                       FIRST, LAST, git_blob_hash)

class DeliveryReadback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = load_originals()
        cls.result = diagnose(cls.originals)

    def test_existing_eur200_outcomes_stay_separate(self):
        r=self.result
        self.assertEqual(set(r['candidates']),set(RESULTS))
        self.assertEqual(r['overlap_weeks_count'],13)
        self.assertEqual(r['weekly_upper_bounds'][0]['iso_week'],FIRST)
        self.assertEqual(r['weekly_upper_bounds'][-1]['iso_week'],LAST)
        self.assertEqual([r['candidates'][x]['executed_entries']
                          for x in ('V2-C006','V2-C012','V2-C031')],[108,35,126])
        self.assertTrue(r['separate_scenario_equity_and_net_must_never_be_added'])
        self.assertFalse(r['common_eur200_account_simulated'])

    def test_all_overlapping_weeks_have_strict_hard21_upper_bound(self):
        r=self.result
        self.assertEqual(r['max_same_iso_week_recorded_accepted_entries_sum'],17)
        self.assertEqual(r['all_reported_rejected_entries'],3)
        self.assertEqual(r['max_weekly_optimistic_bound_including_all_rejections'],20)
        self.assertEqual(r['peak_sum_even_if_on_different_weeks'],20)
        self.assertEqual(r['status'],'CERTAINLY_BELOW_HARD21_FROM_FROZEN_CANDIDATES')
        self.assertEqual(len(r['weekly_upper_bounds']),13)
        for row in r['weekly_upper_bounds']:
            self.assertEqual(sum(row['separate_account_entry_counts'].values()),
                             row['recorded_accepted_entries_sum'])
            self.assertEqual(row['absolute_bound_if_all_original_rejections_added'],
                             row['recorded_accepted_entries_sum']+3)
            self.assertLess(row['absolute_bound_if_all_original_rejections_added'],HARD21)
            self.assertGreater(row['shortfall_to_HARD21_at_least'],0)

    def test_owner_current_risk_bounds_are_not_legacy_stage_b_promotion(self):
        x=self.result['candidates']
        self.assertEqual(x['V2-C012']['owner_margin_80'],'NECESSARY_MARGIN_CAP_FAIL')
        self.assertEqual(x['V2-C031']['owner_free_reserve_120'],
                         'OBSERVED_SCENARIO_FREE_RESERVE_FAIL')
        self.assertEqual(x['V2-C006']['owner_margin_80'],
                         'MARGIN_CAP_NECESSARY_PASS_ONLY')
        self.assertEqual(x['V2-C006']['owner_free_reserve_120'],'FREE_RESERVE_NOT_PROVEN')
        self.assertFalse(self.result['owner_stop_risk_proven'])
        self.assertFalse(self.result['historical_costs_and_fills_certified'])

    def test_no_trading_or_trial_consumption(self):
        r=self.result
        for key in ('new_economic_executions','previous_models_rerun',
                    'new_broker_requests','live_demo_orders','cloud_activations'):
            self.assertEqual(r[key],0)

    def test_incomplete_common_calendar_cannot_be_padded_with_zero(self):
        x=copy.deepcopy(self.originals)
        del x['V2-C006']['frozen_reporting']['weekly_final_equity_eur']['2026-W28']
        with self.assertRaisesRegex(ValueError,'COMMON_OBSERVATION_WINDOW_INCOMPLETE'):
            diagnose(x)

    def test_forged_earlier_deposit_not_accepted(self):
        x=copy.deepcopy(self.originals)
        x['V2-C006']['economic_summary']['starting_equity_eur']=1000
        with self.assertRaisesRegex(ValueError,'SEPARATE_INITIAL_CAPITAL'):
            diagnose(x)

    def test_counts_cannot_be_changed_after_outcome(self):
        x=copy.deepcopy(self.originals)
        x['V2-C031']['base_path']['entries_by_iso_week']['2026-W25']=16
        with self.assertRaisesRegex(ValueError,'C031_ENTRY_INVENTORY'):
            diagnose(x)

    def test_repository_original_bytes_pinned(self):
        path,sha=RESULTS['V2-C006']
        root=Path(__file__).resolve().parents[2]
        self.assertEqual(git_blob_hash((root/path).read_bytes()),sha)
        with tempfile.TemporaryDirectory() as t:
            temp=Path(t)/path
            temp.parent.mkdir(parents=True)
            temp.write_bytes((root/path).read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'FROZEN_BLOB_CHANGED'):
                load_originals(Path(t))

if __name__=='__main__':
    unittest.main()
