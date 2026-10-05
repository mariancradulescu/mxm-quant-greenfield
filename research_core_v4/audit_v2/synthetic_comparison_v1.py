"""Synthetic joint scores only. Reads only its frozen JSON plan; no market loader/network."""
import json, hashlib, pathlib, platform
import numpy as np
from scipy.stats import t as student
ROOT=pathlib.Path(__file__).parent

def wilson(k,n,z):
 p=k/n; den=1+z*z/n;mid=(p+z*z/(2*n))/den;w=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return [float(mid-w),float(mid+w)]

def gen(rng,case,N,D):
 shape=(N,3,4,D+100)
 def noise(shape):
  if case=='heavy_t5':return rng.standard_t(5,shape)/np.sqrt(5/3)
  if case=='skew_centered':return (rng.chisquare(3,shape)-3)/np.sqrt(6)
  return rng.normal(size=shape)
 # Unit marginal variance. Independent + context factor + whole-panel factor.
 x=np.sqrt(.35)*noise((N,1,1,D+100))+np.sqrt(.30)*noise((N,3,1,D+100))+np.sqrt(.35)*noise(shape)
 rho={'AR025':.25,'AR050':.5}.get(case,0)
 if rho:
  for j in range(1,D+100):x[...,j]=rho*x[...,j-1]+np.sqrt(1-rho*rho)*x[...,j]
 if case=='heteroscedastic': x*=np.exp(.7*rng.normal(size=(N,1,1,D+100)))/np.exp(.49)
 x=x[...,-D:];mask=np.ones((N,D),bool)
 if case=='missing_gaps':mask[:,-10:]=False;mask[:,:-10]&=rng.random((N,D-10))>=.05
 return x,mask

def aggregate(x,mask,days):
 if days==1:return x,mask
 N,C,H,D=x.shape;L=D//days
 xx=x.reshape(N,C,H,L,days);mm=mask.reshape(N,L,days);count=mm.sum(-1);valid=count>=3
 y=(xx*mm[:,None,None,:,:]).sum(-1)/np.maximum(count[:,None,None,:],1)
 return y,valid

def hac(x,mask,L):
 n=mask.sum(-1);avg=(x*mask[:,None,None,:]).sum(-1)/n[:,None,None]
 z=(x-avg[...,None])*mask[:,None,None,:]
 v=(z*z).sum(-1)
 for lag in range(1,L+1):v+=2*(1-lag/(L+1))*(z[...,lag:]*z[...,:-lag]).sum(-1)
 se=np.sqrt(np.maximum(v,1e-14))/n[:,None,None]
 return avg/se,avg,se

def corrected(x,mask,cfg,dev):
 y,m=aggregate(x,mask,cfg['aggregation_days']);tt,means,se=hac(y,m,cfg['HAC_lags'])
 p=2*student.sf(np.abs(tt),cfg['reference_t_df']);local=np.minimum(1,4*p);context=local.min(-1)
 order=np.argsort(context,axis=1,kind='stable');reject=np.zeros_like(p,dtype=bool);alive=np.ones(len(x),bool)
 for rank in range(3):
  idx=order[:,rank];alpha=.025/(3-rank);alive&=context[np.arange(len(x)),idx]<=alpha
  reject[np.arange(len(x)),idx,:]=alive[:,None]&(local[np.arange(len(x)),idx,:]<=alpha)
 # Same chosen leaf, no freely substituted temporal target.
 stable=np.zeros_like(reject,dtype=int);direction=np.sign(means)
 for inds in np.array_split(np.arange(x.shape[-1]),4):
  mm=mask[:,inds];qq=(x[...,inds]*mm[:,None,None,:]).sum(-1)/np.maximum(mm.sum(-1)[:,None,None],1)
  stable+=direction*qq>0
 # Asset mean deviations zero-sum, coherent context mean preserved exactly.
 breadth=(direction[...,None]*(means[...,None]+dev)>=0).sum(-1)>=3
 lead=reject&(stable>=3)&breadth
 support=mask.sum(-1)>=168;reject&=support[:,None,None];lead&=support[:,None,None]
 return reject,lead,tt,means,se

def old(x,mask,dev):
 y,m=aggregate(x[:,:,:1],mask,5);N,C,H,W=y.shape
 blocks=y.reshape(N,C,H,21,2).mean(-1);bm=m.reshape(N,21,2).all(-1)
 tt,avg,se=hac(blocks,bm,2);direction=np.sign(avg[:,0,0]);signif=np.all((direction[:,None]*avg[:,:,0]>0)&(np.abs(tt[:,:,0])>=5),axis=1)
 support=bm.sum(-1)>=18
 for q in range(3):
  ii=slice(q*7,(q+1)*7);count=bm[:,ii].sum(-1);support&=count>=5
  mean=(blocks[:,:,:,ii]*bm[:,None,None,ii]).sum(-1)/np.maximum(count[:,None,None],1)
  signif&=np.all(direction[:,None]*mean[:,:,0]>0,axis=1)
 breadth=(direction[:,None,None]*(avg[:,:,0,None]+dev[:,:,0])>0).sum(-1)>=4
 signif&=np.all(breadth,axis=1)&support
 return signif,np.any(np.abs(tt[:,:,0])>=5,axis=1)&support

