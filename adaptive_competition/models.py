from __future__ import annotations
from collections import deque
import numpy as np
from .data import HORIZONS

def basis(x,nonlinear=False):
 if not nonlinear:return x
 # fixed, compact interaction basis; no feature selection.
 return np.concatenate((x,x[...,1:5]*abs(x[...,1:5]),x[...,6:8]*x[...,8:9],x[...,16:18]*x[...,1:2]),axis=-1)

class MatureQueue:
 def __init__(self):self.items=[]
 def add(self,maturity,event):self.items.append((maturity,event))
 def pop(self,now):
  ready=[e for t,e in self.items if t<=now];self.items=[(t,e) for t,e in self.items if t>now];return ready

class ForecastModel:
 """Finite sufficient statistics by exact label maturity day, trailing 56/7d.
 No label from current UTC day participates in refit; this conservatively
 delays all model updates to the next midnight after exact maturity.
 """
 def __init__(self,X,Y,info,nonlinear=False):
  self.X=X;self.Y=Y;self.info=info;self.nonlinear=nonlinear
  self.ci=np.array([info['contexts'].index(m['asset_class']) for m in info['metadata']])
  self.nc=np.bincount(self.ci);self.sw=1/np.sqrt(self.nc[self.ci]);self.D=27 if nonlinear else 19
  self.daily={};self.anchor=None;self.anchor_day=None;self.fitted_day=-1
 def daystats(self,day):
  if day in self.daily:return self.daily[day]
  n=len(self.ci);d=self.D
  xx=np.zeros((n,4,d,d));xy=np.zeros((n,4,d));yy=np.zeros((n,4));cnt=np.zeros((n,4))
  for hi,h in enumerate(HORIZONS):
   # global UTC 30m sampling for statistical updates only, not a trade cap.
   lo=max(0,day*288-h-1);up=min(len(self.X),(day+1)*288-h-1)
   ix=np.arange(((lo+5)//6)*6,up,6)
   for si in range(n):
    x=basis(np.asarray(self.X[ix,si]),self.nonlinear);y=np.asarray(self.Y[ix,si,hi])
    valid=np.isfinite(x).all(axis=1)&np.isfinite(y);x=x[valid];y=np.clip(y[valid],-8,8)
    if len(y):xx[si,hi]=x.T@x;xy[si,hi]=x.T@y;yy[si,hi]=y@y;cnt[si,hi]=len(y)
  self.daily[day]=(xx,xy,yy,cnt)
  return self.daily[day]
 def fit_window(self,day,days):
  stats=[self.daystats(i) for i in range(max(0,day-days),day)]
  xx,xy,yy,cnt=[sum(v[k] for v in stats) for k in range(4)]
  n,h,d=xy.shape;betas=np.zeros_like(xy);variance=np.ones((n,h));se=np.zeros((n,h));tails=np.ones((n,h))*3
  for hi in range(h):
   count=cnt[:,hi];w=self.sw/np.maximum(count,1);w[count==0]=0
   A=np.einsum('s,sij->ij',w,xx[:,hi]);b=np.einsum('s,si->i',w,xy[:,hi])
   penalty=np.eye(d)*.5;penalty[0,0]=.05
   globalb=np.linalg.solve(A+penalty,b)
   for ci in range(len(self.nc)):
    ids=np.flatnonzero(self.ci==ci);wc=w[ids];xc=xx[ids,hi]
    Ac=np.einsum('s,sij->ij',wc,xc);bc=np.einsum('s,si->i',wc,xy[ids,hi])-Ac@globalb
    # context component shrinks toward the global law, not symbol one-hot.
    cb=globalb+np.linalg.solve(Ac+np.eye(d)*2,bc)
    for si in ids:
     if count[si]<24:betas[si,hi]=globalb;continue
     local=(xy[si,hi,0]-xx[si,hi,0]@cb)/count[si]
     cb2=cb.copy();cb2[0]+=np.clip(local,-.25,.25)*count[si]/(count[si]+500)
     betas[si,hi]=cb2
     variance[si,hi]=max(.04,(yy[si,hi]-2*cb2@xy[si,hi]+cb2@xx[si,hi]@cb2)/count[si])
     # Overlap is not independent evidence: daily cluster ceiling, not row count.
     independent=min(days,count[si]/48)
     se[si,hi]=np.sqrt(variance[si,hi]/max(independent,1))
     tails[si,hi]=3*np.sqrt(variance[si,hi])
  return betas,variance,se,tails
 def update(self,day):
  if day==self.fitted_day:return
  # causal periodic reanchor, finite trailing history; bounded overlay.
  if self.anchor is None or day-self.anchor_day>=7:
   self.anchor=self.fit_window(day,56);self.anchor_day=day
  recent=self.fit_window(day,7)
  self.state=tuple(.75*a+.25*b for a,b in zip(self.anchor,recent))
  self.fitted_day=day
  # retain at most 63 UTC maturity-day buckets; no hidden infinite state.
  self.daily={k:v for k,v in self.daily.items() if k>=day-63}
 def predict(self,x,sig):
  x=basis(np.asarray(x),self.nonlinear);valid=np.isfinite(x).all(axis=1)&np.isfinite(sig)
  xb=np.nan_to_num(x);b,var,se,tail=self.state
  normalized=np.einsum('sd,shd->sh',xb,b)
  reliability=1/(1+var)
  mu=normalized*reliability
  scale=sig[:,None]*np.sqrt(np.array(HORIZONS))[None,:]
  # OOD from dimensionless primitives, unavailable relation has separate flag.
  ood=(abs(xb[:,1:16])>=3.99).any(axis=1)
  mu[ood]*=.25
  mu[~valid]=np.nan
  return mu*scale,se*scale,tail*scale,reliability,ood
