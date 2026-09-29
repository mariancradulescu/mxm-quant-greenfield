from __future__ import annotations
import hashlib,json,math,statistics
from typing import Any
from .model import Bar,Series,discover_series
from .signals import EPS,context_ok,mean,median,signal

def _seg(bars,maxgap=450):
    out=[0] if bars else []; n=0
    for a,b in zip(bars,bars[1:]):
        if (b.ts-a.ts).total_seconds()>maxgap:n+=1
        out.append(n)
    return out
def _ci(x):
    if not x:return {'low':None,'high':None,'se':None}
    if len(x)<2:return {'low':x[0],'high':x[0],'se':None}
    m=statistics.fmean(x); se=statistics.stdev(x)/math.sqrt(len(x)); return {'low':m-1.96*se,'high':m+1.96*se,'se':se}
def evaluate_cell(s:Series,mech:str,ctx:dict[str,Any],p:dict[str,Any],hs:list[int],rearm=1):
    b=s.bars; c=[x.close for x in b]; seg=_seg(b); ev=[]; last=-10**12; mh=max(hs)
    for i in range(len(b)):
        if i-last<rearm or not context_ok(ctx,b,c,i):continue
        sig=signal(mech,p,b,c,i)
        if not sig or i+mh>=len(b) or seg[i]!=seg[i+mh]:continue
        rr={}
        for h in hs: rr[str(h)]=None if seg[i]!=seg[i+h] or c[i]==0 else sig*(c[i+h]/c[i]-1)
        if any(v is not None for v in rr.values()): ev.append((i,b[i].ts.date().isoformat(),sig,rr)); last=i
    clusters=0; prev=None
    for i,*_ in ev:
        if prev is None or i-prev>max(1,rearm):clusters+=1
        prev=i
    dates=sorted({e[1] for e in ev}); stats={}
    for h in hs:
        k=str(h); vals=[e[3][k] for e in ev if e[3][k] is not None]; pos=[e[3][k] for e in ev if e[2]>0 and e[3][k] is not None]; neg=[e[3][k] for e in ev if e[2]<0 and e[3][k] is not None]
        dm=[statistics.fmean([e[3][k] for e in ev if e[1]==d and e[3][k] is not None]) for d in dates if any(e[1]==d and e[3][k] is not None for e in ev)]
        n=len(vals); cuts=[0,n//3,2*n//3,n]; chrono=[mean(vals[a:z]) for a,z in zip(cuts,cuts[1:])] if vals else []
        asum=sum(map(abs,vals)); top=sorted(map(abs,vals),reverse=True)[:max(1,math.ceil(n*.1))] if vals else []
        stats[k]={'n':n,'mean_response':mean(vals),'median_response':median(vals),'uncertainty':_ci(dm),'robust_effect_estimate':median(dm),'long_mean':mean(pos),'short_mean':mean(neg),'long_short_asymmetry':None if not pos or not neg else statistics.fmean(pos)-statistics.fmean(neg),'chronological_thirds_mean':chrono,'response_concentration_top10_abs_share':None if asum<=EPS else sum(top)/asum}
    gaps=sum(seg[i]!=seg[i+1] for i in range(max(0,len(b)-1)))
    # Predeclared generic boundary exclusion. Never impute a missing bar.
    sensitivity={}
    for h in hs:
        k=str(h); base=[e[3][k] for e in ev if e[3][k] is not None]
        away=[e[3][k] for e in ev if e[3][k] is not None and
              e[0]>=12 and seg[e[0]-12]==seg[e[0]] and
              e[0]+h+12<len(b) and seg[e[0]+h]==seg[e[0]+h+12]]
        base_mean=mean(base); away_mean=mean(away)
        sensitivity[k]={'variant':'EXCLUDE_EVENTS_WITHIN_12_BARS_OF_GAP_OR_SERIES_EDGE',
                        'baseline_n':len(base),'retained_n':len(away),
                        'baseline_mean':base_mean,'boundary_excluded_mean':away_mean,
                        'mean_delta':None if base_mean is None or away_mean is None else away_mean-base_mean,
                        'sign_stable':None if base_mean is None or away_mean is None else (base_mean>0)==(away_mean>0)}
    return {'symbol':s.symbol,'symbol_id':s.symbol_id,'source':s.source,'mechanism':mech,'context':ctx,'params':p,'event_count':len(ev),'independent_event_clusters':clusters,'independent_date_clusters':len(dates),'horizons':stats,'missingness_sensitivity':{'gap_count':gaps,'bars':len(b),'gap_fraction':gaps/max(1,len(b)-1),'response_sensitivity_by_horizon':sensitivity}}
def _grid(g):
    out=[{}]
    for k,vals in g.items():out=[{**x,k:v} for x in out for v in vals]
    return out
def _dist(a,b):return sum(a.get(k)!=b.get(k) for k in set(a)|set(b))
def _neighbors(cells,h):
    groups={}
    for c in cells:groups.setdefault((c['symbol'],c['mechanism'],json.dumps(c['context'],sort_keys=True)),[]).append(c)
    for g in groups.values():
        for c in g:
            m=c['horizons'].get(str(h),{}).get('robust_effect_estimate'); ns=[d['horizons'].get(str(h),{}).get('robust_effect_estimate') for d in g if d is not c and _dist(c['params'],d['params'])==1]; ns=[x for x in ns if x is not None]
            if m is None or not ns:con=None; width=0
            else:
                sg=1 if m>0 else -1 if m<0 else 0; con=sum((1 if x>0 else -1 if x<0 else 0)==sg for x in ns)/len(ns); width=sum(sg!=0 and x*sg>0 for x in ns)
            c['parameter_neighbor_consistency']=con; c['robust_plateau_width_neighbors']=width
def execute_spec(series:list[Series],spec:dict[str,Any]):
    hs=list(map(int,spec.get('response_horizons_bars',[1,3,6,12]))); cells=[]
    for m in spec['mechanisms']:
        for p in _grid(m.get('parameter_grid',{})):
            for ctx in m.get('contexts') or [{'kind':'ALL'}]:
                for s in series:cells.append(evaluate_cell(s,m['name'],ctx,p,hs,int(m.get('rearm_bars',1))))
    _neighbors(cells,int(spec.get('primary_horizon_bars',hs[0])))
    x={'schema':'mxm.research-core-v3.development-response-surface.v1','status':'COMPLETE_DEVELOPMENT_RESPONSE_SURFACE' if series else 'NO_REPO_RESIDENT_RAW_BARS','causal_live_equivalent_discovery':True,'protected_forward_opened':False,'final_pnl_certification':False,'report_all_cells':True,'series_count':len(series),'symbols':sorted({s.symbol for s in series}),'mechanisms':[m['name'] for m in spec['mechanisms']],'cell_count':len(cells),'cells':cells}
    x['content_sha256']=hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest(); return x
