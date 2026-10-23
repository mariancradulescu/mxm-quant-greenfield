"""Independent array-index/Decimal reference of the precommitted gross-only hypothesis.
No broker fills, portfolio capital, parameter selection or protected observations.
"""
from decimal import Decimal as D
from datetime import datetime,timezone
import hashlib
START='2026-08-20T00:00:00Z';END='2026-09-17T00:00:00Z'
def need(ok,reason):
    if not ok:raise ValueError('MXM_COMPRESSION_REFERENCE_'+reason)
def reference(rows,trace=False):
    clocks=[];values=[];signals=[];ranges=[];start=0
    for i,row in enumerate(rows):
        stamp=row['time_utc'];need(START<=stamp<END and stamp.endswith('Z'),'TIME_FENCE')
        now=int(datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp())
        need(now%300==0 and (not clocks or now>clocks[-1]),'M5_CHRONOLOGY')
        op,hi,lo,cl=(D(str(row[k])) for k in ('open','high','low','close'))
        need(all(v.is_finite() and v>0 for v in (op,hi,lo,cl)) and lo<=op<=hi and lo<=cl<=hi,'OHLC')
        if clocks and now-clocks[-1]!=300:start=i
        tr=hi-lo if i==start else max(hi-lo,abs(hi-values[-1][3]),abs(lo-values[-1][3]))
        signal=0
        if i-start>=48:
            baseline=sum(ranges[i-48:i],D(0));fast=sum(ranges[i-6:i],D(0))
            if baseline>0 and fast*48<=D('.6')*baseline*6:
                high=max(x[1] for x in values[i-12:i]);low=min(x[2] for x in values[i-12:i])
                signal=1 if cl>high else -1 if cl<low else 0
        clocks.append(now);values.append((op,hi,lo,cl));ranges.append(tr);signals.append(signal)
    pending=None;active=None;signature=[];gross=D(0);complete=censored=0
    by_segment={str(s):{'Complete':0,'SumGrossBps':D(0)} for s in range(1,5)};weeks={}
    for i,(now,prices,signal) in enumerate(zip(clocks,values,signals)):
        if i and now-clocks[i-1]!=300:
            if pending is not None or active is not None:censored+=1
            pending=active=None
        if active is not None and now==active[0]:
            _,direction,entry,entry_idx,entry_clock=active
            move=D(direction)*(prices[0]-entry)/entry*10000;gross+=move;complete+=1
            signature.append(f'{entry_idx},{i},{direction}\n')
            date=datetime.fromtimestamp(entry_clock,timezone.utc)
            segment='1' if date.day<27 and date.month==8 else '2' if date.month==8 or date.day<3 else '3' if date.day<10 else '4'
            bucket=by_segment[segment];bucket['Complete']+=1;bucket['SumGrossBps']+=move
            week=date.strftime('%G-W%V');weeks[week]=weeks.get(week,0)+1;active=None
        if pending is not None and now==pending[0]:
            active=(now+3600,pending[1],prices[0],i,now);pending=None
        if active is None and pending is None and signal:pending=(now+600,signal)
    if pending is not None or active is not None:censored+=1
    result=dict(Rows=len(rows),CandidateSignals=sum(x!=0 for x in signals),Complete=complete,Censored=censored,
        SumGrossBps=gross,LedgerSha256=hashlib.sha256(''.join(signature).encode()).hexdigest(),BySegment=by_segment,ByWeek=weeks)
    if trace:result.update(SignalTrace=signals,EpisodeSignatures=signature)
    return result
def reconcile(actual,expected):
    for field in ('Rows','CandidateSignals','Complete','Censored','LedgerSha256','ByWeek'):
        need(actual[field]==expected[field],'EXACT_EPISODE_'+field)
    need(abs(D(str(actual['SumGrossBps']))-expected['SumGrossBps'])<D('.00000001'),'GROSS_SUM')
    need(set(actual['BySegment'])==set(expected['BySegment']),'SEGMENT_SET')
    for key,b in expected['BySegment'].items():
        a=actual['BySegment'][key]
        need(a['Complete']==b['Complete'] and abs(D(str(a['SumGrossBps']))-b['SumGrossBps'])<D('.00000001'),'SEGMENT_SUM')
