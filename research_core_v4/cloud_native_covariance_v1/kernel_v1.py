"""Frozen spread/midpoint concordance; no fitting or outcome-selected parameters."""
import math

def feature(bids, asks):
    if len(bids) != 13 or len(asks) != 13:
        return None
    if any(not math.isfinite(b) or not math.isfinite(a) or not 0 < b < a for b,a in zip(bids,asks)):
        return None
    mids=[math.log((b+a)/2) for b,a in zip(bids,asks)]
    spreads=[math.log(a/b) for b,a in zip(bids,asks)]
    x=[mids[i]-mids[i-1] for i in range(1,13)]
    y=[spreads[i]-spreads[i-1] for i in range(1,13)]
    mx=sum(x)/12; my=sum(y)/12
    xx=sum((v-mx)**2 for v in x); yy=sum((v-my)**2 for v in y)
    if xx<=1e-24 or yy<=1e-24:
        return {'direction':0,'correlation':0.0,'reason':'DEGENERATE_VARIANCE'}
    corr=sum((a-mx)*(b-my) for a,b in zip(x,y))/math.sqrt(xx*yy)
    direction=(1 if corr>0 else -1) if abs(corr)>=0.2 else 0
    return {'direction':direction,'correlation':corr,'reason':'SIGNAL' if direction else 'WEAK_CONCORDANCE'}

def resample(pages,t_ms):
    """Latest causal *changed* price, per side; ambiguous same-ms ordering censored."""
    from m6.cost_evidence import decode_ctrader_tick_page
    streams={}
    for p in pages:
        if p.get('hasMore') or 'error_code' in p:
            return None,'INCOMPLETE_OR_ERROR_PAGE'
        decoded=decode_ctrader_tick_page(p['encoded']); changes=[]; seen={}; previous=None
        for v in decoded:
            ts=int(v.timestamp_ms); price=int(v.raw_tick)
            if ts in seen and seen[ts]!=price:
                return None,'AMBIGUOUS_SAME_MS'
            seen[ts]=price
            if previous is not None and price!=previous:
                changes.append((ts,price/100000))
            previous=price
        streams[p['side']]=changes
    if set(streams)!= {'bid','ask'}:
        return None,'MISSING_SIDE'
    output=[]
    for sample in range(t_ms-60000,t_ms+1,5000):
        pair={}
        for side in ('bid','ask'):
            past=[v for v in streams[side] if v[0]<=sample]
            if not past or sample-past[-1][0]>10000:
                return None,'FEATURE_CHANGE_AGE_OR_GAP'
            pair[side]=past[-1][1]
            pair[side+'_age_ms']=sample-past[-1][0]
        if not 0<pair['bid']<pair['ask']:
            return None,'INVALID_OR_CROSSED_QUOTE'
        output.append(pair)
    return output,'SUPPORTED'
