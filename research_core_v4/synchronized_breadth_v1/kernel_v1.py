"""One frozen leave-target-out participation law; own-price paired control."""
import math
from collections import deque,Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
LAG=900
HORIZON=3600

def reduce(bars):
    out=[]
    for j in range(672):
        t=n.START+j*3600;action=t+LAG
        stamps=list(range(t-3600,t,300));rows=[bars.get(s) for s in stamps]
        x=None;reason='FEATURE_GAP'
        if all(r is not None for r in rows):
            if all(n.frozen.valid_bar(s,r,action) for s,r in zip(stamps,rows)):
                if all(r['tick_volume']>0 for r in rows):
                    ret=10000*math.log(rows[-1]['close']/rows[0]['open'])
                    energy=math.sqrt(sum((10000*math.log(r['close']/r['open']))**2 for r in rows))
                    x=[1.,max(-4.,min(4.,ret/100)),min(4.,energy/100)]
                    reason='FEATURE_VALID'
                else:reason='INACTIVE_FEATURE_ABSTENTION'
            else:reason='FEATURE_RECEIPT'
        exit=action+HORIZON;y=None;label='DOMAIN_CENSOR'
        if exit<=n.END:
            ss=list(range(action,exit,300));rr=[bars.get(s) for s in ss];label='LABEL_GAP'
            if all(r is not None for r in rr):
                label='LABEL_RECEIPT'
                if all(n.frozen.valid_bar(s,r,exit) for s,r in zip(ss,rr)):
                    y=10000*math.log(rr[-1]['close']/rr[0]['open']);label='SUPPORTED'
        out.append({'x':x,'feature':reason,'y':y,'label':label,'entry_reference_price':bars[action]['open'] if action in bars else None})
    return out

def peer_breadth(panel,rosters):
    out={sid:[] for ids in rosters.values() for sid in ids}
    coverage={}
    for group,ids in rosters.items():
        gc=Counter()
        for j in range(672):
            valid={sid:(panel[sid][j]['x'][1]>0)-(panel[sid][j]['x'][1]<0) for sid in ids if panel[sid][j]['x'] is not None}
            total=sum(valid.values())
            for sid in ids:
                own=panel[sid][j]['x'];count=len(valid)-int(sid in valid)
                need=max(8,math.ceil(.5*(len(ids)-1)))
                if own is None:b=None;reason=panel[sid][j]['feature']
                elif count<need:b=None;reason='COMMON_CLOCK_PEER_SUPPORT_ABSTENTION'
                else:b=(total-valid[sid])/count;reason='COMMON_CLOCK_SUPPORTED'
                out[sid].append({'b':b,'peers':count,'required':need,'reason':reason});gc[reason]+=1
        coverage[group]={'roster':len(ids),'target_clocks':len(ids)*672,'reasons':dict(gc)}
    return out,coverage

class Fit:
    def __init__(self,d):self.d=d;self.count=0;self.a=[[float(i==j) for j in range(d)] for i in range(d)];self.c=[0.]*d
    def add(self,x,y):
        self.count+=1
        for i in range(self.d):
            self.c[i]+=x[i]*y
            for j in range(self.d):self.a[i][j]+=x[i]*x[j]
    def predict(self,x):
        m=[self.a[i][:]+[self.c[i]] for i in range(self.d)]
        for i in range(self.d):
            pivot=max(range(i,self.d),key=lambda r:abs(m[r][i]));m[i],m[pivot]=m[pivot],m[i]
            v=m[i][i];assert abs(v)>1e-12
            m[i]=[z/v for z in m[i]]
            for k in range(self.d):
                if k!=i:
                    v=m[k][i];m[k]=[a-v*b for a,b in zip(m[k],m[i])]
        return sum(x[i]*m[i][-1] for i in range(self.d))

