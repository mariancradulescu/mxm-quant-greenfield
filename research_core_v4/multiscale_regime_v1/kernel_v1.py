"""Continuous path occupancy and ordered serial shape; paired own baseline."""
import math
from collections import deque,defaultdict
from datetime import datetime,timezone
import numpy as np
from research_core_v4.compact_baseline_v2 import baseline
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.synchronized_breadth_v1.kernel_v1 import metric,update,finish,merge
NAMES=('OCCUPANCY_DISPLACEMENT','SERIAL_LOCATION_CHANGE')
HORIZON=14400
def observations(bars):
    out={name:[] for name in NAMES}
    for j in range(672):
        h=n.START+j*3600;t=h+900;exit=t+HORIZON
        required=set(range(h-3600,h,300))|{t-300}
        own=baseline(t,[bars[s] for s in required if s in bars]);y=None;label='DOMAIN_CENSOR'
        if exit<=n.END:
            stamps=range(t,exit,300);rows=[bars.get(s) for s in stamps];label='LABEL_GAP'
            if all(r is not None and n.frozen.valid_bar(s,r,exit) for s,r in zip(stamps,rows)):
                y=10000*math.log(rows[-1]['close']/rows[0]['open']);label='SUPPORTED'
        for name,depth in zip(NAMES,(60,24)):
            stamps=range(h-depth*300,h,300);rows=[bars.get(s) for s in stamps];x=None;reason='BASELINE_GAP'
            if own is not None:
                reason='FEATURE_GAP'
                if all(r is not None and n.frozen.valid_bar(s,r,t) for s,r in zip(stamps,rows)):
                    reason='INACTIVE_FEATURE_ABSTENTION'
                    if own[4]>0 and all(r['tick_volume']>0 for r in rows):
                        if name==NAMES[0]:
                            a,b=rows[-12:],rows[:-12]
                            phi=10000*(sum(math.log(r['close']/a[-1]['close']) for r in a)/12-sum(math.log(r['close']/b[-1]['close']) for r in b)/48)
                        else:
                            loc=[(r['close']-r['low'])/(r['high']-r['low']) if r['high']>r['low'] else .5 for r in rows]
                            c=lambda v:sum((v[i]-.5)*(v[i-1]-.5) for i in range(1,12))/11
                            phi=(c(loc[12:])-c(loc[:12]))*(2*float(own[5])-1)
                        x=[float(v) for v in own]+[phi];reason='FEATURE_VALID'
            out[name].append({'x':x,'feature':reason,'y':y,'label':label,'entry_reference_price':bars[t]['open'] if t in bars else None})
    return out
class Fit:
    def __init__(self,d):
        self.d=d;self.count=0;self.mean=np.zeros(d);self.my=0.;self.m2=np.zeros((d,d));self.cy=np.zeros(d)
    def add(self,x,y):
        x=np.asarray(x,dtype=float);self.count+=1;dx=x-self.mean;dy=y-self.my
        self.mean+=dx/self.count;self.my+=dy/self.count
        self.m2+=np.outer(dx,x-self.mean);self.cy+=dx*(y-self.my)
    def predict(self,x):
        sd=np.sqrt(np.maximum(0.,np.diag(self.m2)/self.count));sd=np.where(sd>1e-12,sd,1.)
        a=self.m2/np.outer(sd,sd)+10.*np.eye(self.d);b=self.cy/sd
        return float(self.my+np.dot((np.asarray(x)-self.mean)/sd,np.linalg.solve(a,b)))
def evaluate(sid,obs):
    base=Fit(10);model=Fit(11);pending=deque();weeks=[metric() for _ in range(4)];iso=defaultdict(metric);trials=[]
    for j,r in enumerate(obs):
        action=n.START+j*3600+900;exit=action+HORIZON
        while pending and pending[0][0]<action:
            end,x,y=pending.popleft();assert end<action;base.add(x[:10],y);model.add(x,y)
        x=r['x']
        if j%4==0:
            reason=r['feature'];p0=p1=None
            if x is not None:
                if base.count<32:reason='TRAINING_SUPPORT_ABSTENTION'
                else:p0=base.predict(x[:10]);p1=model.predict(x);reason=r['label']
            tr={'clock':j,'action':action,'exit':exit,'training':base.count,'baseline':p0,'model':p1,'y':r['y'] if p1 is not None else None,'reason':reason,'entry_reference_price':r['entry_reference_price']}
            update(weeks[j//168],tr);iw=datetime.fromtimestamp(action,timezone.utc).isocalendar();update(iso[f'{iw.year}-W{iw.week:02d}'],tr)
            if p1 is not None:trials.append(tr)
        if x is not None and r['y'] is not None:pending.append((exit,x,r['y']))
    assert all(w['calendar']==42 and sum(w['reasons'].values())==42 for w in weeks)
    return {'symbol_id':sid,'four_weeks':[finish(w) for w in weeks],'iso_utc':{k:finish(v) for k,v in iso.items()},'trials':trials}
def family_sensitivity(comparisons):
    """Calendar blocks shared across every identity/comparison, not iid trades."""
    cells=[]
    for name,blocks in comparisons.items():
        for endpoint in ('paired_increment_bps','MSE_improvement_bps2'):
            v=[b[endpoint] for b in blocks]
            if all(x is not None for x in v):cells.append((name,endpoint,np.array(v)))
    if not cells:return {'comparisons':0,'certified':False}
    stat=lambda v:abs(float(v.mean()))/(float(v.std(ddof=1))/2+1e-12)
    observed={(name,end):stat(v) for name,end,v in cells}
    maxima=[]
    for mask in range(16):
        signs=np.array([1 if mask&(1<<i) else -1 for i in range(4)])
        maxima.append(max(stat(v*signs) for _,_,v in cells))
    return {'comparisons':len(cells),'patterns':16,'conditional_shared_block_sign_flip_only':True,'exchangeability_established':False,'certified':False,'cells':[{'comparison':name,'endpoint':end,'absolute_studentized':observed[name,end],'maxT_two_sided_conditional_p':sum(x>=observed[name,end]-1e-10 for x in maxima)/16} for name,end,_ in cells]}