def metric(a,z=1.96):
 k=int(np.sum(a));N=len(a);return {'k':k,'trials':N,'rate':k/N,'wilson':wilson(k,N,z)}

def main():
 plan=json.loads((ROOT/'SYNTHETIC_COMPARISON_PLAN_V1.json').read_text());N=plan['trials_per_case'];D=plan['calendar_days']
 report={'schema':'mxm.v4.synthetic-methodology-comparison.v1','market_data_used':False,'plan_sha256':hashlib.sha256((ROOT/'SYNTHETIC_COMPARISON_PLAN_V1.json').read_bytes()).hexdigest(),'implementation_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'environment':{'python':platform.python_version(),'numpy':np.__version__},'null':{},'power':{},'units':'Unit marginal SD of a DAILY joint context/horizon score. Never bps/profit. Old and corrected share identical synthetic underlying observations.'}
 rng=np.random.default_rng(plan['seed_null'])
 for case in plan['null_cases']:
  x,m=gen(rng,case,N,D);dev=rng.normal(size=(N,3,4,6))/np.sqrt(D);dev-=dev.mean(-1,keepdims=True)
  out={};oldlead,oldnull=old(x,m,dev);out['old_reference']={'universal_complete_lead':metric(oldlead,3.4),'any_context_cutoff':metric(oldnull,3.4)}
  for cfg in plan['candidates']:
   r,l,_,_,_=corrected(x,m,cfg,dev);q=x.copy();q[:,0,0]+=plan['partial_null_shift'];pr,pl,_,_,_=corrected(q,m,cfg,dev);pr[:,0,0]=False;pl[:,0,0]=False
   out[cfg['id']]={'global_null_any_leaf':metric(r.any((1,2)),3.4),'global_null_complete_lead':metric(l.any((1,2)),3.4),'partial_null_false_leaf':metric(pr.any((1,2)),3.4),'partial_null_false_lead':metric(pl.any((1,2)),3.4)}
  report['null'][case]=out;print('null',case,flush=True)
 rng=np.random.default_rng(plan['seed_power'])
 for case in plan['null_cases']:
  base,m=gen(rng,case,N,D);dev=rng.normal(size=(N,3,4,6))/np.sqrt(D);dev-=dev.mean(-1,keepdims=True);report['power'][case]={}
  for alt in plan['alternatives']:
   row={}
   for effect in plan['effects_daily_score_SD']:
    x=base.copy()
    if alt=='all_contexts_one_horizon':x[:,:,0]+=effect
    else:x[:,0,0]+=effect
    out={'old_reference':metric(old(x,m,dev)[0])}
    for cfg in plan['candidates']:
     r,l,_,_,_=corrected(x,m,cfg,dev)
     target=l[:,:,0].any(1) if alt=='all_contexts_one_horizon' else l[:,0,0]
     out[cfg['id']]=metric(target)
    row[str(effect)]=out
   report['power'][case][alt]=row
  print('power',case,flush=True)
 eligible=[];report['candidate_assessment']={}
 for cfg in plan['candidates']:
  name=cfg['id'];passed=all(v[name][k]['wilson'][1]<=.05 for v in report['null'].values() for k in ['global_null_any_leaf','partial_null_false_leaf']);mdi={}
  for case in plan['null_cases']:
   mdi[case]={}
   for alt in plan['alternatives']:
    effects=[e for e in plan['effects_daily_score_SD'] if report['power'][case][alt][str(e)][name]['wilson'][0]>=.8]
    mdi[case][alt]=min(effects) if effects else None
  vals=[v['one_context_one_horizon'] for v in mdi.values()];worst=max(vals) if all(v is not None for v in vals) else float('inf')
  report['candidate_assessment'][name]={'error_gate_pass':passed,'grid_MDI_daily_SD':mdi,'worst_localized_grid_MDI_daily_SD':worst if np.isfinite(worst) else None}
  if passed:eligible.append((worst,0 if name.startswith('DAILY') else 1,name))
 report['selected_inference_candidate']=min(eligible)[2] if eligible else None;report['error_control_certified_for_declared_synthetic_envelope_only']=bool(eligible)
 report['old_grid_MDI_daily_SD']={}
 for case in plan['null_cases']:
  report['old_grid_MDI_daily_SD'][case]={}
  for alt in plan['alternatives']:
   ee=[e for e in plan['effects_daily_score_SD'] if report['power'][case][alt][str(e)]['old_reference']['wilson'][0]>=.8];report['old_grid_MDI_daily_SD'][case][alt]=min(ee) if ee else None
 (ROOT/'SYNTHETIC_COMPARISON_RESULT_V1.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print('selected',report['selected_inference_candidate'],flush=True)
if __name__=='__main__':main()
