"""Time membership only. Never reads prices, selects trades, ranks assets or tests returns."""
PROFILES=(1,12,288)
SLOTS=8064

def reference(packets):
 out=[];ids=set();rows=0
 for p in packets:
  if set(p)!={'ordinal','slots'} or type(p['ordinal']) is not int or not 1<=p['ordinal']<=1576 or p['ordinal'] in ids:raise ValueError('TIME_ONLY_IDENTITY')
  stamps=p['slots']
  if not isinstance(stamps,list) or any(type(x) is not int or not 0<=x<SLOTS for x in stamps) or stamps!=sorted(set(stamps)):raise ValueError('STRICT_TIME_LATTICE')
  ids.add(p['ordinal']);rows+=len(stamps);present=set(stamps)
  # Independent run-interval construction rather than the C# prefix algorithm.
  runs=[]
  for t in stamps:
   if runs and runs[-1][1]+1==t:runs[-1]=(runs[-1][0],t)
   else:runs.append((t,t))
  for block in range(4):
   lo=block*2016;hi=lo+2016
   count=sum(lo<=t<hi for t in stamps)
   longest=max((min(b,hi-1)-max(a,lo)+1 for a,b in runs if a<hi and b>=lo),default=0)
   for h in PROFILES:
    decisions=[d for a,b in runs for d in range(max(lo,a+h),min(hi,b+2))]
    inside=[d for d in decisions if d+1+h<SLOTS]
    future={d for a,b in runs for d in range(a-1,b-h)}
    interior={d for a,b in runs for d in range(a-2,b-h+1)} if h>1 else set()
    complete=sum(d in future for d in inside)
    out.append(dict(Ordinal=p['ordinal'],Block=block+1,Bars=count,LongestRun=longest,Lookback=h,Hold=h,
      CausalDecisions=len(decisions),OutsideArchive=len(decisions)-len(inside),InArchive=len(inside),Complete=complete,
      MissingEntry=sum(d+1 not in present for d in inside),MissingExit=sum(d+1+h not in present for d in inside),
      MissingInterior=sum(h>1 and d not in interior for d in inside)))
 return dict(Packets=len(ids),Rows=rows,Cells=out)

def summarize(actual):
 cells=actual['Cells'];profiles=[]
 for h in PROFILES:
  blocks=[]
  for b in range(1,5):
   xs=[x for x in cells if x['Block']==b and x['Hold']==h]
   n=sum(x['InArchive'] for x in xs);k=sum(x['Complete'] for x in xs)
   blocks.append(dict(block=b,in_archive_causal_decisions=n,complete=k,missing=n-k,
    outside_archive=sum(x['OutsideArchive'] for x in xs),
    at_most_5pct_missing_for_this_unselected_grid=n>0 and 100*(n-k)<=5*n))
  profiles.append(dict(lookback=h,hold=h,blocks=blocks))
 return dict(profiles=profiles,disposition='OBSERVATION_SUPPORT_ONLY_NO_STRATEGY_QUALIFICATION',
  support_does_not_identify_signal_conditioned_censoring=True,return_stability_not_measured=True,
  prices_or_costs_or_fills_not_examined=True,new_strategy_identities=0)
