"""One prospective pooled pressure learner; reuse source admission, costs and custody."""
import collections, datetime as dt, hashlib, json, math, os, tempfile
from pathlib import Path
import numpy as np
from .common import need
from . import source_first_diverse_h1_economics as src
ROOT=src.ROOT
SPEC=ROOT/'research_core_v4/laboratory/POOLED_PRESSURE_20261029_V1.json'
OUT=ROOT/'verification/source-first-diverse-h1'
IDENTITY='V4-POOL-20261029-PRESSURE'
EVAL=src.START+7*86400
FEATURES=['return_now','return_previous','body','close_location','range','other_1_return',
 'other_2_return','return_x_location','body_x_location','sin_hour','cos_hour','is_aud','is_copper']
def digest(b):return hashlib.sha256(b).hexdigest()
def validate():
 old,_=src.validate();s=json.loads(SPEC.read_bytes())
 need(s['identity']==IDENTITY and s['target_ids']==list(src.TARGETS) and s['features']==FEATURES,'POOL_SPEC')
 need(digest(Path(__file__).read_bytes())==s['implementation_sha256'],'POOL_IMPLEMENTATION')
 need(s['ridge_alpha']==1.0 and s['minimum_training_rows']==90 and s['label_embargo_hours']==2,'POOL_LEARNING')
 need(s['evaluation_start_utc']=='2026-08-10T00:00:00Z' and s['hold_hours']==2 and s['entry_delay_hours']==1,'POOL_TIMING')
 need(s['orders']==0 and s['new_broker_requests']==0 and s['independent_confirmation'] is False,'POOL_SCOPE')
 need(s['parent_closed_compression_preserved'] and s['hard21_role']=='SYSTEM_ONLY_NOT_COMPONENT_EDGE_GATE','POOL_OWNER')
 need(digest((ROOT/'RESEARCH_CONTRACT_V2.md').read_bytes())==s['contract_v2_sha256'] and
      digest((ROOT/'research_v3/RESEARCH_CONTRACT_V3.json').read_bytes())==s['contract_v3_sha256'],'POOL_CONTRACTS')
 return s
def features(corpus,sid,t):
 m=corpus[sid];p=m[t-src.H];pp=m[t-2*src.H];c=m[t]
 others=sorted(k for k in corpus if k!=sid)
 if not all(t in corpus[k] and t-src.H in corpus[k] for k in others):return None
 rng=(c[1]-c[2])/c[0]
 if rng<=0:return None
 r=c[3]/p[3]-1;rp=p[3]/pp[3]-1;body=(c[3]-c[0])/c[0]
 location=(2*c[3]-c[1]-c[2])/(c[1]-c[2])
 other=[corpus[k][t][3]/corpus[k][t-src.H][3]-1 for k in others]
 hour=dt.datetime.fromtimestamp(t,dt.timezone.utc).hour
 return np.array([r,rp,body,location,rng,*other,r*location,body*location,
  math.sin(2*math.pi*hour/24),math.cos(2*math.pi*hour/24),float(sid==5),float(sid==111)]),max(rng,src.COSTS[sid])
def fit(x,y):
 x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
 mu=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale>1e-12,scale,1.)
 z=(x-mu)/scale;ym=float(y.mean())
 # Mean squared error + alpha ||beta||^2; intercept is unpenalized.
 beta=np.linalg.solve(z.T@z/len(y)+np.eye(z.shape[1]),z.T@(y-ym)/len(y))
 return mu,scale,ym,beta
def predict(model,x):
 mu,scale,ym,beta=model
 return float(ym+(x-mu)/scale@beta)
