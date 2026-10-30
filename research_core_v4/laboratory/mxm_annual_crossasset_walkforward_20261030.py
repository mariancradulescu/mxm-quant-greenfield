"""ONE pre-registered, development-only, 145-asset M5->hourly cross-class walkforward.
No broker orders, no Cloud, no protected confirmation, no retuning. See --selftest.
Strict previous-week training, time-forward forecast; all instrument identities from PRIMARY145 fixed
source snapshot, no retrospectively filtered winning classes/symbols. Fixed ML hyperparameters.

Decision time t UTC is top of hour, latest observed M5 bar t-5 minutes.
Entry uses original open at t+5min, exit uses original open at t+60min,
not a fictitious fill and not historical Pepperstone BID/ASK commissions/slippage.
Require exact M5 continuity for previous 3 hours and exact future open prices.
TRAINING uses only earlier observed, completed labels and 13 preceding ISO weeks.
RETRAIN every four weeks; no outcome-dependent hyperparameter or class selection.
One global slot at most per hour; do NOT force 21 entries; one EUR200 capital
is NOT modeled in this screening run. STOP rather than promote if net fails.
"""
import argparse,datetime as dt,hashlib,io,json,math,pathlib,zipfile
from collections import Counter,defaultdict
import numpy as np,pandas as pd
from lightgbm import LGBMRegressor

A=pathlib.Path('/mnt/data/files/MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip')
B=pathlib.Path('/mnt/data/files/MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip')
PINS={A:'09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259',
B:'37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e'}
SYMBOL_IDS={3,7,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,37,39,40,41,43,44,46,47,49,50,51,54,60,61,64,75,82,84,86,87,91,93,95,97,98,104,110,116,117,118,130,134,146,251,255,256,262,284,286,323,324,326,888,2083,2086,2737,2738,2739,2740,2742,2744,2746,2753,2762,2763,2764,2765,2766,2767,2768,2769,2770,2771,2772,2773,2774,2775,2776,2777,2779,2780,2781,2783,2785,2786,2788,2917,2924,2926,2998,2999,3000,3002,3019,3020,3025,3027,3029,3032,3033,3034,5402,5403,5406,5410,5411,5414,5424,5449,5470,7186,7187,7188,7189,7190,7191,7192,7193,7194,7195,7196,7198,7285,7286,7393,7394}
F=['r30_over_rv','r60_over_rv','r180_over_rv','last30_range_over_rv','volume_last_hour_ratio','log_hourly_vol_bps','utc_sin','utc_cos']
TRAIN_WEEKS=13
TEST_WEEKS=4
MIN_PREDICTED_GROSS_BPS=20.0
FIRST_WEEK='2025-09-29'
LAST_COMPLETE_END='2026-09-14' # do not include incomplete W38
COSTS=(2,5,10,20,40)
SEED=20261030


def selftest():
  assert len(SYMBOL_IDS)==145
  assert dt.date.fromisoformat(FIRST_WEEK).isocalendar().week==40
  assert dt.date.fromisoformat(LAST_COMPLETE_END).isocalendar().week==38
  assert dt.date.fromisoformat(LAST_COMPLETE_END)-dt.date.fromisoformat(FIRST_WEEK)==dt.timedelta(weeks=50)
  assert set(F)=={'r30_over_rv','r60_over_rv','r180_over_rv','last30_range_over_rv','volume_last_hour_ratio','log_hourly_vol_bps','utc_sin','utc_cos'}
  t=pd.Timestamp('2026-03-02T15:00:00Z'); assert (t-pd.Timedelta(minutes=5)).hour==14
  assert (t+pd.Timedelta(minutes=60))>(t+pd.Timedelta(minutes=5))
  assert MIN_PREDICTED_GROSS_BPS==20.0
  print('ONE_ANNUAL_145_CAUSAL_CROSS_CLASS_ML_SOURCE_BLIND_SELFTEST_PASS')


