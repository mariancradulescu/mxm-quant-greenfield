"""Candidate-blind compact reference map. No file readers or research imports."""
from datetime import datetime, timezone
from fractions import Fraction
import math

ORDER = ('LAST_M5_OPEN','LAST_M5_HIGH','LAST_M5_LOW','LAST_M5_CLOSE','LAST_M5_TICK_VOLUME','HOURLY_PRICE_LOCATION','HOURLY_RANGE','HOURLY_TOTAL_TICK_VOLUME','UTC_WEEKDAY','UTC_5_MINUTE_SLOT_OF_DAY')

def baseline(t, bars):
    """Times are integer UTC epoch seconds; bar timestamp is its open.
    No backward search past an incomplete latest calendar hour is allowed.
    Availability includes original effective record availability, not revisions.
    Return None when any required record is unavailable or invalid.
    """
    if type(t) is not int or t % 300: raise ValueError('M5_DECISION_GRID')
    last=t-300; hour=(t//3600)*3600-3600
    required=set(range(hour,hour+3600,300))|{last}
    selected={}
    for b in bars:
        if b.get('timestamp') not in required: continue
        ts=b['timestamp']
        if ts in selected: return None
        selected[ts]=b
    if set(selected)!=required: return None
    for ts,b in selected.items():
        if type(ts) is not int or ts%300: return None
        a=b.get('available_at')
        if type(a) is not int or a<ts+300 or a>t: return None
        vals=[b.get(k) for k in ('open','high','low','close')]
        if any(type(v) not in (int,float,Fraction) or not math.isfinite(v) for v in vals): return None
        o,h,l,c=vals
        if not l<=min(o,c)<=max(o,c)<=h: return None
        v=b.get('tick_volume')
        if type(v) is not int or v<0: return None
    hbars=[selected[s] for s in range(hour,hour+3600,300)]
    high=max(b['high'] for b in hbars); low=min(b['low'] for b in hbars)
    width=Fraction(high)-Fraction(low)
    location=(Fraction(hbars[-1]['close'])-Fraction(low))/width if width else Fraction(1,2)
    b=selected[last]; dt=datetime.fromtimestamp(t,timezone.utc)
    return tuple(b[k] for k in ('open','high','low','close','tick_volume'))+(location,width,sum(x['tick_volume'] for x in hbars),dt.weekday(),(dt.hour*60+dt.minute)//5)
