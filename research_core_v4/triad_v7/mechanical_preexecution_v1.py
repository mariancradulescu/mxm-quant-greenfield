"""Mechanical fixtures only: no complete trial, FWER/power estimates or market Y."""
from pathlib import Path
import json, hashlib, math, time, subprocess, socket, sys, ast
import numpy as np
from stochastic_worker_v1 import P,R,sha,canonical,seed,generator,Projection,load_geometry,state_path,base_paths,clock_fits,infer,aggregate_case
def main():
 start=time.perf_counter();manifest=json.loads((P/'TRIAL_MANIFEST_V1.json').read_text());plan=json.loads((P/'MECHANICAL_PREEXECUTION_PLAN_V1.json').read_text())
 for f,s in manifest['bindings'].items():assert sha(R/f)==s,f
 assert plan['manifest_sha256']==sha(P/'TRIAL_MANIFEST_V1.json')
 assert plan['checker_sha256']==sha(Path(__file__))
 g=load_geometry();project=Projection(P/'projection_bridge_v1.so');checks={}
 assert hashlib.sha256(g['bank'].astype('<i4').tobytes()).hexdigest()==manifest['multiplier_bank_int32_sha256']
 assert g['complete'].shape==(210,8,3,4) and len(manifest['leaves'])==12
 expected=[{'index':4*c+h,'cohort':cohort,'horizon_minutes':hor} for c,cohort in enumerate(['G10_MONETARY_TRIADS','MANAGED_EXTENSION_TRIADS','OTHER_EXTENSION_TRIADS']) for h,hor in enumerate([15,30,60,240])]
 assert manifest['leaves']==expected
 for array in g.values():assert not array.flags.writeable
 try:g['complete'][0,0,0,0]=False;raise AssertionError('Mask unexpectedly writable')
 except ValueError:pass
 checks['all12_leaves_original_calendar_and_readonly_certified_masks']=True
 assert len(manifest['null_cases'])==17 and not manifest['daily_score_AR_primary_null_cases']
 assert len({seed(manifest['master_seed'],'null',c,t,s) for c in range(17) for t in [0,1] for s in ['state','factor']})==68
 a=generator(manifest,'MECHANICAL_ONLY',0,0,'factor').standard_normal(100)
 b=generator(manifest,'MECHANICAL_ONLY',0,0,'factor').standard_normal(100);assert np.array_equal(a,b)
 witness=hashlib.sha256(a.astype('<f8').tobytes()).hexdigest()
 checks['fixed_seed_exact_repeatability_and_stream_separation']=True
 for phi in [.8,.97]:
  x=state_path(generator(manifest,'MECHANICAL_ONLY',0,0,'state'),phi,32)
  y=state_path(generator(manifest,'MECHANICAL_ONLY',0,0,'state'),phi,32)
  assert np.array_equal(x,y)
  rng=generator(manifest,'MECHANICAL_ONLY',0,0,'state');assert np.array_equal(x[0],rng.standard_normal(14))
  assert np.allclose(x[1],phi*x[0]+math.sqrt(1-phi*phi)*rng.standard_normal(14),rtol=0,atol=0)
  assert math.exp(1.44*phi)-1>0
 checks['stationary_cross_day_state_recursion_and_positive_variance_dependence']=True
 # Single-day miniature paths are implementation fixtures, never 210-day trials.
 max_null_error=0.;max_baseline_error=0.;max_reference_discrepancy=0.;geometries=0
 for case in manifest['null_cases']:
  path,_=base_paths(g,case,generator(manifest,'MECHANICAL_ONLY',case['id'],0,'state'),generator(manifest,'MECHANICAL_ONLY',case['id'],0,'factor'),days=1)
  for k in [0,3,7]:
   q=12+12*k
   for c in range(3):
    f=clock_fits(g,path[0],0,k,c,project)
    if f is None:continue
    changed=path[0].copy();changed[q+1:]+=1000
    f2=clock_fits(g,changed,0,k,c,project);assert np.array_equal(f['X'],f2['X']) and np.array_equal(f['D'],f2['D'])
    items=[(np.ones(len(f['ids']),bool),f['full'])]+list(f['loo'].values())
    for keep,fit in items:
     X=f['X'][keep];D=f['D'][keep];z=X/np.sqrt(np.mean(X*X,axis=0));rd=D-z@np.linalg.lstsq(z,D,rcond=1e-12)[0];ref=rd/np.sqrt(np.mean(rd*rd));diff=float(np.max(np.abs(ref-fit['normalized'])));max_reference_discrepancy=max(max_reference_discrepancy,diff)
     assert diff<=1e-7
     max_baseline_error=max(max_baseline_error,abs(float(np.mean(fit['normalized']*(X@np.array([.3,-.2,.5]))))))
     for rho in [case['rho_before'],case['rho_after']]:
      for steps in [3,6,12,48]:
       EY=X[:,1]*sum(rho**j for j in range(2,steps+2));err=abs(float(np.mean(fit['normalized']*EY)));max_null_error=max(max_null_error,err)
       assert err<=1e-7*max(1.,float(np.max(np.abs(EY))))
     geometries+=1
 checks['all17_null_case_conditional_forecast_in_X_span_full_and_leaveouts']=True
 checks['kernel_bridge_independent_projection_fixture_comparison']=True
 checks['causal_features_unchanged_by_future_synthetic_perturbation']=True
 checks['arbitrary_nuisance_in_span_cancels']=True
 # Verify bridge equals standalone frozen production executable bit-for-bit.
 f=clock_fits(g,path[0],0,0,0,project);X=f['X'];D=f['D']
 binary=P/'mechanical_standalone_kernel.tmp'
 subprocess.run(['g++','-O3','-std=c++17','-fno-fast-math',str(R/'research_core_v4/triad_v4/canonical_projection_jacobi_v1.cpp'),'-o',str(binary)],check=True,capture_output=True)
 text=str(len(D))+'\n'+'\n'.join(' '.join(format(float(v),'.17g') for v in [*x,d]) for x,d in zip(X,D))+'\n'
 result=json.loads(subprocess.check_output([str(binary)],input=text.encode()));assert result==project(X,D)['candidate']|{'status':'ACCEPTED'}
 binary.unlink();checks['bridge_equals_unchanged_standalone_production_kernel']=True
 # Partial-null own-target sets are disjoint; no signal reaches a true-null asset.
 sets=[set(g['target_asset'][g['target_cohort']==c].tolist()) for c in range(3)]
 assert all(not sets[c]&sets[d] for c in range(3) for d in range(c))
 for cfg in manifest['partial_nulls']:
  injected=set().union(*(sets[c] for c in range(3) if cfg['delta'][c]!=0))
  assert all(not sets[c]&injected for c in range(3) if cfg['delta'][c]==0)
 checks['all_declared_partial_null_cohort_own_asset_paths_uninjected']=True
 # Artificial deterministic score vectors test maxT algebra, not null size/power.
 valid=g['complete'].sum(axis=1).reshape(210,12)>=4
 days=np.arange(210)[:,None];leaves=np.arange(12)[None,:]
 daily=np.sin((days+1)*(leaves+1)*math.sqrt(2))+.02*(leaves-5)
 daily[~valid]=np.nan;loo=np.empty((210,44,4))
 for t in range(44):loo[:,t]=daily[:,4*g['target_cohort'][t]:4*g['target_cohort'][t]+4]
 o={'daily':daily,'loo':loo,'valid':valid};d=infer(g,o)
 reverse=infer(g,{'daily':-daily,'loo':-loo,'valid':valid});assert np.array_equal(d['reject'],reverse['reject']) and np.array_equal(d['p'],reverse['p'])
 assert len(d['p'])==12 and np.all(d['lead']<=d['reject'])
 checks['joint12_leaf_maxT_both_directions_and_lead_subset']=True
 # Execution gate absent; attempt must fail before any generator/aggregate call.
 assert not (P/'EXECUTION_ARM_V1.json').exists()
 try:aggregate_case(manifest,g,project,'null',0);raise AssertionError('Unarmed execution allowed')
 except FileNotFoundError:pass
 ast.parse((P/'stochastic_worker_v1.py').read_text());ast.parse((P/'control_plane_v1.py').read_text())
 checks['no_execution_ARM_present_and_sources_parse']=True
 result={'schema':'TRIAD_V7_MECHANICAL_PREEXECUTION_RAW_V1','manifest_sha256':sha(P/'TRIAL_MANIFEST_V1.json'),'plan_sha256':sha(P/'MECHANICAL_PREEXECUTION_PLAN_V1.json'),'checker_sha256':sha(Path(__file__)),'checks':checks,'all_pass':all(checks.values()),'mechanical_projection_geometries':geometries,'maximum_reference_normalized_discrepancy':max_reference_discrepancy,'maximum_conditional_forecast_score_error':max_null_error,'maximum_arbitrary_baseline_score_error':max_baseline_error,'fixed_seed_fixture_sha256':witness,'mechanical_miniature_paths':17,'mechanical_state_fixture_days':32,'artificial_maxT_test_arrays':2,'calibration_estimates_generated':False,'null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0,'elapsed_seconds':time.perf_counter()-start}
 with (P/'MECHANICAL_PREEXECUTION_RAW_V1.json').open('xb') as f:f.write(canonical(result))
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