def per_asset(z,filename,sid,symbol):
  with z.open(filename) as f:
    df=pd.read_csv(f,usecols=['time_utc','open','high','low','close','tick_volume'],dtype={'open':'float64','high':'float64','low':'float64','close':'float64','tick_volume':'float64'})
  if df.empty:raise ValueError('EMPTY_ORIGINAL_MARKET_SOURCE')
  df['time_utc']=pd.to_datetime(df['time_utc'],utc=True,errors='raise')
  if not df['time_utc'].is_monotonic_increasing or df['time_utc'].duplicated().any():raise ValueError('NONMONOTONE_OR_DUPLICATED_SOURCE')
  if (df[['open','high','low','close']]<=0).any().any():raise ValueError('INVALID_ORIGINAL_PRICE')
  ns=df['time_utc'].astype('int64').to_numpy()
  logs=np.log(df['close'].to_numpy())
  rr=np.diff(logs,prepend=np.nan)
  rv_5m=pd.Series(rr**2).rolling(35,min_periods=35).sum().to_numpy()
  rv_h=1e4*np.sqrt(12*rv_5m/35)
  hi30=pd.Series(df['high'].to_numpy()).rolling(6,min_periods=6).max().to_numpy()
  lo30=pd.Series(df['low'].to_numpy()).rolling(6,min_periods=6).min().to_numpy()
  vol1=pd.Series(df['tick_volume'].to_numpy()).rolling(12,min_periods=12).sum().to_numpy()
  vol3=pd.Series(df['tick_volume'].to_numpy()).rolling(36,min_periods=36).sum().to_numpy()
  past3=np.zeros(len(ns),dtype=bool)
  past3[35:]=(ns[35:]-ns[:-35]==35*300*10**9)
  ids=np.flatnonzero((df['time_utc'].dt.minute.to_numpy()==55)&past3&np.isfinite(rv_h)&(rv_h>1e-9))
  if not len(ids):return pd.DataFrame()
  p=ns[ids]
  enterstamp=p+2*300*10**9;exitstamp=p+13*300*10**9
  jj=np.searchsorted(ns,enterstamp);kk=np.searchsorted(ns,exitstamp)
  good=(jj<len(ns))&(kk<len(ns))
  jj=np.minimum(jj,len(ns)-1);kk=np.minimum(kk,len(ns)-1)
  good&=(ns[jj]==enterstamp)&(ns[kk]==exitstamp)
  ids=ids[good];jj=jj[good];kk=kk[good]
  if not len(ids):return pd.DataFrame()
  vals=df[['open']].to_numpy().ravel()
  prices_enter=vals[jj];prices_exit=vals[kk]
  if np.min(prices_enter)<=0 or np.min(prices_exit)<=0:raise ValueError('INVALID_EXEC_PRICE')
  rv=rv_h[ids];hour=((pd.to_datetime(ns[ids]+300*10**9,utc=True).hour)%24).to_numpy()
  features=np.column_stack([
   1e4*(logs[ids]-logs[ids-6])/rv,
   1e4*(logs[ids]-logs[ids-12])/rv,
   1e4*(logs[ids]-logs[ids-35])/rv,
   1e4*(np.log(hi30[ids])-np.log(lo30[ids]))/rv,
   3*vol1[ids]/np.maximum(vol3[ids],1),np.log1p(rv),
   np.sin(2*np.pi*hour/24),np.cos(2*np.pi*hour/24)])
  valid=np.all(np.isfinite(features),axis=1)
  if not valid.any():return pd.DataFrame()
  times=pd.to_datetime(ns[ids]+300*10**9,utc=True)
  ret=1e4*(prices_exit/prices_enter-1)
  out=pd.DataFrame(features,columns=F)
  out.insert(0,'t',times);out.insert(1,'id',sid);out.insert(2,'symbol',symbol)
  out.insert(3,'actual_gross_bps',ret);out.insert(4,'rv_hour_bps',rv)
  return out.iloc[valid].reset_index(drop=True)

