"""Causal feature counts and timestamp-only future availability. No response prices.

Future endpoint masks receive timestamp vectors only. They do NOT certify future
crossed-market/spread validity, economic response, effect or power. Prices are used
only to construct causal features at their own signal time. No response evaluator.
"""
import bisect,math,statistics
from collections import defaultdict

def endpoint_available(timestamps,t):
    i=bisect.bisect_right(timestamps,t)-1
    return i>=0 and 0<=t-timestamps[i]<=2000

def completion_mask(bid_timestamps,ask_timestamps,signal_ms,horizon_seconds):
    entry=signal_ms+1000;end=entry+horizon_seconds*1000
    return all(endpoint_available(ts,t) for ts in [bid_timestamps,ask_timestamps] for t in [entry,end])

def _side(rows):
    ts=[x[0] for x in rows];up=[];down=[];conflicts=[]
    for i,(t,p) in enumerate(rows):
        if i:
            if t<rows[i-1][0] or p<=0:raise ValueError('raw chronology/price')
            old=rows[i-1][1]
            if p>old:up.append(t)
            elif p<old:down.append(t)
            if t==rows[i-1][0] and p!=old:conflicts.append(t)
    return ts,up,down,conflicts

def count_support(bid,ask,start_ms,end_ms):
    if start_ms%1000 or end_ms-start_ms!=3600000:raise ValueError('one-hour integer grid')
    sides=[_side([r for r in rows if r[0]<end_ms]) for rows in [bid,ask]];timestamps=[[r[0] for r in rows] for rows in [bid,ask]]
    # Causal snapshot accessor is NEVER called for an entry/response endpoint.
    def state(t):
        vals=[]
        for rows,ts in [(bid,timestamps[0]),(ask,timestamps[1])]:
            i=bisect.bisect_right(ts,t)-1
            if i<0 or t-ts[i]>2000:return None
            vals.append(rows[i][1])
        b,a=vals
        if not a>=b>0:return None
        return ((a+b)/2,math.log(a/b)*10000)
    snaps={t:state(t) for t in range(start_ms-60000,end_ms,1000)}
    baselines=0;fresh=0;ambiguous=0;signals={};attempt_bits={}
    for lookback in [10,30]:
        for imbalance in [0.6,0.8]:signals[(lookback,imbalance)]=[]
    for t in range(start_ms,end_ms,1000):
        current=snaps[t]
        if current is None:continue
        fresh+=1
        if any(bisect.bisect_right(s[3],t)>bisect.bisect_left(s[3],t-60000) for s in sides):
            ambiguous+=1;continue
        spreads=[snaps[q][1] for q in range(t-60000,t,1000) if snaps[q] is not None]
        if len(spreads)<45:continue
        baseline=statistics.median(spreads)
        if baseline<=0:continue
        baselines+=1
        if current[1]>baseline:continue
        for lookback in [10,30]:
            old=snaps.get(t-lookback*1000)
            if old is None:continue
            counts=[]
            for k in [1,2]:counts.append(sum(bisect.bisect_right(s[k],t)-bisect.bisect_right(s[k],t-lookback*1000) for s in sides))
            n=sum(counts)
            if n<6 or abs(math.log(current[0]/old[0])*10000)/baseline>0.75:continue
            abs_imb=abs(counts[0]-counts[1])/n
            for threshold in [0.6,0.8]:
                if abs_imb>=threshold:signals[(lookback,threshold)].append(t)
    cells=[]
    for lookback in [10,30]:
        for threshold in [0.6,0.8]:
            for horizon in [10,30,90]:
                attempts=[];available=[];until=-1
                for t in signals[(lookback,threshold)]:
                    if t<until:continue
                    attempts.append(t);until=t+1000+horizon*1000
                    if completion_mask(timestamps[0],timestamps[1],t,horizon):available.append(t)
                def bits(items):
                    out=0
                    for t in items:out|=1<<((t-start_ms)//1000)
                    return hex(out)
                for direction in ['CONTINUATION','REVERSION']:
                    cells.append({'cell_id':f'L{lookback}_I{threshold}_H{horizon}_{direction}',
                      'trigger_occurrences':len(signals[(lookback,threshold)]),'nonoverlap_attempts':len(attempts),
                      'timestamp_completable_attempts':len(available),'retention_fraction_timestamp_only':len(available)/len(attempts) if attempts else None,
                      'attempts_three_subwindows':[sum(start_ms+k*1200000<=t<start_ms+(k+1)*1200000 for t in attempts) for k in range(3)],
                      'timestamp_completable_three_subwindows':[sum(start_ms+k*1200000<=t<start_ms+(k+1)*1200000 for t in available) for k in range(3)],
                      'attempt_seconds_mask_hex':bits(attempts),'timestamp_completable_mask_hex':bits(available),
                      'scientific_support_gate_evaluated':False})
    return {'fresh_signal_grid_seconds':fresh,'baseline_qualified_seconds':baselines,'ambiguous_causal_seconds':ambiguous,
      'revision_counts':{'BID_UP':sum(start_ms<=t<end_ms for t in sides[0][1]),'BID_DOWN':sum(start_ms<=t<end_ms for t in sides[0][2]),'ASK_UP':sum(start_ms<=t<end_ms for t in sides[1][1]),'ASK_DOWN':sum(start_ms<=t<end_ms for t in sides[1][2])},
      'cells':cells,'endpoint_mask':'TIMESTAMP_AGES_ONLY_NOT_FUTURE_PRICE_VALIDITY','response_values_read':False,
      'economic_statistics_computed':False,'ten_week_probe_cannot_certify_40_week_or_18_date_gates':True}
