import copy,json,tempfile,unittest
from pathlib import Path
from discovery.canonical import compute_result_hash,verify_spec_hash
from discovery.ledger import append_entry,derive_active_spec_hashes,read_ledger
from discovery.schema import SchemaError,STAGE_A_METRIC_KEYS,validate_candidate_spec,validate_result
ROOT=Path(__file__).resolve().parents[1]
OLD_IDS=[f'V2-C{i:03d}' for i in range(1,6)]; NEW_IDS=[f'V2-C{i:03d}' for i in range(6,13)]
def load(p): return json.loads((ROOT/p).read_text())
def candidate(cid='V2-C006'):
 return load(f'discovery/candidates/{cid}.json')
def metrics():
 return {
  'event_count':0,'gross_pnl':0.0,'coarse_net_pnl':0.0,'gross_return':0.0,'coarse_net_return':0.0,
  'gross_per_event':0.0,'net_per_event':0.0,'cost_burden':0.0,'turnover':0.0,
  'weekly_events':{'2026-W01':0},'active_weeks':0,'longest_inactive_gap':0,
  'weekday_distribution':{'MON':0},'session_distribution':{'ALL':0},'hold_duration':{'mean_bars':0.0},
  'exposure':0.0,'drawdown':0.0,'symbol_contribution':{'SYNTHETIC':0.0},
  'direction_contribution':{'LONG':0.0},'subperiod_contribution':{'DEV':0.0},'regime_contribution':{'ALL':0.0}
 }
def valid_result(cid='V2-C900',spec_hash='a'*64,stage='A'):
 m=metrics()
 if stage=='B':
  m['capital_realization']={'continuous_capital_path':{'state':'AVAILABLE','value':[200.0]},'weekly_final_equity_distribution':{'state':'AVAILABLE','value':[200.0]},'monthly_final_equity_distribution':{'state':'AVAILABLE','value':[200.0]},'capital_occupancy':0.0,'margin_blockers':{'state':'AVAILABLE','value':{'blocked_events':0}},'executed_trade_distribution':{'state':'AVAILABLE','value':[0]}}
 return {'candidate_id':cid,'spec_hash':spec_hash,'stage':stage,'status':'COST_UNRESOLVED','implementation_validity':{'state':'VALID','reason':'synthetic lifecycle fixture'},'metrics':m,'eur200_feasibility':{'state':'NOT_EVALUATED','reason':'synthetic lifecycle fixture'},'cost_confidence':{'state':'UNRESOLVED','reason':'synthetic lifecycle fixture'},'data_completeness':{'state':'SUFFICIENT','reason':'synthetic lifecycle fixture'},'provenance':{'data_evidence':{'identity':'SYNTHETIC_DATA','binding':{'type':'DATASET_SHA256','sha256':'1'*64}},'cost_evidence':{'identity':'SYNTHETIC_COST','state':'UNRESOLVED','sha256':'2'*64},'evaluator':{'version':'test-v1','sha256':'3'*64}}}