def read_source():
  for path,sha in PINS.items():
    with path.open('rb') as f:
      if hashlib.file_digest(f,'sha256').hexdigest()!=sha:raise ValueError('SOURCE_ZIP_SHA_MISMATCH_'+path.name)
  frames=[];seen=set(); source_rows=0
  for path in [B,A]:
    with zipfile.ZipFile(path) as z:
      meta=json.loads(z.read('SELECTED_IDENTITY_MANIFEST.json'))
      names={int(e['symbol_id']):e['broker_symbol'] for e in meta['symbols']}
      for name in sorted(z.namelist()):
        if not(name.startswith('raw/') and name.endswith('_M5.csv')):continue
        sid=int(name.split('/')[-1].split('_')[0]);
        if sid not in SYMBOL_IDS or sid in seen:continue
        seen.add(sid)
        df=per_asset(z,name,sid,names[sid]);frames.append(df)
  if seen!=SYMBOL_IDS:raise ValueError('SOURCE_145_IDENTITY_CONTRACT_MISMATCH '+str(sorted(SYMBOL_IDS-seen)))
  allrows=pd.concat(frames,ignore_index=True).sort_values(['t','id'],kind='mergesort')
  allrows=allrows[(allrows.t>=pd.Timestamp(FIRST_WEEK,tz='UTC')) & (allrows.t<pd.Timestamp(LAST_COMPLETE_END,tz='UTC'))].copy()
  if allrows.duplicated(['t','id']).any():raise ValueError('DUPLICATE_DECISION')
  return allrows


