"""Two prospectively frozen extraction laws; no fit, rank or historical outcomes."""
import math
from research_core_v4.numeric_development_v1.numeric_streaming_executor_v1 import NumericalStop

MECHANISMS=('RANGE_TRANSLATION_CONTINUATION','ACTIVITY_IMPACT_DECELERATION_REVERSAL')
LAGS=(0,300,900)

def need(ok,code):
    if not ok:raise NumericalStop(code)

def hours(buffer,t,lag):
    need(type(t) is int and t%3600==0 and lag in LAGS,'WAVE_DECISION_GRID')
    q=t-lag;h=3600*(q//3600)-3600;out=[]
    for start in (h-3600,h):
        timestamps=[start+300*k for k in range(12)]
        if any(ts not in buffer for ts in timestamps):return None,'FEATURE_GAP'
        rows=[buffer[ts] for ts in timestamps]
        need(all(b.get('timestamp')==ts and type(b.get('available_at')) is int and b['available_at']>=ts+300 for ts,b in zip(timestamps,rows)),'WAVE_FEATURE_TIMESTAMP')
        if any(b['available_at']>q for b in rows):return None,'FEATURE_RECEIPT'
        for b in rows:
            need(all(type(b[k]) in (int,float) and math.isfinite(b[k]) for k in ('open','high','low','close')),'NONFINITE_FEATURE')
            need(0<b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high'],'INVALID_FEATURE_OHLC')
            need(type(b['tick_volume']) is int and b['tick_volume']>=0,'INVALID_FEATURE_VOLUME')
        out.append({'o':rows[0]['open'],'c':rows[-1]['close'],'l':min(b['low'] for b in rows),'u':max(b['high'] for b in rows),'v':sum(b['tick_volume'] for b in rows)})
    return out,'FEATURE_VALID'

def directions(buffer,t,lag):
    hs,reason=hours(buffer,t,lag)
    if hs is None:return {m:(None,reason) for m in MECHANISMS},False
    p,c=hs
    if c['l']>p['l'] and c['u']>p['u'] and c['c']>c['o']:d=1
    elif c['l']<p['l'] and c['u']<p['u'] and c['c']<c['o']:d=-1
    else:d=None
    answer={MECHANISMS[0]:(d,'EMITTED' if d else 'NO_EVENT')}
    if p['v']==0 or c['v']==0:answer[MECHANISMS[1]]=(None,'ZERO_ACTIVITY')
    else:
        r1=math.log(p['c']/p['o']);r2=math.log(c['c']/c['o'])
        need(math.isfinite(r1) and math.isfinite(r2),'NONFINITE_IMPACT')
        hit=r1*r2>0 and abs(r2)>abs(r1) and c['v']>p['v'] and abs(r2)*p['v']<abs(r1)*c['v']
        answer[MECHANISMS[1]]=(-1 if r2>0 else 1,'EMITTED') if hit else (None,'NO_EVENT')
    return answer,True
