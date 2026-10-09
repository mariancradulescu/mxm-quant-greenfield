"""Pure prospective directional-response kernel; no readers, broker or PnL."""
import math

def sign(x):return (x>0)-(x<0)
def valid_bar(ts,b,cutoff):
    if b.get('timestamp')!=ts or type(ts) is not int or ts%300:raise ValueError('TIMESTAMP')
    a=b.get('available_at')
    if type(a) is not int or not ts+300<=a<=cutoff:return False
    vals=[b.get(k) for k in ('open','high','low','close')]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in vals):raise ValueError('NONFINITE_OHLC')
    o,h,l,c=vals
    if not 0<l<=min(o,c)<=max(o,c)<=h:raise ValueError('INVALID_OHLC')
    v=b.get('tick_volume')
    if type(v) is not int or v<0:raise ValueError('INVALID_VOLUME')
    return True

def directions(bars,t,lag):
    if type(t) is not int or t%3600 or lag not in (0,300,900):raise ValueError('DECISION_GRID')
    q=t-lag;hour=q//3600*3600-3600
    need=set(range(hour,hour+3600,300))|{q-300}
    if any(ts not in bars for ts in need):return None,'FEATURE_GAP'
    if any(not valid_bar(ts,bars[ts],q) for ts in need):return None,'FEATURE_RECEIPT'
    total=sum(bars[ts]['tick_volume'] for ts in range(hour,hour+3600,300))
    if total==0:return None,'ZERO_ACTIVITY'
    numerator=sum(bars[ts]['tick_volume']*sign(bars[ts]['close']-bars[ts]['open']) for ts in range(hour,hour+3600,300))
    da=sign(numerator);b=bars[q-300];db=sign(b['close']-b['open'])
    if da==0 or db==0:return None,'COMMON_ZERO_DIRECTION_ABSTENTION'
    return (da,db),'SUPPORTED'

def response(bars,t,lag,observed_until,domain_end):
    maturity=t+3600+lag
    if maturity>domain_end:return None,'DOMAIN_CENSOR'
    if observed_until<maturity:raise ValueError('LABEL_NOT_MATURE')
    need=range(t-300,t+3600,300)
    if any(ts not in bars for ts in need):return None,'LABEL_GAP'
    if any(not valid_bar(ts,bars[ts],observed_until-lag) for ts in need):return None,'LABEL_RECEIPT'
    return math.log(bars[t+3300]['close']/bars[t-300]['close']),'SUPPORTED'
