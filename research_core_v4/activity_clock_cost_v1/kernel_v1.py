"""New activity-time location, mature-label controls and fixed EUR200 screen.

Quote volume is broker tick count, not traded volume or aggressor flow.
Every feature uses completed M5 bars; no interpolation inside a bar.
"""
import math
from collections import deque
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.compact_baseline_v2 import baseline
from research_core_v4.multiscale_regime_v1.kernel_v1 import Fit

def feature(rows):
    if len(rows)!=12 or any(r['tick_volume']<=0 for r in rows):
        return None
    total=sum(r['tick_volume'] for r in rows);acc=0
    for k,r in enumerate(rows):
        acc+=r['tick_volume']
        if 2*acc>=total:break
    return {'activity_half_index':k,'activity_time_displacement_bps':10000*math.log(rows[k]['close']/rows[5]['close'])}

def observations(bars):
    out=[]
    for j in range(672):
        h=n.START+j*3600;action=h+900;end=action+14400
        stamps=list(range(h-3600,h,300));rows=[bars.get(s) for s in stamps]
        required=set(stamps)|{action-300}
        own=baseline(action,[bars[s] for s in required if s in bars])
        f=None;x=None;reason='FEATURE_GAP'
        if own is not None and all(r is not None and n.frozen.valid_bar(s,r,action) for s,r in zip(stamps,rows)):
            f=feature(rows);reason='INACTIVE_FEATURE' if f is None else 'FEATURE_VALID'
            if f is not None:
                body=10000*math.log(rows[-1]['close']/rows[0]['open'])
                energy=math.sqrt(sum((10000*math.log(r['close']/r['open']))**2 for r in rows))
                x=[float(v) for v in own]+[body,energy,f['activity_time_displacement_bps']]
        last=bars.get(action-300);ref=None
        if last is not None and n.frozen.valid_bar(action-300,last,action):ref=last['close']
        y=None;exitprice=None;label='DOMAIN_CENSOR'
        if end<=n.END:
            ss=list(range(action,end,300));rr=[bars.get(s) for s in ss];label='LABEL_GAP'
            if all(r is not None and n.frozen.valid_bar(s,r,end) for s,r in zip(ss,rr)):
                y=10000*math.log(rr[-1]['close']/rr[0]['open']);exitprice=rr[-1]['close'];label='SUPPORTED'
        out.append({'clock':j,'action':action,'exit':end,'x':x,'feature':reason,'phi':f,
                    'causal_reference_price':ref,'causal_h1_range':float(own[6]) if own is not None else None,
                    'y':y,'label':label,'entry_reference_price':bars[action]['open'] if action in bars else None,
                    'exit_reference_price':exitprice})
    return out

def evaluate(obs,economic_gate):
    base=Fit(12);model=Fit(13);pending=deque();trials=[]
    for r in obs:
        action=r['action']
        while pending and pending[0][0]<action:
            maturity,x,y=pending.popleft();assert maturity<action
            base.add(x[:12],y);model.add(x,y)
        x=r['x'];economic=economic_gate(r);p0=p1=None
        reason=r['feature']
        if x is not None:
            reason=economic['reason']
            if economic['research_pass']:
                if base.count<32:reason='TRAINING_SUPPORT_ABSTENTION'
                else:
                    p0=base.predict(x[:12]);p1=model.predict(x);reason=r['label']
        if r['clock']%4==0:
            trials.append({**{k:v for k,v in r.items() if k!='x'},'training':base.count,
              'baseline':p0,'model':p1,'reason':reason,'economics':economic})
        # Identical causal economic screen and strictly matured rows in BOTH fits.
        if x is not None and economic['research_pass'] and r['y'] is not None:
            pending.append((r['exit'],x,r['y']))
    assert len(trials)==168 and all(sum(t['clock']//168==b for t in trials)==42 for b in range(4))
    return trials

def paired_return(direction,entry,exit):
    if direction==0:return 0.
    return 10000*math.log(exit['bid']/entry['ask']) if direction>0 else 10000*math.log(entry['bid']/exit['ask'])

def stats(rows):
    valid=[r for r in rows if r['model'] is not None and r['y'] is not None]
    nvalid=len(valid);mean=lambda fn:sum(fn(r) for r in valid)/nvalid if nvalid else None
    side=[r for r in valid if r.get('quote_model_bps') is not None]
    mside=lambda fn:sum(fn(r) for r in side)/len(side) if side else None
    sign=lambda x:(x>0)-(x<0)
    friction=lambda r:r['economics']['fee_bps']+abs(r['y'])*r['economics']['current_pnl_conversion_fraction']
    from collections import Counter
    return {'calendar':len(rows),'research_economically_supported':sum(r['economics']['research_pass'] for r in rows),
      'predictions':sum(r['model'] is not None for r in rows),'paired':nvalid,'reasons':dict(Counter(r['reason'] for r in rows)),
      'model_gross_bps':mean(lambda r:sign(r['model'])*r['y']),
      'baseline_gross_bps':mean(lambda r:sign(r['baseline'])*r['y']),
      'paired_increment_bps':mean(lambda r:(sign(r['model'])-sign(r['baseline']))*r['y']),
      'MSE_improvement_bps2':mean(lambda r:(r['y']-r['baseline'])**2-(r['y']-r['model'])**2),
      'model_reference_less_causal_current_fee_scenario_bps':mean(lambda r:sign(r['model'])*r['y']-friction(r)),
      'sensitivity_after_fee_plus_2_5_10_bps':{str(c):mean(lambda r:sign(r['model'])*r['y']-friction(r)-c) for c in (2,5,10)},
      'exact_quote_pairs':len(side),'quote_side_model_bps':mside(lambda r:r['quote_model_bps']),
      'quote_side_baseline_bps':mside(lambda r:r['quote_baseline_bps']),
      'quote_paired_increment_bps':mside(lambda r:r['quote_model_bps']-r['quote_baseline_bps']),
      'quote_model_less_current_fee_bps':mside(lambda r:r['quote_model_bps']-r['economics']['fee_bps']-abs(r['quote_model_bps'])*r['economics']['current_pnl_conversion_fraction']),
      'NET_certified':False,'actual_entries':0}