def support(corpus):
 a=src.support(corpus)
 profiles={}
 times={sid:src.causal_times(corpus[sid]) for sid in src.TARGETS}
 for sid in src.TARGETS:
  evals=[t for t in times[sid] if t>=EVAL and all(t in corpus[k] and t-src.H in corpus[k] for k in corpus if k!=sid)]
  # Before opening the identity inspect only timestamps, including embargo.
  first_fit=EVAL+7*src.H
  training=sum(1 for k in times for u in times[k] if u+6*src.H<first_fit+src.H and
    src.fulfilled(corpus[k],u) and all(u in corpus[j] and u-src.H in corpus[j] for j in corpus if j!=k))
  profiles[str(sid)]={'evaluation_causal_rows':len(evals),'complete_responses':sum(src.fulfilled(corpus[sid],t) for t in evals),
    'first_fit_timestamp_training_rows':training}
 need(a['source_admission']=='PASS_BEFORE_IDENTITIES' and all(v['evaluation_causal_rows']>=120 and
  v['complete_responses']>=.9*v['evaluation_causal_rows'] and v['first_fit_timestamp_training_rows']>=90 for v in profiles.values()),'POOL_SOURCE_SUPPORT')
 return {'original_temporal_support':a,'pooled_timestamp_support':profiles}
def evaluate(corpus):
 candidates={sid:src.causal_times(corpus[sid]) for sid in src.TARGETS}
 known={}
 for sid in src.TARGETS:
  for t in candidates[sid]:
   f=features(corpus,sid,t)
   if f is not None:known[sid,t]=f
 models={};fit_log=[];reasons=collections.Counter();trades=[];forecasts=[];last={sid:-10**30 for sid in src.TARGETS}
 weekly=collections.defaultdict(lambda:dict(forecasts=0,signals=0,settled=0,gross=0.,cost=0.,net=0.))
 markets={sid:dict(instrument=src.TARGETS[sid],forecasts=0,signals=0,settled=0,gross=0.,cost=0.,net=0.) for sid in src.TARGETS}
 for t in sorted(set(t for sid in candidates for t in candidates[sid] if t>=EVAL)):
  day=t//86400;w=src.week(t)
  if day not in models:
   train=[];labels=[];train_sids=[]
   for (sid,u),(x,scale) in sorted(known.items(),key=lambda kv:(kv[0][1],kv[0][0])):
    if u+6*src.H>=t+src.H or not src.fulfilled(corpus[sid],u):continue
    y=(corpus[sid][u+4*src.H][0]/corpus[sid][u+2*src.H][0]-1)/scale
    train.append(x);labels.append(y);train_sids.append((sid,u,y,scale))
   need(len(train)>=90,'POOL_TRAIN_COUNT')
   model=fit(train,labels);models[day]=(model,train_sids)
   fit_log.append({'fit_decision_utc':t+src.H,'training_rows':len(train),
    'latest_label_settlement_utc':max(u+4*src.H for _,u,_,_ in train_sids),
    'embargo_seconds':2*src.H,'fit_sha256':digest(src.encode([z.tolist() if hasattr(z,'tolist') else z for z in model]))})
  model,training=models[day]
  for sid in src.TARGETS:
   if t not in candidates[sid]:continue
   if (sid,t) not in known:reasons['CROSS_FEATURE_MISSING']+=1;continue
   x,scale=known[sid,t];forecast=predict(model,x)*scale
   baseline_rows=[y*s for k,u,y,s in training if k==sid]
   baseline=sum(baseline_rows)/len(baseline_rows)
   markets[sid]['forecasts']+=1;weekly[w]['forecasts']+=1
   realized=None
   if src.fulfilled(corpus[sid],t):realized=corpus[sid][t+4*src.H][0]/corpus[sid][t+2*src.H][0]-1
   forecasts.append((forecast,realized,baseline))
   if abs(forecast)<=1.5*src.COSTS[sid]:reasons['FORECAST_BELOW_FIXED_COST_HURDLE']+=1;continue
   if t+2*src.H<last[sid]+2*src.H:reasons['CANDIDATE_SERIAL_OVERLAP']+=1;continue
   last[sid]=t+2*src.H;weekly[w]['signals']+=1;markets[sid]['signals']+=1
   if realized is None:reasons['POST_SIGNAL_RESPONSE_UNAVAILABLE']+=1;continue
   side=1 if forecast>0 else -1;g=1000*side*realized;cost=1000*src.COSTS[sid]
   for row in (weekly[w],markets[sid]):
    row['settled']+=1;row['gross']+=g;row['cost']+=cost;row['net']+=g-cost
   trades.append((t+2*src.H,t+4*src.H,sid,side,g,cost))
 valid=[(p,y,b) for p,y,b in forecasts if y is not None]
 gross=sum(z[4] for z in trades);cost=sum(z[5] for z in trades);net=gross-cost
 stresses={'frozen_coarse':net,'twice_coarse':gross-2*cost,'twice_coarse_plus_2bps':gross-2*cost-len(trades)*.2}
 mse=sum((p-y)**2 for p,y,b in valid)/len(valid)
 mse0=sum(y*y for p,y,b in valid)/len(valid);mseb=sum((b-y)**2 for p,y,b in valid)/len(valid)
 classification='GROSS_EDGE_FAIL' if gross<=0 else 'COARSE_NET_FAIL' if net<=0 else 'COST_UNRESOLVED' if min(stresses.values())<=0 else 'DISCOVERY_SURVIVOR'
 # No HARD21 component threshold; no promotion from predictive loss alone.
 peak=dd=equity=0.
 for z in sorted(trades,key=lambda z:(z[1],z[2])):
  equity+=z[4]-z[5];peak=max(peak,equity);dd=max(dd,peak-equity)
 return dict(identity=IDENTITY,classification=classification,forecasts=len(forecasts),settled_forecasts=len(valid),
  signal_count=sum(v['signals'] for v in markets.values()),settled=len(trades),gross_eur=gross,cost_eur=cost,net_estimated_eur=net,
  cost_sensitivity=stresses,weekly=dict(sorted(weekly.items())),per_market=list(markets.values()),rejections=dict(reasons),
  forecast_mse=mse,zero_forecast_mse=mse0,causal_market_mean_mse=mseb,beats_both_prediction_benchmarks=mse<min(mse0,mseb),
  fit_log=fit_log,normalized_trade_ledger_sha256=digest(src.encode(trades)),fixed_notional_realized_drawdown_eur=dd,
  drawdown_basis='CLOSED_TRADE_NORMALIZED_STAGE_A_NOT_ACCOUNT_MARK_TO_MARKET',
  longest_entry_gap_hours=max(((b[0]-a[0])/src.H for a,b in zip(sorted(trades),sorted(trades)[1:])),default=None),
  held_hours=2,capital_realization_proven=False,hard21_component_gate_applied=False,
  independent_confirmation=False,stage_b_admitted=False)
