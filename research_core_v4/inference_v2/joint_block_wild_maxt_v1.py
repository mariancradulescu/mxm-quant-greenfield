"""Joint calendar-block wild bootstrap-t maxT. Synthetic-only certification driver.
No nominal t CDF/HAC used by the new method; old() is a read-only diagnostic.
"""
import argparse, hashlib, json, math, pathlib, platform, socket, sys
import numpy as np
R=pathlib.Path(__file__).resolve().parents[2]
PLAN='research_core_v4/inference_v2/JBW_MAXT_CERTIFICATION_PLAN_V1.json'

def canonical(d):return (json.dumps(d,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def fence():
 def denied(*a,**k):raise RuntimeError('NETWORK_FORBIDDEN_SYNTHETIC_ONLY')
 socket.socket=denied;socket.create_connection=denied;socket.getaddrinfo=denied

def wilson(k,n,z):
 p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den;w=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return [float(mid-w),float(mid+w)]

def metric(k,n,z):return {'rejections':int(k),'trials':int(n),'rate':float(k/n),'wilson':wilson(k,n,z)}

def generate(rng,case,N,d):
 D=d['days'];T=D+128;w=(.25,.35,.40);rho=.1
 if case=='AR025':rho=.25
 if case=='AR050':rho=.5
 if case=='strong_common_factors':w=(.80,.15,.05);rho=.25
 def noise(shape):
  if case=='heavy_t5':return rng.standard_t(5,size=shape)/np.sqrt(5/3)
  if case=='centered_skew':return (rng.chisquare(3,size=shape)-3)/np.sqrt(6)
  return rng.normal(size=shape)
 common=noise((N,T,1,1));context=noise((N,T,3,1));own=noise((N,T,3,4))
 x=np.sqrt(w[0])*common+np.sqrt(w[1])*context+np.sqrt(w[2])*own
 for t in range(1,T):x[:,t]=rho*x[:,t-1]+np.sqrt(1-rho*rho)*x[:,t]
 x=x[:,-D:,:,:].reshape(N,D,12)
 if case=='heteroscedastic':x*=np.exp(.7*rng.normal(size=(N,D,1)))/np.exp(.49)
 if case=='variance_change':x[:,:105]*=.5;x[:,105:]*=np.sqrt(1.75)
 mask=np.ones((N,D,12),bool)
 if case=='isolated_missing':mask&=rng.random((N,D,1))>=.1;mask&=rng.random((N,D,12))>=.05
 if case=='contiguous_gaps':mask[:,84:112]=False;mask&=rng.random((N,D,12))>=.02
 # Construct equal-weight coherent asset means for frozen old diagnostic only.
 dev=rng.normal(size=(N,3,4,6))/np.sqrt(D);dev-=dev.mean(axis=-1,keepdims=True)
 return x,mask,dev

def cluster(x,mask,d):
 N,D,L=x.shape;B=D//d['block_days'];v=x.reshape(N,B,d['block_days'],L);m=mask.reshape(N,B,d['block_days'],L)
 counts=m.sum(axis=2);valid=counts>=7;means=(v*m).sum(axis=2)/np.maximum(counts,1)
 n=valid.sum(axis=1);mu=(means*valid).sum(axis=1)/np.maximum(n,1)
 u=(means-mu[:,None,:])*valid
 sumu2=(u*u).sum(axis=1);sd=np.sqrt(sumu2/np.maximum(n-1,1));se=sd/np.sqrt(np.maximum(n,1))
 assert np.all(se>1e-12),'Degenerate supported score variance'
 thirds=[];support=n>=12
 for idx in np.array_split(np.arange(D),3):
  c=mask[:,idx].sum(axis=1);thirds.append((x[:,idx]*mask[:,idx]).sum(axis=1)/np.maximum(c,1));support&=c>=42
 return {'means':mu,'centered':u,'n':n,'sumu2':sumu2,'se':se,'thirds':np.stack(thirds,axis=1),'support':support,'valid':valid,'counts':counts}

def bootstrap_reference(g,bank):
 u=g['centered'];n=g['n'];s2=g['sumu2']
 totals=np.einsum('rb,nbl->nrl',bank,u,optimize=True)
 variance=(n[:,None,:]*s2[:,None,:]-totals*totals)/np.maximum(n[:,None,:]-1,1)
 assert np.min(variance)>=-1e-8,'Numerical wild variance negativity'
 tstar=totals/np.sqrt(np.maximum(variance,1e-14))
 return np.sort(np.max(np.abs(tstar),axis=-1),axis=-1)

def adjusted_p(sorted_max,abs_t):
 N,B=sorted_max.shape;L=abs_t.shape[-1];low=np.zeros((N,L),dtype=int);high=np.full((N,L),B,dtype=int);rows=np.arange(N)[:,None]
 for _ in range(int(math.ceil(math.log2(B+1)))+1):
  mid=(low+high)//2;values=sorted_max[rows,np.minimum(mid,B-1)];move=(mid<B)&(values<abs_t)&(low<high)
  low=np.where(move,mid+1,low);high=np.where((~move)&(low<high),mid,high)
 assert np.array_equal(low,high),'Reference search incomplete'
 return (1+B-low)/(B+1)

def decision(g,ref,shift,d):
 mu=g['means']+shift[None,:];t=mu/g['se'];p=adjusted_p(ref,np.abs(t));rej=(p<=d['nominal_family_alpha'])&g['support']
 orient=np.sign(mu);stable=((g['thirds']+shift[None,None,:])*orient[:,None,:]>0).sum(axis=1)>=2
 lead=rej&stable
 return rej,lead,p,t

def shift_vector(spec):
 s=np.zeros(12)
 for key,v in spec.items():c,h=map(int,key.split(':'));s[4*c+h]=v
 return s

def old_diagnostic(x,mask,dev):
 # Invoke only immutable old universal pure-array diagnostic, not either failed method.
 sys.path.insert(0,str(R))
 from research_core_v4.audit_v2.synthetic_comparison_v1 import old
 xx=x.reshape(len(x),210,3,4).transpose(0,2,3,1);m=mask.reshape(len(x),210,3,4)[:,:,:,0].all(axis=-1)
 return old(xx,m,dev)[0]

def invariant_checks(d,bank):
 rng=np.random.default_rng(2026100515);x,m,_=generate(rng,'isolated_missing',8,d);g=cluster(x,m,d);ref=bootstrap_reference(g,bank);shift=shift_vector(d['null_configurations']['multiple_contexts_remaining_true_nulls']);g2=cluster(x+shift[None,None,:],m,d);ref2=bootstrap_reference(g2,bank)
 assert np.allclose(ref,ref2,rtol=1e-10,atol=1e-10),'Translation centered reference'
 a=decision(g,ref,shift,d);b=decision(g2,ref2,np.zeros(12),d);assert np.array_equal(a[0],b[0]) and np.array_equal(a[1],b[1]),'Direct shifted decision'
 assert np.all(a[1]<=a[0]),'Lead subset'
 # Verify studentization formula directly for first draw and first data vector.
 z=bank[0,:,None]*g['centered'][0];valid=g['valid'][0];j=0;v=z[valid[:,j],j];direct=v.mean()/(v.std(ddof=1)/np.sqrt(len(v)));tot=z[:,j].sum();derived=tot/np.sqrt((g['n'][0,j]*g['sumu2'][0,j]-tot*tot)/(g['n'][0,j]-1));assert np.isclose(direct,derived,rtol=1e-12,atol=1e-12),'Studentization recomputation'
 y=x.copy();y[:,140:]+=123;g3=cluster(y,m,d);assert np.array_equal(g['counts'][:,:10],g3['counts'][:,:10]);assert np.allclose((g['centered']+g['means'][:,None,:])[:,:10]*g['valid'][:,:10],(g3['centered']+g3['means'][:,None,:])[:,:10]*g3['valid'][:,:10],rtol=1e-10,atol=1e-10),'Prior block means changed by future perturbation'
 # Dedicated calendar mask witness: an entire original block absent, not reindexed.
 mm=np.ones_like(m);mm[:,42:56]=False;gg=cluster(x,mm,d);assert not gg['valid'][:,3].any() and gg['valid'][:,4].all();assert gg['n'].min()==14
 brute=(1+(ref[:,:,None]>=np.abs(a[3])[:,None,:]).sum(axis=1))/(d['bootstrap_draws']+1);assert np.array_equal(brute,a[2]),'Adjusted p rank algebra'
 # Common multiplier kernel means scalar bank[b,r] applies to entireleafvector, not independent draw perleaf.
 assert bank.shape==(d['bootstrap_draws'],15) and set(np.unique(bank))=={-1.,1.}
 ng=cluster(-x,m,d);nr=bootstrap_reference(ng,bank);assert np.allclose(ref,nr,atol=1e-12);assert np.array_equal(decision(g,ref,np.zeros(12),d)[0],decision(ng,nr,np.zeros(12),d)[0]),'Both-direction invariance'
 return {'pass':True,'seed':2026100515,'translation_reference_max_absolute_difference':float(np.max(np.abs(ref-ref2))),'direct_shift_decisions_identical':True,'bootstrap_t_formula_checked':True,'p_rank_matches_bruteforce':True,'calendar_gap_position_preserved':True,'common_multiplier_across_leaves':True,'lead_subset_significance':True,'both_direction_invariance':True}

def run(d):
 fence();bank_rng=np.random.default_rng(d['seed_common_multiplier_bank']);bank=bank_rng.choice(np.array([-1.,1.]),size=(d['bootstrap_draws'],15));inv=invariant_checks(d,bank)
 out={'schema':'mxm.v4.joint-block-wild-maxt-raw-synthetic-result.v1','method':d['method'],'interpretation_present':False,'plan_sha256':sha(R/PLAN),'implementation_sha256':sha(__file__),'environment':{'python':platform.python_version(),'numpy':np.__version__,'platform':platform.platform(),'executable_sha256':sha(sys.executable)},'seeds':{k:d[k] for k in ['seed_null','seed_power','seed_common_multiplier_bank']},'multiplier_bank_sha256':hashlib.sha256(bank.tobytes()).hexdigest(),'invariants':inv,'null':{},'power':{},'old_diagnostic':{},'market_inputs_used':False,'market_response_opened':False,'broker_contacts':0,'historical_requests':0,'orders':0,'units':'Marginal daily synthetic innovation/score SD; not bps/profit. rho processes normalized to unit marginal variance; deterministic variance_change average variance1.'}
 rng=np.random.default_rng(d['seed_null']);N=d['null_trials_per_case'];z=d['precision_derivation']['simultaneous_Wilson_z']
 for case in d['null_cases']:
  specs=d['null_configurations'];counts={cfg:{'any_false_significance':0,'any_false_complete_lead':0,'false_context_selection':0,'any_true_nonnull_lead':0} for cfg in specs};witness=hashlib.sha256();support=0
  for start in range(0,N,128):
   n=min(128,N-start);x,m,_=generate(rng,case,n,d);g=cluster(x,m,d);ref=bootstrap_reference(g,bank);witness.update(g['centered'].tobytes());witness.update(g['valid'].tobytes());witness.update(ref.tobytes());support+=int(g['support'].all(axis=1).sum())
   for cfg,spec in specs.items():
    shift=shift_vector(spec);true_null=shift==0;reject,lead,_,_=decision(g,ref,shift,d);false=lead&true_null[None,:];nonnull=~true_null
    counts[cfg]['any_false_significance']+=int((reject&true_null).any(axis=1).sum());counts[cfg]['any_false_complete_lead']+=int(false.any(axis=1).sum())
    nullcontexts=true_null.reshape(3,4).all(axis=1);counts[cfg]['false_context_selection']+=int((lead.reshape(n,3,4).any(axis=2)&nullcontexts[None,:]).any(axis=1).sum());counts[cfg]['any_true_nonnull_lead']+=int((lead&nonnull).any(axis=1).sum())
  out['null'][case]={'configurations':{cfg:{k:metric(v,N,z) for k,v in cc.items()} for cfg,cc in counts.items()},'all_leaf_support_trials':support,'computation_witness_sha256':witness.hexdigest()};print(json.dumps({'phase':'null','case':case,'trials':N}),flush=True)
 rng=np.random.default_rng(d['seed_power']);N=d['power_trials_per_case'];effects=d['power_effects_daily_score_SD']
 for case in d['null_cases']:
  specs=d['power_alternatives'];counts={alt:{str(e):{'any_target_lead':0,'all_target_leads':0,'per_target_leaf':{key:0 for key in spec},'old_universal_complete':0} for e in effects} for alt,spec in specs.items()}
  for start in range(0,N,128):
   n=min(128,N-start);x,m,dev=generate(rng,case,n,d);g=cluster(x,m,d);ref=bootstrap_reference(g,bank)
   for alt,spec in specs.items():
    direction=shift_vector(spec);target=direction!=0
    for e in effects:
     shift=direction*e;_,lead,_,_=decision(g,ref,shift,d);ct=counts[alt][str(e)];ct['any_target_lead']+=int(lead[:,target].any(axis=1).sum());ct['all_target_leads']+=int(lead[:,target].all(axis=1).sum())
     for key in spec:
      c,h=map(int,key.split(':'));ct['per_target_leaf'][key]+=int(lead[:,4*c+h].sum())
     ct['old_universal_complete']+=int(old_diagnostic(x+shift[None,None,:],m,dev).sum())
  out['power'][case]={alt:{e:{'any_target_lead':metric(ct['any_target_lead'],N,1.96),'all_target_leads':metric(ct['all_target_leads'],N,1.96),'per_target_leaf':{key:metric(v,N,1.96) for key,v in ct['per_target_leaf'].items()},'old_universal_complete':metric(ct['old_universal_complete'],N,1.96)} for e,ct in rows.items()} for alt,rows in counts.items()};print(json.dumps({'phase':'power','case':case,'trials':N}),flush=True)
 return out

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();d=json.loads((R/PLAN).read_bytes());result=run(d);path=pathlib.Path(a.output);path.write_bytes(canonical(result));print(json.dumps({'raw_result_saved':str(path),'sha256':sha(path),'interpretation_present':False}),flush=True)
