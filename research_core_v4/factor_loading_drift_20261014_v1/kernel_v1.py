"""One prospective loading-drift augmentation. All returns are DEVELOPMENT."""
import math
from collections import Counter,defaultdict,deque
from datetime import datetime,timezone
import numpy as np
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as native
START=native.START;END=native.END;HOURS=672;LAG=900;HOLD=3600

def sign(v):return int(v>0)-int(v<0)
def clip(v):return max(-4.,min(4.,v))
def iso(t):
 d=datetime.fromtimestamp(t,timezone.utc).isocalendar();return f'{d.year}-W{d.week:02d}'

def reduce(bars):
 # Future arrays are separate: feature extraction never reads them.
 feature=np.full((HOURS,3),np.nan);paths=np.full((HOURS,12,4),np.nan);entry=np.full(HOURS,np.nan);exit_ref=np.full(HOURS,np.nan)
 for j in range(HOURS):
  t=START+j*3600;stamps=list(range(t-3900,t,300));rr=[bars.get(s) for s in stamps]
  if all(r is not None and native.frozen.valid_bar(s,r,t) and r['tick_volume']>0 for s,r in zip(stamps,rr)):
   feature[j]=[10000*math.log(rr[-1]['close']/rr[0]['close']),max(r['high'] for r in rr[1:])-min(r['low'] for r in rr[1:]),rr[-1]['close']]
  action=t+LAG
  if action in bars:entry[j]=bars[action]['open']
  if action+HOLD-300 in bars:exit_ref[j]=bars[action+HOLD-300]['close']
  ss=list(range(action,action+HOLD,300));rr=[bars.get(s) for s in ss]
  if action+HOLD<=END and all(r is not None and native.frozen.valid_bar(s,r,action+HOLD) for s,r in zip(ss,rr)):
   paths[j]=[[r[z] for z in ('open','high','low','close')] for r in rr]
 return {'feature':feature,'path':paths,'entry':entry,'exit_reference':exit_ref}

def factors(panel,groups):
 out={};coverage={}
 for g,ids in groups.items():
  a=np.array([panel[s]['feature'][:,0] for s in ids]);ok=np.isfinite(a);counts=ok.sum(axis=0);sums=np.where(ok,a,0.).sum(axis=0);required=max(8,math.ceil((len(ids)-1)/2));gc=Counter()
  for n,sid in enumerate(ids):
   k=counts-ok[n];valid=ok[n]&(k>=required);f=np.full(HOURS,np.nan);f[valid]=(sums[valid]-a[n,valid])/k[valid];out[sid]=f
   gc['supported_target_hours']+=int(valid.sum());gc['target_hours']+=HOURS
  coverage[g]={'roster':len(ids),'minimum_peers':required,**dict(gc)}
 return out,coverage

def beta(history,n):
 if len(history)<n:return None
 a=np.asarray(list(history)[-n:],dtype=float);f=a[:,1];y=a[:,2];fc=f-f.mean();var=float(fc@fc)
 if var/n<1e-8:return None
 return clip(float(fc@(y-y.mean())/var))

class Fit:
 def __init__(self,d):self.a=np.eye(d);self.b=np.zeros(d);self.n=0
 def add(self,x,y):
  x=np.asarray(x);self.a+=np.outer(x,x);self.b+=x*y;self.n+=1
 def predict(self,x):return float(np.asarray(x)@np.linalg.solve(self.a,self.b))

def forecasts(sid,obs,factor):
 history=deque();pending=deque();base=Fit(6);model=Fit(7);trials=[];why=Counter()
 for j in range(HOURS):
  t=START+j*3600;action=t+LAG
  while pending and pending[0][0]<action:
   _,x,y=pending.popleft();base.add(x[:6],y);model.add(x,y)
  while history and history[0][0]<t-14*86400:history.popleft()
  f=factor[j];own=obs['feature'][j,0];x=None;p0=p1=None;bslow=bfast=None
  reason='FEATURE_OR_SYNCHRONOUS_PEER_GAP'
  if math.isfinite(own) and math.isfinite(f):
   bfast=beta(history,24);bslow=beta(history,72)
   if bfast is not None and bslow is not None:
    phase=2*math.pi*(t%86400)/86400;price=obs['feature'][j,2];rng=obs['feature'][j,1]
    x=[1.,clip(own/100),min(4.,10000*rng/price/100),math.sin(phase),math.cos(phase),clip(bslow*f/100),clip((bfast-bslow)*f/100)]
    reason='MATURE_PAIRED_TRAINING_INSUFFICIENT'
    if model.n>=32:p0=base.predict(x[:6]);p1=model.predict(x);reason='PREDICTION'
   else:reason='PRIOR_24_72_FACTOR_LOADING_SUPPORT'
   # Current return may update future loading fits, never its own loading feature.
   history.append((t,f,own))
  path=obs['path'][j];supported=bool(np.isfinite(path).all());y=10000*math.log(path[-1,3]/path[0,0]) if supported else None
  if x is not None and y is not None:pending.append((action+HOLD,x,y))
  atr=float(np.mean([obs['feature'][k,1] for k in range(max(0,j-24),j) if math.isfinite(obs['feature'][k,1])])) if j>0 and any(math.isfinite(obs['feature'][k,1]) for k in range(max(0,j-24),j)) else None
  why[reason]+=1
  if p1 is not None:
   trials.append({'sid':sid,'j':j,'t':action,'exit':action+HOLD,'block':j//168,'iso':iso(action),'model':p1,'baseline':p0,'loading_fast':bfast,'loading_slow':bslow,'factor':f,'new_feature':x[-1],'y':y,'atr_price':atr,'train_n':model.n})
 return trials,dict(why)

def metrics(trials):
 rr=[x for x in trials if x['y'] is not None];n=len(rr)
 return {'predictions':len(trials),'supported':n,'exit_censored':len(trials)-n,'direction_disagreements':sum(sign(x['model'])!=sign(x['baseline']) for x in rr),
  'model_gross_sum_bps':sum(sign(x['model'])*x['y'] for x in rr),'baseline_gross_sum_bps':sum(sign(x['baseline'])*x['y'] for x in rr),
  'model_mean_gross_bps':sum(sign(x['model'])*x['y'] for x in rr)/n if n else None,'baseline_mean_gross_bps':sum(sign(x['baseline'])*x['y'] for x in rr)/n if n else None,
  'paired_increment_bps':sum((sign(x['model'])-sign(x['baseline']))*x['y'] for x in rr)/n if n else None,
  'MSE_improvement_bps2':sum((x['y']-x['baseline'])**2-(x['y']-x['model'])**2 for x in rr)/n if n else None}

def stop_path(direction,path,distance):
 if not np.isfinite(path).all():return None
 p0=float(path[0,0]);stop=p0-direction*distance
 for n,(op,hi,lo,cl) in enumerate(path):
  if (direction>0 and op<=stop) or (direction<0 and op>=stop):return {'price':float(op),'kind':'BAR_OPEN_GAP_STOP','bar':n,'stop':stop}
  if (direction>0 and lo<=stop) or (direction<0 and hi>=stop):return {'price':float(stop),'kind':'BAR_RANGE_STOP_PROXY','bar':n,'stop':stop}
 return {'price':float(path[-1,3]),'kind':'FIXED_60MIN_CLOSE_REFERENCE','bar':11,'stop':stop}
