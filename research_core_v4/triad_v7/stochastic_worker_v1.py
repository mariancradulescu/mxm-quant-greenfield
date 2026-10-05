"""Synthetic quoted-asset paths only. No market price or future-response reader.
Full trial execution is called only by the separately armed control plane.
"""
from pathlib import Path
import ctypes, hashlib, json, math, importlib.util, base64, io
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(o):return (json.dumps(o,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
def seed(master,mode,case,trial,stream):
 s=f'MXM_TRIAD_V7|{master}|{mode}|{case}|{trial}|{stream}'
 return int.from_bytes(hashlib.sha256(s.encode('ascii')).digest()[:16],'little')
def generator(manifest,mode,case,trial,stream):
 return np.random.Generator(np.random.PCG64(seed(manifest['master_seed'],mode,case,trial,stream)))
def require_execution_arm(manifest,mode):
 arm=json.loads((P/'EXECUTION_ARM_V1.json').read_text())
 assert arm['schema']=='TRIAD_V7_SEPARATE_STATISTICAL_EXECUTION_ARM_V1'
 assert arm['manifest_sha256']==sha(P/'TRIAL_MANIFEST_V1.json')
 assert arm['authority_sha256']==sha(P/'PREEXECUTION_AUTHORITY_V1.json')
 assert arm['authorized_phase']==mode and arm['real_response_authorized'] is False
 assert arm['maximum_case_attempts']==1 and arm['automatic_retry'] is False
 assert manifest==json.loads((P/'TRIAL_MANIFEST_V1.json').read_text())
class NumericalUnavailable(RuntimeError):pass
class Projection:
 def __init__(self,library):
  self.lib=ctypes.CDLL(str(library));self.fn=self.lib.triad_v7_projection
  ptr=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
  self.fn.argtypes=[ctypes.c_int,ptr,ptr,ptr];self.fn.restype=ctypes.c_int
  spec=importlib.util.spec_from_file_location('v6_frozen_support',R/'research_core_v4/triad_v6/one_sided_numerical_certificate_v1.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);self.support=module.production_support
 def __call__(self,X,D):
  X=np.ascontiguousarray(X,dtype=np.float64);D=np.ascontiguousarray(D,dtype=np.float64);out=np.zeros(8+len(D),np.float64)
  assert self.fn(len(D),X,D,out)==0
  c={'accepted':bool(out[0]),'rank':int(out[1]),'sweeps':int(out[2]),'singular_values':out[3:6].tolist(),'rms':float(out[6]),'orthogonality_error':float(out[7]),'normalized':out[8:].tolist() if out[0] else []}
  support=self.support(X.tolist(),D.tolist(),c)
  if not support['accepted']:raise NumericalUnavailable(support['reason'])
  return {'normalized':np.array(c['normalized']),'rms':c['rms'],'candidate':c,'support':support}
def load_geometry():
 # This immutable file contains only topology/scales/timestamp booleans/signs.
 v=np.fromstring((R/'research_core_v4/triad_v2/EXACT_SYNTHETIC_GEOMETRY_V1.txt').read_text(),sep=' ');at=0
 def take(n,shape):
  nonlocal at
  out=v[at:at+n].reshape(shape);at+=n;return out
 asset=take(75*14,(75,14));rels=take(107*9,(107,9));targets=take(44*2,(44,2)).astype(int)
 causal=take(210*8*107,(210,8,107)).astype(bool);complete=take(210*8*3*4,(210,8,3,4)).astype(bool)
 bank=take(1023*15,(1023,15)).astype(np.int8);assert at==len(v)
 numerical=json.loads((R/'research_core_v4/triad_v6/ACTUAL_NUMERICAL_SUPPORT_SUMMARY_V1.json').read_text())
 # Certified actual numerical support: all 1184 causal clocks in each cohort.
 assert all(x['numerically_unavailable']==0 for x in numerical['whole_cohort_clock_support'])
 assert numerical['all_actual_safety_certificates_pass'] and numerical['complete_12_leaf_support_pass']
 g={'scale':asset[:,0],'load':asset[:,1:],'relation_cohort':rels[:,0].astype(int),'relation_target':rels[:,1].astype(int),'relation_scale':rels[:,2],'leg':rels[:,3::2].astype(int),'sign':rels[:,4::2],'target_cohort':targets[:,0],'target_asset':targets[:,1],'causal':causal,'complete':complete,'bank':bank}
 for a in g.values():a.setflags(write=False)
 return g
def state_path(rng,phi,days):
 # Exact stationary Gaussian initialization; every original day is evolved,
 # including weekends/gaps. Only state persists; conditional score mean does not.
 out=np.empty((days,14));out[0]=rng.standard_normal(14)
 for d in range(1,days):out[d]=phi*out[d-1]+math.sqrt(1-phi*phi)*rng.standard_normal(14)
 return out
def base_paths(g,case,state_rng,factor_rng,days=210):
 states=state_path(state_rng,case['state_phi'],days);base=np.empty((days,146,75))
 for day in range(days):
  rho=case['rho_before'] if day<105 else case['rho_after']
  load=g['load'].copy()
  if case['strong_factor']:load[:,0]*=4;load[:,1:]*=.4
  if case['covariance_drift']:
   book=(.35 if day<105 else 1.75) if case['combined'] else (.25+1.5*day/209)
   load[:,5:]*=book;load[:,0]*=1.5
  if case['state_phi']>0:load*=np.exp(.35*states[day,1:])[None,:]
  vol=math.exp(.6*states[day,0]-.36) if case['state_phi']>0 else (math.exp(.45*states[day,0]-.2025) if case['heteroscedastic'] else 1.)
  if case['combined']:vol*=.6 if day<105 else 1.3
  shocks=factor_rng.standard_normal((146,13))
  if case['noise']=='T5':shocks*=np.sqrt(3/factor_rng.chisquare(5,(146,13)))
  if case['noise']=='SKEW_CHI3':shocks=(factor_rng.chisquare(3,(146,13))-3)/math.sqrt(6)
  variance12=12+2*sum((12-k)*rho**k for k in range(1,12))
  scales=g['scale']/np.sqrt(variance12*np.sum(load*load,axis=1))
  innovations=(shocks@load.T)*scales[None,:]*vol
  base[day,0]=innovations[0]
  for b in range(1,146):base[day,b]=rho*base[day,b-1]+math.sqrt(1-rho*rho)*innovations[b]
 return base,states
def clock_fits(g,path,day,k,c,project):
 q=12+12*k;past=path[q-11:q+1].sum(axis=0);last=path[q]
 rr=np.flatnonzero((g['relation_cohort']==c)&g['causal'][day,k]);values={}
 for r in rr:
  val=float(np.clip(np.sum(g['sign'][r]*past[g['leg'][r]])/g['relation_scale'][r],-3,3))
  values.setdefault(int(g['relation_target'][r]),[]).append(val)
 ids=sorted(values);declared=np.flatnonzero(g['target_cohort']==c).tolist()
 # No numerical/support-selected row subsets: causal membership only.
 if len(ids)<max(5,(len(declared)+1)//2) or len(rr)<(int((g['relation_cohort']==c).sum())+1)//2:return None
 assets=g['target_asset'][ids];X=np.column_stack([np.ones(len(ids)),last[assets]/g['scale'][assets],past[assets]/g['scale'][assets]])
 D=np.array([np.mean(values[t]) for t in ids]);full=project(X,D);loo={}
 for target in declared:
  keep=np.array([t!=target for t in ids]);loo[target]=(keep,full if keep.all() else project(X[keep],D[keep]))
 return {'ids':ids,'assets':assets,'X':X,'D':D,'full':full,'loo':loo}
def scores(g,base,case,delta,project):
 days=len(base);daily=np.full((days,12),np.nan);loo=np.full((days,44,4),np.nan);valid=np.zeros((days,12),bool)
 for day in range(days):
  path=base[day].copy();stored=[];rho=case['rho_before'] if day<105 else case['rho_after']
  for k in range(8):
   fits=[clock_fits(g,path,day,k,c,project) for c in range(3)];stored.append(fits)
   # Save all causal full/leaveout projections BEFORE injecting any future impulse.
   for c,f in enumerate(fits):
    if f is None or delta[c]==0:continue
    at=14+12*k;effect=delta[c]*f['full']['normalized']*g['scale'][f['assets']]
    path[at:,f['assets']]+=rho**np.arange(146-at)[:,None]*effect[None,:]
  sums=np.zeros(12);counts=np.zeros(12,int);ls=np.zeros((44,4))
  for k,fits in enumerate(stored):
   entry=13+12*k
   for c,f in enumerate(fits):
    if f is None:continue
    for hi,steps in enumerate([3,6,12,48]):
     if not g['complete'][day,k,c,hi]:continue
     Y=path[entry+1:entry+steps+1,f['assets']].sum(axis=0)/g['scale'][f['assets']]
     leaf=4*c+hi;sums[leaf]+=float(np.mean(f['full']['normalized']*Y));counts[leaf]+=1
     # ghat omitted only by inherited exact span-cancellation identity.
     for target,(keep,fit) in f['loo'].items():ls[target,hi]+=float(np.mean(fit['normalized']*Y[keep]))
  for l in range(12):
   valid[day,l]=counts[l]>=4
   if valid[day,l]:daily[day,l]=sums[l]/counts[l]
  for t in range(44):
   for hi in range(4):
    l=4*int(g['target_cohort'][t])+hi
    if valid[day,l]:loo[day,t,hi]=ls[t,hi]/counts[l]
 return {'daily':daily,'loo':loo,'valid':valid}
def infer(g,o,alpha=.025):
 daily=o['daily'];valid=o['valid'];assert daily.shape==valid.shape==(210,12)
 blocks=np.full((15,12),np.nan);n=np.zeros(12,int)
 for b in range(15):
  for l in range(12):
   use=valid[b*14:(b+1)*14,l]
   if use.sum()>=7:blocks[b,l]=daily[b*14:(b+1)*14,l][use].mean();n[l]+=1
 support=bool((n>=12).all() and all((valid[i:i+70].sum(axis=0)>=42).all() for i in [0,70,140]))
 if not support:raise NumericalUnavailable('FIXED_TIMESTAMP_OR_SYNTHETIC_FULL_FAMILY_SUPPORT_FAILURE')
 mu=np.nanmean(blocks,axis=0);u=np.where(np.isfinite(blocks),blocks-mu,0);ss=np.sum(u*u,axis=0)
 if not np.isfinite(ss).all() or (ss<=1e-20).any():raise NumericalUnavailable('DEGENERATE_STUDENTIZATION')
 obs=mu/np.sqrt(ss/(n*(n-1)));totals=g['bank']@u;den=(n[None,:]*ss[None,:]-totals*totals)/(n[None,:]-1)
 if (den< -1e-12).any():raise NumericalUnavailable('NEGATIVE_BOOTSTRAP_VARIANCE')
 # A zero bootstrap variance with nonzero numerator is infinite T, never zero.
 ts=np.divide(np.abs(totals),np.sqrt(np.maximum(den,0)),out=np.full_like(totals,np.inf),where=den>0)
 ts[(den==0)&(totals==0)]=0
 maximum=np.max(ts,axis=1);p=(1+np.sum(maximum[:,None]>=np.abs(obs)[None,:],axis=0))/1024
 reject=p<=alpha;lead=reject.copy();direction=np.sign(obs)
 for l in range(12):
  c,hi=divmod(l,4)
  for a,b in [(0,105),(105,210)]:
   use=valid[a:b,l]
   if not use.any() or direction[l]*daily[a:b,l][use].sum()<=0:lead[l]=False
  for target in np.flatnonzero(g['target_cohort']==c):
   values=o['loo'][:,target,hi][valid[:,l]]
   if not np.isfinite(values).all() or direction[l]*values.sum()<=0:lead[l]=False
 assert np.all(lead<=reject)
 return {'reject':reject,'lead':lead,'p':p,'t':obs,'support':True}
def trial(manifest,g,project,mode,case_id,index):
 require_execution_arm(manifest,mode)
 case=manifest['null_cases'][case_id]
 base,states=base_paths(g,case,generator(manifest,mode,case_id,index,'state'),generator(manifest,mode,case_id,index,'factor'))
 configs=manifest['partial_nulls'] if mode=='null' else manifest['power_cells']
 rows=[]
 for config in configs:
  delta=config['delta'];o=scores(g,base,case,delta,project);d=infer(g,o)
  true_null=np.repeat(np.array(delta)==0,4);nonnull=~true_null
  rows.append({'cell_id':config['id'],'false_significance':bool((d['reject']&true_null).any()),'false_lead':bool((d['lead']&true_null).any()),'any_nonnull_lead':bool((d['lead']&nonnull).any()),'all_nonnull_leads':bool(d['lead'][nonnull].all()) if nonnull.any() else False,'per_leaf_lead':d['lead'].astype(int).tolist(),'support':True})
 return rows
def aggregate_case(manifest,g,project,mode,case_id):
 # Only the armed control-plane may call this. No pilot/partial-result inference.
 require_execution_arm(manifest,mode)
 n=manifest['null_trials_per_case'] if mode=='null' else manifest['power_trials_per_case']
 cells=manifest['partial_nulls'] if mode=='null' else manifest['power_cells'];counts={c['id']:{'false_significance':0,'false_lead':0,'any_nonnull_lead':0,'all_nonnull_leads':0,'supported':0,'per_leaf_lead':[0]*12} for c in cells}
 for i in range(n):
  rows=trial(manifest,g,project,mode,case_id,i)
  for row in rows:
   ct=counts[row['cell_id']]
   for k in ['false_significance','false_lead','any_nonnull_lead','all_nonnull_leads']:ct[k]+=int(row[k])
   ct['supported']+=int(row['support']);ct['per_leaf_lead']=[a+b for a,b in zip(ct['per_leaf_lead'],row['per_leaf_lead'])]
 return {'schema':'TRIAD_V7_COMPLETE_CASE_RAW_V1','mode':mode,'case_id':case_id,'trials':n,'cells':counts,'interpretation':'PENDING_DURABLE_RAW_CHECKPOINT','numerical_failures':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'orders':0}
