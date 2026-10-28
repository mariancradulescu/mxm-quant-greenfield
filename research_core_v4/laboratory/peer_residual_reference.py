"""Full-array, leave-one-out reference. Original bars are indicative, never fills."""
from fractions import Fraction
from datetime import datetime,timezone
from collections import defaultdict
import hashlib,json
FIRST=1787184000 # validated below from UTC literal
sec=lambda t:int(datetime.fromisoformat(t.replace('Z','+00:00')).timestamp())
FIRST=sec('2026-08-20T00:00:00Z');EVAL=sec('2026-08-27T00:00:00Z');END=sec('2026-09-17T00:00:00Z')
def move(a,b):
 q=(Fraction(str(b))/Fraction(str(a))-1)*10**12
 n,d=abs(q.numerator),q.denominator;units=n//d+(2*(n%d)>=d)
 return -units if q<0 else units

def reference(packets):
 opens={};by_time=defaultdict(list);rows_count=0;seen=set()
 for p in packets:
  ordinal=p['ordinal'];assert 1<=ordinal<=1576 and ordinal not in seen;seen.add(ordinal)
  rows={};last=-1
  for r in p['rows']:
   t=sec(r['time_utc']);assert r['time_utc'].endswith('Z') and FIRST<=t<END and t%300==0 and t>last
   o,h,l,c=[Fraction(str(r[k])) for k in ('open','high','low','close')]
   assert 0<l<=o<=h and l<=c<=h;rows[t]=r;last=t;rows_count+=1
  opens[ordinal]={t:r['open'] for t,r in rows.items()}
  for d in sorted(t+300 for t in rows if (t+300)%3600==0 and t+300<END):
   if all(d-300*k in rows for k in range(1,13)):
    by_time[d].append((ordinal,p['group'],p['eligible'],move(rows[d-3600]['open'],rows[d-300]['close'])))
 signature=''.join(f'{t},{o},{g},{int(e)},{q}\n' for t,fs in sorted(by_time.items()) for o,g,e,q in sorted(fs))
 ledger=[]
 for d in range(EVAL,END,3600):
  groups=defaultdict(list)
  for f in by_time[d]:groups[f[1]].append(f)
  candidates=[]
  for fs in groups.values():
   if len(fs)<11:continue
   for ordinal,group,eligible,value in fs:
    if not eligible:continue
    peers=sorted(f[3] for f in fs if f[0]!=ordinal);median2=peers[(len(peers)-1)//2]+peers[len(peers)//2]
    residual=2*value-median2;candidates.append((abs(residual),ordinal,group,residual))
  best=sorted(candidates,key=lambda x:(-x[0],x[1]))[0] if candidates else None
  item=dict(T=d,N=len(candidates),Ordinal=None,Group=None,Direction=None,Residual2=None,Entry=None,Exit=None,Status='NO_SIGNAL',GrossUnits=None)
  if best and best[0]>=4000000000:
   _,ordinal,group,residual=best;direction=-1 if residual>0 else 1;entry,exit=d+300,d+3300
   complete=all(t in opens[ordinal] for t in range(entry,exit+1,300))
   item.update(Ordinal=ordinal,Group=group,Direction=direction,Residual2=residual,Entry=entry,Exit=exit,Status='COMPLETE' if complete else 'CENSORED',GrossUnits=direction*move(opens[ordinal][entry],opens[ordinal][exit]) if complete else None)
  ledger.append(item)
 return dict(Packets=len(seen),Rows=rows_count,FeatureSha256=hashlib.sha256(signature.encode()).hexdigest(),Ledger=ledger)

def verdict(result):
 completed=[r for r in result['Ledger'] if r['Status']=='COMPLETE'];censored=[r for r in result['Ledger'] if r['Status']=='CENSORED'];n=len(completed);gross=sum(r['GrossUnits'] for r in completed)
 block=lambda t:2 if t<sec('2026-09-03T00:00:00Z') else 3 if t<sec('2026-09-10T00:00:00Z') else 4
 blocks={k:[r for r in completed if block(r['Entry'])==k] for k in (2,3,4)};contributions=defaultdict(int)
 for r in completed:contributions[r['Ordinal']]+=r['GrossUnits']
 absolute=sorted((abs(v) for v in contributions.values()),reverse=True)
 gates={'at_least_100_complete':n>=100,'censor_fraction_at_most_5pct':n+len(censored)>0 and len(censored)*100<=5*(n+len(censored)),
 'gross_positive':gross>0,'mean_above_reference_5bps':gross>n*500000000,
 'all_three_source_blocks_above_5bps':all(v and sum(r['GrossUnits'] for r in v)>len(v)*500000000 for v in blocks.values()),
 'top5_absolute_symbol_contribution_at_most_50pct':bool(sum(absolute)) and sum(absolute[:5])*2<=sum(absolute)}
 label='DATA_LIMITED' if not gates['at_least_100_complete'] or not gates['censor_fraction_at_most_5pct'] else 'GROSS_NONPOSITIVE' if not gates['gross_positive'] else 'REFERENCE_FRICTION_FAIL' if not gates['mean_above_reference_5bps'] else 'REFERENCE_TEMPORAL_FAIL' if not gates['all_three_source_blocks_above_5bps'] else 'REFERENCE_CONCENTRATION_FAIL' if not gates['top5_absolute_symbol_contribution_at_most_50pct'] else 'CONDITIONAL_HEADROOM_COSTS_EXECUTION_UNRESOLVED'
 metrics={'complete':n,'censored':len(censored),'sum_gross_units':gross,'reference_remaining_units':{str(bps):gross-n*bps*10**8 for bps in (5,10,20,40)},'blocks':blocks,'symbol_contributions':dict(contributions)}
 return label,gates,metrics
