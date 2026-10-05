"""Prospectively frozen deterministic semantic counterexample, synthetic only.
Tests the exact frozen prefix-only feature projection score, not another method.
No file containing real prices/support-fit coefficients is loaded. No MC tuning.
"""
import json,pathlib,hashlib
import numpy as np
R=pathlib.Path('.');B=R/'research_core_v4/triad_v1'
def read(p):return json.loads((R/p).read_bytes())
def h(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
p=read(str(B/'INCREMENTAL_NULL_SEMANTICS_CERTIFICATION_PLAN_V1.json'));d=read(p['design_ref']);assert h(p['design_ref'])==p['design_sha256']
assert h(str(B/'incremental_null_semantics_v1.py'))==p['implementation_sha256']
n=512;bits=np.arange(n);v60=.001*np.where((bits//8)%2,1.,-1.);z=.001*np.where((bits//16)%2,1.,-1.);v5=.0002*np.where((bits//32)%2,1.,-1.);clock=bits%8
X=np.column_stack([np.ones(n),v5,v60]+[(clock==k).astype(float) for k in range(1,8)]);assert np.linalg.matrix_rank(X)==10
prefix_F=.5*v60+z;beta=np.linalg.pinv(X,rcond=1e-12)@prefix_F;prefix_res=prefix_F-X@beta;rms=np.sqrt(np.mean(prefix_res**2));own_rms=np.sqrt(np.mean(v60**2));assert rms>1e-10 and own_rms>1e-10
# F is an actual currency closure change: targetuv=v60; bridgeuA=v60-F;
# bridgevA=0. Values are log changes, so exp() prices are strictly positive.
def algebra(F):return v60-(v60-F)+np.zeros(n)
assert np.max(np.abs(algebra(prefix_F)-prefix_F))<1e-15
rows=[]
for regime,coef in [('STABLE_FEATURE_CONTROL_COVARIANCE',.5),('PREFIX_TO_DEVELOPMENT_FEATURE_CONTROL_COVARIANCE_CHANGE',1.5)]:
 F=coef*v60+z;assert np.max(np.abs(algebra(F)-F))<1e-15
 feature=np.clip((F-X@beta)/rms,-3,3)
 for direction in [1,-1]:
  for hh in [15,30,60,240]:
   # Declared conditional mean future response depends only on own60min control.
   # Relational z adds NO conditional predictive information by construction.
   Y=direction*(hh/60)*v60/own_rms
   score=feature*Y;moment=float(score.mean());expected=0. if regime.startswith('STABLE') else direction*hh/60
   assert abs(moment-expected)<1e-10, 'counterexample arithmetic mismatch'
   conditional_incremental_information=0.
   rows.append({'regime':regime,'horizon_minutes':hh,'baseline_direction':direction,'conditional_incremental_information':conditional_incremental_information,'mean_frozen_score':moment,'required_incremental_null_mean':0.,'absolute_deviation':abs(moment),'semantic_null_invariance_pass':abs(moment)<=p['numerical_zero_tolerance']})
# Exact test also repeats across all3 paidcohorts, no best cohort/horizon selection.
cohort_rows=[dict(x,cohort=c) for c in d['cohorts'] for x in rows]
out={'schema':'mxm.v4.triad.incremental-null-semantic-raw.v1','plan_sha256':h(str(B/'INCREMENTAL_NULL_SEMANTICS_CERTIFICATION_PLAN_V1.json')),'implementation_sha256':p['implementation_sha256'],'design_sha256':p['design_sha256'],'real_price_or_market_inputs_used':False,'real_response_openings':0,'future_real_signed_response_computations':0,'prefix_synthetic_rows':512,'synthetic_prefix_rank':int(np.linalg.matrix_rank(X)),'synthetic_prefix_beta':beta.tolist(),'synthetic_prefix_residual_RMS':float(rms),'synthetic_ownleg60min_RMS':float(own_rms),'numerical_zero_tolerance':p['numerical_zero_tolerance'],'rows':cohort_rows,'all_preflight_gates_pass':all(x['semantic_null_invariance_pass'] for x in cohort_rows),'MC_trials_executed':0,'seeds_used':None,'broker_contacts':0,'historical_requests':0,'interpretation_present':False}
(B/'INCREMENTAL_NULL_SEMANTICS_RAW_RESULT_V1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'all_preflight_gates_pass':out['all_preflight_gates_pass'],'rows':len(cohort_rows),'stable_max_abs':max(x['absolute_deviation'] for x in rows if x['regime'].startswith('STABLE')),'changed_covariance_scores':[x['mean_frozen_score'] for x in rows if not x['regime'].startswith('STABLE')],'real_response_openings':0,'future_real_signed_response_computations':0}))
