"""Vectorized, semantically equivalent execution of the frozen V3 response grid.

Input is one authenticated series at a time. Never fills a gap or changes a timestamp.
"""
from __future__ import annotations
import hashlib,json,math,statistics
from collections import defaultdict
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from .engine import _grid,_neighbors,_ci,_seg
from .signals import EPS,context_ok,signal,mean,median


def _rolling_abs_return(c):
 r=np.zeros(len(c),dtype=float)
 np.divide(c[1:],c[:-1],out=r[1:],where=c[:-1]!=0)
 r[1:]=np.abs(r[1:]-1)
 r[1:][c[:-1]==0]=np.nan
 return r

class Features:
 def __init__(self,s):
  self.s=s;self.b=s.bars;self.n=len(self.b)
  self.c=np.array([x.close for x in self.b],dtype=float)
  self.hi=np.array([x.high for x in self.b],dtype=float)
  self.lo=np.array([x.low for x in self.b],dtype=float)
  self.ranges=np.maximum(EPS,self.hi-self.lo)
  self.absret=_rolling_abs_return(self.c)
  self.hours=np.array([x.ts.hour for x in self.b],dtype=np.int8)
  self.seg=np.asarray(_seg(self.b),dtype=np.int32)
  self._signal={};self._context={};self._rolling={}
 def roll_abs_mean(self,n):
  if n not in self._rolling:
   arr=np.full(self.n,np.nan)
   if self.n>=n:
    vals=np.nan_to_num(self.absret,nan=0.0)
    sums=np.cumsum(np.r_[0.0,vals])
    arr[n-1:]=(sums[n:]-sums[:-n])/n
   self._rolling[n]=arr
  return self._rolling[n]
 def context(self,ctx):
  key=json.dumps(ctx,sort_keys=True)
  if key in self._context:return self._context[key]
  out=np.ones(self.n,dtype=bool);kind=ctx.get('kind','ALL')
  if kind=='VOLATILITY_QUANTILE':
   out[:]=False;n=int(ctx.get('lookback',48));ref=int(ctx.get('reference_bars',1000))
   # Early partial reference windows use the unmodified scalar definition.
   edge=min(self.n,ref+n+1)
   for i in range(edge):out[i]=context_ok(ctx,self.b,self.c,i)
   qlo=float(ctx.get('q_low',0));qhi=float(ctx.get('q_high',1))
   for base in range(edge,self.n,4096):
    end=min(self.n,base+4096)
    # Each row contains abs returns from i-ref through i-1.
    windows=sliding_window_view(self.absret,ref)[base-ref:end-ref]
    lo=np.quantile(windows,qlo,axis=1);hi=np.quantile(windows,qhi,axis=1)
    current=self.roll_abs_mean(n)[base:end]
    out[base:end]=(lo<=current)&(current<=hi)
  elif kind=='UTC_HOUR':out[:]=np.isin(self.hours,ctx.get('hours',[]))
  elif kind=='DAY_OF_WEEK':out[:]=[x.ts.weekday() in ctx.get('days',[]) for x in self.b]
  elif kind!='ALL':out[:]=False
  self._context[key]=out;return out
 def signals(self,mech,p):
  key=(mech,json.dumps(p,sort_keys=True))
  if key in self._signal:return self._signal[key]
  out=np.zeros(self.n,dtype=np.int8);c=self.c;N=self.n
  if mech=='REGIME_CONTEXT_CONDITIONED':
   v=p.get('variant',p)
   if isinstance(v,dict):out=self.signals(v.get('base','TREND_MOMENTUM'),v.get('base_params',{'lookback':24,'threshold':0})).copy()
  elif mech=='TREND_MOMENTUM':
   n=int(p['lookback']);t=float(p.get('threshold',0))
   if N>n:
    rr=np.full(N-n,np.nan);np.divide(c[n:],c[:-n],out=rr,where=c[:-n]!=0);rr-=1
    out[n:]=np.where(rr>=t,1,np.where(rr<=-t,-1,0))
  elif mech=='MEAN_REVERSION':
   n=int(p['lookback']);t=float(p['z'])
   if N>=n:
    windows=sliding_window_view(c,n);av=np.mean(windows,axis=1);sd=np.std(windows,axis=1)
    z=np.divide(c[n-1:]-av,sd,out=np.zeros_like(av),where=sd>EPS)
    out[n-1:]=np.where(sd>EPS,np.where(z>=t,-1,np.where(z<=-t,1,0)),0)
  elif mech=='BREAKOUT_VOLATILITY_EXPANSION':
   n=int(p['lookback']);ratio=float(p.get('range_ratio',1.5))
   if N>n:
    prior_hi=sliding_window_view(self.hi,n)[:N-n].max(axis=1)
    prior_lo=sliding_window_view(self.lo,n)[:N-n].min(axis=1)
    base=np.median(sliding_window_view(self.ranges,n)[:N-n],axis=1)
    active=self.hi[n:]-self.lo[n:]>=ratio*base
    out[n:]=np.where(active,np.where(c[n:]>prior_hi,1,np.where(c[n:]<prior_lo,-1,0)),0)
  elif mech=='VOLATILITY_STATE':
   n=int(p['lookback']);ref=int(p.get('reference',max(5*n,100)));q=float(p.get('quantile',.8));state=str(p.get('state','HIGH'))
   edge=min(N,ref+n+1)
   for i in range(edge):out[i]=signal(mech,p,self.b,c,i)
   rv=self.roll_abs_mean(n)
   quant=q if state=='HIGH' else 1-q
   for base in range(edge,N,4096):
    end=min(N,base+4096)
    windows=sliding_window_view(rv,ref-1)[base-ref+1:end-ref+1]
    cut=np.quantile(windows,quant,axis=1);cur=rv[base:end]
    active=cur>=cut if state=='HIGH' else cur<=cut
    signed=np.where(c[base:end]/c[base-1:end-1]-1>=0,1,-1)
    out[base:end]=np.where(active,signed,0)
  elif mech=='SESSION_TIME_SEASONALITY':
   out[:]=np.where(np.isin(self.hours,p.get('hours',[])),int(p.get('direction',1)),0)
  self._signal[key]=out;return out


