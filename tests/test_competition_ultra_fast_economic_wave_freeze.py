import hashlib,json,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from discovery.canonical import verify_spec_hash
from m7.competition_ultra_fast_stage_a_evaluator import CAP,single
ROOT=Path(__file__).resolve().parents[1]
IDS=("V2-C017","V2-C018","V2-C019","V2-C020","V2-C021","V2-C022")
EVAL_SHA="b9b8fdecd7b415116149e611ff09961fe92793c66ec3d42796afa12946a46c6d"
class UltraFastEconomicWaveFreezeTests(unittest.TestCase):
 def test_01_capture_acceptance_exact_and_zero_economics(self):
  a=json.loads((ROOT/'data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json').read_text())
  self.assertEqual(a['source']['zip_sha256'],CAP);self.assertEqual(a['validation']['friction_records'],32);self.assertEqual(a['validation']['stage_a_selected_count'],10)
  self.assertEqual(a['validation']['friction_state_counts'],{'FRICTION_FAIL':19,'FRICTION_PASS':10,'FRICTION_WATCH':3});self.assertEqual(a['validation']['cost_confidence_counts'],{'FULL_FRICTION_RESOLVED':32})
  self.assertEqual(a['safety']['economic_outcomes_opened'],0);self.assertEqual(a['safety']['v2_attempts_consumed'],0);self.assertFalse(a['safety']['protected_evidence_opened'])
 def test_02_all_specs_are_hash_valid_and_wave_bound(self):
  w=json.loads((ROOT/'discovery/COMPETITION_ULTRA_FAST_ECONOMIC_WAVE_01_V1.json').read_text());self.assertEqual(w['candidate_ids'],list(IDS))
  for cid in IDS:
   s=json.loads((ROOT/'discovery/candidates'/f'{cid}.json').read_text());self.assertTrue(verify_spec_hash(s));self.assertEqual(s['spec_hash'],w['candidate_spec_hashes'][cid]);self.assertTrue(s['provenance']['frozen_before_candidate_own_economic_outcome'])
 def test_03_evaluator_is_exact_hash_bound_before_outcomes(self):
  w=json.loads((ROOT/'discovery/COMPETITION_ULTRA_FAST_ECONOMIC_WAVE_01_V1.json').read_text());p=ROOT/w['evaluator_ref'];h=hashlib.sha256(p.read_bytes()).hexdigest()
  self.assertEqual(h,EVAL_SHA);self.assertEqual(w['evaluator_sha256'],EVAL_SHA)
 def test_04_cost_is_candidate_independent_and_selected_resolved(self):
  c=json.loads((ROOT/'evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json').read_text());a=json.loads((ROOT/'data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json').read_text())
  self.assertTrue(c['rule']['candidate_independent']);self.assertTrue(c['rule']['outcome_blind']);self.assertEqual(set(c['symbols']),set(a['selected_markets']))
  self.assertTrue(all(v['roundtrip_cost_fraction']>0 and v['source_cost_confidence_state']=='FULL_FRICTION_RESOLVED' for v in c['symbols'].values()))
 def test_05_execution_gate_and_accounting_authority_remain_historically_pre_outcome(self):
  w=json.loads((ROOT/'discovery/COMPETITION_ULTRA_FAST_ECONOMIC_WAVE_01_V1.json').read_text());s=json.loads((ROOT/'CURRENT_STATE.json').read_text())
  self.assertIn('REQUIRE_EXACT_HEAD',w['execution_gate']);self.assertEqual(w['accounting_before_execution']['new_attempts_consumed'],0);self.assertEqual(w['accounting_before_execution']['v2_attempts_used'],2);self.assertEqual(w['accounting_before_execution']['remaining'],82);self.assertFalse(w['protected_evidence_opened']);self.assertFalse(s['protected_evidence_opened'])
 def test_06_historical_freeze_authority_stays_pre_outcome_without_claiming_live_results_absent(self):
  w=json.loads((ROOT/'discovery/COMPETITION_ULTRA_FAST_ECONOMIC_WAVE_01_V1.json').read_text());s=json.loads((ROOT/'CURRENT_STATE.json').read_text())
  self.assertEqual(w['status'],'FROZEN_BEFORE_C017_C022_ECONOMIC_OUTCOMES_PENDING_EXACT_HEAD_CI');self.assertEqual(w['accounting_before_execution']['economic_outcomes_opened'],0)
  self.assertEqual(w['accounting_before_execution']['v2_attempts_used'],2);self.assertEqual(w['accounting_before_execution']['remaining'],82)
  self.assertEqual(s['competition_ultra_fast_economic_wave']['opened_candidate_ids'],list(IDS));self.assertEqual(s['competition_ultra_fast_economic_wave']['unopened_candidate_ids'],[])
 def test_07_synthetic_momentum_is_next_open_fixed_hold_and_costed(self):
  t=datetime(2026,1,1,tzinfo=timezone.utc);q=[{'t':t+timedelta(minutes=5*i),'o':100+i,'h':101+i,'l':99+i,'c':100.5+i} for i in range(40)]
  x=single(q,'V2-C017','MOM',0.001)[0];self.assertEqual(x['e'],q[13]['t']);self.assertEqual(x['x'],q[24]['t']+timedelta(minutes=5));self.assertEqual(x['d'],'LONG');self.assertEqual(x['costf']*1000,1.0)
if __name__=='__main__':unittest.main()
