"""Prospective H1 sign-transition information vs unconditional drift.

All updates use strictly matured labels. Evaluation uses disjoint four-hour
positions; hourly training labels overlap and are not independent trials.
No parameter/symbol/side search or significance claim.
"""
import math
from collections import Counter,deque
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
LAG=900
HORIZON=14400

def state_at(bars,t):
    rows=[bars.get(ts) for ts in range(t-7200,t,300)]
    if any(r is None for r in rows):return None,'FEATURE_GAP'
    if any(not n.frozen.valid_bar(ts,r,t+LAG) for ts,r in zip(range(t-7200,t,300),rows)):return None,'FEATURE_RECEIPT'
    signs=[]
    for rs in (rows[:12],rows[12:]):
        r=math.log(rs[-1]['close']/rs[0]['open']);s=(r>0)-(r<0)
        if s==0:return None,'ZERO_H1_BODY'
        signs.append(s)
    return tuple(signs),'FEATURE_VALID'

def label_at(bars,t):
    entry=t+LAG;exit=entry+HORIZON
    if exit>n.END:return None,'DOMAIN_CENSOR'
    stamps=range(entry,exit,300)
    if any(ts not in bars for ts in stamps):return None,'LABEL_GAP'
    if any(not n.frozen.valid_bar(ts,bars[ts],exit) for ts in stamps):return None,'LABEL_RECEIPT'
    y=10000*math.log(bars[exit-300]['close']/bars[entry]['open'])
    assert math.isfinite(y)
    return y,'SUPPORTED'

def metrics():return {'calendar':42,'eligible_model_predictions':0,'supported':0,'emitted_model':0,'emitted_baseline':0,'gross_model_sum_bps':0.,'gross_baseline_sum_bps':0.,'squared_error_model_sum':0.,'squared_error_baseline_sum':0.,'reasons':{},'by_state':{}}

def evaluate(bars):
    week=[metrics() for _ in range(4)];pending=deque();total=0;sum_y=0.;states={};trials=[]
    for j in range(672):
        t=n.START+j*3600;action=t+LAG
        # Strict inequality prevents the current timestamp's label from entering training.
        while pending and pending[0][0]<action:
            maturity,state,y=pending.popleft();total+=1;sum_y+=y
            count,value=states.get(state,(0,0.));states[state]=(count+1,value+y)
        state,reason=state_at(bars,t)
        if j%4==0:
            m=week[j//168];forecast=None
            if state is not None:
                count,value=states.get(state,(0,0.))
                if total<32 or count<8:reason='TRAINING_SUPPORT_ABSTENTION'
                else:
                    mu0=sum_y/total;mu1=(value+mu0)/(count+1);forecast=(mu0,mu1);m['eligible_model_predictions']+=1
                    d0=(mu0>0)-(mu0<0);d1=(mu1>0)-(mu1<0);m['emitted_baseline']+=int(d0!=0);m['emitted_model']+=int(d1!=0)
                    y,reason=label_at(bars,t)
                    if y is not None:
                        m['supported']+=1;m['gross_model_sum_bps']+=d1*y;m['gross_baseline_sum_bps']+=d0*y
                        m['squared_error_model_sum']+=(y-mu1)**2;m['squared_error_baseline_sum']+=(y-mu0)**2
                        name=str(state);m['by_state'][name]=m['by_state'].get(name,0)+1
                    trials.append({'clock':j,'fixed_week':j//168,'state':list(state),'training_total':total,'training_state':count,'forecast_baseline_bps':mu0,'forecast_state_bps':mu1,'direction_baseline':d0,'direction_state':d1,'response_bps':y,'support':reason,'entry_reference':action,'exit_reference':action+HORIZON})
            m['reasons'][reason]=m['reasons'].get(reason,0)+1
        if state is not None:
            y,_=label_at(bars,t)
            if y is not None:pending.append((action+HORIZON,state,y))
    assert all(sum(m['reasons'].values())==42 for m in week)
    return {'four_weeks':week,'trials':trials,'mature_training_labels':total,'training_overlap':'HOURLY_FOUR_HOUR_LABELS_NOT_INDEPENDENT','net_established':False}