def evaluate_fast(f,mech,ctx,p,hs,rearm):
 b=f.b;c=f.c;seg=f.seg;N=f.n;mh=max(hs)
 sig=f.signals(mech,p);mask=(sig!=0)&f.context(ctx)
 mask[max(0,N-mh):]=False
 if N>mh:mask[:N-mh]&=seg[:N-mh]==seg[mh:]
 candidates=np.flatnonzero(mask);indices=[];last=-10**12
 for i in candidates:
  if i-last<rearm:continue
  indices.append(int(i));last=int(i)
 ev=[]
 for i in indices:
  rr={str(h):None if seg[i]!=seg[i+h] or c[i]==0 else int(sig[i])*(c[i+h]/c[i]-1) for h in hs}
  ev.append((i,b[i].ts.date().isoformat(),int(sig[i]),rr))
 clusters=0;prev=None
 for i,*_ in ev:
  if prev is None or i-prev>max(1,rearm):clusters+=1
  prev=i
 dates=sorted({e[1] for e in ev});stats={};sensitivity={}
 gaps=int(np.count_nonzero(seg[1:]!=seg[:-1]))
 for h in hs:
  k=str(h);valid=[e for e in ev if e[3][k] is not None]
  vals=[e[3][k] for e in valid];pos=[e[3][k] for e in valid if e[2]>0];neg=[e[3][k] for e in valid if e[2]<0]
  grouped=defaultdict(list)
  for e in valid:grouped[e[1]].append(e[3][k])
  dm=[statistics.fmean(grouped[d]) for d in dates if d in grouped]
  n=len(vals);cuts=[0,n//3,2*n//3,n];chrono=[mean(vals[a:z]) for a,z in zip(cuts,cuts[1:])] if vals else []
  asum=sum(map(abs,vals));top=sorted(map(abs,vals),reverse=True)[:max(1,math.ceil(n*.1))] if vals else []
  stats[k]={'n':n,'mean_response':mean(vals),'median_response':median(vals),'uncertainty':_ci(dm),'robust_effect_estimate':median(dm),'long_mean':mean(pos),'short_mean':mean(neg),'long_short_asymmetry':None if not pos or not neg else statistics.fmean(pos)-statistics.fmean(neg),'chronological_thirds_mean':chrono,'response_concentration_top10_abs_share':None if asum<=EPS else sum(top)/asum}
  away=[e[3][k] for e in valid if e[0]>=12 and seg[e[0]-12]==seg[e[0]] and e[0]+h+12<N and seg[e[0]+h]==seg[e[0]+h+12]]
  base_mean=mean(vals);away_mean=mean(away)
  sensitivity[k]={'variant':'EXCLUDE_EVENTS_WITHIN_12_BARS_OF_GAP_OR_SERIES_EDGE','baseline_n':len(vals),'retained_n':len(away),'baseline_mean':base_mean,'boundary_excluded_mean':away_mean,'mean_delta':None if base_mean is None or away_mean is None else away_mean-base_mean,'sign_stable':None if base_mean is None or away_mean is None else (base_mean>0)==(away_mean>0)}
 return {'symbol':f.s.symbol,'symbol_id':f.s.symbol_id,'source':f.s.source,'mechanism':mech,'context':ctx,'params':p,'event_count':len(ev),'independent_event_clusters':clusters,'independent_date_clusters':len(dates),'horizons':stats,'missingness_sensitivity':{'gap_count':gaps,'bars':N,'gap_fraction':gaps/max(1,N-1),'response_sensitivity_by_horizon':sensitivity}}

def execute_one(s,spec):
 f=Features(s);hs=list(map(int,spec['response_horizons_bars']));cells=[]
 for m in spec['mechanisms']:
  for p in _grid(m.get('parameter_grid',{})):
   for ctx in m.get('contexts') or [{'kind':'ALL'}]:
    cells.append(evaluate_fast(f,m['name'],ctx,p,hs,int(m.get('rearm_bars',1))))
 _neighbors(cells,int(spec['primary_horizon_bars']))
 return cells
