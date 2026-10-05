"""Frozen causal leave-one-out residual information; real opening has no authority here."""
import csv,hashlib,json,math,random,statistics
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
HORIZONS=(12,48)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
def read_series(path):
 out={}
 with Path(path).open() as f:
  for row in csv.DictReader(f):
   t=int(datetime.fromisoformat(row['time_utc'].replace('Z','+00:00')).timestamp())+300;p=float(row['close'])
   require(t not in out and t%300==0 and math.isfinite(p) and p>0,'invalid authentic completed M5 bar');out[t]=p
 require(list(out)==sorted(out),'nonchronological M5');return out

def hour_returns(series,t):
 # Every close in the path must exist; gaps are never filled.
 if not all(t-k*300 in p for p in series.values() for k in range(13)):return None
 return {sid:math.log(p[t]/p[t-3600]) for sid,p in series.items()}
def leave_out(values,sid):
 require(sid in values and len(values)==6,'exact six-member context');return math.fsum(v for k,v in sorted(values.items()) if k!=sid)/5

def fit_reference(history,sid):
 y=[r[sid] for r in history];f=[leave_out(r,sid) for r in history];n=len(y);require(n>=288,'factor calibration support')
 my=statistics.fmean(y);mf=statistics.fmean(f);vf=math.fsum((x-mf)**2 for x in f)
 require(vf>0,'singular factor');beta=math.fsum((a-my)*(b-mf) for a,b in zip(y,f))/vf;alpha=my-beta*mf
 sigma=math.sqrt(math.fsum((a-alpha-beta*b)**2 for a,b in zip(y,f))/(n-2));require(math.isfinite(sigma) and sigma>0,'singular residual')
 return {'alpha':alpha,'beta':beta,'sigma':sigma,'training_hours':n}
def fit(history,sid):
 # Independent sufficient-statistic implementation, checked against reference.
 n=len(history);require(n>=288,'factor calibration support');y=[r[sid] for r in history];f=[leave_out(r,sid) for r in history]
 sy=math.fsum(y);sf=math.fsum(f);sff=math.fsum(x*x for x in f);syf=math.fsum(a*b for a,b in zip(y,f));v=sff-sf*sf/n;require(v>0,'singular factor')
 beta=(syf-sy*sf/n)/v;alpha=(sy-beta*sf)/n;sigma=math.sqrt(math.fsum((a-alpha-beta*b)**2 for a,b in zip(y,f))/(n-2));require(sigma>0 and math.isfinite(sigma),'singular residual')
 return {'alpha':alpha,'beta':beta,'sigma':sigma,'training_hours':n}