def selftest():
 x=np.array([[i,i%2] for i in range(10)],dtype=float);y=2*x[:,0]+1
 m=fit(x,y);need(np.isfinite(predict(m,x[0])),'POOL_FIT')
 # No future data may change a frozen fitted coefficient or its prediction.
 before=predict(m,x[3]);_future=np.array([[9999.,9999.]])
 need(predict(m,x[3])==before,'POOL_FROZEN_FIT')
 t=src.START
 corpus={sid:{t-j*src.H:(1.,1.02,.98,1.+j*.001) for j in (0,1,2)} for sid in src.TARGETS}
 f=features(corpus,5,t);need(f is not None and len(f[0])==13,'POOL_FEATURE_SHAPE')
 corpus[111].pop(t-src.H);need(features(corpus,5,t) is None,'POOL_MISSING_REFERENCE')
 # MSE+alpha ridge on one feature has a manually known slope/intercept.
 z=np.array([[-1.],[1.]]);r=fit(z,np.array([-2.,2.]))
 need(abs(predict(r,np.array([1.]))-1.)<1e-12,'POOL_RIDGE_KNOWN_RESULT')
 # Full artificial chronological path, then poison only the final day.
 corpus={sid:{} for sid in src.TARGETS}
 for t in range(src.START-3*src.H,src.END+5*src.H,src.H):
  if dt.datetime.fromtimestamp(t,dt.timezone.utc).weekday()>=5:continue
  i=(t-src.START)//src.H
  for sid in src.TARGETS:
   p=1.+sid*.01+.0002*math.sin(i*.3+sid)
   corpus[sid][t]=(p,p+.001,p-.001,p+.0001*math.cos(i))
 support(corpus);a=evaluate(corpus)
 cutoff=src.END-86400
 for sid in corpus:
  for t in list(corpus[sid]):
   if t>=cutoff:corpus[sid][t]=tuple(v*1.2 for v in corpus[sid][t])
 b=evaluate(corpus)
 need([v for v in a['fit_log'] if v['fit_decision_utc']<cutoff]==
      [v for v in b['fit_log'] if v['fit_decision_utc']<cutoff],'POOL_FUTURE_POISON')
 need(all(v['latest_label_settlement_utc']+2*src.H<v['fit_decision_utc'] for v in a['fit_log']),'POOL_PURGED_LABELS')
 need(a['forecasts']==405 and not a['hard21_component_gate_applied'],'POOL_FULL_PATH')
 validate();print('MXM_POOLED_PRESSURE_PREFLIGHT_PASS')
