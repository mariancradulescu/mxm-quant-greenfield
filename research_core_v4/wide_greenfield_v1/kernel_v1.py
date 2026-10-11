"""Frozen nonlinear return-distribution and bipower magnitude information laws."""
import bisect,math,statistics
from collections import defaultdict,Counter
from datetime import datetime,timezone
import numpy as np
HOUR=3600
START=int(datetime(2024,9,16,tzinfo=timezone.utc).timestamp())
SCORE=int(datetime(2025,1,6,tzinfo=timezone.utc).timestamp())
END=int(datetime(2026,9,17,tzinfo=timezone.utc).timestamp())
ORIGINAL=int(datetime(2026,8,20,tzinfo=timezone.utc).timestamp())
NAMES=('NONLINEAR_MULTISCALE_RETURN_DISTRIBUTION','BIPOWER_JUMP_MAGNITUDE_INFORMATION')
QUOTE_WEEKS=('2025-W05','2025-W17','2025-W29','2025-W41','2026-W01','2026-W13','2026-W25','2026-W37')
def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
def weeks():
 return sorted({iso(t) for t in range(SCORE,END,86400) if t+7*86400<=END and datetime.fromtimestamp(t,timezone.utc).weekday()==0})
def sign(x):return int(x>0)-int(x<0)
def horizon(asset_class):return 24 if any(w in asset_class.lower() for w in ('stock','equit','etf')) else 8

def features(bars,t,times=None):
 times=sorted(bars) if times is None else times;i=bisect.bisect_left(times,t);tt=times[max(0,i-97):i]
 if len(tt)<97 or tt[-1]!=t-HOUR or t-tt[0]>14*86400:return None
 rr=np.diff(np.log([bars[x][3] for x in tt]));v=float(np.sum(rr*rr))
 if not v>1e-14:return None
 scale=math.sqrt(v/96);v8=float(np.mean(rr[-8:]**2));v96=v/96
 sem=float(np.sum(rr[rr<0]**2))/v
 trend=float(np.sum(rr[-24:]))/(math.sqrt(24)*scale)
 gap=math.log(bars[tt[-1]][0]/bars[tt[-2]][3])/scale
 v24=float(np.sum(rr[-24:]**2));bv=math.pi/2*float(np.sum(np.abs(rr[-24:][1:])*np.abs(rr[-24:][:-1])))*24/23
 jump=max(0.,v24-bv)/v24 if v24 else 0.
 return {'return_state':[max(-6.,min(6.,trend)),max(-6.,min(6.,math.log(max(v8,1e-14)/v96))),2*sem-1,max(-6.,min(6.,gap))], 'magnitude_state':[max(-6.,min(6.,math.log(max(v8,1e-14)/v96))),jump,2*sem-1], 'price':bars[tt[-1]][3],'scale_bps':10000*scale,'last_prior_open':tt[-1]}

def label(bars,t,h):
 a=bars.get(t-HOUR);b=bars.get(t+(h-1)*HOUR)
 if a is None or b is None:return None
 return math.log(b[3]/a[3])*10000

def forecast(state,training,mode):
 if len(training)<128:return None
 zz=training[-768:];xx=np.asarray([x[1] for x in zz]);dd=np.sum((xx-np.asarray(state))**2,axis=1)
 ii=np.argsort(dd,kind='stable')[:32];yy=np.asarray([zz[int(i)][2] for i in ii]);all_y=np.asarray([x[2] for x in zz])
 if mode=='magnitude':yy=np.abs(yy);all_y=np.abs(all_y)
 mu=float(np.mean(yy));base=float(np.mean(all_y));d=sign(mu)
 loss=float(np.quantile(-d*yy,.95,method='higher')) if mode=='return' else None
 return {'model':mu,'baseline':base,'d':d if mode=='return' else 0,'b':sign(base) if mode=='return' else 0,'tail95_bps':max(0.,loss) if loss is not None else None,'neighbors':32,'mature_training':len(zz)}

