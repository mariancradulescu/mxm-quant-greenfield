import json,unittest
from pathlib import Path
from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger
ROOT=Path(__file__).resolve().parents[1]
def load(p): return json.loads((ROOT/p).read_text())
class M5WaveFreeze(unittest.TestCase):
 def test_m5_01_original_wave_is_preserved_and_deferred_pre_outcome(self):
  w=load('discovery/WAVE_01_V1.json'); self.assertEqual(w['status'],'DEFERRED_PRE_OUTCOME_DATA_AVAILABILITY_ANCHOR'); self.assertEqual(len(w['candidate_ids']),5); self.assertEqual(len(set(w['candidate_ids'])),5); self.assertEqual(w['economic_outcomes_opened'],0); self.assertFalse(w['deferral']['economic_failure']); self.assertFalse(w['deferral']['contamination'])
 def test_m5_02_original_candidates_validate_hashes_and_match_wave(self):
  w=load('discovery/WAVE_01_V1.json')
  for cid in w['candidate_ids']:
   spec=load(f'discovery/candidates/{cid}.json'); self.assertTrue(verify_spec_hash(spec)); self.assertEqual(spec['spec_hash'],w['candidate_spec_hashes'][cid]); self.assertEqual(spec['cost_state']['state'],'UNRESOLVED')
 def test_m5_03_original_materially_distinct_families_preserved(self):
  fam=load('discovery/WAVE_01_V1.json')['materially_distinct_families']; self.assertEqual(set(fam),{'TREND_MOMENTUM','MEAN_REVERSION','BREAKOUT_VOLATILITY_EXPANSION','CROSS_SECTIONAL_RANKING','RELATIVE_VALUE_COINTEGRATION'})
 def test_m5_04_ledger_preserves_original_freezes_and_has_no_results(self):
  es=read_ledger(ROOT/'discovery/ledger.jsonl'); old=[e for e in es if e['entry_type']=='CANDIDATE_FROZEN' and e['candidate_id'] in [f'V2-C{i:03d}' for i in range(1,6)]]; self.assertEqual([e['sequence'] for e in old],[1,2,3,4,5]); self.assertFalse(any(e['entry_type']=='RESULT_RECORDED' for e in es))
 def test_m5_05_budget_and_protected_boundary_unchanged(self):
  w=load('discovery/WAVE_01_V1.json'); self.assertEqual(w['search_budget'],84); self.assertEqual(w['v2_attempts_used'],0); self.assertEqual(w['protected_forward_start'],'2026-09-17T12:02:58Z')
 def test_m5_06_state_preserves_m5_complete_and_m6_pending(self):
  s=load('CURRENT_STATE.json'); self.assertEqual(s['m5']['status'],'COMPLETE'); self.assertEqual(s['m6']['status'],'PENDING'); self.assertEqual(s['v2_attempts_used'],0); self.assertEqual(s['v2_evaluated_identities'],0); self.assertIsNone(s['latest_economic_outcome']); self.assertEqual(s['m5']['result_entries'],0); self.assertEqual(s['phase'],'PRIMARY_WAVE_FROZEN_PRE_M6')
if __name__=='__main__': unittest.main(verbosity=2)
