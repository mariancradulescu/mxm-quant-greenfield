"""Offline arrays/bisect quote-headroom reference; not a portfolio or net result."""
import hashlib,json,subprocess,tempfile,os
from bisect import bisect_left
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from .common import need
from .usd_pair_alignment import reference as alignment
ROOT=Path(__file__).resolve().parents[2]
PROJECT='research_core_v4/laboratory/csharp/spread_reversion/MxmSpreadReversion.csproj'

def source_rows(path):
    trace=[]
    with tempfile.TemporaryDirectory() as d:
        empty=Path(d)/'empty.ndjson';empty.write_bytes(b'');source=alignment(empty,path,trace)
    rows=[]
    for line in trace:
        stamp,_,book,_,_=line.split('|');v=[None if x=='-' else int(x) for x in book.split(',')]
        rows.append((int(stamp),v[0],v[3],v[1],v[4]))
    return source,rows

def valid(r,positive=True):
    t,b,a,bt,at=r
    return b is not None and a is not None and b>0 and (a>b if positive else a>=b) and bt is not None and at is not None and bt<=t and at<=t and t-bt<=5000 and t-at<=5000

def reference(rows):
    candidates=[]
    for index,r in enumerate(rows):
        if index==0:continue
        p=rows[index-1];t,b,a,bt,at=r
        if not valid(r) or not valid(p) or t-p[0]>1000 or datetime.fromtimestamp(t/1000,timezone.utc).weekday()>=5:continue
        spread=p[2]-p[1];sign=0
        if bt==t and at!=t and p[1]-b>=spread:sign=1
        elif at==t and bt!=t and a-p[2]>=spread:sign=-1
        if sign:candidates.append((index,sign))
    episodes=[];unresolved=[];decisions={};blocked=-1
    for index,sign in candidates:
        decision=rows[index][0]
        if decision<blocked:continue
        blocked=decision+3000;decisions[decision]=sign;entry=None;unmarked=0;max_gap=0;done=False
        for j in range(index+1,len(rows)):
            r=rows[j];t,b,a,_,_=r
            if entry is None:
                reason='ENTRY_TIMEOUT' if t>decision+1000 else 'ENTRY_UNAVAILABLE' if not valid(r) else None
                if reason:
                    unresolved.append(dict(Decision=decision,Direction=sign,Entry=None,ObservedThrough=t,Reason=reason,UnmarkedGroups=0));done=True;break
                if t>=decision+250:entry=r
            else:
                if t>entry[0]+1500:
                    unresolved.append(dict(Decision=decision,Direction=sign,Entry=entry[0],ObservedThrough=t,Reason='EXIT_TIMEOUT',UnmarkedGroups=unmarked));done=True;break
                max_gap=max(max_gap,t-rows[j-1][0]);unmarked+=int(not valid(r,False))
                if valid(r) and t>=entry[0]+1000:
                    ep=D(entry[2] if sign>0 else entry[1])/100000;xp=D(b if sign>0 else a)/100000
                    episodes.append(dict(Decision=decision,Entry=entry[0],Exit=t,Direction=sign,EntryPrice=ep,ExitPrice=xp,GrossUsd=sign*(xp-ep)*1000,UnmarkedGroups=unmarked,MaximumGroupGapMs=max_gap));done=True;break
        if not done:
            unresolved.append(dict(Decision=decision,Direction=sign,Entry=None if entry is None else entry[0],ObservedThrough=rows[-1][0],Reason='TERMINAL_UNSETTLED',UnmarkedGroups=unmarked))
    h=hashlib.sha256()
    for r in rows:h.update(f'{r[0]},{decisions.get(r[0],0)}\n'.encode())
    return dict(Signals=len(decisions),Complete=len(episodes),Censored=len(unresolved),DecisionSha256=h.hexdigest(),Episodes=episodes,Unresolved=unresolved)

def reconcile(actual,expected):
    need(actual==expected,'SPREAD_ALL_DECISIONS_EPISODES_CENSORS_RECONCILED')

def decide(result):
    episodes=result['Episodes'];n=len(episodes);c=result['Censored'];gross=sum((e['GrossUsd'] for e in episodes),D(0))
    days={i:D(0) for i in range(7,12)};day_counts={i:0 for i in days}
    for e in episodes:
        day=datetime.fromtimestamp(e['Decision']/1000,timezone.utc).day
        if day in days:days[day]+=e['GrossUsd'];day_counts[day]+=1
    path_unknown=sum(e['UnmarkedGroups']>0 or e['MaximumGroupGapMs']>5000 for e in episodes)
    gates=dict(at_least_100_complete=n>=100,censor_at_most_5pct=n+c>0 and D(c)/D(n+c)<=D('.05'),
      all_complete_paths_observed=path_unknown==0,gross_spread_only_headroom_positive=gross>0,
      all_five_days_gross_positive=all(days[d]>0 and day_counts[d]>0 for d in days))
    disposition=('DATA_LIMITED' if not gates['censor_at_most_5pct'] or not gates['all_complete_paths_observed'] else
      'SUPPORT_FAIL' if not gates['at_least_100_complete'] else 'GROSS_FAIL' if not gates['gross_spread_only_headroom_positive'] else
      'TEMPORAL_FAIL' if not gates['all_five_days_gross_positive'] else 'CONDITIONAL_GROSS_HEADROOM_COSTS_UNRESOLVED')
    metrics=dict(complete=n,censored=c,unresolved_paths=path_unknown,gross_spread_only_usd=str(gross),
      gross_component_per_complete_usd=str(gross/n) if n else None,days={str(d):dict(complete=day_counts[d],gross_usd=str(days[d])) for d in days})
    return disposition,gates,metrics

def run(rows):
    with tempfile.TemporaryDirectory() as d:
        a=Path(d)/'input.ndjson';b=Path(d)/'output.json';a.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',str(a),str(b)],capture_output=True,check=True)
        result=json.loads(b.read_bytes(),parse_float=D);source,groups=source_rows(a)
        need(result['source']==source,'SPREAD_EVERY_SOURCE_GROUP_HASH');reconcile(result['result'],reference(groups));return result
