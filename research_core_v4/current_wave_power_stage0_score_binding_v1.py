"""Exact legal synthetic conditional-null audit; no reader of numeric market data.

This is not a null Monte Carlo or power experiment and does not choose a scorer.
It tests whether affine residualization can silently stand for sigma(B) control.
"""
import importlib.util,json,pathlib,hashlib,unittest
from fractions import Fraction as F
from datetime import datetime,timedelta,timezone
R=pathlib.Path('.');S='research_core_v4/state/';P='STRICT_PREOUTCOME_V2_'
START='54d0c9583178c51496f9403ac79ae6d7cd833fcc';FREEZE='b613fea4f249d834b100988f7a473fbe533fa28d'
def load(p):return json.loads((R/p).read_bytes())
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def artifact(n):return load(S+P+n+'.json')
def baseline_function():
 spec=importlib.util.spec_from_file_location('frozen_compact_baseline',(R/'research_core_v4/compact_baseline_v2.py').resolve());m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.baseline
def fabricated_bars(q,phi,y):
 # A hypothetical single-event legal domain, never broker records.
 bars=[]
 for t in range(3600,10800,300):
  close=1 if 6300<=t<7200 and phi==-1 else 3
  bars.append({'timestamp':t,'available_at':t+300,'open':2,'high':4,'low':1,'close':close,'tick_volume':q})
 future=F(6) if y==1 else F(3,2)
 for k in range(12):
  t=10800+k*300;o=F(3) if k==0 else future
  bars.append({'timestamp':t,'available_at':t+300,'open':o,'high':max(o,future),'low':min(o,future),'close':future,'tick_volume':q})
 return bars
def phi_map(bars):
 def state(lo,hi):
  b=[x for x in bars if lo<=x['timestamp']<hi];high=max(x['high'] for x in b);low=min(x['low'] for x in b);loc=(F(b[-1]['close'])-low)/(high-low) if high>low else F(1,2)
  return 1 if loc>F(1,2) else -1 if loc<F(1,2) else 0
 return state(6300,7200)*state(7200,10800)
def validity_projection(bars):
 return tuple((x['timestamp'],x['low']<=min(x['open'],x['close'])<=max(x['open'],x['close'])<=x['high'],x['open']>0,x['close']>0,type(x['tick_volume']) is int and x['tick_volume']>=0) for x in bars)
