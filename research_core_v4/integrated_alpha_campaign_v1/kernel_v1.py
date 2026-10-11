"""Three frozen information mechanisms; source extraction and outcomes separated."""
import math,statistics
from datetime import datetime,timezone
from collections import Counter,defaultdict
import numpy as np
PREFIX=int(datetime(2025,9,16,tzinfo=timezone.utc).timestamp())
START=int(datetime(2025,10,20,tzinfo=timezone.utc).timestamp())
END=int(datetime(2026,9,17,tzinfo=timezone.utc).timestamp())
ORIGINAL=int(datetime(2026,8,20,tzinfo=timezone.utc).timestamp())
H=14400;NAMES=('MATCHED_PEER_PARTICIPATION','SIGNED_CUBIC_REGIME','MATCHED_ACTIVITY_LOW_IMPACT')
G10={'EUR','USD','GBP','JPY','CHF','AUD','NZD','CAD'}
def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
def sign(x):return int(x>0)-int(x<0)
def grid(start=START,end=END):
    # Four-hour holding interval; anchor preserves existing 09:15/13:15 references.
    t=((start-4500+H-1)//H)*H+4500
    return range(t,end,H)
def complete_weeks():
    return sorted({iso(t) for t in range(START,END,86400) if t+7*86400<=END and datetime.fromtimestamp(t,timezone.utc).weekday()==0})
def block(t):return (t-ORIGINAL)//604800 if ORIGINAL<=t<END else None
def segment(bars,t,n):
    z=[bars.get(t-300-n*300+i*300) for i in range(n)]
    return z if all(x is not None for x in z) else None
def feature(bars,t):
    pp=segment(bars,t,48)
    if pp is None:return None
    last=pp[-12:];prev=pp[:36]
    r=[math.log(x[3]/x[0]) for x in last];q=sum(x*x for x in r)
    a={'body':math.log(last[-1][3]/last[0][0]),'prior3':math.log(prev[-1][3]/prev[0][0]),'body4':math.log(pp[-1][3]/pp[0][0]),'cubic':sum(x*x*x for x in r)/q**1.5 if q>0 else 0.,'volume':sum(x[4] for x in last),'range':max(x[1] for x in pp)-min(x[2] for x in pp),'price':last[-1][3],'weekly':None}
    weeks=[segment(bars,t-w*604800,12) for w in range(1,5)]
    if all(z is not None for z in weeks):a['weekly']=[[math.log(z[-1][3]/z[0][0]),sum(x[4] for x in z)] for z in weeks]
    return a
def label(bars,t):
    if t+H>END:return None
    z=[bars.get(t+i*300) for i in range(48)]
    return 10000*math.log(z[-1][3]/z[0][0]) if all(x is not None for x in z) else None
def extract(bars):return [[t,feature(bars,t),label(bars,t)] for t in grid()]
def surprise(f):
    return bool(f and f['weekly'] is not None and f['volume']>=2*statistics.median(x[1] for x in f['weekly']) and statistics.median(x[1] for x in f['weekly'])>0)
def peer_direction(target,t,features,pairs):
    if target not in pairs:return 0,'NO_G10_CURRENCY_PAIR'
    A,B=pairs[target];scores=[]
    for currency in (A,B):
        roster={}
        for sid,(a,b) in pairs.items():
            if sid==target or currency not in (a,b):continue
            other=b if a==currency else a
            if other in (A,B):continue
            roster.setdefault(other,[]).append((sid,1 if a==currency else -1))
        known=[];active=[]
        for other,rr in roster.items():
            vals=[(f,orient) for sid,orient in rr if (f:=features.get((sid,t))) is not None and f['weekly'] is not None]
            if vals:known.append(other)
            vv=[orient*sign(f['body']) for f,orient in vals if surprise(f) and f['body']!=0]
            if vv:active.append(sum(vv)/len(vv))
        if len(known)<max(2,math.ceil(len(roster)/2)):return 0,'PEER_SYNCHRONIZED_SUPPORT'
        if len(active)<2:return 0,'PEER_ACTIVITY_QUORUM'
        scores.append(sum(active)/len(active))
    a,b=scores
    return (1,'SIGNAL') if a>=2/3 and b<=-2/3 else (-1,'SIGNAL') if a<=-2/3 and b>=2/3 else (0,'NO_OPPOSING_CURRENCY_CONSENSUS')
def decisions(sid,t,f,features,pairs):
    if f is None:return [(0,'FEATURE_GAP')]*3
    a=peer_direction(sid,t,features,pairs)
    b=(sign(f['cubic']),'SIGNAL') if f['cubic']*f['prior3']>0 else (0,'CUBIC_REGIME_DISAGREEMENT')
    if f['weekly'] is None:c=(0,'FOUR_WEEK_MATCH_GAP')
    elif not surprise(f):c=(0,'NO_MATCHED_ACTIVITY_SHOCK')
    else:
        impact=abs(f['body'])/(1+f['volume']);prior=statistics.median(abs(r)/(1+v) for r,v in f['weekly'])
        c=(sign(f['prior3']),'SIGNAL') if impact<=prior and f['prior3'] else (0,'NO_LOW_IMPACT_ABSORPTION')
    return [a,b,c]
def events(records,pairs,features):
    out=[]
    for sid,rr in records.items():
        for t,f,y in rr:
            bb=sign(f['body4']) if f else 0
            for name,(d,reason) in zip(NAMES,decisions(sid,t,f,features,pairs)):
                out.append({'sid':sid,'t':t,'exit':t+H,'iso':iso(t),'block':block(t),'family':name,'d':d,'b':bb,'reason':reason,'feature':f,'y':y if d and bb else None})
    return out
def stats(rr):
    v=[r for r in rr if r['d'] and r['b'] and r['y'] is not None];n=len(v)
    return {'calendar':len(rr),'moments':len({r['t'] for r in rr}),'feature_valid':sum(r['feature'] is not None for r in rr),'signals':sum(bool(r['d']) for r in rr),'signal_moments':len({r['t'] for r in rr if r['d']}),'paired':n,'censored_signals':sum(r['d']!=0 and r['y'] is None for r in rr),'model_mean_bps':sum(r['d']*r['y'] for r in v)/n if n else None,'baseline_mean_bps':sum(r['b']*r['y'] for r in v)/n if n else None,'increment_mean_bps':sum((r['d']-r['b'])*r['y'] for r in v)/n if n else None,'reasons':dict(Counter(r['reason'] for r in rr))}
def report(rr):return {'global':stats(rr),'blocks':[stats([r for r in rr if r['block']==b]) for b in range(4)],'weeks':{w:stats([r for r in rr if r['iso']==w]) for w in complete_weeks()}}
def clustered(rr):
    by=defaultdict(list)
    for r in rr:
        if r['d'] and r['b'] and r['y'] is not None:by[r['t']].append(r)
    weeks=complete_weeks();a=[];b=[];counts=[]
    for w in weeks:
        zz=[v for t,v in by.items() if iso(t)==w];counts.append(len(zz))
        a.append(statistics.mean(statistics.mean(r['d']*r['y'] for r in v) for v in zz) if zz else None)
        b.append(statistics.mean(statistics.mean(r['b']*r['y'] for r in v) for v in zz) if zz else None)
    valid=[j for j in range(len(weeks)) if a[j] is not None];model=np.array([a[j] for j in valid]);increment=np.array([a[j]-b[j] for j in valid]);lo=[None,None]
    if len(valid)>=24:
        # Preserve chronological adjacent 2-week clusters; shared resample across estimands.
        rng=np.random.default_rng(20261011);boot=[[],[]];blocks=[list(range(j,min(j+2,len(weeks)))) for j in range(len(weeks)-1)]
        for _ in range(2000):
            idx=[j for v in rng.choice(len(blocks),size=math.ceil(len(weeks)/2)) for j in blocks[int(v)]][:len(weeks)]
            ii=[j for j in idx if a[j] is not None]
            if ii:
                boot[0].append(statistics.mean(a[j] for j in ii));boot[1].append(statistics.mean(a[j]-b[j] for j in ii))
        lo=[float(np.quantile(v,.05/3)) for v in boot]
    positive=sum(a[j]>0 and a[j]>b[j] for j in valid)
    lead=len(valid)>=24 and all(x is not None and x>0 for x in lo) and positive>=math.ceil(.75*len(valid))
    return {'supported_complete_weeks':len(valid),'weekly_supported_moments':dict(zip(weeks,counts)),'weekly_equal_clock_model_bps':dict(zip(weeks,a)),'weekly_equal_clock_baseline_bps':dict(zip(weeks,b)),'model_mean_bps':float(model.mean()) if len(model) else None,'increment_mean_bps':float(increment.mean()) if len(increment) else None,'joint_positive_weeks':positive,'one_sided_family3_bootstrap_lower_bps':lo,'exploratory_gross_lead':lead,'independent_observations':'NOT_IDENTIFIED;CLOCK_CLUSTER_CROSS_ASSET;2_WEEK_RESAMPLE_IS_DESCRIPTIVE_NOT_HOLDOUT_CONFIRMATION'}
