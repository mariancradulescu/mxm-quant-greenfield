"""Offline array selection/Decimal fill reference; uses independent source bisect replay."""
from decimal import Decimal as D,localcontext
from datetime import datetime,timezone
from itertools import islice
import hashlib,json
from pathlib import Path
from .usd_pair_alignment import reference as source_reference

def session(t):
    d=datetime.fromtimestamp(t/1000,timezone.utc)
    return d.weekday()<5 and 6<=d.hour<=19 and (d.hour<19 or d.minute<=57)
def read_routes(eur,gbp):
    trace=[];source=source_reference(eur,gbp,trace)
    rows=[]
    for line in trace:
        stamp,code,gbp,fx,_=line.split('|')
        a=[None if x=='-' else int(x) for x in gbp.split(',')]
        b=[None if x=='-' else int(x) for x in fx.split(',')]
        rows.append((int(stamp),code,a[0],a[3],b[0],b[3]))
    return source,rows

def reference(rows):
    with localcontext() as ctx:
        ctx.prec=65
        first={}
        for i,r in enumerate(rows):first.setdefault(r[0]//60000,i)
        candidates=[];lines=[]
        for minute,index in first.items():
            r=rows[index];t,code,b,a,fb,fa=r;signal=0
            prev=rows[first[minute-1]] if minute-1 in first else None
            good=lambda x:x[1]=='READY_STRICT_PRIOR_FX' and x[0]%60000<=5000 and session(x[0])
            if good(r) and prev is not None and good(prev):
                fx=D(fb+fa)/D(prev[4]+prev[5])-1
                gbp=D(b+a)/D(prev[2]+prev[3])-1
                spread=D(2*(a-b))/D(a+b)
                sign=(fx>0)-(fx<0)
                if spread>0 and abs(fx)>=4*spread and sign*(fx-gbp)>=2*spread:signal=sign
            lines.append(f'{t},{signal}\n')
            if signal:candidates.append((index,signal))
        episodes=[];signals=censored=0;busy=-1;blocked=-1
        for index,sign in candidates:
            d=rows[index][0]
            if d<busy or d<=blocked:continue
            signals+=1;entered=None;done=False;unmarked=0
            for r in islice(rows,index+1,None):
                t,code,b,a,fb,fa=r
                if t>d+80000 or not session(t):
                    busy=t;blocked=max(blocked,d+80000);censored+=1;done=True;break
                if entered is None:
                    if code!='READY_STRICT_PRIOR_FX' or t>d+10000:
                        busy=t;blocked=max(blocked,d+80000);censored+=1;done=True;break
                    if t>=d+5000:entered=r
                elif t>entered[0]+65000:
                    busy=t;blocked=max(blocked,d+80000);censored+=1;done=True;break
                elif code!='READY_STRICT_PRIOR_FX':unmarked+=1
                elif t>=entered[0]+60000:
                    ep=D(entered[3] if sign>0 else entered[2])/100000
                    xp=D(b if sign>0 else a)/100000
                    gross=sign*(xp-ep)*1000;net=gross-D('.12')
                    eur=net/(D(fa if net>=0 else fb)/100000)
                    episodes.append(dict(Decision=d,Entry=entered[0],Exit=t,Direction=sign,EntryPrice=ep,
                      ExitPrice=xp,GrossUsd=gross,NetUsd=net,NetEur=eur,UnmarkedGroups=unmarked))
                    busy=t;done=True;break
            if not done:censored+=1;busy=2**63
        return {'Signals':signals,'Complete':len(episodes),'Censored':censored,
          'DecisionSha256':hashlib.sha256(''.join(lines).encode()).hexdigest(),'Episodes':episodes}

def reconcile(actual,expected):
    for k in ('Signals','Complete','Censored','DecisionSha256'):
        if actual[k]!=expected[k]:raise ValueError('LEADLAG_'+k)
    if len(actual['Episodes'])!=len(expected['Episodes']):raise ValueError('EPISODE_COUNT')
    for a,e in zip(actual['Episodes'],expected['Episodes']):
        if set(a)!=set(e):raise ValueError('EPISODE_FIELDS')
        for k,v in e.items():
            if isinstance(v,D):
                if abs(D(str(a[k]))-v)>D('1e-23'):raise ValueError('EPISODE_'+k)
            elif a[k]!=v:raise ValueError('EPISODE_'+k)

def decide(result):
    n=result['Complete'];c=result['Censored'];episodes=result['Episodes']
    gross=sum((D(str(x['GrossUsd'])) for x in episodes),D(0));net=sum((D(str(x['NetEur'])) for x in episodes),D(0))
    days={str(d):{'complete':0,'net_eur':D(0)} for d in range(7,12)}
    for e in episodes:
        day=str(datetime.fromtimestamp(e['Entry']/1000,timezone.utc).day)
        days[day]['complete']+=1;days[day]['net_eur']+=D(str(e['NetEur']))
    gates={'at_least_100_complete':n>=100,'gross_positive':gross>0,'scenario_net_positive':net>0,
      'all_five_days_positive':all(x['complete']>0 and x['net_eur']>0 for x in days.values()),
      'censor_at_most_5pct':n+c>0 and D(c)/D(n+c)<=D('.05')}
    # Never evaluate observed net as success if omitted exits exceed the preregistered bound.
    verdict=('DATA_LIMITED' if not gates['censor_at_most_5pct'] else 'SUPPORT_FAIL' if not gates['at_least_100_complete'] else
      'GROSS_FAIL' if not gates['gross_positive'] else 'SCENARIO_NET_FAIL' if not gates['scenario_net_positive'] else
      'TEMPORAL_FAIL' if not gates['all_five_days_positive'] else 'DEVELOPMENT_SURVIVOR_UNCONFIRMED')
    return verdict,{'gates':gates,'complete':n,'censored':c,'gross_usd':str(gross),'scenario_net_eur':str(net),
       'days':{k:{'complete':v['complete'],'net_eur':str(v['net_eur'])} for k,v in days.items()}}
