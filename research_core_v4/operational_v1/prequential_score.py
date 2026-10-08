"""Prospective model-relative score. Array entry point is synthetic-only in Stage0.
No market adapters or real feature/response producers are imported here.
"""
from dataclasses import dataclass
import numpy as np
DAY=86400
@dataclass
class PrefixFit:
    means: np.ndarray
    sds: np.ndarray
    zero: np.ndarray
    ymean: float
    ysd: float
    beta_b: np.ndarray
    beta_aug: np.ndarray
    train_indices: np.ndarray
    weights: np.ndarray
    refit: int

def weights_equal_identity(ids):
    _, inv, counts=np.unique(ids,return_inverse=True,return_counts=True)
    # Total weight one, equally allocated to identities, then their events.
    return 1.0/(len(counts)*counts[inv])

def solve_ridge(x,y,w):
    z=np.column_stack([np.ones(len(x)),x])
    penalty=np.full(z.shape[1],0.5);penalty[0]=0.05
    return np.linalg.solve((z*w[:,None]).T@z+np.diag(penalty),z.T@(w*y))

def fit_prefix(t,maturity,ids,b,phi,y,valid,refit,domain_start):
    assert b.shape[1]==10 and np.all(maturity>t)
    if refit-domain_start<56*DAY:return None
    # Entire current UTC day is excluded. Maximum-label plus closed-bar purge
    # is strict: a training decision must precede refit by >240min+5min.
    day_start=(refit//DAY)*DAY
    mask=valid&(t>=refit-56*DAY)&(t<day_start)&(t+245*60<refit)&(maturity<refit)&(t%1800==0)
    idx=np.flatnonzero(mask)
    if not len(idx):return None
    w=weights_equal_identity(ids[idx]);x=np.column_stack([b[idx],phi[idx]])
    mean=(x*w[:,None]).sum(0);sd=np.sqrt(((x-mean)**2*w[:,None]).sum(0));zero=sd<=1e-12
    scale=np.maximum(sd,1e-12);xx=(x-mean)/scale;xx[:,zero]=0
    ym=float(w@y[idx]);ys=float(np.sqrt(w@((y[idx]-ym)**2)));ys=max(ys,1e-12)
    yy=np.clip((y[idx]-ym)/ys,-8,8)
    return PrefixFit(mean,scale,zero,ym,ys,solve_ridge(xx[:,:10],yy,w),solve_ridge(xx,yy,w),idx,w,refit)

def predict(f,b,phi):
    xx=(np.concatenate([b,phi])-f.means)/f.sds;xx[f.zero]=0
    pb=float(np.clip(np.r_[1.,xx[:10]]@f.beta_b,-8,8))
    pa=float(np.clip(np.r_[1.,xx]@f.beta_aug,-8,8))
    return pb,pa

def prequential(t,maturity,ids,b,phi,y,valid,domain_start,domain_end):
    order=np.lexsort((ids,t));assert np.array_equal(order,np.arange(len(t))), 'canonical time/identity ordering'
    rows=[];audit=[]
    for refit in range(domain_start+56*DAY,domain_end,7*DAY):
        f=fit_prefix(t,maturity,ids,b,phi,y,valid,refit,domain_start)
        if f is None:continue
        idx=np.flatnonzero(valid&(t>=refit)&(t<min(refit+7*DAY,domain_end))&(maturity<domain_end))
        audit.append({'refit':refit,'train_indices':f.train_indices.tolist(),'zero_coordinates':np.flatnonzero(f.zero).tolist(),'training_identity_weights':{str(i):float(f.weights[ids[f.train_indices]==i].sum()) for i in np.unique(ids[f.train_indices])}})
        for k in idx:
            # Both predictions depend only on frozen prefix fit and current inputs.
            pb,pa=predict(f,b[k],phi[k]);yy=float(np.clip((y[k]-f.ymean)/f.ysd,-8,8))
            d=(yy-pb)**2-(yy-pa)**2
            rows.append((int(t[k]//DAY),int(ids[k]),d,pb,pa,int(k),refit))
    daily={}
    for date in sorted({r[0] for r in rows}):
        ir={}
        for row in rows:
            if row[0]==date:ir.setdefault(row[1],[]).append(row[2])
        daily[date]=float(np.mean([np.mean(v) for v in ir.values()]))
    return rows,daily,audit
