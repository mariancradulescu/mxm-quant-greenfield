import json,unittest
from pathlib import Path
from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger,derive_active_spec_hashes
ROOT=Path(__file__).resolve().parents[1]; IDS=[f'V2-C{i:03d}' for i in range(1,6)]
def load(p): return json.loads((ROOT/p).read_text())
class M51CandidateSemantics(unittest.TestCase):
 def test_m51_01_position_reentry_concurrency_explicit_all_five(self):
  for cid in IDS:
   p=load(f'discovery/candidates/{cid}.json')['position_admission_policy']
   for k in ('max_simultaneous_active_positions_per_symbol','max_simultaneous_candidate_instances','same_direction_pyramiding_allowed','opposite_signal_while_active','same_timestamp_exit_and_new_entry_opportunity'): self.assertIn(k,p)
   self.assertFalse(p['same_direction_pyramiding_allowed']); self.assertIn('IGNORE',p['opposite_signal_while_active'])
  self.assertFalse(load('discovery/candidates/V2-C001.json')['position_admission_policy']['multi_leg_relationship_counts_as_one_active_candidate_instance'])
  for cid in ('V2-C004','V2-C005'): self.assertTrue(load(f'discovery/candidates/{cid}.json')['position_admission_policy']['multi_leg_relationship_counts_as_one_active_candidate_instance'])
 def test_m51_02_stage_a_economic_units_exact_and_multileg_math(self):
  for cid in IDS:
   u=load(f'discovery/candidates/{cid}.json')['stage_a_economic_unit']; self.assertEqual(u['normalization_currency'],'EUR'); self.assertEqual(u['relationship_gross_absolute_entry_notional_eur'],1000.0); self.assertFalse(u['post_outcome_resizing_allowed']); self.assertIn('causal quote-currency-to-EUR',u['conversion_basis'])
  for cid in ('V2-C001','V2-C002','V2-C003'): self.assertEqual(load(f'discovery/candidates/{cid}.json')['stage_a_economic_unit']['per_leg_absolute_entry_notional_eur'],1000.0)
  for cid in ('V2-C004','V2-C005'):
   u=load(f'discovery/candidates/{cid}.json')['stage_a_economic_unit']; self.assertEqual(u['per_leg_absolute_entry_notional_eur'],500.0); self.assertIn('abs(q_i)',u['equal_absolute_unit_notional_definition']); self.assertIn('500',u['quantity_formula'])
 def test_m51_03_c005_mean_cross_is_strictly_causal(self):
  x=load('discovery/candidates/V2-C005.json')['exit']; self.assertTrue(x['mean_cross_same_bar_close_fill_forbidden']); self.assertIn('completed',x['mean_cross_detection'].lower()); self.assertIn('STRICTLY_AFTER_DETECTION_TIMESTAMP',x['mean_cross_fill']); self.assertIn('SCHEDULED_AT_ENTRY',x['max_hold_intent'])
 def test_m51_04_append_only_refreeze_supersession_history_preserved(self):
  es=read_ledger(ROOT/'discovery/ledger.jsonl'); freezes=[e for e in es if e['entry_type']=='CANDIDATE_FROZEN' and e['candidate_id'] in IDS]; refs=[e for e in es if e['entry_type']=='CANDIDATE_REFROZEN_PRE_OUTCOME' and e['candidate_id'] in IDS]; self.assertEqual(len(freezes),5); self.assertEqual(len(refs),5); self.assertFalse(any(e['entry_type']=='RESULT_RECORDED' for e in es)); self.assertEqual([e['sequence'] for e in freezes],[1,2,3,4,5]); self.assertEqual([e['sequence'] for e in refs],[6,7,8,9,10])
  for f,r in zip(freezes,refs): self.assertEqual(r['payload']['old_spec_hash'],f['spec_hash']); self.assertEqual(r['payload']['new_spec_hash'],r['spec_hash']); self.assertFalse(r['payload']['outcome_seen']); self.assertFalse(r['payload']['attempt_consumed'])
 def test_m51_05_active_old_hashes_match_corrected_specs(self):
  active=derive_active_spec_hashes(read_ledger(ROOT/'discovery/ledger.jsonl')); w=load('discovery/WAVE_01_V1.json')
  for cid in IDS:
   s=load(f'discovery/candidates/{cid}.json'); self.assertTrue(verify_spec_hash(s)); self.assertEqual(active[cid],s['spec_hash']); self.assertEqual(w['candidate_spec_hashes'][cid],s['spec_hash']); self.assertEqual(w['pre_outcome_semantic_completion']['active_spec_hashes'][cid],s['spec_hash'])
 def test_m51_06_global_invariants_and_m6_pending(self):
  s=load('CURRENT_STATE.json'); self.assertEqual(s['v2_search_budget'],84); self.assertEqual(s['v2_attempts_used'],0); self.assertEqual(s['v2_evaluated_identities'],0); self.assertEqual(s['v2_protected_forward_start'],'2026-09-17T12:02:58Z'); self.assertEqual(s['m6']['status'],'PENDING'); self.assertIsNone(s['latest_economic_outcome']); self.assertEqual(s['m5']['m5_1']['status'],'PASS')
if __name__=='__main__': unittest.main()
