"""Independent array reconstruction of completed-minute features and rolling OLS.
No quote source is a broker fill. Reference-price errors are not account P&L.
"""
from collections import defaultdict
from decimal import Decimal as D,localcontext,ROUND_HALF_UP
import hashlib,json
from pathlib import Path

def fmt(x):return format(x.quantize(D('.00000001'),rounding=ROUND_HALF_UP),'.8f')
def reference(paths):
 with localcontext() as c:
  c.prec=50
  return _reference(paths)
def _reference(paths):
 samples=[];last_bucket=None;last_x=last_mid=None;all_forecasts=[];segments=[];digest=hashlib.sha256();decisions=hashlib.sha256();audits=[];seq=0;flat_due=next_allowed=0
 for path in paths:
  events=defaultdict(lambda:{'bid':set(),'ask':set()});rows=0;prev=-1
  with Path(path).open() as f:
   for line in f:
    e=json.loads(line);t=e['t'];v=e['raw'];side=e['side']
    assert set(e)=={'t','side','raw'} and type(t)is int and type(v)is int and t>=prev and v>0 and side in ('bid','ask')
    prev=t;events[t][side].add(v);rows+=1
  # Build minute arrays independently from streaming C# state.
  book={};side_times={};minutes=defaultdict(lambda:{'signed':0,'count':0,'mid':None});snapshots=[]
  for t,sides in sorted(events.items()):
   bucket=t//60000*60000;m=minutes[bucket]
   for side,values in sides.items():
    if values:
     v=next(iter(values)) if len(values)==1 else None;prior=book.get(side)
     if v is not None and prior is not None and v!=prior:m['signed']+=(1 if v>prior else -1);m['count']+=1
     book[side]=v;side_times[side]=t
   b,a=book.get('bid'),book.get('ask')
   if b is not None and a is not None and a>=b:m['mid']=D(a+b)/200000
   healthy=b is not None and a is not None and a>b and t-side_times['bid']<=5000 and t-side_times['ask']<=5000
   snapshots.append((t,b,a,healthy))
  keys=sorted(minutes)
  # A feature is exposed only at the first actual quote of the next observed minute.
  first_times={}
  for t,*_ in snapshots:first_times.setdefault(t//60000*60000,t)
  forecasts=[];by_available={}
  for old,new in zip(keys,keys[1:]):
   m=minutes[old]
   if m['mid'] is None:continue
   x=D(m['signed'])/m['count'] if m['count'] else D(0);mid=m['mid']
   if last_bucket is not None and old==last_bucket+60000:
    samples.append((last_x,10000*(mid-last_mid)/last_mid));samples=samples[-256:]
   last_bucket,last_x,last_mid=old,x,mid
   if len(samples)<64:continue
   # centered full-array covariance, no incremental queue/sum implementation
   mx=sum(z[0] for z in samples)/len(samples);my=sum(z[1] for z in samples)/len(samples)
   beta=sum((u-mx)*(v-my) for u,v in samples)/(1+sum((u-mx)**2 for u,v in samples));pred=my+beta*(x-mx)
   t=first_times[new];rec={'available':t,'bucket':old,'samples':len(samples),'x':fmt(x),'prediction':fmt(pred),'mid':fmt(mid)}
   forecasts.append(rec);by_available[t]=(rec,pred)
   digest.update(f'{t}|{old}|{len(samples)}|{fmt(x)}|{fmt(pred)}\n'.encode())
  count=0;bad=0
  for t,b,a,healthy in snapshots:
   if not healthy:bad+=1;continue
   if flat_due and t>=flat_due:
    seq+=1;decisions.update(f'{t}|{seq}|0\n'.encode());flat_due=0;next_allowed=max(next_allowed,t+5000);continue
   f=by_available.get(t)
   if f is None or t//60000*60000!=f[0]['bucket']+60000 or t<next_allowed or flat_due:continue
   from datetime import datetime,timezone
   utc=datetime.fromtimestamp(t/1000,timezone.utc)
   if utc.weekday()>=5 or not 7<=utc.hour<15:continue
   bid,ask=D(b)/100000,D(a)/100000;hurdle=10000*(ask-bid+D('.00004')+D('.00006'))/((ask+bid)/2)
   direction=1 if f[1]>hurdle else -1 if f[1]<-hurdle else 0
   if not direction:continue
   audits.append({'t':t,'direction':direction,'prediction':fmt(f[1]),'hurdle':fmt(hurdle)});count+=1;seq+=1
   decisions.update(f'{t}|{seq}|{direction}\n'.encode());flat_due=t+60000;next_allowed=t+65000
  all_forecasts.extend(forecasts);segments.append({'rows':rows,'predictions':len(forecasts),'signals':count,'invalid':bad,'forecasts':forecasts,'input_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()})
 return {'summaries':segments,'audits':audits,'prediction_sha256':digest.hexdigest(),'decision_sha256':decisions.hexdigest(),'learned_samples':len(samples)}

def forecast_errors(summaries):
 """All forecasts, including absent next-minute targets; no candidate rescue.
 Error comparison uses a zero-return CASH forecast, not a traded account.
 """
 output=[]
 for segment in summaries:
  seq=segment['forecasts'];index={x['bucket']:x for x in seq};mse=D(0);zero=D(0);n=0;missing=0;directional=D(0)
  for f in seq:
   future=index.get(f['bucket']+60000)
   if future is None:missing+=1;continue
   target=10000*(D(future['mid'])-D(f['mid']))/D(f['mid']);pred=D(f['prediction']);n+=1
   mse+=(pred-target)**2;zero+=target**2;directional+=(target if pred>0 else -target if pred<0 else 0)
  output.append({'forecasts':len(seq),'matched':n,'missing_target':missing,'mse_model_bps2':str(mse/n) if n else None,'mse_zero_bps2':str(zero/n) if n else None,
   'mean_signed_midpoint_response_bps':str(directional/n) if n else None,'model_beats_zero_mse':n>0 and mse<zero,
   'executable_return_or_account_pnl':False})
 return output

def reconcile(actual,expected):
 for key in ('summaries','audits','prediction_sha256','decision_sha256','learned_samples'):
  if actual[key]!=expected[key]:raise ValueError('INNOVATION_REFERENCE_'+key)
 if actual['initial_funding_count']!=1 or actual['initial_capital_eur']!=200:raise ValueError('INNOVATION_CAPITAL')
 if actual['account'] is not None:
  a=actual['account'];cash=D(200)
  for t in a['Ledger']:
   cash+=D(str(t['GrossEur']))-D(str(t['CommissionEur']))
   if abs(cash-D(str(t['CashEur'])))>D('.0000001'):raise ValueError('INNOVATION_LEDGER_CASH')
  if abs(cash-D(str(a['FinalCashEur'])))>D('.0000001'):raise ValueError('INNOVATION_TERMINAL_CASH')
 return True
