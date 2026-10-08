"""Exact-mask daily synthetic full-procedure power. No real values accepted.
All V1 scientific components remain exact; V2 cutoff is read from its frozen file.
"""
import hashlib,json,pathlib
import numpy as np
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'research_core_v4/operational_v2'))
from bank import R,P,C,core,seed,sha,canonical

def structural_support(mask):
 D,L=mask.shape;assert L==261 and D%7==0
 v=mask.reshape(D//7,7,L).any(1);ok=v.sum(0)>=12
 for ix in np.array_split(np.arange(len(v)),3):ok &=v[ix].sum(0)>=4
 return ok

def run_power(mask,geometry_hash):
 p=json.loads((R/P).read_bytes());pb=(R/P).read_bytes();cf=json.loads((R/C).read_bytes());v1=json.loads((R/p['invariant_power_ref']).read_bytes());engine,gen=core()
 assert type(mask) is np.ndarray and mask.dtype==bool and mask.ndim==2 and mask.shape[1]==261
 D,L=mask.shape;assert D%7==0 and D<=168
 N=p['precision']['trials_per_case'];z=4.669289888046892;supported=structural_support(mask);alpha=cf['selected_k']/1024
 out={'schema':'mxm.operational-v2.exact-mask-power-result.v1','protocol_sha256':sha(R/P),'cutoff_freeze_sha256':sha(R/C),'geometry_sha256':geometry_hash,'daily_score_mask_sha256':hashlib.sha256(mask.tobytes()).hexdigest(),'score_calendar_days':D,'paid_leaves':261,'support_eligible_leaf_count':int(supported.sum()),'selected_k':cf['selected_k'],'alpha_V2':alpha,'effects':v1['power']['effects'],'units':'SYNTHETIC_DAILY_INCREMENTAL_SCORE_MARGINAL_SD','target_simultaneous_lower95':.8,'cases':{},'real_inputs':0}
 if not supported.any():
  for case,effect in v1['power']['effects'].items():out['cases'][case]={'effect':effect,'counts':[0]*261,'wilson_lowers':[0.]*261,'trials_executed':0,'method':'DETERMINISTIC_UNSUPPORTED_NO_LEAF_CAN_LEAD'}
 else:
  B=D//7;bank_seed=seed(pb,'POWER','MULTIPLIERS','COMMON',B);bank=np.random.default_rng(bank_seed).choice([-1.,1.],size=(1023,B))
  for case,effect in v1['power']['effects'].items():
   ss=seed(pb,'POWER','INNOVATIONS',case,B);rng=np.random.default_rng(ss);ct=np.zeros(L,np.int64);witness=hashlib.sha256()
   for start in range(0,N,16):
    n=min(16,N-start);x,_=gen.generate(v1,case,n,B,rng);m=np.broadcast_to(mask,(n,D,L));g=engine.cluster(x,m);ref=engine.bootstrap_max(g,bank);shift=np.full((n,L),effect);_,_,pv,_=engine.decisions(g,ref,shift)
    stable=((g['third']+effect)>0).sum(1)>=2;lead=(pv<=alpha)&g['support']&stable;ct+=lead.sum(0);witness.update(g['u'].tobytes());witness.update(ref.tobytes())
   lo,hi=engine.wilson(ct,N,z);out['cases'][case]={'effect':effect,'counts':ct.tolist(),'wilson_lowers':lo.tolist(),'wilson_uppers':hi.tolist(),'trials_executed':N,'innovations_seed_hex':format(ss,'064x'),'multiplier_seed_hex':format(bank_seed,'064x'),'witness_sha256':witness.hexdigest()}
 eligible=np.all(np.array([out['cases'][c]['wilson_lowers'] for c in ['NORMAL','AR025','AR050']])>=.8,axis=0)
 out['source_ready']={s:bool(any(eligible[j] for j,l in enumerate(v1['paid_leaves']) if l['source']==s)) for s in v1['sources']};out['shared_ready']=all(out['source_ready'].values());return out