def proof():
 pplus={0:F(3,4),1:F(1,4),2:F(3,4)};atoms=[];base=baseline_function();mask=None;B_by_q={}
 for q in range(3):
  for phi in (-1,1):
   for y in (-1,1):
    bars=fabricated_bars(q,phi,y);b=base(10800,bars);assert b is not None and len(b)==10
    assert phi_map(bars)==phi
    assert b[4]==q and b[7]==12*q
    assert b[:4]==(2,4,1,3) and b[5]==F(2,3) and b[6]==3
    assert q not in B_by_q or B_by_q[q]==b;B_by_q[q]=b
    m=validity_projection(bars);assert all(all(v for v in row[1:]) for row in m)
    assert mask is None or mask==m;mask=m
    pp=pplus[q] if phi==1 else 1-pplus[q];py=pplus[q] if y==1 else 1-pplus[q]
    atoms.append({'q':q,'phi':phi,'y_over_log2':y,'probability':F(1,3)*pp*py})
 assert sum(a['probability'] for a in atoms)==1
 E=lambda fn:sum(a['probability']*fn(a) for a in atoms)
 mean_phi=E(lambda a:F(a['phi']));mean_y=E(lambda a:F(a['y_over_log2']));mean_q=E(lambda a:F(a['q']))
 assert mean_phi==mean_y==F(1,6) and mean_q==1
 assert E(lambda a:(a['q']-mean_q)*(a['phi']-mean_phi))==0
 assert E(lambda a:(a['q']-mean_q)*(a['y_over_log2']-mean_y))==0
 # All ten B coordinates lie in span{1,q}; the population affine nuisances
 # therefore have intercept1/6 and slope0, with no finite-prefix error needed.
 affine_score=E(lambda a:(F(a['phi'])-mean_phi)*(F(a['y_over_log2'])-mean_y))
 m={q:2*pplus[q]-1 for q in range(3)}
 oracle_score=E(lambda a:(F(a['phi'])-m[a['q']])*(F(a['y_over_log2'])-m[a['q']]))
 assert affine_score==F(2,9) and oracle_score==0
 for q in range(3):
  aa=[a for a in atoms if a['q']==q]
  assert sum(a['probability'] for a in aa)==F(1,3)
  assert sum(a['probability']*(a['phi']-m[q])*(a['y_over_log2']-m[q]) for a in aa)==0
 return {'schema':'mxm.v4.power.stage0-score-binding-audit.result.v1','protocol_freeze_commit':FREEZE,'scope':'EXACT_FABRICATED_LEGAL_DOMAIN_PROOF_NO_MARKET_VALUES','status':'AFFINE_SURROGATE_NOT_CENTERED_UNDER_FROZEN_CONDITIONAL_INFORMATION_NULL','atoms':[{k:str(v) if isinstance(v,F) else v for k,v in a.items()} for a in atoms],'atom_count':12,'all_validity_and_window_masks_identical':True,'frozen_baseline_dimensions':10,'B_affine_span':['1','q'],'B_activity_coordinates':['q','12*q'],'conditional_Phi_mean_by_q':{str(q):str(m[q]) for q in m},'population_affine_nuisance':{'intercept':'1/6','q_slope':'0'},'conditional_null_Y_independent_Phi_given_B':True,'conditional_feature_variance':'3/4','population_affine_residual_score_expectation_in_log2_units':str(affine_score),'exact_conditioning_score_expectation':str(oracle_score),'nuisance_bias_present_even_with_population_oracle_linear_fits':True,'future_log_return_relation':'Y=ln(2)*y_over_log2; legal h1 endpoints6 or3/2 from close3','feature_and_response_are_synthetic_only':True,'real_feature_values':0,'real_response_values':0,'real_return_inputs':0,'broker_requests':0,'power_trials':0,'null_monte_carlo_trials':0,'no_synthetic_effect_grid_selected_or_retuned':True,'not_a_current_wave_estimator_failure':'Affine surrogate was never an accepted current-wave scorer. This result blocks silently importing it, not an existing certified current-wave design.','not_an_impossibility_theorem':'A richer justified nuisance model, conditional randomization design, or explicitly scoped predictive benchmark may work. Those require a new complete score/prefix/null specification before synthetic certification.','not_source_redundancy_or_global_null':True}

