"""Fixed H1 RV amplitude states: prequential first/second moment information.

No variance concentration, sign carrier, symbol selection or outcome tuning.
Mean and risk estimands are separate; risk information is not directional alpha.
"""
import math
from collections import deque
from research_core_v4.owner_frontier_v1.transition_kernel_v1 import label_at,n,LAG,HORIZON

def feature_at(bars,t):
    stamps=range(t-3600,t,300);rows=[bars.get(s) for s in stamps]
    if any(r is None for r in rows):return None,'FEATURE_GAP'
    if any(not n.frozen.valid_bar(s,r,t+LAG) for s,r in zip(stamps,rows)):return None,'FEATURE_RECEIPT'
    rv=sum((10000*math.log(r['close']/r['open']))**2 for r in rows)
    if not math.isfinite(rv) or rv<=0:return None,'ZERO_RV_ABSTENTION'
    return math.log(rv),'FEATURE_VALID'

def metrics():
    return {'calendar':42,'eligible_model_predictions':0,'supported':0,'emitted_model':0,'emitted_baseline':0,
      'gross_model_sum_bps':0.,'gross_baseline_sum_bps':0.,'squared_error_model_sum':0.,'squared_error_baseline_sum':0.,
      'risk_squared_error_model_sum':0.,'risk_squared_error_baseline_sum':0.,'risk_qlike_model_sum':0.,'risk_qlike_baseline_sum':0.,'reasons':{}}

def evaluate(bars):
    weeks=[metrics() for _ in range(4)];pending=deque();mature=[];trials=[]
    sum_y=sum_y2=sum_x=0.
    for j in range(672):
        t=n.START+j*3600;action=t+LAG
        while pending and pending[0][0]<action:
            _,x,y=pending.popleft();mature.append((x,y));sum_x+=x;sum_y+=y;sum_y2+=y*y
        x,reason=feature_at(bars,t)
        if j%4==0:
            m=weeks[j//168]
            if x is not None:
                total=len(mature)
                if total<32:reason='TRAINING_SUPPORT_ABSTENTION'
                else:
                    threshold=sum_x/total;state=int(x>threshold)
                    selected=[y for fx,y in mature if int(fx>threshold)==state]
                    if len(selected)<8:reason='STATE_SUPPORT_ABSTENTION'
                    else:
                        mu0=sum_y/total;mu1=(sum(selected)+mu0)/(len(selected)+1)
                        v0=sum_y2/total;v1=(sum(y*y for y in selected)+v0)/(len(selected)+1)
                        if min(v0,v1)<=0:reason='ZERO_RISK_BASELINE_ABSTENTION'
                        else:
                            m['eligible_model_predictions']+=1
                            d0=(mu0>0)-(mu0<0);d1=(mu1>0)-(mu1<0)
                            m['emitted_model']+=int(d1!=0);m['emitted_baseline']+=int(d0!=0)
                            y,reason=label_at(bars,t)
                            if y is not None:
                                m['supported']+=1;m['gross_model_sum_bps']+=d1*y;m['gross_baseline_sum_bps']+=d0*y
                                m['squared_error_model_sum']+=(y-mu1)**2;m['squared_error_baseline_sum']+=(y-mu0)**2
                                m['risk_squared_error_model_sum']+=(y*y-v1)**2;m['risk_squared_error_baseline_sum']+=(y*y-v0)**2
                                m['risk_qlike_model_sum']+=math.log(v1)+y*y/v1;m['risk_qlike_baseline_sum']+=math.log(v0)+y*y/v0
                            trials.append({'clock':j,'fixed_week':j//168,'training_total':total,'training_state':len(selected),'state':state,
                              'forecast_baseline_bps':mu0,'forecast_state_bps':mu1,'risk_second_moment_baseline_bps2':v0,'risk_second_moment_state_bps2':v1,
                              'response_bps':y,'support':reason,'entry_reference':action,'exit_reference':action+HORIZON})
            m['reasons'][reason]=m['reasons'].get(reason,0)+1
        if x is not None:
            y,_=label_at(bars,t)
            if y is not None:pending.append((action+HORIZON,x,y))
    assert all(sum(m['reasons'].values())==42 for m in weeks)
    return {'four_weeks':weeks,'trials':trials,'mature_training_labels':len(mature),'net_established':False}

def merge(items):
    out=[]
    for w in range(4):
        ms=[x['result']['four_weeks'][w] for x in items]
        m={k:sum(v[k] for v in ms) for k in metrics() if k!='reasons'}
        reasons={}
        for v in ms:
            for k,c in v['reasons'].items():reasons[k]=reasons.get(k,0)+c
        m['reasons']=reasons;s=m['supported']
        for name,num in [('model_gross_supported_bps',m['gross_model_sum_bps']),('baseline_gross_supported_bps',m['gross_baseline_sum_bps']),
            ('mean_squared_error_improvement',m['squared_error_baseline_sum']-m['squared_error_model_sum']),
            ('risk_mean_squared_error_improvement_bps4',m['risk_squared_error_baseline_sum']-m['risk_squared_error_model_sum']),
            ('risk_mean_qlike_improvement',m['risk_qlike_baseline_sum']-m['risk_qlike_model_sum'])]:m[name]=num/s if s else None
        out.append(m)
    return out