def one_experiment(data):
  dates=pd.to_datetime(data.t,utc=True)
  first=pd.Timestamp(FIRST_WEEK,tz='UTC');last=pd.Timestamp(LAST_COMPLETE_END,tz='UTC')
  rows=[];folds=[]
  fold_start=first+pd.Timedelta(weeks=TRAIN_WEEKS)
  while fold_start<last:
    test_end=min(last,fold_start+pd.Timedelta(weeks=TEST_WEEKS))
    train=data[(dates>=fold_start-pd.Timedelta(weeks=TRAIN_WEEKS)) & (dates<fold_start-pd.Timedelta(hours=2))]
    test=data[(dates>=fold_start)&(dates<test_end)]
    if len(train)<1000 or len(test)==0:raise ValueError('INSUFFICIENT_SOURCE_FOR_REGISTERED_ML')
    model=LGBMRegressor(objective='huber',alpha=0.9,n_estimators=120,learning_rate=0.04,
       max_depth=4,num_leaves=9,min_child_samples=400,reg_lambda=50,
       colsample_bytree=1.0,random_state=SEED,n_jobs=2,verbosity=-1)
    target=np.clip(train.actual_gross_bps.to_numpy()/train.rv_hour_bps.to_numpy(),-5,5)
    model.fit(train[F].to_numpy(dtype=np.float64),target)
    pred=model.predict(test[F].to_numpy(dtype=np.float64))*test.rv_hour_bps.to_numpy()
    # One deterministic global slot, choose max ABS forecast if meets before-outcome
    # broker-cost proxy hurdle of 20bp; never force trades to reach HARD21.
    test=test.copy();test['prediction_bps']=pred;test['abs_prediction_bps']=np.abs(pred)
    test=test[test.abs_prediction_bps>MIN_PREDICTED_GROSS_BPS]
    test=test.sort_values(['t','abs_prediction_bps','id'],ascending=[True,False,True],kind='mergesort')
    chosen=test.drop_duplicates('t',keep='first')
    chosen=chosen.assign(signed_gross_bps=np.sign(chosen.prediction_bps)*chosen.actual_gross_bps)
    rows.append(chosen[['t','id','symbol','prediction_bps','actual_gross_bps','signed_gross_bps','rv_hour_bps']].copy())
    folds.append({'training_start':str(fold_start-pd.Timedelta(weeks=TRAIN_WEEKS)),'training_end_exclusive':str(fold_start-pd.Timedelta(hours=2)),
                  'test_start':str(fold_start),'test_end_exclusive':str(test_end),'train_examples':len(train),
                  'candidates_exceed_hurdle':len(test),'globally_nonoverlapping_selected':len(chosen)})
    fold_start=test_end
  trade=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame()
  trade=trade.sort_values('t')
  period_weeks=pd.date_range(first+pd.Timedelta(weeks=TRAIN_WEEKS),last,freq='7D',inclusive='left')
  weekly=[]
  for t in period_weeks:
    t2=t+pd.Timedelta(weeks=1)
    p=trade[(trade.t>=t)&(trade.t<t2)]
    n=len(p);g=float(p.signed_gross_bps.sum())
    weekly.append({'iso_week':f'{t.isocalendar().year}-W{t.isocalendar().week:02d}',
        'modeled_proposals':n,'gross_bps_sum':round(g,4),
        'hypothetical_cost_bps_net_sum':{str(c):round(g-c*n,4) for c in COSTS}})
  totals={str(c):{'net_bps_sum':round(sum(w['hypothetical_cost_bps_net_sum'][str(c)] for w in weekly),4),
      'positive_weeks':sum(w['hypothetical_cost_bps_net_sum'][str(c)]>0 for w in weekly)} for c in COSTS}
  gross=float(trade.signed_gross_bps.sum())
  raw={'schema':'mxm.annual145-global-nonlinear-cross-asset-walkforward-first-development.v1',
       'source_sha256':{p.name:sha for p,sha in PINS.items()},
       'source_145_count':len(SYMBOL_IDS),'data_source':'AUTHENTIC_ORIGINAL_SOURCE_EXPOSED_DEVELOPMENT_NOT_PROTECTED',
       'model':'LightGBM_huber_normalized_future_55min_aggregate_cross_asset',
       'train_weeks':TRAIN_WEEKS,'test_weeks_per_refit':TEST_WEEKS,'frozen_predictive_hurdle_bps':MIN_PREDICTED_GROSS_BPS,
       'chronology':'3h genuinely continuous M5 feature history, next available original M5 open +5min entry / +60min exit; labels never in training block after decision',
       'starting_capital_EUR_200_funded':False,'real_historical_Pepperstone_costs':False,
       'real_broker_fill_count':0,'hard21_executed':False,'cloud_operational':False,'orders':0,
       'not_a_production_strategy':True,'one_hypothesis_no_retuning':True,'no_future_confirmation_opened':True,
       'all_asset_feature_rows':len(data),'weekly_out_of_training_count':len(weekly),'observed_trades':len(trade),
       'weeks_with_21_modeled_proposals':sum(w['modeled_proposals']>=21 for w in weekly),
       'gross_bps_sum':round(gross,4),'hypothetical_cost_scenarios':totals,'folds':folds,
       'weekly_aggregate':weekly,
       'by_symbol':{k:{'n':int(len(v)),'gross_bps':round(float(v.signed_gross_bps.sum()),4)} for k,v in trade.groupby('symbol')},
       'decision':'NO_DECISION_UNTIL_FIRST_ACTUAL_OUTCOME'}
  if not len(trade):raw['decision']='STOP_NO_SOURCE_ECONOMIC_OPPORTUNITIES'
  elif gross<=0 or totals['20']['net_bps_sum']<=0 or sum(w['hypothetical_cost_bps_net_sum']['20']>0 for w in weekly)<0.65*len(weekly):
     raw['decision']='CLOSE_DEVELOPMENT_NO_ROBUST_20BPS_HYPOTHETICAL_NET_NO_PROMOTION'
  else:raw['decision']='ONLY_CONDITIONAL_BROKER_COST_MIN_LOT_EUR200_ACCOUNT_FOLLOWUP_NOT_PROMOTION'
  return raw,trade

if __name__=='__main__':
  p=argparse.ArgumentParser();p.add_argument('action',choices=['selftest','evaluate']);p.add_argument('--out',default='/mnt/data/MXM_ANNUAL145_GLOBAL_ML_FIRST_PUBLIC_20261030.json');p.add_argument('--private',default='/mnt/data/MXM_ANNUAL145_GLOBAL_ML_FIRST_PRIVATE_20261030.json');a=p.parse_args()
  selftest()
  if a.action=='evaluate':
    data=read_source();print('SOURCE_AUTHENTICATED_145_FEATURE_ROWS',len(data),flush=True)
    result,trade=one_experiment(data)
    pathlib.Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    pathlib.Path(a.private).write_text(trade.to_json(orient='records',date_format='iso'))
    print('RESULT',json.dumps({k:result[k] for k in ['all_asset_feature_rows','weekly_out_of_training_count','observed_trades','weeks_with_21_modeled_proposals','gross_bps_sum','hypothetical_cost_scenarios','decision']},sort_keys=True),flush=True)