def events(series,design,context):
 require(design['training_end']+48*300<design['evaluation_start'],'disjoint estimation/evaluation purge')
 ids=design['memberships'][context];require(set(series)==set(ids),'fixed context membership')
 training=[r for t in sorted(series[ids[0]]) if design['training_start']+3600<=t<=design['training_end'] and t%3600==0 and (r:=hour_returns(series,t)) is not None]
 models={sid:fit(training,sid) for sid in ids}
 # Membership and coefficients are frozen using only disjoint prefix history.
 out=[]
 for t in sorted(series[ids[0]]):
  if not design['evaluation_start']<=t<=design['evaluation_end'] or t%14400:continue
  r=hour_returns(series,t)
  if r is None:continue
  for sid in sorted(ids):
   m=models[sid];z=(r[sid]-m['alpha']-m['beta']*leave_out(r,sid))/m['sigma']
   require(math.isfinite(z),'nonfinite causal innovation')
   if abs(abs(z)-2)<1e-10:raise ValueError('numerically ambiguous frozen boundary')
   if abs(z)<2:continue
   # No future PRICE accessor in this producer: timestamp sets only.
   retained={str(h):all(t+k*300 in p for p in series.values() for k in range(1,h+1)) for h in HORIZONS}
   out.append({'context':context,'symbol_id':sid,'time':t,'week':(t-design['evaluation_start'])//604800,'direction':1 if z>0 else -1,'model':m,'retained':retained})
 return out,models

def geometry(events,h):
 byweek=defaultdict(set);counts=defaultdict(int);retained=defaultdict(int)
 for e in events:
  counts[e['symbol_id']]+=1
  if e['retained'][str(h)]:byweek[e['week']].add(e['symbol_id']);retained[e['symbol_id']]+=1
 weeks=sorted(w for w,s in byweek.items() if len(s)>=4);blocks=sorted(b for b in range(22) if 2*b in weeks and 2*b+1 in weeks)
 return {'valid_weeks':weeks,'two_week_blocks':blocks,'events':len(events),'events_by_symbol':dict(counts),'retained_by_symbol':dict(retained),'support_pass':len(weeks)>=24 and len(blocks)>=12 and len(counts)==6 and all(counts[s]>=20 and retained[s]/counts[s]>=0.8 for s in counts) and all(sum(b//8==q for b in blocks)>=3 for q in range(3))}

def prepare(series_by_context,design):
 all_events=[];summaries={};models={}
 for c in sorted(design['memberships']):
  es,m=events(series_by_context[c],design,c);all_events.extend(es);models[c]=m;summaries[c]={str(h):geometry(es,h) for h in HORIZONS}
 joint=sorted(set.intersection(*(set(g['two_week_blocks']) for hs in summaries.values() for g in hs.values())))
 eligible=all(g['support_pass'] for hs in summaries.values() for g in hs.values()) and len(joint)>=12 and joint==list(range(joint[0],joint[-1]+1))
 return {'joint_calendar_blocks':joint,'inference_geometry_eligible':eligible,'schema':'mxm.v4.factor-residual-support.v1','design_sha256':sha(canonical(design)),'event_geometry_sha256':sha(canonical(all_events)),'models_sha256':sha(canonical(models)),'contexts':summaries,'response_opened':False,'broker_contacts':0,'historical_requests':0},all_events

def response(e,h,series):
 # This accessor is used ONLY by explicit synthetic evaluator tests in this task.
 require(h in HORIZONS and e['retained'][str(h)],'right censored response');t=e['time'];sid=e['symbol_id'];m=e['model']
 vals={k:math.log(p[t+h*300]/p[t]) for k,p in series.items()};residual=vals[sid]-m['beta']*leave_out(vals,sid)-m['alpha']*(h/12)
 return e['direction']*residual/(m['sigma']*math.sqrt(h/12))

def block_means(events,h,series_by_context,context):
 grouped=defaultdict(list);es=[e for e in events if e['context']==context];g=geometry(es,h);require(g['support_pass'],'DATA_LIMITED_UNTESTED_NOT_NULL')
 for e in es:
  if e['retained'][str(h)]:grouped[(e['week'],e['symbol_id'],e['direction'])].append(response(e,h,series_by_context[context]))
 weekly={}
 for w in g['valid_weeks']:
  symbols=[]
  for sid in sorted({s for ww,s,d in grouped if ww==w}):
   dirs=[statistics.fmean(grouped[w,sid,d]) for d in (-1,1) if (w,sid,d) in grouped];symbols.append(statistics.fmean(dirs))
  weekly[w]=statistics.fmean(symbols)
 return {b:(weekly[2*b]+weekly[2*b+1])/2 for b in g['two_week_blocks']}

def hac_se(values):
 n=len(values);require(n>=12,'block support');mu=statistics.fmean(values);v=[x-mu for x in values];gamma=math.fsum(x*x for x in v)/n
 for lag in (1,2):gamma+=2*(1-lag/3)*math.fsum(v[i]*v[i-lag] for i in range(lag,n))/n
 require(gamma>0 and math.isfinite(gamma),'degenerate HAC');return math.sqrt(gamma/n)
def hac_t(values):return statistics.fmean(values)/hac_se(values)
def inference(leaves,seed=20261005,resamples=1023):
 # Common calendar blocks preserve cross-context/horizon dependence.
 ids=sorted(set.intersection(*(set(v) for v in leaves.values())));require(len(ids)>=12 and ids==list(range(ids[0],ids[-1]+1)),'joint contiguous block support')
 keys=sorted(leaves);vectors={k:[leaves[k][i] for i in ids] for k in keys};observed={k:hac_t(v) for k,v in vectors.items()};center={k:[x-statistics.fmean(v) for x in v] for k,v in vectors.items()};rng=random.Random(seed);maxima=[];se={k:hac_se(v) for k,v in vectors.items()}
 for _ in range(resamples):
  indices=[]
  while len(indices)<len(ids):
   start=rng.randrange(len(ids));indices.extend((start+j)%len(ids) for j in range(3))
  maxima.append(max(abs(hac_t([center[k][i] for i in indices[:len(ids)]])) for k in keys))
 adjusted={k:(1+sum(m>=abs(t) for m in maxima))/(resamples+1) for k,t in observed.items()}
 return {'adjusted_pvalues':adjusted,'statistics':observed,'joint_calendar_blocks':ids,'bootstrap':'CENTERED_CIRCULAR_MBB_LENGTH3_SHARED_ALL4_LEAVES_HAC_LAG2','alpha':0.01,'assumption':'short-memory approximately stationary block vectors; asymptotic not finite-sample exact'}

def evaluate_synthetic_only(series,design):
 require(design.get('synthetic_only') is True,'REAL_RESPONSE_NOT_AUTHORIZED')
 support,es=prepare(series,design);leaves={c+':'+str(h):block_means(es,h,series,c) for c in sorted(series) for h in HORIZONS};result=inference(leaves);gate=decision(leaves,result)
 survivors=[]
 for lead in gate['eligible_horizons']:
  if all(asset_breadth(es,lead['horizon'],series,c,lead['direction']) for c in series):survivors.append(lead)
 gate['eligible_horizons']=survivors;gate['classification']='REPLICATED_INFORMATION_LEAD_DISJOINT_CONFIRMATION_REQUIRED' if survivors else 'NO_REPLICATED_DEVELOPMENT_LEAD_NOT_GLOBAL_NULL'
 return {'support':support,'inference':result,'decision':gate}


def decision(leaves,result):
    keys=sorted(leaves);contexts=sorted({k.split(':')[0] for k in keys});survivors=[]
    require(len(contexts)==2 and len(keys)==4,'entire prospectively frozen family')
    for h in HORIZONS:
        names=[c+':'+str(h) for c in contexts];signs=[1 if statistics.fmean(leaves[k].values())>0 else -1 for k in names]
        if signs[0]!=signs[1] or not all(result['adjusted_pvalues'][k]<=.01 for k in names):continue
        stable=True
        for k in names:
            for q in range(3):
                values=[v for b,v in leaves[k].items() if b//8==q]
                if len(values)<3 or signs[0]*statistics.fmean(values)<=0:stable=False
        if stable:survivors.append({'horizon':h,'direction':signs[0]})
    return {'classification':'REPLICATED_INFORMATION_LEAD_PENDING_ASSET_BREADTH_AND_DISJOINT_CONFIRMATION' if survivors else 'NO_REPLICATED_DEVELOPMENT_LEAD_NOT_GLOBAL_NULL','eligible_horizons':survivors,'candidate_promotion_authorized':False,'economic_null_claimed':False,'orders_authorized':False}


def asset_breadth(events,h,series,context,direction):
    units=defaultdict(list)
    for e in events:
        if e['context']==context and e['retained'][str(h)]:units[e['symbol_id'],e['week'],e['direction']].append(response(e,h,series[context]))
    symbols=sorted(series[context]);passed=0
    for sid in symbols:
        weeks=[]
        for w in sorted({w for s,w,d in units if s==sid}):
            dirs=[statistics.fmean(units[sid,w,d]) for d in (-1,1) if (sid,w,d) in units];weeks.append(statistics.fmean(dirs))
        if weeks and direction*statistics.fmean(weeks)>0:passed+=1
    return passed>=4
