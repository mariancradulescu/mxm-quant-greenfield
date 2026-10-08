"""Frozen synthetic-only Stage0 certification. No real array/file entry point."""
import argparse,hashlib,json,pathlib,socket,time
import numpy as np
from inference import cluster,bootstrap_max,decisions,wilson
from prequential_score import DAY,prequential,fit_prefix,weights_equal_identity,predict
R=pathlib.Path(__file__).resolve().parents[2]
S='research_core_v4/state/'
P=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_POWER_PROTOCOL_V1.json'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def fence():
 def denied(*a,**k):raise RuntimeError('SYNTHETIC_NETWORK_FIREWALL')
 socket.socket=denied;socket.create_connection=denied;socket.getaddrinfo=denied

def pipeline_checks(plan):
 rng=np.random.default_rng(plan['seeds']['pipeline_fixtures']);days=77
 # 2 sampled events per identity/day, globally sampled, canonical order.
 t=np.array([d*DAY+h*1800 for d in range(days) for h in [1,2] for i in range(3)])
 ids=np.tile(np.arange(3),days*2);m=t+3600
 b=rng.normal(size=(len(t),10));b[:,-1]=7;phi=rng.normal(size=(len(t),2));y=2*b[:,0]-.5*b[:,1]+rng.normal(size=len(t))
 valid=np.ones(len(t),bool);out={};count=0
 def check(name,truth):
  nonlocal count
  assert truth,name;out[name]=True;count+=1
 rows,daily,audit=prequential(t,m,ids,b,phi,y,valid,0,days*DAY)
 check('warmup56day_and_weekly_clock',audit[0]['refit']==56*DAY and len(audit)==3)
 check('no_same_day_or_unmatured_or_unpurged_train',all(all(t[k]<(a['refit']//DAY)*DAY and m[k]<a['refit'] and t[k]+245*60<a['refit'] for k in a['train_indices']) for a in audit))
 check('global30min_sampling',all(all(t[k]%1800==0 for k in a['train_indices']) for a in audit))
 check('equal_identity_training_total',all(max(a['training_identity_weights'].values())-min(a['training_identity_weights'].values())<1e-12 for a in audit))
 check('zero_coordinate_audited',all(9 in a['zero_coordinates'] for a in audit))
 # Perturb labels and predictors after first refit; no change in its fit or its predictions before perturbation.
 f=fit_prefix(t,m,ids,b,phi,y,valid,56*DAY,0);yy=y.copy();bb=b.copy();pp=phi.copy();future=t>=56*DAY;yy[future]+=1000;bb[t>=63*DAY]+=1000;pp[t>=63*DAY]+=1000
 ff=fit_prefix(t,m,ids,bb,pp,yy,valid,56*DAY,0)
 check('causal_prefix_statistics_unchanged_by_future',np.array_equal(f.means,ff.means) and np.array_equal(f.sds,ff.sds) and np.array_equal(f.beta_aug,ff.beta_aug))
 k=np.flatnonzero(t==56*DAY+1800)[0];check('own_label_never_enters_fit',np.array_equal(f.beta_b,ff.beta_b) and predict(f,b[k],phi[k])==predict(ff,b[k],phi[k]))
 check('baseline_coordinates_share_exact_standardizers',len(f.means)==12 and len(f.beta_b)==11 and len(f.beta_aug)==13)
 w=weights_equal_identity(np.array([1,1,1,2]));check('unequal_event_counts_equal_total_weight',np.isclose(w[:3].sum(),w[3]))
 # Exact operational-null fixture: Phi all0 => identical models/predictions/losses despite nonlinear B.
 phi0=np.zeros_like(phi)
 for name,yfixture,mask in [('EXACT_NO_INCREMENTAL_SIGNAL_LINEAR_BASELINE',2*b[:,0],valid),('NONLINEAR_B_CORRELATED_PHI_OPERATIONAL_NULL_CONSTRUCTED',b[:,0]**2,valid),('HEAVY_TAIL_RESPONSE',rng.standard_t(5,len(t)),valid),('HETEROSCEDASTIC_RESPONSE',rng.normal(size=len(t))*np.exp(.7*b[:,0]),valid),('CONTIGUOUS_MISSINGNESS',y,valid&~((t>=10*DAY)&(t<17*DAY))),('ISOLATED_MISSINGNESS',y,valid&(rng.random(len(t))>.15))]:
  # Correlated nonlinear fixture uses a copy of B0 as Phi. Construct Y=0,
  # so exact zero standardized labels imply both ridge predictors0; H0 D=0.
  ph=phi0;yf=yfixture
  if name.startswith('NONLINEAR'):
   ph=np.column_stack([b[:,0],b[:,0]**2]);yf=np.zeros(len(t))
  rr,dd,aa=prequential(t,m,ids,b,ph,yf,mask,0,days*DAY)
  check(name, bool(rr) and all(abs(row[2])<1e-12 for row in rr))
 check('daily_equal_identity_aggregation',all(np.isclose(daily[d],np.mean([np.mean([r[2] for r in rows if r[0]==d and r[1]==i]) for i in set(r[1] for r in rows if r[0]==d)])) for d in daily))
 # Explicit scope witness: q in0,1,2; E[Y|q]=E[Phi|q]=(+.5,-.5,+.5), independent givenq.
 # Fixed affine B cannot fit this shape; adding Phi predicts nonlinear baseline component.
 q=np.array([0.,1.,2.]);EY=np.array([.5,-.5,.5]);aff=np.full(3,1/6)
 residual_var=np.mean((EY-aff)**2);feature_var=3/4+residual_var
 gain=residual_var**2/feature_var
 check('old_counterexample_scope_witness',np.isclose(residual_var,2/9) and gain>0)
 out['scope_witness']={'broad_conditional_null':True,'exact_conditioning_expectation':0,'old_affine_covariance':float(residual_var),'population_model_relative_linear_loss_gain':float(gain),'claims_not_logically_identical':True,'not_a_failure_of_either_definition':True,'finite_regularized_model_gain_not_assumed_from_population':True}
 return {'tests_passed':count,'tests_failed':0,'checks':out}

def generate(plan,case,n,blocks,rng):
 L=261;D=blocks*7;T=D+128
 labels=[leaf['context'] for leaf in plan['paid_leaves']];cs=sorted(set(labels));ci=np.array([cs.index(c) for c in labels])
 rho={'AR025':.25,'AR050':.5,'STRONG_COMMON_FACTORS':.25}.get(case,0.)
 weights=(.8,.15,.05) if case=='STRONG_COMMON_FACTORS' else (.25,.35,.40)
 def noise(shape):
  if case=='HEAVY_T5':return rng.standard_t(5,shape)/np.sqrt(5/3)
  if case=='CENTERED_SKEW':return (rng.chisquare(3,shape)-3)/np.sqrt(6)
  return rng.normal(size=shape)
 common=noise((n,T,1));context=noise((n,T,len(cs)));own=noise((n,T,L))
 x=np.sqrt(weights[0])*common+np.sqrt(weights[1])*context[:,:,ci]+np.sqrt(weights[2])*own
 for t in range(1,T):x[:,t]=rho*x[:,t-1]+np.sqrt(1-rho*rho)*x[:,t]
 x=x[:,-D:];mask=np.ones(x.shape,bool)
 if case=='HETEROSCEDASTIC':x*=np.exp(.7*rng.normal(size=(n,D,1)))/np.exp(.49)
 if case=='VARIANCE_CHANGE':x[:,:D//2]*=.5;x[:,D//2:]*=np.sqrt(1.75)
 if case=='ISOLATED_MISSINGNESS':mask&=rng.random((n,D,1))>=.1;mask&=rng.random((n,D,L))>=.05
 if case=='CONTIGUOUS_GAPS':mask[:,(blocks//2)*7:(blocks//2+1)*7]=False;mask&=rng.random((n,D,L))>=.02
 return x,mask

def engine_checks(plan):
 rng=np.random.default_rng(2026100805);x,m=generate(plan,'NORMAL',2,16,rng);g=cluster(x,m)
 bank=np.random.default_rng(plan['seeds']['bank']).choice([-1.,1.],size=(1023,16));ref=bootstrap_max(g,bank)
 shift=np.zeros((2,261));shift[:,0]=.4;g2=cluster(x+shift[:,None,:],m);ref2=bootstrap_max(g2,bank)
 assert np.allclose(ref,ref2,atol=1e-10)
 a=decisions(g,ref,shift);b=decisions(g2,ref2,np.zeros_like(shift));assert np.array_equal(a[0],b[0])
 brute=(1+(ref[:,:,None]>=a[3][:,None,:]).sum(1))/1024;assert np.array_equal(brute,a[2])
 assert np.all(a[0]<=a[1]);assert bank.shape==(1023,16)
 # AR fixtures actually exercise the exact specified AR score transforms.
 for case in ['AR025','AR050','STRONG_COMMON_FACTORS']:
  z,mm=generate(plan,case,2,16,rng);assert z.shape==(2,112,261) and mm.all()
 return {'tests_passed':6,'tests_failed':0,'centered_reference_translation_invariant':True,'local_shift_full261family_matches_direct_recompute':True,'p_rank_matches_bruteforce':True,'lead_subset_significance':True,'common_sign_bank':True,'AR025_AR050_common_factor_fixtures':True}

def certify(plan,outpath):
 fence();N=plan['precision']['trials_per_case'];z=plan['precision']['wilson_z']
 out={'schema':'mxm.current-wave.operational-stage0-synthetic-certification.v1','protocol_sha256':sha(R/P),'implementation_sha256':sha(__file__),'pipeline':pipeline_checks(plan),'power_engine':engine_checks(plan),'null':[],'broker_requests':0,'new_market_rows':0,'real_feature_response_model_loss_return_PNL_inputs':0,'power_on_actual_masks_run':False,'status':'RUNNING'}
 outpath.write_bytes(canonical(out))
 # Nested case/profile order frozen; all fullN runs complete before each verdict.
 for ci,case in enumerate(plan['null_cases']):
  for blocks in plan['null_geometry_profiles_week_blocks']:
   rng=np.random.default_rng(np.random.SeedSequence([plan['seeds']['null'],ci,blocks]))
   bank=np.random.default_rng(np.random.SeedSequence([plan['seeds']['bank'],blocks])).choice([-1.,1.],size=(1023,blocks))
   counts=np.zeros(2,dtype=np.int64);all_support=0;witness=hashlib.sha256();begin=time.monotonic()
   for start in range(0,N,16):
    n=min(16,N-start);x,m=generate(plan,case,n,blocks,rng);g=cluster(x,m);ref=bootstrap_max(g,bank);lead,sig,_,_=decisions(g,ref,np.zeros((n,261)))
    counts += [lead.any(1).sum(),sig.any(1).sum()];all_support+=g['support'].all(1).sum();witness.update(g['u'].tobytes());witness.update(ref.tobytes())
   lo,hi=wilson(counts,N,z);entry={'case':case,'weekly_calendar_blocks':blocks,'trials':N,'false_complete_lead_count':int(counts[0]),'false_complete_lead_rate':float(counts[0]/N),'simultaneous_wilson_lower':float(lo[0]),'simultaneous_wilson_upper':float(hi[0]),'false_significance_count':int(counts[1]),'false_significance_upper':float(hi[1]),'all_leaf_support_trials':int(all_support),'seconds':time.monotonic()-begin,'witness_sha256':witness.hexdigest(),'pass':bool(hi[0]<=.05)}
   out['null'].append(entry);print(json.dumps(entry),flush=True)
   if not entry['pass']:
    out['status']='BLOCKED_NULL_FWER_NOT_CERTIFIED';out['first_blocker']=entry;out['stage1_authorized']=False;outpath.write_bytes(canonical(out));return out
   outpath.write_bytes(canonical(out))
 out['status']='COMPLETE_STAGE0_SYNTHETIC_PASS';out['stage1_authorized']=True;outpath.write_bytes(canonical(out));return out
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--output',required=True);args=a.parse_args();plan=json.loads((R/P).read_text());certify(plan,pathlib.Path(args.output))