def observations(bars,asset_class):
 # Hourly forecast clocks are dependent; executable allocation separately enforces holding horizons.
 times=sorted(bars);fs={t:features(bars,t,times) for t in range(max(START,min(times)+HOUR),END,HOUR)} if times else {}
 out=[]
 for fam in NAMES:
  h=horizon(asset_class) if fam==NAMES[0] else 2;mode='return' if fam==NAMES[0] else 'magnitude';key='return_state' if mode=='return' else 'magnitude_state'
  train=[];pending=[];p=0
  for t,f in sorted(fs.items()):
   # One extra hour of publication allowance for labels. No current/exit label drives entry forecasts.
   while p<len(pending) and pending[p][0]+h*HOUR<t:
    u,x,y=pending[p];p+=1
    if y is not None:train.append((u,x,y))
   fc=forecast(f[key],train,mode) if f else None
   if t>=SCORE:out.append({'t':t,'family':fam,'h':h,'feature':f,'forecast':fc,'y':label(bars,t,h),'iso':iso(t),'block':(t-ORIGINAL)//604800 if ORIGINAL<=t<END else None})
   if f and t//HOUR%6==0:pending.append((t,f[key],label(bars,t,h)))
 return out

def stats(rows,fam):
 valid=[r for r in rows if r['forecast'] and r['y'] is not None];forecasted=[r for r in rows if r['forecast']]
 z={'calendar':len(rows),'feature_valid':sum(r['feature'] is not None for r in rows),'forecasted':len(forecasted),'paired':len(valid),'exit_censored':len(forecasted)-len(valid),'abstention_reasons':dict(Counter('FEATURE_GAP' if not r['feature'] else 'MATURE_SUPPORT_LT128' if not r['forecast'] else 'FORECAST' for r in rows))}
 if fam==NAMES[0]:
  z.update(model_gross_mean_bps=statistics.mean(r['forecast']['d']*r['y'] for r in valid) if valid else None,baseline_gross_mean_bps=statistics.mean(r['forecast']['b']*r['y'] for r in valid) if valid else None,increment_mean_bps=statistics.mean((r['forecast']['d']-r['forecast']['b'])*r['y'] for r in valid) if valid else None)
 else:z.update(model_gross_mean_bps=None,baseline_gross_mean_bps=None,increment_mean_bps=None)
 z['mean_model_prediction_bps']=statistics.mean(r['forecast']['model'] for r in forecasted) if forecasted else None
 z['mean_baseline_prediction_bps']=statistics.mean(r['forecast']['baseline'] for r in forecasted) if forecasted else None
 z['paired_mse_improvement_bps2']=statistics.mean((abs(r['y']) if fam==NAMES[1] else r['y'])**2-2*(abs(r['y']) if fam==NAMES[1] else r['y'])*r['forecast']['baseline']+r['forecast']['baseline']**2-((abs(r['y']) if fam==NAMES[1] else r['y'])-r['forecast']['model'])**2 for r in valid) if valid else None
 z['actual_abs_return_mean_bps']=statistics.mean(abs(r['y']) for r in valid) if valid else None
 return z

def report(rows,fam):
 return {'global':stats(rows,fam),'blocks':[stats([r for r in rows if r['block']==b],fam) for b in range(4)],'complete_weeks':{w:stats([r for r in rows if r['iso']==w],fam) for w in weeks()}}

def clustered(rows,fam):
 byclock=defaultdict(list)
 for r in rows:
  if r['forecast'] and r['y'] is not None:byclock[r['t']].append(r)
 byweek=defaultdict(list)
 for t,rr in byclock.items():
  f=[r['forecast'] for r in rr];y=[r['y'] for r in rr];mse=np.mean([((abs(v) if fam==NAMES[1] else v)-q['baseline'])**2-((abs(v) if fam==NAMES[1] else v)-q['model'])**2 for q,v in zip(f,y)])
  inc=np.mean([(q['d']-q['b'])*v for q,v in zip(f,y)]) if fam==NAMES[0] else 0.
  byweek[iso(t)].append((float(mse),float(inc)))
 zz=[np.mean(byweek[w],axis=0) for w in weeks() if byweek[w]];nn=len(zz);a=np.asarray(zz);lower=None
 if nn>=26:
  rng=np.random.default_rng(20261012);samples=[]
  for _ in range(2000):
   ii=np.concatenate([(np.arange(4)+int(v))%nn for v in rng.integers(0,nn,size=math.ceil(nn/4))])[:nn];samples.append(np.mean(a[ii],axis=0))
  lower=np.quantile(samples,.05/3,axis=0).tolist()
 halves=[np.mean(a[:nn//2],axis=0).tolist(),np.mean(a[nn//2:],axis=0).tolist()] if nn>=2 else []
 lead=bool(lower and lower[0]>0 and (fam==NAMES[1] or lower[1]>0) and all(x[0]>0 and (fam==NAMES[1] or x[1]>0) for x in halves))
 return {'supported_weeks':nn,'equal_clock_equal_week_mse_improvement_bps2':float(np.mean(a[:,0])) if nn else None,'equal_clock_equal_week_increment_bps':float(np.mean(a[:,1])) if nn and fam==NAMES[0] else None,'lower_one_sided_family3':[float(x) for x in lower] if lower else None,'temporal_halves':halves,'exploratory_information_lead':lead,'alpha_validated':False,'independent_N':'UNIDENTIFIED_SERIAL_CROSS_ASSET;4_WEEK_BOOTSTRAP_DESCRIPTIVE_PRIOR_SELECTION_NOT_ERASED'}