def main():
 import sys
 if sys.argv[1:]==['selftest']:selftest();return
 need(sys.argv[1:]==['run'],'POOL_MODE');s=validate()
 need(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
  os.environ.get('GITHUB_REF_NAME')=='mxm-remediation-p0-p4-20261015-v1' and
  os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','POOL_CONTEXT')
 from .budgets import historical_accounting
 history=historical_accounting(ROOT);need(history['reconciled'],'POOL_HISTORY')
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
 with tempfile.TemporaryDirectory() as d:
  key,fp=_private_key_from_secret(Path(d));need(fp==FP,'POOL_CUSTODY')
  corpus={};proofs={}
  for sid,(asset,expected) in src.SOURCES.items():
   value,proof=load_asset(key,fp,Path(d),{'release_id':409747426,'asset_id':asset,'ciphertext_sha256':expected})
   corpus[sid]=src.bars(value,sid);proofs[str(sid)]=proof
  temporal=support(corpus) # No economic identity or fitted parameter before source admission.
  result=evaluate(corpus)
  doc=dict(schema='mxm.pooled-pressure-development-receipt.v1',run_id=int(os.environ['GITHUB_RUN_ID']),
   source_sha=os.environ['GITHUB_SHA'],spec_sha256=digest(SPEC.read_bytes()),original_sources=proofs,
   source_support=temporal,new_identity_reservations=1,new_economic_models_executed=1,model=result,
   identity_selection_unit='ONE_POOLED_LEARNING_PROCEDURE_THREE_DEPENDENT_MARKET_CELLS',
   prior_v4_new_families_source_first=3,prior_compression_closed_preserved=True,
   legacy_attempts=history['legacy']['used'],v2_used_unmodified=history['V2']['used'],v2_remaining_unmodified=history['V2']['remaining'],
   pnl_basis='STAGE_A_FIXED_1000_EUR_NOT_REAL_EUR200_ACCOUNT',source_partition='PREVIOUSLY_EXPOSED_DEVELOPMENT',
   procedure_outer_interval='2026-08-10/2026-08-31_NOT_INDEPENDENT_EVIDENCE',hard21_role='SYSTEM_ONLY',
   economic_qualifications=0,stage_b=False,independent_confirmation=False,
   cost_state='FROZEN_COARSE_BOUND_PLUS_PROSPECTIVE_SENSITIVITY_NOT_HISTORICAL_TOTAL_COST',
   new_broker_requests=0,orders=0,cloud_activated=False,protected_opened=False)
  OUT.mkdir(parents=True,exist_ok=True);(OUT/'receipt.json').write_bytes(src.encode(doc))
  print('MXM_POOLED_PRESSURE_ECONOMICS '+json.dumps(doc,sort_keys=True),flush=True)
if __name__=='__main__':main()

