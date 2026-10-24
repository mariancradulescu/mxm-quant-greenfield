"""Independent array/bisect target alignment, no incremental C# state replication."""
from bisect import bisect_right
from datetime import datetime,timezone
from decimal import Decimal as D,ROUND_HALF_UP
import hashlib
START='2026-08-20T00:00:00Z';END='2026-09-17T00:00:00Z';EVALUATE='2026-08-27T00:00:00Z'
def need(ok,why):
    if not ok:raise ValueError('MXM_PATH_STATE_REFERENCE_'+why)
def digest(lines):return hashlib.sha256(''.join(lines).encode()).hexdigest()
def rounded(value):return value.quantize(D('.00000001'),rounding=ROUND_HALF_UP)
def reference(rows,trace=False):
    clocks=[];opens=[];closes=[];runs=[];run=0
    for row in rows:
        stamp=row['time_utc'];need(stamp.endswith('Z') and START<=stamp<END,'TIME_FENCE')
        date=datetime.fromisoformat(stamp.replace('Z','+00:00'));now=int(date.timestamp())
        need(date.microsecond==0 and now%300==0 and (not clocks or now>clocks[-1]),'M5_CHRONOLOGY')
        op,hi,lo,cl=(D(str(row[k])) for k in ('open','high','low','close'))
        need(all(v.is_finite() and v>0 for v in (op,hi,lo,cl)) and lo<=op<=hi and lo<=cl<=hi,'OHLC')
        if clocks and now-clocks[-1]!=300:run+=1
        clocks.append(now);opens.append(op);closes.append(cl);runs.append(run)
    contexts=[]
    for i in range(len(rows)):
        if i<3 or runs[i]!=runs[i-3] or any(closes[j]==closes[j-1] for j in range(i-2,i+1)):
            contexts.append(None);continue
        # Full indexed four-close tuple, rather than the learner's rolling queue.
        bits=[int(closes[j]>closes[j-1]) for j in range(i-2,i+1)]
        contexts.append(4*bits[0]+2*bits[1]+bits[2])
    labels={cell:[] for cell in range(8)};training=[];mature_count=0
    for origin,cell in enumerate(contexts):
        end=origin+14
        if cell is None or end>=len(rows) or runs[origin]!=runs[end]:continue
        y=rounded((opens[end]-opens[origin+2])/opens[origin+2]*10000)
        labels[cell].append((end,y));training.append((end,f'{origin},{end},{cell},{y:.8f}\n'));mature_count+=1
    times={cell:[x[0] for x in values] for cell,values in labels.items()}
    signals=[0]*len(rows);forecasts=[];forecast_values=[None]*len(rows);ready=0
    for i,cell in enumerate(contexts):
        if cell is None:continue
        at=bisect_right(times[cell],i);prior=labels[cell][max(0,at-32):at]
        if len(prior)<16:continue
        ready+=1;mean=rounded(sum((y for _,y in prior),D(0))/(len(prior)+16));forecast_values[i]=mean
        forecasts.append(f'{i},{cell},{mean:.8f}\n')
        if rows[i]['time_utc']>=EVALUATE:signals[i]=1 if mean>10 else -1 if mean< -10 else 0
    # Independently select nonoverlapping episodes using absolute source clock deadlines.
    pending=active=None;signature=[];gross=D(0);complete=censored=0
    by_segment={str(s):{'Complete':0,'SumGrossBps':D(0)} for s in range(1,5)};weeks={}
    for i,(now,op,signal) in enumerate(zip(clocks,opens,signals)):
        if i and runs[i]!=runs[i-1]:
            if pending is not None or active is not None:censored+=1
            pending=active=None
        if active is not None and now==active[0]:
            _,direction,entry,entry_idx,entry_clock=active
            move=D(direction)*(op-entry)/entry*10000;gross+=move;complete+=1
            signature.append(f'{entry_idx},{i},{direction}\n')
            stamp=datetime.fromtimestamp(entry_clock,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            segment='1' if stamp<'2026-08-27' else '2' if stamp<'2026-09-03' else '3' if stamp<'2026-09-10' else '4'
            by_segment[segment]['Complete']+=1;by_segment[segment]['SumGrossBps']+=move
            week=datetime.fromtimestamp(entry_clock,timezone.utc).strftime('%G-W%V');weeks[week]=weeks.get(week,0)+1;active=None
        if pending is not None and now==pending[0]:active=(now+3600,pending[1],op,i,now);pending=None
        if active is None and pending is None and signal:pending=(now+600,signal)
    if pending is not None or active is not None:censored+=1
    result=dict(Rows=len(rows),CandidateSignals=sum(x!=0 for x in signals),TrainingLabels=mature_count,
        TrainingCensored=sum(x is not None for x in contexts)-mature_count,ReadyForecasts=ready,
        SignalSha256=digest([f'{i},{s}\n' for i,s in enumerate(signals) if s]),ForecastSha256=digest(forecasts),
        TrainingSha256=digest([line for _,line in sorted(training)]),Complete=complete,Censored=censored,
        SumGrossBps=gross,LedgerSha256=digest(signature),BySegment=by_segment,ByWeek=weeks)
    if trace:result.update(SignalTrace=signals,ForecastTrace=forecast_values,EpisodeSignatures=signature,Contexts=contexts)
    return result

def reconcile(actual,expected):
    for field in ('Rows','CandidateSignals','TrainingLabels','TrainingCensored','ReadyForecasts','Complete','Censored',
                  'SignalSha256','ForecastSha256','TrainingSha256','LedgerSha256','ByWeek'):
        need(actual[field]==expected[field],'EXACT_'+field)
    need(abs(D(str(actual['SumGrossBps']))-expected['SumGrossBps'])<D('.00000001'),'GROSS_SUM')
    need(set(actual['BySegment'])==set(expected['BySegment']),'SEGMENT_SET')
    for key,expected in expected['BySegment'].items():
        value=actual['BySegment'][key]
        need(value['Complete']==expected['Complete'] and
             abs(D(str(value['SumGrossBps']))-expected['SumGrossBps'])<D('.00000001'),'SEGMENT_SUM')
