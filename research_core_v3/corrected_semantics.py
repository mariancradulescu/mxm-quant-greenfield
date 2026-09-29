"""Outcome-informed DEVELOPMENT corrections; no execution or confirmation claim.

The historical common max-horizon event cohort is retained for comparability.
Strict variants are subsets of that rearmed cohort, never newly rearmed events.
"""
from __future__ import annotations
import json, math
import numpy as np
from .fast_engine import Features
from .engine import _grid

VARIANTS=('ORIGINAL_CLOSE_TO_CLOSE','CORRECTED_LIKE_FOR_LIKE_NEXT_OPEN','STRICT_FULL_DEPENDENCY_CONTINUOUS_CLOSE_TO_CLOSE','CORRECTED_NEXT_OPEN_PLUS_STRICT_FULL_DEPENDENCY_CONTINUITY')

def mechanism_start(mechanism,p,i):
    if mechanism=='MEAN_REVERSION': return i-int(p['lookback'])+1
    if mechanism in ('TREND_MOMENTUM','BREAKOUT_VOLATILITY_EXPANSION'): return i-int(p['lookback'])
    if mechanism=='VOLATILITY_STATE':
        n=int(p['lookback']); ref=int(p.get('reference',max(5*n,100)))
        return max(0,i-ref-n+1)
    if mechanism=='SESSION_TIME_SEASONALITY': return i
    if mechanism=='REGIME_CONTEXT_CONDITIONED':
        v=p.get('variant',p)
        return mechanism_start(v.get('base','TREND_MOMENTUM'),v.get('base_params',{'lookback':24,'threshold':0}),i)
    raise ValueError('unknown mechanism')

def dependency_start(mechanism,p,ctx,i):
    start=mechanism_start(mechanism,p,i)
    kind=ctx.get('kind','ALL')
    if kind=='VOLATILITY_QUANTILE':
        # Actual scalar and vector paths both consume abs returns, each needing
        # its preceding close. Early partial references retain their exact start.
        n=int(ctx.get('lookback',48)); ref=int(ctx.get('reference_bars',1000))
        start=min(start,max(n,i-ref)-1)
    elif kind not in ('ALL','UTC_HOUR','DAY_OF_WEEK'): raise ValueError('unknown context')
    return start

def response(close,opens,i,h,direction,next_open=False):
    if h<1 or i+h>=len(close): raise ValueError('invalid horizon')
    entry=opens[i+1] if next_open else close[i]
    return direction*(close[i+h]/entry-1)

def exact_segments(bars):
    return np.r_[0,np.cumsum([(b.ts-a.ts).total_seconds()!=300 for a,b in zip(bars,bars[1:])])].astype(np.int32) if bars else np.array([],dtype=np.int32)

def nullable_mean(x): return float(np.mean(x)) if len(x) else None

def statistics_for(indices,values,directions,f,h):
    n=len(values)
    dates=np.array([f.b[int(i)].ts.date().isoformat() for i in indices])
    unique=np.unique(dates)
    dm=np.array([np.mean(values[dates==d]) for d in unique])
    week_groups={}
    for i,v in zip(indices,values):
        iso=f.b[int(i)].ts.isocalendar(); key=f'{iso.year}-W{iso.week:02d}'
        week_groups.setdefault(key,[]).append(float(v))
    wm={k:float(np.mean(v)) for k,v in sorted(week_groups.items())}
    w=np.array(list(wm.values()))
    se=float(np.std(w,ddof=1)/math.sqrt(len(w))) if len(w)>1 else None
    ci={'method':'UTC_ISO_WEEK_CLUSTER_NORMAL_APPROXIMATION_DEVELOPMENT','low':None,'high':None,'se':se}
    if se is not None: ci.update(low=float(w.mean()-1.96*se),high=float(w.mean()+1.96*se))
    thirds=[]
    if n:
        # Equal elapsed-time thirds, not event-count thirds.
        first=f.b[0].ts.timestamp(); duration=f.b[-1].ts.timestamp()-first
        bins=np.minimum(2,np.array([int(3*(f.b[int(i)].ts.timestamp()-first)/max(1,duration)) for i in indices]))
        thirds=[nullable_mean(values[bins==k]) for k in range(3)]
    absolute=np.abs(values); total=float(absolute.sum()); count=max(1,math.ceil(n*.1))
    concentration=float(np.partition(absolute,n-count)[-count:].sum()/total) if n and total else None
    clusters=0; end=-1
    for i in indices:
        if i>end: clusters+=1
        end=max(end,int(i)+h)
    long=nullable_mean(values[directions>0]); short=nullable_mean(values[directions<0])
    return {'n':n,'independent_event_clusters':clusters,'independent_date_clusters':len(unique),'date_support_is_not_independence_proof':True,'independent_week_clusters':len(w),'mean_response':nullable_mean(values),'median_response':float(np.median(values)) if n else None,'robust_effect_estimate':float(np.median(dm)) if n else None,'uncertainty':ci,'chronological_thirds':thirds,'response_concentration_top10_abs_share':concentration,'long_mean':long,'short_mean':short,'long_short_asymmetry':None if long is None or short is None else long-short,'week_cluster_means':wm}