class PreM6IntegrityClosure(unittest.TestCase):
 def test_01_candidate_missing_position_policy_rejected(self):
  s=candidate(); s.pop('position_admission_policy')
  with self.assertRaises(SchemaError): validate_candidate_spec(s)
 def test_02_candidate_missing_stage_a_economic_unit_rejected(self):
  s=candidate(); s.pop('stage_a_economic_unit')
  with self.assertRaises(SchemaError): validate_candidate_spec(s)
 def test_03_stage_a_empty_metrics_rejected(self):
  r=valid_result(); r['metrics']={}
  with self.assertRaises(SchemaError): validate_result(r)
 def test_04_stage_a_incomplete_metrics_rejected(self):
  r=valid_result(); r['metrics'].pop('regime_contribution')
  with self.assertRaises(SchemaError): validate_result(r)
 def test_05_stage_b_missing_capital_realization_rejected(self):
  r=valid_result(stage='B'); r['metrics'].pop('capital_realization')
  with self.assertRaises(SchemaError): validate_result(r)
 def test_06_empty_implementation_validity_rejected(self):
  r=valid_result(); r['implementation_validity']={}
  with self.assertRaises(SchemaError): validate_result(r)
 def test_07_empty_cost_confidence_rejected(self):
  r=valid_result(); r['cost_confidence']={}
  with self.assertRaises(SchemaError): validate_result(r)
 def test_08_empty_data_completeness_rejected(self):
  r=valid_result(); r['data_completeness']={}
  with self.assertRaises(SchemaError): validate_result(r)
 def test_09_empty_eur200_feasibility_rejected(self):
  r=valid_result(); r['eur200_feasibility']={}
  with self.assertRaises(SchemaError): validate_result(r)
 def test_10_missing_data_provenance_rejected(self):
  r=valid_result(); r['provenance'].pop('data_evidence')
  with self.assertRaises(SchemaError): validate_result(r)
 def test_11_missing_cost_provenance_rejected(self):
  r=valid_result(); r['provenance'].pop('cost_evidence')
  with self.assertRaises(SchemaError): validate_result(r)
 def test_12_missing_evaluator_binding_rejected(self):
  r=valid_result(); r['provenance'].pop('evaluator')
  with self.assertRaises(SchemaError): validate_result(r)
 def test_13_result_for_unfrozen_candidate_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'ledger.jsonl'; r=valid_result('V2-C900','a'*64)
   with self.assertRaises(ValueError): append_entry(p,entry_type='RESULT_RECORDED',candidate_id='V2-C900',spec_hash='a'*64,payload={'result':r,'result_hash':compute_result_hash(r)})
 def test_14_result_against_stale_hash_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'ledger.jsonl'; append_entry(p,entry_type='CANDIDATE_FROZEN',candidate_id='V2-C900',spec_hash='a'*64,payload={}); r=valid_result('V2-C900','b'*64)
   with self.assertRaises(ValueError): append_entry(p,entry_type='RESULT_RECORDED',candidate_id='V2-C900',spec_hash='b'*64,payload={'result':r,'result_hash':compute_result_hash(r)})
 def test_15_result_against_current_active_hash_lifecycle_valid(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'ledger.jsonl'; append_entry(p,entry_type='CANDIDATE_FROZEN',candidate_id='V2-C900',spec_hash='a'*64,payload={}); r=valid_result('V2-C900','a'*64); e=append_entry(p,entry_type='RESULT_RECORDED',candidate_id='V2-C900',spec_hash='a'*64,payload={'result':r,'result_hash':compute_result_hash(r)}); self.assertEqual(e['entry_type'],'RESULT_RECORDED')
 def test_16_pre_outcome_refreeze_after_any_result_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'ledger.jsonl'; append_entry(p,entry_type='CANDIDATE_FROZEN',candidate_id='V2-C900',spec_hash='a'*64,payload={}); r=valid_result('V2-C900','a'*64); append_entry(p,entry_type='RESULT_RECORDED',candidate_id='V2-C900',spec_hash='a'*64,payload={'result':r,'result_hash':compute_result_hash(r)})
   with self.assertRaises(ValueError): append_entry(p,entry_type='CANDIDATE_REFROZEN_PRE_OUTCOME',candidate_id='V2-C900',spec_hash='b'*64,payload={'old_spec_hash':'a'*64,'new_spec_hash':'b'*64,'outcome_seen':False,'attempt_consumed':False})
 def test_17_existing_ledger_hash_chain_valid(self): self.assertEqual(len(read_ledger(ROOT/'discovery/ledger.jsonl')),20)
 def test_18_old_c001_c005_freeze_refreeze_history_preserved(self):
  es=read_ledger(ROOT/'discovery/ledger.jsonl'); self.assertEqual([(e['sequence'],e['candidate_id'],e['entry_type']) for e in es[:10]],[(1,'V2-C001','CANDIDATE_FROZEN'),(2,'V2-C002','CANDIDATE_FROZEN'),(3,'V2-C003','CANDIDATE_FROZEN'),(4,'V2-C004','CANDIDATE_FROZEN'),(5,'V2-C005','CANDIDATE_FROZEN'),(6,'V2-C001','CANDIDATE_REFROZEN_PRE_OUTCOME'),(7,'V2-C002','CANDIDATE_REFROZEN_PRE_OUTCOME'),(8,'V2-C003','CANDIDATE_REFROZEN_PRE_OUTCOME'),(9,'V2-C004','CANDIDATE_REFROZEN_PRE_OUTCOME'),(10,'V2-C005','CANDIDATE_REFROZEN_PRE_OUTCOME')])
 def test_19_active_hashes_existing_candidates_deterministic(self):
  active=derive_active_spec_hashes(read_ledger(ROOT/'discovery/ledger.jsonl'))
  for cid in OLD_IDS: self.assertEqual(active[cid],candidate(cid)['spec_hash'])
 def test_20_new_primary_candidates_active_completion_matches_specs(self):
  base=load('discovery/PRIMARY_WAVE_02_V1.json'); completion=load('discovery/PRIMARY_WAVE_02_PRE_OUTCOME_COMPLETION_V1.json'); self.assertEqual(base['candidate_ids'],NEW_IDS); active=derive_active_spec_hashes(read_ledger(ROOT/'discovery/ledger.jsonl'))
  for cid in NEW_IDS:
   s=candidate(cid); self.assertTrue(verify_spec_hash(s)); self.assertEqual(completion['original_candidate_hashes'][cid],base['candidate_spec_hashes'][cid]); self.assertEqual(completion['active_candidate_hashes'][cid],s['spec_hash']); self.assertEqual(active[cid],s['spec_hash'])
 def test_21_no_economic_result_created_by_correction(self): self.assertFalse(any(e['entry_type']=='RESULT_RECORDED' for e in read_ledger(ROOT/'discovery/ledger.jsonl')))
 def test_22_v2_attempts_remain_zero(self): self.assertEqual(load('CURRENT_STATE.json')['v2_attempts_used'],0)
 def test_23_v2_evaluated_identities_remain_zero(self): self.assertEqual(load('CURRENT_STATE.json')['v2_evaluated_identities'],0)
 def test_24_protected_forward_timestamp_unchanged(self):
  self.assertEqual(load('V2_PROTECTED_FORWARD_START.json')['V2_PROTECTED_FORWARD_START'],'2026-09-17T12:02:58Z'); self.assertFalse(load('V2_PROTECTED_FORWARD_START.json')['protected_evidence_opened'])
 def test_25_old_wave_frozen_artifact_separate_deferral_and_not_active_primary(self):
  old=load('discovery/WAVE_01_V1.json'); d=load('discovery/WAVE_01_DEFERRAL_V1.json'); st=load('CURRENT_STATE.json'); self.assertEqual(old['status'],'FROZEN_BEFORE_ANY_V2_ECONOMIC_OUTCOME'); self.assertEqual(d['state'],'DEFERRED_PRE_OUTCOME_DATA_AVAILABILITY_ANCHOR'); self.assertEqual(st['active_primary_wave_id'],'PRIMARY_WAVE_02')
 def test_26_candidate_json_schema_requires_new_generic_fields(self):
  s=load('discovery/candidate.schema.json'); self.assertIn('position_admission_policy',s['required']); self.assertIn('stage_a_economic_unit',s['required']); self.assertEqual(s['properties']['position_admission_policy']['minProperties'],1); self.assertEqual(s['properties']['stage_a_economic_unit']['minProperties'],1)
 def test_27_data_requirements_v1_derived_after_wave_freeze_and_preserved(self):
  d=load('data/PRIMARY_WAVE_02_DATA_REQUIREMENTS_V1.json'); self.assertTrue(d['derivation_order']['wave_frozen_first']); self.assertTrue(d['derivation_order']['data_requirements_derived_after_freeze']); self.assertEqual(set(d['requirements']),set(NEW_IDS)); self.assertEqual(d['economic_outcomes_opened'],0)
 def test_28_frontier_selection_is_outcome_blind_and_not_data_led(self):
  w=load('discovery/PRIMARY_WAVE_02_V1.json'); self.assertTrue(w['outcome_blind_selection']); self.assertFalse(w['data_availability_primary_selection_criterion']); self.assertEqual(w['shared_data_efficiency_role'],'SECONDARY_TIE_BREAK_ONLY')
 def test_29_cost_confidence_states_remain_exactly_frozen_three(self):
  self.assertEqual(set(load('DISCOVERY_COST_MODEL_V1.json')['allowed_cost_confidence_states']),{'VERIFIED','CONSERVATIVE_BOUND','UNRESOLVED'})
if __name__=='__main__': unittest.main(verbosity=2)
