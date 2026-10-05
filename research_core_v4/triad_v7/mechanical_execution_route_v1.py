"""Single-day route and artificial gate inputs only, not calibration trials."""
import json, hashlib, copy
import numpy as np
import stochastic_worker_v1 as w
import control_plane_v1 as cp
def main():
 p=w.P;m=json.loads((p/'TRIAL_MANIFEST_V1.json').read_text());plan=json.loads((p/'MECHANICAL_EXECUTION_ROUTE_PLAN_V1.json').read_text())
 assert plan['manifest_sha256']==w.sha(p/'TRIAL_MANIFEST_V1.json') and plan['checker_sha256']==w.sha(__file__)
 g=w.load_geometry();project=w.Projection(p/'projection_bridge_v1.so');case=m['null_cases'][16]
 base,_=w.base_paths(g,case,w.generator(m,'MECHANICAL_ROUTE_ONLY',16,0,'state'),w.generator(m,'MECHANICAL_ROUTE_ONLY',16,0,'factor'),days=1)
 original=w.clock_fits;captured=[]
 def trace(g,path,day,k,c,project):
  result=original(g,path,day,k,c,project)
  if result:captured.append({'k':k,'c':c,'X':result['X'].copy(),'D':result['D'].copy(),'path':path.copy()})
  return result
 w.clock_fits=trace
 try:
  reference=w.scores(g,base,case,[0,0,0],project);baseline=captured.copy();captured.clear()
  configurations=m['partial_nulls']+[{'id':x['id'],'delta':[.1*v for v in x['direction']]} for x in m['power_alternatives']]
  digests=[]
  for config in configurations:
   result=w.scores(g,base,case,config['delta'],project);events=captured.copy();captured.clear()
   assert result['daily'].shape==(1,12) and result['loo'].shape==(1,44,4)
   assert np.array_equal(result['valid'],reference['valid']) and np.isfinite(result['daily'][result['valid']]).all()
   for event,old in zip(events,baseline):
    assert (event['k'],event['c'])==(old['k'],old['c'])
    if config['delta'][event['c']]==0:
     assets=g['target_asset'][g['target_cohort']==event['c']]
     assert np.array_equal(event['X'],old['X'])
     assert np.array_equal(event['path'][:,assets],old['path'][:,assets])
   digests.append(hashlib.sha256(result['daily'].tobytes()+result['loo'].tobytes()).hexdigest())
  repeat=w.scores(g,base,case,configurations[-1]['delta'],project)
  assert hashlib.sha256(repeat['daily'].tobytes()+repeat['loo'].tobytes()).hexdigest()==digests[-1]
 finally:w.clock_fits=original
 # Manufactured endpoint counts test the exact gate code; they are never trial evidence.
 n=m['null_trials_per_case'];ct={'false_significance':0,'false_lead':0,'any_nonnull_lead':0,'all_nonnull_leads':0,'supported':n,'per_leaf_lead':[0]*12}
 raw={'mode':'null','case_id':0,'trials':n,'numerical_failures':0,'cells':{x['id']:copy.deepcopy(ct) for x in m['partial_nulls']}}
 good=cp.interpret(raw,m);assert good['pass']
 raw['cells'][m['partial_nulls'][0]['id']]['false_significance']=n;assert not cp.interpret(raw,m)['pass']
 raw['cells'][m['partial_nulls'][0]['id']]['false_significance']=0;raw['cells'][m['partial_nulls'][0]['id']]['supported']=0;assert not cp.interpret(raw,m)['pass']
 try:
  raw['cells'].pop(m['partial_nulls'][0]['id']);cp.interpret(raw,m);raise AssertionError('Missing null cell accepted')
 except AssertionError as e:
  assert str(e)!='Missing null cell accepted'
 n=m['power_trials_per_case'];zero={'false_significance':0,'false_lead':0,'any_nonnull_lead':0,'all_nonnull_leads':0,'supported':n,'per_leaf_lead':[0]*12}
 power={'mode':'power','case_id':0,'trials':n,'numerical_failures':0,'cells':{x['id']:copy.deepcopy(zero) for x in m['power_cells']}}
 low=cp.interpret(power,m);assert not low['pass'] and all(x['MDI_grid'] is None for x in low['rows'])
 for cell in m['power_cells']:
  if cell['effect']>0:
   power['cells'][cell['id']]['any_nonnull_lead']=n;power['cells'][cell['id']]['all_nonnull_leads']=n
 assert cp.interpret(power,m)['pass']
 assert not (p/'EXECUTION_ARM_V1.json').exists()
 result={'schema':'TRIAD_V7_MECHANICAL_EXECUTION_ROUTE_RAW_V1','manifest_sha256':w.sha(p/'TRIAL_MANIFEST_V1.json'),'plan_sha256':w.sha(p/'MECHANICAL_EXECUTION_ROUTE_PLAN_V1.json'),'checker_sha256':w.sha(__file__),'all_pass':True,'checks':{'single_day_complete_feature_projection_signal_score_leaveout_route':True,'all4_partial_null_and_all7_power_direction_routes':True,'true_null_own_paths_and_X_unchanged_by_nonnull_signal':True,'full12_leaf_calendar_availability_identical':True,'repeat_route_bit_identical':True,'exact_confidence_gate_endpoint_inputs':True,'missing_null_cell_rejected':True,'low_power_is_inconclusive_not_null':True},'fixture_digests':digests,'manufactured_gate_inputs_are_not_evidence':True,'complete_trial_or_FWER_power_estimate_generated':False,'null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0}
 with (p/'MECHANICAL_EXECUTION_ROUTE_RAW_V1.json').open('xb') as f:f.write(w.canonical(result))
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
