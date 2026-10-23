"""Independent full-hour array lookup / Decimal implementation. DEVELOPMENT only."""
from decimal import Decimal as D,ROUND_HALF_UP
from datetime import datetime,timezone
import hashlib
START='2026-08-20T00:00:00Z';END='2026-09-17T00:00:00Z';EVALUATE='2026-08-27T00:00:00Z'
def need(ok,reason):
    if not ok:raise ValueError('MXM_SEASONALITY_REFERENCE_'+reason)
def reference(rows,trace=False):
    clocks=[];values=[]
    for row in rows:
        stamp=row['time_utc'];need(START<=stamp<END and stamp.endswith('Z'),'TIME_FENCE')
        date=datetime.fromisoformat(stamp.replace('Z','+00:00'));now=int(date.timestamp())
        need(date.microsecond==0 and now%300==0 and (not clocks or now>clocks[-1]),'M5_CHRONOLOGY')
        op,hi,lo,cl=(D(str(row[k])) for k in ('open','high','low','close'))
        need(all(v.is_finite() and v>0 for v in (op,hi,lo,cl)) and lo<=op<=hi and lo<=cl<=hi,'OHLC')
        clocks.append(now);values.append((op,hi,lo,cl))
    # Build completed hour samples independently by indexing twelve original bars.
    hours=[]
    for i,t in enumerate(clocks):
        if i>=11 and t%3600==3300 and clocks[i-11]==t-3300 and all(clocks[j+1]-clocks[j]==300 for j in range(i-11,i)):
            sample=((values[i][0]-values[i-10][0])/values[i-10][0]*10000).quantize(D('.00000001'),rounding=ROUND_HALF_UP)
            hours.append((i,t,(t//3600)%24,sample))
    signals=[0]*len(rows);ready=0
    for i,t,slot,_ in hours:
        target=(slot+1)%24
        prior=[sample for _,clock,hour,sample in hours if clock<t and hour==target][-5:]
        if len(prior)<5:continue
        ready+=1;total=sum(prior,D(0))
        if rows[i]['time_utc']>=EVALUATE:signals[i]=1 if total>50 else -1 if total< -50 else 0
    pending=active=None;signature=[];gross=D(0);complete=censored=0
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
            segment='1' if date.month==8 and date.day<27 else '2' if date.month==8 or date.day<3 else '3' if date.day<10 else '4'
            bucket=by_segment[segment];bucket['Complete']+=1;bucket['SumGrossBps']+=move
            week=date.strftime('%G-W%V');weeks[week]=weeks.get(week,0)+1;active=None
        if pending is not None and now==pending[0]:
            active=(now+3000,pending[1],prices[0],i,now);pending=None
        if active is None and pending is None and signal:pending=(now+600,signal)
    if pending is not None or active is not None:censored+=1
    result=dict(Rows=len(rows),CandidateSignals=sum(x!=0 for x in signals),TrainingHours=len(hours),ReadyForecasts=ready,
        SignalSha256=hashlib.sha256(''.join(f'{i},{sign}\n' for i,sign in enumerate(signals) if sign).encode()).hexdigest(),
        Complete=complete,Censored=censored,SumGrossBps=gross,LedgerSha256=hashlib.sha256(''.join(signature).encode()).hexdigest(),
        BySegment=by_segment,ByWeek=weeks)
    if trace:result.update(SignalTrace=signals,EpisodeSignatures=signature)
    return result

def reconcile(actual,expected):
    for field in ('Rows','CandidateSignals','TrainingHours','ReadyForecasts','Complete','Censored','SignalSha256','LedgerSha256','ByWeek'):
        need(actual[field]==expected[field],'EXACT_EPISODE_'+field)
    need(abs(D(str(actual['SumGrossBps']))-expected['SumGrossBps'])<D('.00000001'),'GROSS_SUM')
    need(set(actual['BySegment'])==set(expected['BySegment']),'SEGMENT_SET')
    for key,b in expected['BySegment'].items():
        a=actual['BySegment'][key]
        need(a['Complete']==b['Complete'] and abs(D(str(a['SumGrossBps']))-b['SumGrossBps'])<D('.00000001'),'SEGMENT_SUM')
