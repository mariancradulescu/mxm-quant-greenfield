from __future__ import annotations
import math,statistics
from typing import Any
from .model import Bar
EPS=1e-12

def mean(x):return statistics.fmean(x) if x else None
def median(x):return statistics.median(x) if x else None
def quantile(xs,q):
    if not xs:return None
    s=sorted(xs); x=(len(s)-1)*q; lo=int(math.floor(x)); hi=int(math.ceil(x))
    return s[lo] if lo==hi else s[lo]*(hi-x)+s[hi]*(x-lo)
def roll_mean(x,i,n):return statistics.fmean(x[i-n+1:i+1]) if n>0 and i+1>=n else None
def roll_std(x,i,n):return statistics.pstdev(x[i-n+1:i+1]) if n>1 and i+1>=n else None
def ret(c,i,n):return None if i<n or c[i-n]==0 else c[i]/c[i-n]-1.0

def context_ok(ctx,bars,c,i):
    if not ctx or ctx.get('kind','ALL')=='ALL':return True
    k=ctx.get('kind')
    if k=='UTC_HOUR':return bars[i].ts.hour in set(ctx.get('hours',[]))
    if k=='DAY_OF_WEEK':return bars[i].ts.weekday() in set(ctx.get('days',[]))
    if k=='VOLATILITY_QUANTILE':
        n=int(ctx.get('lookback',48)); start=max(n,i-int(ctx.get('reference_bars',1000))); hist=[]
        for j in range(start,i+1):
            r=ret(c,j,1)
            if r is not None:hist.append(abs(r))
        if len(hist)<max(20,n):return False
        cur=statistics.fmean(hist[-n:]); lo=quantile(hist[:-1],float(ctx.get('q_low',0))); hi=quantile(hist[:-1],float(ctx.get('q_high',1)))
        return lo is not None and hi is not None and lo<=cur<=hi
    return False

def signal(mech,p,bars,c,i):
    if mech=='MEAN_REVERSION':
        n=int(p['lookback']); m=roll_mean(c,i,n); sd=roll_std(c,i,n)
        if m is None or sd is None or sd<=EPS:return 0
        z=(c[i]-m)/sd; t=float(p['z']); return -1 if z>=t else 1 if z<=-t else 0
    if mech=='TREND_MOMENTUM':
        r=ret(c,i,int(p['lookback'])); t=float(p.get('threshold',0)); return 0 if r is None else 1 if r>=t else -1 if r<=-t else 0
    if mech=='BREAKOUT_VOLATILITY_EXPANSION':
        n=int(p['lookback']); ratio=float(p.get('range_ratio',1.5))
        if i<n:return 0
        prior=bars[i-n:i]; hi=max(x.high for x in prior); lo=min(x.low for x in prior); base=statistics.median(max(EPS,x.high-x.low) for x in prior)
        if bars[i].high-bars[i].low<ratio*base:return 0
        return 1 if bars[i].close>hi else -1 if bars[i].close<lo else 0
    if mech=='VOLATILITY_STATE':
        n=int(p['lookback']); refn=int(p.get('reference',max(5*n,100))); state=str(p.get('state','HIGH')); q=float(p.get('quantile',.8))
        if i<refn+1:return 0
        rv=[]
        for j in range(i-refn+1,i+1):
            vals=[abs(r) for k in range(max(1,j-n+1),j+1) if (r:=ret(c,k,1)) is not None]
            if vals:rv.append(statistics.fmean(vals))
        cut=quantile(rv[:-1],q if state=='HIGH' else 1-q)
        if cut is None:return 0
        cur=rv[-1]; active=cur>=cut if state=='HIGH' else cur<=cut
        if not active:return 0
        r=ret(c,i,1); return 1 if (r or 0)>=0 else -1
    if mech=='SESSION_TIME_SEASONALITY':return int(p.get('direction',1)) if bars[i].ts.hour in set(map(int,p.get('hours',[]))) else 0
    if mech=='REGIME_CONTEXT_CONDITIONED':
        v=p.get('variant',p)
        if not isinstance(v,dict):return 0
        return signal(str(v.get('base','TREND_MOMENTUM')),dict(v.get('base_params',{'lookback':24,'threshold':0})),bars,c,i)
    return 0
