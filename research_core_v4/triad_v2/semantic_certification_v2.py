"""Synthetic analytic identification, positive and no-leakage controls only.
No real price/response loader. Gate and seeds must be committed beforehand.
"""
import json,pathlib,hashlib
import numpy as np
from research_core_v4.triad_v2.orthogonal_score_v2 import score,current_projection,forward_baseline,clock_baseline_beta,eligible_training_indices
R=pathlib.Path('.');B='research_core_v4/triad_v2/'
def read(p):return json.loads((R/p).read_bytes())
def h(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
p=read(B+'SEMANTIC_IDENTIFICATION_PLAN_V1.json');d=read(p['design_ref']);assert h(p['design_ref'])==p['design_sha256'] and h(p['implementation_ref'])==p['implementation_sha256'];assert h(B+'orthogonal_score_v2.py')==p['kernel_sha256']
rng=np.random.default_rng(p['seed']);tol=p['tolerance'];rows=[];positives=[];learning=[];fwl=[];max_null=0.;max_alt_error=0.
# Synthetic g fitting includes noisylabels; the estimates are never oracles.
for ci,c in enumerate(d['universe']['cohorts']):
 n=d['universe']['target_counts'][c];dec=np.repeat(np.arange(92)*1440+480,8*n).reshape(92,8,n);dec+=np.arange(8)[None,:,None]*60;dec=dec.ravel();clock=np.tile(np.repeat(np.arange(8),n),92)
 v5=rng.normal(size=len(dec));v60=rng.normal(size=len(dec));trainX=np.column_stack([np.ones(len(dec)),v5,v60]+[(clock==k).astype(float) for k in range(1,8)])
 for hi,hor in enumerate(d['horizons_minutes']):
  maturation=dec+hor;oldbeta=np.array([.3,.2,-.4]+[.01*k for k in range(1,8)])*(1+hi/4)
  trainY=trainX@oldbeta+.3*rng.standard_t(5,size=len(dec));T=90*1440;fit=forward_baseline(trainX,trainY,dec,maturation,T);g=clock_baseline_beta(fit['beta'],2)
  forbidden=~np.isin(np.arange(len(dec)),fit['training_indices']);changed=trainY.copy();changed[forbidden]+=1e6
  fit2=forward_baseline(trainX,changed,dec,maturation,T);leakerror=float(np.max(np.abs(fit2['beta']-fit['beta'])));assert leakerror==0
  tomorrow=eligible_training_indices(dec,maturation,T+1440);assert np.all(dec[tomorrow]>=T+1440-90*1440) and np.all(maturation[tomorrow]+240<T+1440)
  assert all(dec[k]<T+1440-90*1440 for k in set(fit['training_indices'])-set(tomorrow))
  boundary=eligible_training_indices(np.array([T-1000,T-1000]),np.array([T-240,T-241]),T);assert boundary.tolist()==[1]
  learning.append({'cohort':c,'horizon':hor,'training_rows':len(fit['training_indices']),'last_maturity_plus_purge':fit['last_maturity_plus_purge'],'update_time':T,'future_label_perturbation_error':leakerror,'strict_boundary_pass':True,'tomorrow_added_rows':len(set(tomorrow)-set(fit['training_indices']))})
  tt=np.arange(n);X0=np.column_stack([np.ones(n),np.sin(2*np.pi*tt/n),np.cos(2*np.pi*tt/n)]);Z0=np.sin(4*np.pi*tt/n)+.3*np.cos(6*np.pi*tt/n)
  for case in p['null_cases']:
   stages=p['gradual_steps'] if case=='gradual_covariance_drift' else 1
   for step in range(stages):
    fraction=(step+1)/stages;X=X0.copy();beta=np.array([.4,.6,-.8])*(1+hi/3)
    cov=np.array([.2,.5,-.25]);Z=Z0.copy()
    if case in ['abrupt_covariance_change','simultaneous_baseline_covariance_change']:cov=np.array([1.7,-2.3,1.5])
    if case=='gradual_covariance_drift':cov+=fraction*np.array([1.2,-2.,3.])
    if case in ['baseline_coefficient_change','simultaneous_baseline_covariance_change']:beta+=np.array([2.,-3.,4.])
    if case=='heterogeneous_cohort_changes':cov+=np.array([ci,-1.5*ci,.7*ci]);beta*=(-1 if ci==1 else 1)*(ci+1)
    if case=='horizon_dependent_baseline':beta*=hor/15;cov+=hi*np.array([.3,-.5,.7])
    if case=='common_factor_covariance_change':X[:,1]+=.7*X0[:,2];X[:,2]*=(1+.4*ci);cov+=np.array([.6,1.8,-2.2]);Z*=1+.5*ci
    for baseline_sign in [1,-1]:
     D=np.clip(X@cov+Z,-3,3);Y=X@(baseline_sign*beta)
     s=score(X,D,Y,g);max_null=max(max_null,abs(s['psi']))
     fitD=s['projection'];QY=Y-X@(np.linalg.pinv(X,rcond=1e-12)@Y);fwlcoef=float(fitD['residual']@QY/(fitD['residual']@fitD['residual']));equiv=abs(fwlcoef-s['partial_coefficient'])
     direct=np.linalg.lstsq(np.column_stack([X,D]),Y,rcond=1e-12)[0][-1];directerr=abs(float(direct)-s['partial_coefficient']);fwl.append({'error':equiv,'direct_OLS_error':directerr})
     rows.append({'case':case,'step':step,'cohort':c,'horizon':hor,'baseline_sign':baseline_sign,'conditional_linear_incremental_information':0.,'psi':s['psi'],'partial_coefficient':s['partial_coefficient'],'orthogonality_error':fitD['orthogonality_error'],'pass':abs(s['psi'])<=tol and abs(s['partial_coefficient'])<=tol and equiv<=tol and directerr<=tol})
  # Alternatives under simultaneousshift: no forcedzero, both andheterogeneoussigns.
  X=X0;D=np.clip(X@np.array([.6,1.2,-.8])+Z0,-3,3);beta=np.array([2.,-3.,4.])*(1+hi)
  for label,theta in [('positive',.2),('negative',-.2),('heterogeneous',-.2 if ci==1 else .2)]:
   Y=X@beta+theta*D;s=score(X,D,Y,g);expected=theta*s['projection']['rms'];error=max(abs(s['psi']-expected),abs(s['partial_coefficient']-theta));max_alt_error=max(max_alt_error,error)
   loo=[]
   for omitted in range(n):
    ii=np.arange(n)!=omitted;s2=score(X[ii],D[ii],Y[ii],g);loo.append(s2['psi']*theta>0)
   positives.append({'cohort':c,'horizon':hor,'alternative':label,'theta':theta,'psi':s['psi'],'expected_psi':expected,'partial_coefficient':s['partial_coefficient'],'leave_each_target_out_direction_pass':all(loo),'pass':error<=tol and s['psi']*theta>0 and all(loo)})
passed=all(x['pass'] for x in rows+positives) and all(x['future_label_perturbation_error']==0 for x in learning)
out={'schema':'mxm.v4.triad-v2.semantic-raw.v1','plan_sha256':h(B+'SEMANTIC_IDENTIFICATION_PLAN_V1.json'),'design_sha256':p['design_sha256'],'implementation_sha256':p['implementation_sha256'],'kernel_sha256':p['kernel_sha256'],'seed':p['seed'],'tolerance':tol,'null_results':rows,'positive_controls':positives,'learning_no_leakage':learning,'max_null_abs_psi':max_null,'max_positive_control_error':max_alt_error,'max_FWL_error':max(x['error'] for x in fwl),'max_direct_OLS_equivalence_error':max(x['direct_OLS_error'] for x in fwl),'all_semantic_gates_pass':passed,'stochastic_FWER_claimed':False,'power_claimed':False,'real_market_inputs_used':False,'real_future_signed_response_computations':0,'real_response_openings':0,'broker_contacts':0,'interpretation_present':False}
(R/(B+'SEMANTIC_RAW_RESULT_V1.json')).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['all_semantic_gates_pass','max_null_abs_psi','max_positive_control_error','max_FWL_error','max_direct_OLS_equivalence_error']}));print({'null_checks':len(rows),'positive_controls':len(positives),'chronological_checks':len(learning)})