def metric():
    return dict(calendar=0,predictions=0,supported=0,emitted_model=0,emitted_baseline=0,direction_disagreements=0,
      model_gross_sum_bps=0.,baseline_gross_sum_bps=0.,model_squared_error_sum=0.,baseline_squared_error_sum=0.,
      model_forecast_abs_sum_bps=0.,baseline_forecast_abs_sum_bps=0.,reasons={})

def update(m,trial):
    m['calendar']+=1;r=trial['reason'];m['reasons'][r]=m['reasons'].get(r,0)+1
    if trial.get('model') is None:return
    m['predictions']+=1;d1=(trial['model']>0)-(trial['model']<0);d0=(trial['baseline']>0)-(trial['baseline']<0)
    m['emitted_model']+=int(d1!=0);m['emitted_baseline']+=int(d0!=0);m['direction_disagreements']+=int(d1!=d0)
    y=trial['y']
    if y is not None:
        m['supported']+=1;m['model_gross_sum_bps']+=d1*y;m['baseline_gross_sum_bps']+=d0*y
        m['model_squared_error_sum']+=(y-trial['model'])**2;m['baseline_squared_error_sum']+=(y-trial['baseline'])**2
        m['model_forecast_abs_sum_bps']+=abs(trial['model']);m['baseline_forecast_abs_sum_bps']+=abs(trial['baseline'])

def finish(m):
    s=m['supported'];m['model_gross_bps']=m['model_gross_sum_bps']/s if s else None;m['baseline_gross_bps']=m['baseline_gross_sum_bps']/s if s else None
    m['paired_increment_bps']=(m['model_gross_sum_bps']-m['baseline_gross_sum_bps'])/s if s else None
    m['MSE_improvement_bps2']=(m['baseline_squared_error_sum']-m['model_squared_error_sum'])/s if s else None
    return m

def evaluate(sid,panel,breadth):
    base=Fit(3);model=Fit(4);pending=deque();weeks=[metric() for _ in range(4)];iso=defaultdict(metric);trials=[]
    for j,(obs,peer) in enumerate(zip(panel[sid],breadth[sid])):
        t=n.START+j*3600;action=t+LAG
        while pending and pending[0][0]<action:
            _,x,y=pending.popleft();base.add(x[:3],y);model.add(x,y)
        x=obs['x'];b=peer['b'];reason=peer['reason'];p0=p1=None
        if b is not None:
            x=x+[b]
            if base.count<32:reason='TRAINING_SUPPORT_ABSTENTION'
            else:p0=base.predict(x[:3]);p1=model.predict(x);reason=obs['label']
        trial={'clock':j,'action':action,'exit':action+HORIZON,'training':base.count,'peers':peer['peers'],'required':peer['required'],
          'breadth':b,'entry_reference_price':obs.get('entry_reference_price'),'baseline':p0,'model':p1,'y':obs['y'] if p1 is not None else None,'reason':reason}
        update(weeks[j//168],trial)
        iw=datetime.fromtimestamp(action,timezone.utc).isocalendar();update(iso[f'{iw.year}-W{iw.week:02d}'],trial)
        trials.append(trial)
        if b is not None and obs['y'] is not None:pending.append((action+HORIZON,x,obs['y']))
    assert all(m['calendar']==168 and sum(m['reasons'].values())==168 for m in weeks)
    return {'symbol_id':sid,'four_weeks':[finish(m) for m in weeks],'iso_utc':{k:finish(m) for k,m in iso.items()},'trials':trials}

def merge(results,key='four_weeks'):
    keys=range(4) if key=='four_weeks' else sorted({k for r in results for k in r[key]})
    out=[]
    for k in keys:
        m=metric()
        for r in results:
            a=r[key][k] if key=='four_weeks' else r[key].get(k,metric())
            for name in metric():
                if name!='reasons':m[name]+=a[name]
            for name,count in a['reasons'].items():m['reasons'][name]=m['reasons'].get(name,0)+count
        m['block' if key=='four_weeks' else 'iso_week']=k;out.append(finish(m))
    return out