class Validation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.r=proof()
 def test_exact_conditional_null(self):self.assertTrue(self.r['conditional_null_Y_independent_Phi_given_B']);self.assertEqual(self.r['exact_conditioning_score_expectation'],'0')
 def test_population_bias_not_finite_prefix(self):self.assertEqual(self.r['population_affine_residual_score_expectation_in_log2_units'],'2/9');self.assertTrue(self.r['nuisance_bias_present_even_with_population_oracle_linear_fits'])
 def test_source_not_degenerate(self):self.assertEqual(self.r['conditional_feature_variance'],'3/4');self.assertEqual(self.r['atom_count'],12)
 def test_identical_nonoutcome_geometry(self):self.assertTrue(self.r['all_validity_and_window_masks_identical'])
 def test_exact_result_reproduction(self):self.assertEqual(self.r,artifact('CURRENT_WAVE_POWER_STAGE0_SCORE_BINDING_AUDIT_RESULT_V1'))
 def test_accepted_authorities_immutable(self):
  for p,h in artifact('CURRENT_WAVE_PROGRESSIVE_DEPTH_STAGE0_AUTHORITY_V1')['immutable_inputs_sha256'].items():self.assertEqual(sha(p),h,p)
 def test_paid_leaf_and_identity_accounting(self):
  d=artifact('CURRENT_WAVE_PROGRESSIVE_DEPTH_PAID_LEAF_INVENTORY_V1');roster=load(d['roster_ref'])['entries'];expected={(r['SYMBOL_ID'],r['BROKER_NATIVE_CONTEXT']) for r in roster}
  self.assertEqual(len(expected),1575);self.assertEqual(len(d['leaves']),261)
  for s in d['current_wave']:
   for h in ([12] if s=='REGIME_AND_STRUCTURAL_BREAK_STATE' else [1,12]):
    got={(i,l['context']) for l in d['leaves'] if l['source']==s and l['horizon_M5']==h for i in l['cohort_identities']};self.assertEqual(got,expected)
  self.assertTrue(all(l['paid'] for l in d['leaves']))
 def test_exact_six_block_calendar_without_transport(self):
  d=artifact('CURRENT_WAVE_PROGRESSIVE_SUPPORT_DEPTH_CALENDAR_V1');end=datetime(2026,8,20,tzinfo=timezone.utc)
  for b in d['blocks']:
   begin=end-timedelta(days=28);self.assertEqual(b['from_utc'],begin.isoformat().replace('+00:00','Z'));self.assertEqual(b['end_exclusive_utc'],end.isoformat().replace('+00:00','Z'));self.assertEqual(b['requests_made'],0);end=begin
  self.assertEqual(len(d['blocks']),6);self.assertEqual(d['maximum_cumulative_days'],196);self.assertFalse(d['stationarity_or_repetition_assumed']);self.assertFalse(d['acquisition_arm_created'])
 def test_five_sources_six_parked_unchanged(self):
  a=artifact('CURRENT_WAVE_PROGRESSIVE_DEPTH_STAGE0_AUTHORITY_V1');f=artifact('CURRENT_TESTABILITY_FRONTIER_V1');self.assertEqual(a['current_wave'],f['current_wave']);self.assertEqual(a['parked_sources'],f['parked_sources']);self.assertEqual(len(a['current_wave']),5);self.assertEqual(len(a['parked_sources']),6)
 def test_effect_grid_unchanged_and_not_power_claim(self):
  p=artifact('CURRENT_WAVE_POWER_STAGE0_SCORE_BINDING_AUDIT_PROTOCOL_V1');d=load(S+'V4_DISCOVERY_PROTOCOL_V2.json')['power'];self.assertEqual(p['effect_grid_SD'],{'normal':d['normal_local_MDE_SD'],'AR025':d['AR025_local_MDE_SD'],'AR050':d['AR050_local_MDE_SD']});self.assertEqual(p['minimum_power_lower95'],0.8);self.assertFalse(p['complete_pass_fail_procedure_frozen']);self.assertIsNone(p['trial_count'])
 def test_zero_ingress_and_stopped_before_broker(self):
  a=artifact('CURRENT_WAVE_PROGRESSIVE_DEPTH_STAGE0_AUTHORITY_V1')
  for k in ('new_ctrader_requests','new_rows_streamed','additional_blocks_acquired','power_trials','null_monte_carlo_trials','new_economic_outcomes','search_budget_use','raw_M5_reads','encrypted_asset_body_reads','real_feature_response_return_pnl_inputs'):self.assertEqual(a[k],0,k)
  for k in ('acquisition_arm_created','complete_power_protocol_frozen','protected_forward_opened','confirmation_opened'):self.assertFalse(a[k],k)
 def test_old_receipt_unknown_not_promoted(self):
  a=artifact('HISTORICAL_RECEIPT_REVISION_PROVENANCE_BOUNDARY_V1');self.assertEqual(a['original_available_at'],'UNKNOWN_ALL_POTENTIAL_EVENTS');self.assertEqual(a['old_causal_counts']['PASS'],0)
 def test_canonical_history_preserved_and_current_aligned(self):
  a=artifact('CURRENT_WAVE_PROGRESSIVE_DEPTH_STAGE0_AUTHORITY_V1')
  for p in a['canonical_states']:
   before=load('baseline/'+p);after=load(p)
   for k,v in before.items():
    if k not in a['allowed_operational_changes']:self.assertEqual(after[k],v,(p,k))
   self.assertEqual(after['current_authority'],S+P+'CURRENT_WAVE_PROGRESSIVE_DEPTH_STAGE0_AUTHORITY_V1.json');self.assertEqual(after['current_authority_sha256'],sha(after['current_authority']))
 def test_new_artifact_bindings(self):
  for p,h in artifact('CURRENT_WAVE_PROGRESSIVE_DEPTH_STAGE0_AUTHORITY_V1')['new_artifacts_sha256'].items():self.assertEqual(sha(p),h,p)

if __name__=='__main__':
 import sys
 if '--derive' in sys.argv:print(json.dumps(proof(),sort_keys=True,indent=2,allow_nan=False));raise SystemExit(0)
 unittest.main()