def evaluate_corrected(f,mechanism,p,ctx,hs,rearm):
    sig=f.signals(mechanism,p); candidates=np.flatnonzero((sig!=0)&f.context(ctx)); seg=exact_segments(f.b); mh=max(hs)
    indices=[];last=-10**12;forward_removed=0
    for raw in candidates:
        i=int(raw)
        if i+mh>=f.n or seg[i]!=seg[i+mh]: forward_removed+=1;continue
        if i-last<rearm: continue
        indices.append(i);last=i
    indices=np.array(indices,dtype=int)
    starts=np.array([dependency_start(mechanism,p,ctx,int(i)) for i in indices],dtype=int)
    strict=(starts>=0)&(seg[np.maximum(starts,0)]==seg[indices])
    opens=np.array([b.open for b in f.b]);results={}
    for v in VARIANTS:
        ids=indices[strict] if 'STRICT' in v else indices
        horizons={}
        for h in hs:
            entry=opens[ids+1] if v in (VARIANTS[1],VARIANTS[3]) else f.c[ids]
            vals=sig[ids]*(f.c[ids+h]/entry-1)
            horizons[str(h)]=statistics_for(ids,vals,sig[ids],f,h)
        results[v]={'event_count':len(ids),'horizons':horizons}
    deltas={}
    for h in hs:
        means=[results[v]['horizons'][str(h)]['mean_response'] for v in VARIANTS]
        delta=lambda a,b:None if a is None or b is None else a-b
        deltas[str(h)]={'timing_effect_delta':delta(means[1],means[0]),'continuity_effect_delta':delta(means[3],means[1]),'sign_stability':None if any(x is None for x in means) else len({x>0 for x in means})==1}
    return {'symbol':f.s.symbol,'symbol_id':f.s.symbol_id,'mechanism':mechanism,'params':p,'context':ctx,'original_event_count':len(indices),'strict_dependency_event_count':int(strict.sum()),'event_retention_fraction':float(strict.mean()) if len(strict) else None,'events_removed_for_backward_dependency_gap':int((~strict).sum()),'events_removed_for_forward_gap':forward_removed,'forward_removal_count_is_pre_rearm':True,'common_forward_cohort_horizon':mh,'dependency_start_min':int(starts.min()) if len(starts) else None,'variants':results,'effects':deltas}

def adjacent(a,b,grid):
    diffs=[k for k in grid if a.get(k)!=b.get(k)]
    if len(diffs)!=1: return False
    k=diffs[0]; axis=grid[k]
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in axis): return False
    axis=sorted(axis)
    return abs(axis.index(a[k])-axis.index(b[k]))==1

def execute_corrected(series,spec):
    f=Features(series);cells=[]
    for m in spec['mechanisms']:
        for p in _grid(m['parameter_grid']):
            for ctx in m.get('contexts') or [{'kind':'ALL'}]:
                cells.append(evaluate_corrected(f,m['name'],p,ctx,spec['response_horizons_bars'],m.get('rearm_bars',1)))
    h=str(spec['primary_horizon_bars'])
    for c in cells:
        grid=next(m['parameter_grid'] for m in spec['mechanisms'] if m['name']==c['mechanism'])
        neighbors=[d for d in cells if d['mechanism']==c['mechanism'] and d['context']==c['context'] and adjacent(c['params'],d['params'],grid)]
        effects=[d['variants'][VARIANTS[3]]['horizons'][h]['robust_effect_estimate'] for d in neighbors]
        valid=[x for x in effects if x is not None]
        c['parameter_neighbor_consistency']=sum(x>0 for x in valid)/len(valid) if valid else None
        c['positive_adjacent_neighbors']=sum(x>0 for x in valid)
        c['numeric_neighbor_count']=len(neighbors)
    return cells
