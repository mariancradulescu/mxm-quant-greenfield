"""Pure synthetic decision fixtures. Never imports or executes probe/transport."""
import copy,hashlib,json,socket,unittest,urllib.request
from pathlib import Path
from unittest.mock import patch
from research_core_v4.quote_probe_decision_law_v1 import load_bound,decide,CELLS,LAW_PATH
ROOT=Path(__file__).resolve().parents[1]
class DecisionLawProof(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.law,cls.plan=load_bound(ROOT)
 def setUp(self):
  self.execution={'status':'PROBE_COMPLETED_SUPPORT_TRANSPORT_ONLY','plan_sha256':self.law['bindings']['probe_plan']['sha256'],'source_file_sha256':{self.law['bindings']['probe_contract']['path']:self.law['bindings']['probe_contract']['sha256']},'frontier_identity_sha256':self.plan['frontier_identity_sha256'],'scope_view_verified':True,'base_requests_completed':1120,'base_request_total':1120,'no_window_side_slots':0,'local_totals':{'all_local_files_bytes':1000000},'elapsed_active_seconds_all_resumes':60,'historical_wire_attempts_including_retry':1120,'response_values_computed':False,'pnl_computed':False,'orders_sent':0,'full_capture_started':False}
  self.verify={k:True for k in ['exact_manifest_complete','checkpoint_integrity','scope_account_binding','lossless_reconstruction','package_checksums']};self.verify['saturated_1ms']=False
  self.matrix=[]
  for ident in self.plan['identities']:
   for week in self.plan['week_indices']:
    self.matrix.append({'symbol_id':ident['symbol_id'],'asset_class':ident['asset_class'],'week_index':week,'status':'SINGLETON_TRANSPORT_ONLY_NO_FEATURE_COUNTS' if ident['transport_only_singleton'] else 'SUPPORT_COUNTS_ONLY','support':{'response_values_read':False,'cells':[{'cell_id':c,'nonoverlap_attempts':0,'timestamp_completable_attempts':0,'retention_fraction_timestamp_only':None} for c in CELLS]}})
  self.contexts=sorted({i['asset_class'] for i in self.plan['identities'] if not i['transport_only_singleton']})
 def plausible(self,context,weeks=8,completed=16,attempts=20,cell=CELLS[0]):
  for r in self.matrix:
   if r['asset_class']==context and r['week_index'] in self.plan['week_indices'][:weeks]:
    c=next(c for c in r['support']['cells'] if c['cell_id']==cell);c.update(nonoverlap_attempts=attempts,timestamp_completable_attempts=completed,retention_fraction_timestamp_only=completed/attempts)
 def run_law(self):return decide(self.law,self.plan,self.execution,self.matrix,self.verify)
 def test_zero_plausible_contexts_stop_not_null(self):
  r=self.run_law();self.assertEqual(r['classification'],'DATA_LIMITED_ACQUISITION_NOT_JUSTIFIED');self.assertEqual(r['plausible_contexts'],[]);self.assertFalse(r['economic_null_claimed']);self.assertFalse(r['mechanism_closure_declared'])
 def test_exactly_one_context_second_stage_review_only(self):
  self.plausible(self.contexts[0]);r=self.run_law();self.assertEqual(r['plausible_contexts'],self.contexts[:1]);self.assertTrue(r['second_stage_design_review_eligible']);self.assertFalse(r['second_stage_acquisition_authorized']);self.assertFalse(r['scientific_response_authorized']);self.assertFalse(r['full1576_capture_authorized'])
 def test_multiple_contexts_report_all27_all24_siblings(self):
  for ctx in self.contexts[:3]:self.plausible(ctx)
  r=self.run_law();self.assertEqual(r['plausible_contexts'],self.contexts[:3]);self.assertEqual(len(r['all27_context_same_cell_common_week_counts']),27);self.assertTrue(all(len(c)==24 for c in r['all27_context_same_cell_common_week_counts'].values()))
 def test_transport_budget_failure_overrides_support(self):
  self.plausible(self.contexts[0])
  for key,value in [('elapsed_active_seconds_all_resumes',7200.01),('historical_wire_attempts_including_retry',11201)]:
   original=self.execution[key];self.execution[key]=value;self.assertEqual(self.run_law()['classification'],'TRANSPORT_ARCHITECTURE_NOT_FEASIBLE_AS_CURRENTLY_CONFIGURED');self.execution[key]=original
  self.execution['local_totals']['all_local_files_bytes']=2000000001;self.assertEqual(self.run_law()['action'],'STOP_FAIL_CLOSED')
 def test_saturated1ms_forces_stop(self):
  self.plausible(self.contexts[0]);self.verify['saturated_1ms']=True;self.assertEqual(self.run_law()['action'],'STOP_FAIL_CLOSED')
 def test_checkpoint_account_and_lossless_failure(self):
  for key in ['checkpoint_integrity','scope_account_binding','lossless_reconstruction']:
   self.verify[key]=False;self.assertEqual(self.run_law()['action'],'STOP_FAIL_CLOSED');self.verify[key]=True
 def test_seven_vs_eight_common_weeks(self):
  self.plausible(self.contexts[0],weeks=7);self.assertEqual(self.run_law()['classification'],'DATA_LIMITED_ACQUISITION_NOT_JUSTIFIED');self.plausible(self.contexts[0],weeks=8);self.assertTrue(self.run_law()['second_stage_design_review_eligible'])
 def test_exact15_and80percent_boundary(self):
  self.plausible(self.contexts[0],completed=15,attempts=18);self.assertTrue(self.run_law()['second_stage_design_review_eligible'])
  self.plausible(self.contexts[0],completed=14,attempts=15);self.assertFalse(self.run_law()['second_stage_design_review_eligible'])
  self.plausible(self.contexts[0],completed=15,attempts=19);self.assertFalse(self.run_law()['second_stage_design_review_eligible'])
  self.plausible(self.contexts[0],completed=16,attempts=20);self.assertTrue(self.run_law()['second_stage_design_review_eligible'])
 def test_pair_must_share_same_cell_not_each_best_cell(self):
  ctx=self.contexts[0];ids=[i['symbol_id'] for i in self.plan['identities'] if i['asset_class']==ctx]
  for r in self.matrix:
   if r['symbol_id'] in ids:
    c=r['support']['cells'][ids.index(r['symbol_id'])];c.update(nonoverlap_attempts=20,timestamp_completable_attempts=16,retention_fraction_timestamp_only=0.8)
  self.assertFalse(self.run_law()['second_stage_design_review_eligible'])
 def test_incomplete_or_malformed_matrix_fail_closed(self):
  self.matrix.pop();self.assertEqual(self.run_law()['action'],'STOP_FAIL_CLOSED')
 def test_bad_unfavorable_sibling_not_hidden_by_short_circuit(self):
  self.matrix[1]['support']['cells'][0]['nonoverlap_attempts']=-1;self.assertEqual(self.run_law()['action'],'STOP_FAIL_CLOSED')
 def test_unavailable_counts_not_inferred_as_support(self):
  self.plausible(self.contexts[0]);r=next(x for x in self.matrix if x['asset_class']==self.contexts[0]);r['status']='ENDPOINT_UNAVAILABLE';self.assertFalse(self.run_law()['second_stage_design_review_eligible'])
 def test_binding_mismatch_fail_closed(self):
  self.execution['plan_sha256']='0'*64;self.assertEqual(self.run_law()['action'],'STOP_FAIL_CLOSED')
 def test_science_plan_and_historical_law_unchanged_current_rebinding(self):
  old=ROOT/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_POST_PROBE_DECISION_LAW_V1.json'
  self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(),'9c03409cab9c5d5623aa2bd5a694afcc3bb8a6915572a6ae27876aa0bc62a6d2')
  self.assertEqual(self.law['thresholds'],json.loads(old.read_bytes())['thresholds'])
  self.assertEqual(hashlib.sha256((ROOT/self.law['implementation']).read_bytes()).hexdigest(),self.law['implementation_sha256'])
 def test_singletons_cannot_enable_continuation(self):
  for r in self.matrix:
   if r['status']=='SINGLETON_TRANSPORT_ONLY_NO_FEATURE_COUNTS':
    for c in r['support']['cells']:c.update(nonoverlap_attempts=20,timestamp_completable_attempts=16,retention_fraction_timestamp_only=0.8)
  self.assertEqual(self.run_law()['classification'],'DATA_LIMITED_ACQUISITION_NOT_JUSTIFIED')
 def test_exact_transport_cap_boundaries_are_inclusive(self):
  self.plausible(self.contexts[0]);self.execution['local_totals']['all_local_files_bytes']=2000000000;self.execution['elapsed_active_seconds_all_resumes']=7200;self.execution['historical_wire_attempts_including_retry']=11200
  self.assertTrue(self.run_law()['second_stage_design_review_eligible'])
 def test_no_network_and_deterministic_order(self):
  self.plausible(self.contexts[0]);
  with patch.object(socket,'create_connection',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(urllib.request,'urlopen',side_effect=AssertionError('NETWORK_FORBIDDEN')):
   a=self.run_law();self.matrix.reverse();self.assertEqual(a,self.run_law())
if __name__=='__main__':unittest.main()
