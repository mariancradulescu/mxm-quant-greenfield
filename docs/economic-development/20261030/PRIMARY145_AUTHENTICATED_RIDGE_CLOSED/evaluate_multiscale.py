"""Single predeclared pooled multiscale regression policy: one real-data DEVELOPMENT read.
Never historical bid/ask or broker fills; numeric friction is hypothetical bps only.
"""
from pathlib import Path
from collections import defaultdict,Counter
import datetime as dt,json,math
import numpy as np
from sklearn.linear_model import Ridge
P=Path('/mnt/data/mxm_primary145_originals')
files=sorted(P.glob('features-*.npz'))
assert len(files)==5,files
parts=[]
for fn in files:
 with np.load(fn) as z:
  parts.append({k:z[k] for k in ('X','y','t','sid','future','baseline')})
D={k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
X=np.asarray(D['X'],dtype='float64');Y=np.asarray(D['y'],dtype='float64');T=D['t'];SID=D['sid']
assert len(X)==len(Y)==len(T)==len(SID) and len(np.unique(SID))==145
utc=lambda y,m,d:int(dt.datetime(y,m,d,tzinfo=dt.timezone.utc).timestamp())
train_end=utc(2026,6,1);test_start=utc(2026,6,8);test_end=utc(2026,9,17)
actual=np.isfinite(Y)
sigma=np.maximum(np.expm1(X[:,5]*5),0.05)
normalized=np.where(actual,np.clip(np.nan_to_num(Y,nan=0.0)/(sigma*np.sqrt(8)),-20,20),np.nan)
training=(T<train_end-8*300)&actual
holdout=(T>=test_start)&(T<test_end)
assert training.sum()>100000 and holdout.sum()>100000 and np.all(T[training]+8*300<train_end)
policy=Ridge(alpha=1000,fit_intercept=True,solver='cholesky')
policy.fit(X[training],normalized[training]);pred=np.asarray(policy.predict(X[holdout])*sigma[holdout]*np.sqrt(8),dtype=np.float64)
ht=T[holdout];hs=SID[holdout];hy=Y[holdout];hb=D['baseline'][holdout];hf=actual[holdout]
finite=np.isfinite(pred)&(np.abs(pred)>=20)
# Time/score-only choice. Sorting by -magnitude, then UTC then symbol ID.
candidates=np.flatnonzero(finite)
rank=np.lexsort((hs[candidates],-np.abs(pred[candidates]),ht[candidates]))
selection=candidates[rank]
unique_hours,pos=np.unique(ht[selection],return_index=True)
chosen=selection[pos]
assert len(np.unique(ht[chosen]))==len(chosen)
S=[];gross=[];base=[];weeks=defaultdict(lambda:Counter());months=defaultdict(lambda:Counter());by_symbol=Counter()
for j in chosen:
 at=dt.datetime.fromtimestamp(int(ht[j]),dt.timezone.utc)
 w=at.strftime('%G-W%V');m=at.strftime('%Y-%m');sid=int(hs[j]);side=1 if pred[j]>0 else -1
 g=side*float(hy[j]) if hf[j] else None
 v={'datetime_utc':at.isoformat().replace('+00:00','Z'),'symbol_id':sid,'side':side,'predicted_gross_bps':float(pred[j]),'observed_gross_bps':g,'future_observed':bool(hf[j])}
 S.append(v);by_symbol[sid]+=1;wk=weeks[w];mo=months[m]
 for C in (wk,mo):
  C['proposals']+=1
  if g is None:C['censored']+=1
  else:
   C['complete']+=1;C['gross_bps_sum']+=g;C['positive']+=int(g>0)
   for cost in (10,20,40):C[f'hypothetical_net_{cost}bps_sum']+=g-cost
 if g is not None:
  gross.append(g)
  if hb[j]:base.append(float(hb[j])*float(hy[j]))
print('MODEL_TRAINED',training.sum(),'EVAL_AVAILABLE',holdout.sum(),'EVAL_FUTURE_LABELLED',np.sum(actual[holdout]),'CANDIDATE_HOURS',len(chosen),flush=True)
G=np.asarray(gross)
summary={'schema':'mxm.primary145.predeclared-crossscale-ridge-development.v1',
 'source':'ORIGINALS_SHA256_VERIFIED_LOCAL_PRIMARY145_11406418_M5','data_partition':'DEVELOPMENT_ONLY',
 'time_split':{'train_before_utc':'2026-06-01T00:00:00Z','embargo_to_utc':'2026-06-08T00:00:00Z','eval_until_utc':'2026-09-17T00:00:00Z'},
 'model':{'type':'pooled_ridge_cross_scale_ohlcv_non_market_specific','alpha':1000,'train_rows':int(training.sum()),'features':['normalized_return_1M5','normalized_return_6M5','normalized_return_12M5','normalized_return_48M5','volume_6vs48','realized_sigma_48','return_12_x_volume','return_48_x_volume'],'weights':policy.coef_.tolist(),'intercept':float(policy.intercept_), 'training_normalized_label_clipped_to':[-20,20]},
 'policy':{'selection':'max_abs_model_gross_pred_per_utc_hour_one_common_slot','threshold_predicted_abs_bps':20,'earliest_entry':'second_future_bar_open_5min_after_closed_bar_actionability','exit':'8_M5_bars_after_hypothetical_entry','max_concurrent_positions':1,'no_future_filtered_selection':True},
 'coverage':{'all_input_source_series':145,'all_feature_candidates':int(len(X)),'train_valid_rows':int(training.sum()),'test_feature_rows':int(holdout.sum()),'test_future_observable_feature_rows':int(hf.sum()),'test_opportunity_hours':len(chosen),'observed_gross_completions':int(len(gross)),'censored_chosen_opportunities':int(len(chosen)-len(gross))},
 'gross_model':{'gross_bps_sum':float(np.sum(G)), 'mean_gross_bps':float(np.mean(G)) if len(G) else None,'median_gross_bps':float(np.median(G)) if len(G) else None,'positive_share':float(np.mean(G>0)) if len(G) else None},
 'assumed_roundtrip_cost_only_bps':{str(cost):float(np.sum(G)-cost*len(G)) for cost in (10,20,40)},
 'weekly':{w:dict(c) for w,c in sorted(weeks.items())},'monthly':{m:dict(c) for m,c in sorted(months.items())},
 'symbol_concentration_top10':by_symbol.most_common(10),
 'historical_broker_costs_proven':False,'historical_bidask_executable_fills_proven':False,'eur200_continuous_funded_account_replayed':False,
 'minimum_broker_lattice_enforced':False,'hard21_broker_executed_certified':False,'independent_confirmation_proven':False,
 'protected_forward_opened':False,'live_demo_orders':0,'cloud_activated':False}
full={**summary,'private_chosen_episode_outcomes':S}
(P/'PRIMARY145_RIDGE_SINGLE_DEVELOPMENT_PRIVATE.json').write_text(json.dumps(full,sort_keys=True,separators=(',',':'))+'\n')
(P/'PRIMARY145_RIDGE_SINGLE_DEVELOPMENT_PUBLIC.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
print('RESULT',json.dumps({k:v for k,v in summary.items() if k not in ('weekly','monthly','model','policy')},sort_keys=True))
print('WEEKS',{w:{'n':v['proposals'],'complete':v['complete'],'censored':v.get('censored',0),'gross':round(v['gross_bps_sum'],2),'net20':round(v['hypothetical_net_20bps_sum'],2)} for w,v in summary['weekly'].items()})