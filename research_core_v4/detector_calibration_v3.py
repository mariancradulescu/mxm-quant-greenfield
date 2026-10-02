"""Research Core V4 detector calibration V3.

Synthetic only. No broker access, no market outcomes, no protected forward.
Calibrates hierarchical structural contexts, sibling volatility contexts,
heterogeneous symbol prevalence and stressed noise.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np

SEED=20261002
W,C,S,V,H=28,3,6,2,4
HSHAPE=np.array([0.5,1.0,0.75,0.4],dtype=float)
HCORR=0.65 ** np.abs(np.arange(H)[:,None]-np.arange(H)[None,:])
SCORR=np.array([[1.0,0.5],[0.5,1.0]])
LEAF_CHOL=np.linalg.cholesky(np.kron(SCORR,HCORR))

PREVALENCE={
 "6_OF_6_POSITIVE":np.array([1,1,1,1,1,1.],float),
 "5_OF_6_POSITIVE":np.array([1,1,1,1,1,0.],float),
 "4_OF_6_POSITIVE":np.array([1,1,1,1,0,0.],float),
 "STRUCTURAL_SUBSET_3_OF_6":np.array([1,1,1,0,0,0.],float),
 "HETEROGENEOUS_POSITIVE_MAGNITUDES":np.array([1.5,1.25,1,.75,.5,.25],float),
 "ONE_ZERO_ONE_WEAK":np.array([1,1,1,1,.25,0.],float),
 "ONE_OPPOSITE_SIGN":np.array([1,1,1,1,1,-.5],float),
 "TWO_OPPOSITE_SIGN":np.array([1,1,1,1,-.5,-.5],float),
}
STATE_MULT={
 "EFFECT_PRESENT_BOTH_VOL_STATES":np.array([1.,1.]),
 "EFFECT_PRESENT_HIGH_VOL_ONLY":np.array([0.,1.]),
 "EFFECT_PRESENT_LOW_VOL_ONLY":np.array([1.,0.]),
 "EFFECT_STRONGER_HIGH_THAN_LOW":np.array([.4,1.]),
 "EFFECT_STRONGER_LOW_THAN_HIGH":np.array([1.,.4]),
}

def _noise(n,noise,rng,base_se):
    if noise=="FAT_TAILED_INNOVATIONS_T5":
        z=rng.standard_t(5,size=(n,C,S,W,V*H))/np.sqrt(5/3)
    else:
        z=rng.normal(size=(n,C,S,W,V*H))
    z=np.einsum("...k,lk->...l",z,LEAF_CHOL)
    common=rng.normal(size=(n,C,1,W,V*H))
    common=np.einsum("...k,lk->...l",common,LEAF_CHOL)
    cw=.65 if noise=="STRONGER_CROSS_SYMBOL_COMMON_FACTOR" else .30
    y=np.sqrt(1-cw*cw)*z+cw*common
    for t in range(1,W):
        y[:,:,:,t,:]=.25*y[:,:,:,t-1,:]+np.sqrt(1-.25**2)*y[:,:,:,t,:]
    lv=rng.normal(size=(n,C,W))
    for t in range(1,W):
        lv[:,:,t]=.85*lv[:,:,t-1]+np.sqrt(1-.85**2)*lv[:,:,t]
    y*=np.exp(.22*lv-.5*.22**2)[:,:,None,:,None]
    if noise=="WEEKLY_REGIME_SHIFTS":
        reg=np.ones((n,C,W))
        for b in range(0,W,4):
            reg[:,:,b:b+4]=rng.choice([.65,1.75],size=(n,C,1),p=[.55,.45])
        y*=reg[:,:,None,:,None]
    if noise=="UNEQUAL_SYMBOL_NOISE":
        y*=np.array([.55,.75,.95,1.15,1.40,1.70])[None,None,:,None,None]
    if noise=="UNEQUAL_EVENT_COUNTS":
        y*=np.sqrt(50/np.array([16,24,40,64,96,160.]))[None,None,:,None,None]
    return y*base_se*np.sqrt(W)

def simulate(n,effect_bps,prevalence,state_scenario,noise,seed,base_se=10.,all_contexts=False,micro_dilution=False):
    rng=np.random.default_rng(seed)
    y=_noise(n,noise,rng,base_se)
    valid=np.ones((n,C,S,W),bool)
    if noise=="MISSING_SYMBOL_WEEKS":
        valid=rng.random((n,C,S,W))>.16
        valid &= ~(rng.random((n,C,W))<.03)[:,:,None,:]
    sm=PREVALENCE[prevalence]
    vm=STATE_MULT[state_scenario]
    eff=float(effect_bps)*(.70 if micro_dilution else 1.0)
    arr=np.zeros((C,S,V,H))
    contexts=range(C) if all_contexts else [0]
    for c in contexts:
        arr[c]=sm[:,None,None]*vm[None,:,None]*HSHAPE[None,None,:]*eff
    y += arr.reshape(1,C,S,1,V*H)
    return y.reshape(n,C,S,W,V,H),valid

def pool_context_week(y,valid):
    masked=np.where(valid[:,:,:,:,None,None],y,np.nan)
    pooled=np.nanmean(masked,axis=2)
    nvalid=valid.sum(axis=2)
    return np.where(nvalid[:,:,:,None,None]>=4,pooled,np.nan)

def block_t(pooled):
    n,c,_,v,h=pooled.shape
    blocks=np.nanmean(pooled.reshape(n,c,14,2,v,h),axis=3)
    count=np.sum(np.isfinite(blocks),axis=2)
    mean=np.nanmean(blocks,axis=2)
    sd=np.nanstd(blocks,axis=2,ddof=1)
    t=mean/(sd/np.sqrt(count))
    return np.where(count>=12,t,-np.inf)

def max_t(y,valid):
    pooled=pool_context_week(y,valid)
    t=block_t(pooled)
    return t.reshape(y.shape[0],C,-1).max(axis=2),t,pooled

def p_from_null(x,null_pool):
    idx=np.searchsorted(null_pool,x,side="left")
    return (len(null_pool)-idx+1)/(len(null_pool)+1)

def holm(p,alpha=.05):
    n,m=p.shape
    order=np.argsort(p,axis=1)
    sp=np.take_along_axis(p,order,axis=1)
    cut=alpha/(m-np.arange(m))
    rs=np.cumprod((sp<=cut).astype(int),axis=1).astype(bool)
    out=np.zeros_like(rs)
    out[np.arange(n)[:,None],order]=rs
    return out

def gates(y,valid,t,pooled):
    n=y.shape[0]
    flat=t.reshape(n,C,-1)
    sel=np.argmax(flat,axis=2)
    selv,selh=sel//H,sel%H
    out=np.zeros((n,C),bool)
    for c in range(C):
        temporal=[]
        for q in range(4):
            qmean=np.nanmean(pooled[:,c,q*7:(q+1)*7,:,:],axis=1)
            temporal.append(qmean[np.arange(n),selv[:,c],selh[:,c]]>0)
        temporal=np.stack(temporal,axis=1).sum(axis=1)>=3
        arr=np.where(valid[:,c,:,:,None,None],y[:,c],np.nan)
        sm=np.nanmean(arr,axis=2)
        chosen=sm[np.arange(n)[:,None],np.arange(S)[None,:],selv[:,c,None],selh[:,c,None]]
        breadth=np.sum(chosen>0,axis=1)>=3
        out[:,c]=temporal & breadth
    return out

def evaluate(y,valid,null_pool):
    lm,t,pooled=max_t(y,valid)
    reject=holm(p_from_null(lm,null_pool))
    gate=gates(y,valid,t,pooled)
    lead=reject & gate
    return {
      "global_any":float(lead.any(axis=1).mean()),
      "active_context":float(lead[:,0].mean()),
      "holm_any":float(reject.any(axis=1).mean()),
    }

def build_null(noise,reps,seed,base_se=10.):
    y,v=simulate(reps,0,"6_OF_6_POSITIVE","EFFECT_PRESENT_BOTH_VOL_STATES",noise,seed,base_se)
    lm,_,_=max_t(y,v)
    return np.sort(lm.ravel())

def quick_report():
    pool=build_null("BASELINE",1200,SEED+1)
    y,v=simulate(800,0,"6_OF_6_POSITIVE","EFFECT_PRESENT_BOTH_VOL_STATES","BASELINE",SEED+2)
    null=evaluate(y,v,pool)
    y2,v2=simulate(800,20,"4_OF_6_POSITIVE","EFFECT_PRESENT_HIGH_VOL_ONLY","BASELINE",SEED+3)
    alt=evaluate(y2,v2,pool)
    return {"negative_control":null,"heterogeneous_high_only_20bps":alt,"market_data_used":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--quick",action="store_true")
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    result=quick_report()
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output: args.output.write_text(text,encoding="utf-8")
    else: print(text,end="")

if __name__=="__main__":
    main()
