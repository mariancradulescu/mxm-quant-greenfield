import json,unittest
from pathlib import Path
from research_v3.mean_reversion_epoch48_stage2_robust_neighborhood import EFFECT_SCENARIOS,N,LOOKBACKS,THRESHOLDS,TARGET_POWER,ZERO,Stage2Error,_adjacent,build_stage2,identify_symbol_regions,validate_freeze
ROOT=Path(__file__).resolve().parents[1]; FREEZE=ROOT/'research_v3/EPOCH48_MEAN_REVERSION_STAGE2_ROBUST_NEIGHBORHOOD_FREEZE_V1.json'
def freeze(): return json.loads(FREEZE.read_text())
def ctx(): return {f'S{i}':{'symbol_id':i,'peer_candidate_cohort_id':f'p{i}','structural_stratum':{'asset_class':'X','product_type':'Y','coverage_bucket':'Z','session_regions':'R'},'minimum_directional_margin_eur':1,'schedule_minutes_per_week':1} for i in range(N)}
def rows(ok=None):
 ok=ok or {}; out=[]
 for i in range(N):
  s=f'S{i}'
  for l in LOOKBACKS:
   for t in THRESHOLDS:
    out.append({'broker_symbol':s,'lookback_bars':l,'absolute_standardized_deviation_threshold':t,'closed_form_power_estimates':[{'standardized_effect':e,'estimated_power':TARGET_POWER if ok.get((s,l,t,e),False) else 0.0} for e in EFFECT_SCENARIOS],'eligible_contiguous_windows':10,'reversal_event_count':2,'event_availability_rate':.1,'dependence_adjusted_effective_date_clusters':5.0})
 return out
class FreezeTests(unittest.TestCase):
 def test_real_authority(self): validate_freeze(freeze(),ROOT)
 def test_no_cohort_majority(self):
  b=json.dumps(freeze()).lower(); self.assertNotIn('bare majority',b); self.assertNotIn('count of power-adequate identities',b)
 def test_reject_common_optimum(self):
  f=freeze(); f['stage2_neighborhood_law']['scope_unit']='COHORT_COMMON_PARAMETER_REGION'
  with self.assertRaises(Stage2Error): validate_freeze(f,ROOT)
 def test_reject_economic_crossing(self):
  f=freeze(); f['interpretation_boundary']['economic_outcome_opened']=True
  with self.assertRaises(Stage2Error): validate_freeze(f,ROOT)
class RegionTests(unittest.TestCase):
 def test_rook_adjacency(self):
  self.assertTrue(_adjacent((12,1.0),(12,1.5))); self.assertTrue(_adjacent((12,1.0),(24,1.0))); self.assertFalse(_adjacent((12,1.0),(24,1.5)))
 def test_symbol_specific_not_cohort_vote(self):
  x=identify_symbol_regions(rows({('S0',12,1.0,.5):True,('S0',12,1.5,.5):True}),ctx()); a=next(z for z in x if z['broker_symbol']=='S0'); b=next(z for z in x if z['broker_symbol']=='S1')
  self.assertTrue(a['effect_scenarios']['0.5']['supported_parameter_neighborhood_exists']); self.assertFalse(b['effect_scenarios']['0.5']['supported_parameter_neighborhood_exists'])
 def test_isolated_rejected(self):
  x=identify_symbol_regions(rows({('S0',12,1.0,.5):True}),ctx()); a=next(z for z in x if z['broker_symbol']=='S0'); self.assertFalse(a['effect_scenarios']['0.5']['supported_parameter_neighborhood_exists'])
 def test_zero_event_not_eligible(self):
  x=rows({('S0',12,1.0,.5):True,('S0',12,1.5,.5):True})
  for r in x:
   if r['broker_symbol']=='S0' and r['lookback_bars']==12: r['reversal_event_count']=0; r['event_availability_rate']=0
  a=next(z for z in identify_symbol_regions(x,ctx()) if z['broker_symbol']=='S0'); self.assertFalse(a['effect_scenarios']['0.5']['supported_parameter_neighborhood_exists'])
 def test_zero_history_rejected(self):
  x=rows(); x[0]['broker_symbol']=ZERO
  with self.assertRaises(Stage2Error): identify_symbol_regions(x,ctx())
class Integration(unittest.TestCase):
 def test_real_result_pre_response_symbol_specific(self):
  x=build_stage2(ROOT); self.assertEqual(x['status'],'COMPLETE_NON_ECONOMIC_MEAN_REVERSION_STAGE2_SYMBOL_CONTEXT_ROBUST_REGION_IDENTIFICATION'); self.assertEqual(len(x['symbol_context_parameter_regions']),33); self.assertEqual(x['scope']['research_unit'],'SYMBOL_X_MECHANISM_X_CONTEXT_X_ROBUST_PARAMETER_REGION'); self.assertFalse(x['scope']['cross_symbol_common_optimum_required']); self.assertFalse(x['interpretation_boundary']['response_return_or_pnl_statistic_opened']); self.assertFalse(x['summary']['symbols_ranked']); self.assertFalse(x['summary']['family_closed']); self.assertEqual(x['accounting_effect'],{'economic_outcomes_opened':0,'v2_attempts_consumed':0,'search_budget_change':0}); self.assertTrue(all(len(e['all_12_cells'])==12 for s in x['symbol_context_parameter_regions'] for e in s['effect_scenarios'].values()))
if __name__=='__main__': unittest.main()
