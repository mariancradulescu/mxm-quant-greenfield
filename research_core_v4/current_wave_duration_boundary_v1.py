"""Deterministic nonoutcome mask audit. No market adapter or power simulation."""
import gzip,hashlib,json,pathlib,unittest
import numpy as np
R=pathlib.Path('.')
S='research_core_v4/state/';P='STRICT_PREOUTCOME_V2_'
START='aee51de1bcd3b8d2849a3ce0b40b6a9fa416a2f3'
FREEZE='c96c700623df9798d7b1bc393ebda2cad461551f'
WAVE=['MULTISCALE_PRICE_STATE','VOLATILITY_AND_REALIZED_VARIANCE_STATE','BROKER_NATIVE_ACTIVITY_STATE','CROSS_SECTIONAL_RELATIVE_STATE','REGIME_AND_STRUCTURAL_BREAK_STATE']
OUTPUTS={'event_masks.npz':'26acadf914fbcd904badd2200186424bf54f485af09cf69e797bf837f0f3aba7','support_counts.json.gz':'c9e272ffdea09790516ef2998a8635cbbe3da566d01f5c3d94ec76619ca4106b','dependence_geometry.json.gz':'3ec7a8a5045f2920c5043b720c070705a1ea15b659475cde2b809b61bad0daf3'}
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def load(p):return json.loads((R/p).read_bytes())
def artifact(n):return load(S+P+n+'.json')
def masks():return np.load(R/'support_only_v1/results/event_masks.npz',allow_pickle=False)
def counts():return json.loads(gzip.decompress((R/'support_only_v1/results/support_counts.json.gz').read_bytes()))
def geometry():return json.loads(gzip.decompress((R/'support_only_v1/results/dependence_geometry.json.gz').read_bytes()))
def audit():
 for n,h in OUTPUTS.items():assert sha('support_only_v1/results/'+n)==h,n
 c=counts();g=geometry();z=masks();records=c['per_candidate_identity_context_horizon']
 assert len(records)==14175
 result={'schema':'mxm.v4.current-wave.mask-duration-identifiability-result.v1','scope':'DURABLE_NONOUTCOME_MASKS_ONLY','protocol_freeze_commit':FREEZE,'allowed_mask_hashes':OUTPUTS,'old_original_available_at':'ALL_UNKNOWN_BYTE_EXACT','observed_calendar_days':28,'observed_domain':{'from_utc':'2026-08-20T00:00:00Z','end_exclusive_utc':'2026-09-17T00:00:00Z'},'current_wave':WAVE,'sources':{},'context_horizon_geometry':{},'identity_horizon_records_verified':0,'causal_unknown_arrays_verified':0,'first_nondefensible_quantity':'POSITIVE_OUT_OF_DOMAIN_CALENDAR_SUPPORT_LOWER_ENVELOPE','identified_incremental_support_lower_bound_without_transport_assumption':0,'transport_law_from_observed_masks':None,'minimum_duration_days':None,'shared_duration_days':None,'duration_search_started':False,'power_trials':0,'null_trials':0,'historical_effect_inputs':0,'new_economic_outcomes':0,'search_budget_use':0,'protected_forward_opened':False,'confirmation_opened':False,'status':'DURATION_UNIDENTIFIED_PENDING_INDEPENDENT_AUDIT'}
 for s in WAVE:
  horizons=[12] if s==WAVE[-1] else [1,12];total=0
  for h in horizons:
   rr=[r for r in records if r['source']==s and r['horizon_M5']==h]
   assert len(rr)==1575 and len({r['identity'] for r in rr})==1575
   key=s+'__'+str(h);slots=672 if s==WAVE[-1] else 8064;per_day=24 if s==WAVE[-1] else 288
   expected={key+'__'+k for k in ('baseline','feature','response','joint','causal_unknown')}
   assert expected<=set(z.files)
   for k in expected:assert z[k].dtype==np.uint8 and z[k].shape==(1575,slots//8)
   assert np.all(z[key+'__causal_unknown']==255);result['causal_unknown_arrays_verified']+=1
   joint=np.unpackbits(z[key+'__joint'],axis=1,bitorder='little')
   conjunction=np.bitwise_and(np.bitwise_and(z[key+'__baseline'],z[key+'__feature']),z[key+'__response'])
   assert np.array_equal(conjunction,z[key+'__joint'])
   daily=joint.reshape(1575,28,per_day).sum(axis=2)
   assert all(np.array_equal(daily[i],r['per_day_complete_counts']) and int(daily[i].sum())==r['geometric_joint_count'] for i,r in enumerate(rr))
   assert all(r['causal_pass_count']==r['causal_false_count']==0 and r['causal_unknown_count']==slots for r in rr)
   result['identity_horizon_records_verified']+=len(rr);total+=int(daily.sum())
   ctxs=sorted({r['context'] for r in rr});assert len(ctxs)==29
   result['context_horizon_geometry'][key]={}
   for ctx in ctxs:
    ix=[i for i,r in enumerate(rr) if r['context']==ctx]
    union=joint[ix].any(axis=0).reshape(28,per_day).sum(axis=1)
    entry=g['calendar_support'][key][ctx]
    assert np.array_equal(union,entry['per_date_entry_slot_counts'])
    assert int(union.sum())==entry['unique_entry_slots']
    week=union.reshape(4,7).sum(axis=1)
    result['context_horizon_geometry'][key][ctx]={'identity_count':len(ix),'daily_unique_entry_slots':union.tolist(),'observed_week_unique_entry_slots':week.tolist(),'observed_week_min':int(week.min()),'observed_week_max':int(week.max()),'observed_supported_dates':int(np.count_nonzero(union)),'identities_with_zero_observed_joint_support':int(np.count_nonzero(daily[ix].sum(axis=1)==0)),'out_of_domain_support_lower_bound_without_transport_law':0,'weekly_minimum_is_observed_not_future_bound':True}
  result['sources'][s]={'observed_joint_nodes':total,'valid_source_minimum_duration_days':None,'source_retained':True,'ranking':None}
 support=artifact('CURRENT_WAVE_SUPPORT_RESULT_V1')
 assert {s:result['sources'][s]['observed_joint_nodes'] for s in WAVE}==support['source_geometric_joint_counts']
 result['joint_node_total_verified']=sum(x['observed_joint_nodes'] for x in result['sources'].values())
 assert result['joint_node_total_verified']==18277854
 result['extension_counterexample']={'observed_domain':'Every existing packed mask and incidence remains fixed','extension_A':'Repeat an observed calendar-compatible support pattern outside the observed domain, as a hypothetical assumption only','extension_B':'No rows available outside the observed domain; every additional joint mask false','same_allowed_observations':True,'B_excluded_by_any_observed_mask':False,'logical_result':'No positive uniform incremental support lower bound is identified. A numerical conditional duration needs a declared transport model; no actual broker absence is inferred.'}
 result['dependence_nonidentification']={'same_fixed_support_geometry':True,'unit_marginal_variance_examples':['Cov(Z_d,Z_e)=1[d=e]','Cov(Z_d,Z_e)=1 for all d,e'], 'variance_of_mean':['1/n','1'],'both_positive_semidefinite':True,'interpretation':'Structural incidence does not impose a quantitative decay bound. AR025/AR050 are prospective finite scenarios, not measured correlation bounds. This is an analytic illustration, not simulation or observed score estimation.'}
 return result

class BoundaryValidation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.r=audit()
 def test_accepted_input_bindings(self):
  for p,h in artifact('CURRENT_WAVE_POWER_DURATION_BOUNDARY_AUTHORITY_V1')['immutable_input_sha256'].items():self.assertEqual(sha(p),h,p)
 def test_exact_current_wave_and_parked(self):
  f=artifact('CURRENT_TESTABILITY_FRONTIER_V1');b=artifact('CURRENT_WAVE_POWER_DURATION_SCIENTIFIC_BLOCKER_V1')
  self.assertEqual(f['current_wave'],WAVE);self.assertEqual(b['current_wave'],WAVE);self.assertEqual(b['parked_sources'],f['parked_sources']);self.assertEqual(len(f['parked_sources']),6)
 def test_original_unknown_and_conjunction(self):
  self.assertEqual(self.r['causal_unknown_arrays_verified'],9);self.assertEqual(self.r['identity_horizon_records_verified'],14175)
 def test_full_mask_domain(self):
  z=masks();self.assertEqual(len(z.files),48)
  for k in z.files:self.assertEqual(z[k].dtype,np.uint8)
 def test_geometric_nodes_and_calendar_parity(self):self.assertEqual(self.r['joint_node_total_verified'],18277854);self.assertEqual(len(self.r['context_horizon_geometry']),9)
 def test_deterministic_result(self):self.assertEqual(self.r,artifact('CURRENT_WAVE_MASK_DURATION_IDENTIFIABILITY_RESULT_V1'))
 def test_causal_separation_no_receipt_upgrade(self):
  a=artifact('CURRENT_WAVE_CAUSAL_SEMANTIC_SEPARATION_V1');self.assertEqual(a['original_receipt_revision_provenance'],'UNKNOWN');self.assertFalse(a['support_masks_modified']);self.assertEqual(a['old_causal_certified_nodes'],0)
  for p,h in a['bindings'].items():self.assertEqual(sha(p),h)
 def test_schedule_completed_and_future_window(self):
  # Exhaust the exact 8064 entry slots, using timestamp arithmetic only.
  t=np.arange(8064)*300;h=t//3600*3600
  for s in WAVE:
   tt=t[::12] if s==WAVE[-1] else t;hh=tt//3600*3600
   lo=hh-(4500 if s==WAVE[0] else 7200 if s==WAVE[-1] else 3600)
   self.assertTrue(bool(np.all(hh<=tt)));self.assertTrue(bool(np.all(tt-300+300<=tt)));self.assertTrue(bool(np.all(lo<hh)))
   for horizon in ([12] if s==WAVE[-1] else [1,12]):self.assertTrue(bool(np.all(tt+300*horizon>tt)))
 def test_nonidentification_is_not_broker_absence(self):
  e=self.r['extension_counterexample'];self.assertTrue(e['same_allowed_observations']);self.assertFalse(e['B_excluded_by_any_observed_mask']);self.assertIsNone(self.r['minimum_duration_days']);self.assertEqual(self.r['identified_incremental_support_lower_bound_without_transport_assumption'],0)
 def test_frozen_effect_grid_only(self):
  p=artifact('CURRENT_WAVE_DURATION_IDENTIFIABILITY_AUDIT_PROTOCOL_V1');d=load(S+'V4_DISCOVERY_PROTOCOL_V2.json')['power']
  self.assertEqual(p['power_effect_grid'],{k:d[k] for k in ('normal_local_MDE_SD','AR025_local_MDE_SD','AR050_local_MDE_SD')});self.assertEqual(p['minimum_power_lower_95_bound'],0.80)
 def test_no_simulation_or_duration_claim(self):
  b=artifact('CURRENT_WAVE_POWER_DURATION_SCIENTIFIC_BLOCKER_V1')
  self.assertEqual(b['power_trials'],0);self.assertEqual(b['null_trials'],0);self.assertIsNone(b['source_specific_minimum_duration_days']);self.assertIsNone(b['shared_duration_days']);self.assertFalse(b['power_target_met']);self.assertFalse(b['acquisition_arm_created'])
 def test_all_historical_canonical_fields_preserved(self):
  a=artifact('CURRENT_WAVE_POWER_DURATION_BOUNDARY_AUTHORITY_V1')
  for p in a['canonical_states']:
   before=load('baseline/'+p);after=load(p)
   for k,v in before.items():
    if k not in a['allowed_operational_state_changes']:self.assertEqual(after[k],v,(p,k))
   self.assertEqual(after['current_authority'],S+P+'CURRENT_WAVE_POWER_DURATION_BOUNDARY_AUTHORITY_V1.json');self.assertEqual(after['current_authority_sha256'],sha(S+P+'CURRENT_WAVE_POWER_DURATION_BOUNDARY_AUTHORITY_V1.json'))
 def test_no_external_boundary_crossing(self):
  a=artifact('CURRENT_WAVE_POWER_DURATION_BOUNDARY_AUTHORITY_V1')
  for k in ('raw_M5_reads','encrypted_asset_body_reads','redecryptions','broker_requests','ctrader_requests','new_market_data_requests','feature_value_computations','response_value_computations','return_inputs','pnl_inputs','new_economic_outcomes','search_budget_use','power_trials'):self.assertEqual(a[k],0,k)
  self.assertFalse(a['protected_forward_opened']);self.assertFalse(a['confirmation_opened'])
 def test_manifest_sha_bindings(self):
  a=artifact('CURRENT_WAVE_POWER_DURATION_BOUNDARY_AUTHORITY_V1')
  for p,h in a['new_artifact_sha256'].items():self.assertEqual(sha(p),h,p)

if __name__=='__main__':
 import sys
 if '--derive' in sys.argv:
  print(json.dumps(audit(),indent=2,sort_keys=True,allow_nan=False));raise SystemExit(0)
 unittest.main()
