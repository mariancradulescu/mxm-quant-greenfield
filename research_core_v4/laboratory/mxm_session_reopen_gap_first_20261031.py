"""FIRST/FROZEN single EUR200 session-reopening partial-gap correction policy.
Distinct from closed rolling-volume response, wick rejection and pooled ML.
Replay is a hypothetical linear USD-cash scenario, never broker NET proof.
Policy is fixed before outcome inspection. No outcome-driven selection/re-tuning.
"""
import collections, hashlib, io, json, pathlib, zipfile
import numpy as np
import pandas as pd

ROOT=pathlib.Path('/mnt/data');SRC=ROOT/'files'
BROKER=SRC/'MXM_COMPETITION_BROKER_UNIVERSE_V2.zip'
ZIPS=[SRC/'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip',SRC/'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip']
BROKER_HASH='9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77'
POLICY='SESSION_REOPEN_PARTIAL_GAP_CORRECTION_ONE_FROZEN_FIRST_TRIAL_V1'
START='2026-01-05T00:00:00Z';END='2026-09-14T00:00:00Z'
USD_EUR=0.90;COST_BPS=10.0;EXTRA_SLIPPAGE_EUR=0.10
INITIAL_EUR=200.0;TICKET_MARGIN_CAP=80.0;FREE_RESERVE=120.0;MAX_ENTRY_LOSS_EUR=2.0
SESSION_GAP_MIN_SECONDS=3600;SESSION_GAP_MAX_SECONDS=5*86400
GAP_BPS_MIN=80.0;CONFIRM_FRACTION=0.10;HOLD_M5=6;MAX_STOP_GAP_FRACTION=.50
MIN_STOP_AS_FRACTION_OF_PRICE=.0004;MIN_EXPECTED_NET_CASH_SIGNAL=.20

def check(x,msg):
 if not x:raise ValueError('MXM_GAP_'+msg)

def selftest():
 check(INITIAL_EUR==200 and HOLD_M5==6 and USD_EUR==.9 and GAP_BPS_MIN==80,'FROZEN_POLICY')
 def signal(prev,op,cl):
  gap=op-prev
  if abs(gap)/prev*10000 < GAP_BPS_MIN:return 0
  if gap>0 and op-cl >=CONFIRM_FRACTION*gap:return -1
  if gap<0 and cl-op >=CONFIRM_FRACTION*(-gap):return +1
  return 0
 check(signal(100,102,101.9)==0,'MUST_CONFIRM_TEN_PERCENT')
 check(signal(100,102,101.7)==-1,'GAP_UP_FADES')
 check(signal(100,98,98.3)==+1,'GAP_DOWN_FADES')
 check(signal(100,100.1,100.0)==0,'TINY_GAP')
 return signal

def source():
 check(hashlib.sha256(BROKER.read_bytes()).hexdigest()==BROKER_HASH,'BROKER_HASH')
 with zipfile.ZipFile(BROKER) as z:
  k=[x for x in z.namelist() if x.endswith('BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V2.json')];check(len(k)==1,'BROKER_MEMBER')
  broker=json.loads(z.read(k[0]))
 check(broker['account_currency']=='EUR' and broker['starting_capital_eur']==200 and not broker['orders_placed'] and len(broker['symbols'])==5324,'BROKER_SCOPE')
 bmap={int(x['symbol_id']):x for x in broker['symbols']};seen=set();elig=collections.Counter()
 for path in ZIPS:
  with zipfile.ZipFile(path) as z:
   manifest=json.loads(z.read('CAPTURE_MANIFEST.json'));payraw=z.read('V3_CAPTURE_PAYLOAD.json')
   check(hashlib.sha256(payraw).hexdigest()==manifest['sha256_per_canonical_payload']['V3_CAPTURE_PAYLOAD.json'],'CAPTURE_HASH')
   info=json.loads(payraw);check(info['classification']=='DEVELOPMENT_ONLY' and not info['protected_forward_opened'],'SOURCE_PARTITION')
   for item in info['series']:
    sid=int(item['symbol_id']);check(sid not in seen,'SOURCE_DUP');seen.add(sid)
    b=bmap[sid]
    # source-blind cash/margin only; never infer historical broker fees from current snapshot
    m=b['expected_margin_at_min_volume']
    if not(b['quote_asset']=='USD' and b['commission_type']==2 and b['min_commission_asset']=='USD' and b['min_commission_type']==1 and b['buy_eligible_current'] and b['sell_eligible_current'] and 0<m['buy_margin_eur']<=TICKET_MARGIN_CAP and 0<m['sell_margin_eur']<=TICKET_MARGIN_CAP):continue
    data=z.read(item['file']);check(hashlib.sha256(data).hexdigest()==item['sha256'],'RAW_SHA')
    df=pd.read_csv(io.BytesIO(data),dtype={'open':'float64','high':'float64','low':'float64','close':'float64'},usecols=['time_utc','open','high','low','close'])
    check(len(df)==item['row_count'],'RAW_ROWS')
    t=pd.to_datetime(df.time_utc,utc=True).to_numpy(dtype='datetime64[s]').astype('int64')
    o,h,l,c=(df[n].to_numpy(dtype='float64') for n in ['open','high','low','close'])
    check(np.all(np.diff(t)>0) and all(np.isfinite(k).all() and (k>0).all() for k in [o,h,l,c]),'RAW_QUALITY')
    elig[b['asset_class']]+=1
    yield sid,b,t,o,h,l,c
 check(len(seen)==157,'TOTAL_ORIGINAL_PRICE_SOURCE_ROSTER')

def evaluate():
 signal=selftest();left=int(pd.Timestamp(START).timestamp());right=int(pd.Timestamp(END).timestamp())
 proposals=[];eligible=collections.Counter();signal_counts=collections.Counter()
 for sid,b,t,o,h,l,c in source():
  eligible[b['asset_class']]+=1
  gap=np.diff(t);idx=np.flatnonzero((gap>=SESSION_GAP_MIN_SECONDS) & (gap<=SESSION_GAP_MAX_SECONDS))+1
  if not len(idx):continue
  units=int(b['min_volume_cents'])/100.0;ppu=units*USD_EUR
  check(units>0 and int(b['min_volume_cents'])==int(b['expected_margin_at_min_volume']['volume_cents']),'BROKER_MIN_TICKET')
  fee=2*max((int(b['min_volume_cents'])/int(b['lot_size']))*(int(b['precise_trading_commission_rate'])/1e8),int(b['precise_min_commission'])/1e8)*USD_EUR
  margin=max(float(b['expected_margin_at_min_volume']['buy_margin_eur']),float(b['expected_margin_at_min_volume']['sell_margin_eur']))
  for k in idx:
   if k+1>=len(t) or t[k]<left or t[k]>=right or t[k+1]-t[k]!=300:continue
   direction=signal(c[k-1],o[k],c[k])
   if direction==0:continue
   gap_price=abs(o[k]-c[k-1]);signal_counts['confirmed_gap_signals']+=1
   # Known at first completed genuine five-minute bar. No future source completeness test here.
   proposed_entry_time=int(t[k]+600)   # one full M5 extra bar of latency from completed first bar
   if k+2>=len(t) or t[k+2]!=proposed_entry_time:
    signal_counts['entry_time_unobserved']+=1;continue
   cost=fee+ppu*o[k]*COST_BPS/10000+EXTRA_SLIPPAGE_EUR
   stop=max(0.,min(MAX_STOP_GAP_FRACTION*gap_price,(MAX_ENTRY_LOSS_EUR-cost)/ppu))
   if stop<=0 or (stop/o[k])<MIN_STOP_AS_FRACTION_OF_PRICE:continue
   signal_cash=ppu*gap_price-cost
   if signal_cash<=MIN_EXPECTED_NET_CASH_SIGNAL:continue
   # Deterministic rank based only on cash gap size, not future outcomes.
   score=signal_cash
   proposals.append({'sid':sid,'cls':b['asset_class'],'time':proposed_entry_time,'direction':direction,'score':score,
    'margin':margin,'fee':fee,'ppu':ppu,'stop':stop,'cost_bps':COST_BPS,'usd_eur':USD_EUR,'index':k+2,
    't':t,'o':o,'h':h,'l':l,'c':c})
 proposals.sort(key=lambda x:(x['time'],-x['score'],x['sid']))
 equity=INITIAL_EUR;peak=equity;drawdown=0;book=[];reject=collections.Counter();censored=0;busy_until=left
 for e in proposals:
  if e['time']<busy_until:continue
  i=e['index'];t=e['t'];o=e['o'];h=e['h'];l=e['l'];ppu=e['ppu'];d=e['direction']
  entry=float(o[i]);cost=e['fee']+ppu*entry*COST_BPS/10000+EXTRA_SLIPPAGE_EUR
  total_loss=e['stop']*ppu+cost
  if total_loss>MAX_ENTRY_LOSS_EUR+1e-10:reject['entry_total_stop_loss_gt_existing_2eur']+=1;continue
  if equity-e['margin']-cost<FREE_RESERVE:reject['post_cost_margin_below_existing_120eur']+=1;continue
  if e['margin']>TICKET_MARGIN_CAP:reject['margin_cap']+=1;continue
  # Future MUST not influence candidate admission; absent future invalidates the complete funded path.
  if i+HOLD_M5>=len(t) or t[i+HOLD_M5]!=e['time']+300*HOLD_M5 or np.any(np.diff(t[i:i+HOLD_M5+1])!=300):
   censored+=1;reject['future_not_observable_NO_FUNDED_PROOF']+=1;break
  stopprice=entry-d*e['stop'];stopped=False;price=float(o[i+HOLD_M5]);exit_idx=i+HOLD_M5
  for j in range(i,i+HOLD_M5):
   if d>0 and l[j]<=stopprice:
    price=min(float(o[j]),stopprice);stopped=True;exit_idx=j;break
   if d<0 and h[j]>=stopprice:
    price=max(float(o[j]),stopprice);stopped=True;exit_idx=j;break
  realized=ppu*d*(price-entry)-cost;equity+=realized;peak=max(equity,peak);drawdown=max(drawdown,peak-equity)
  # No overlapping position. A stop closes at observed bar j; conservative remain busy until planned horizon.
  busy_until=int(t[i+HOLD_M5])
  week=pd.Timestamp(e['time'],unit='s',tz='UTC').strftime('%G-W%V')
  book.append({'sid':e['sid'],'asset_class':e['cls'],'week':week,'time':e['time'],'stop':stopped,'cost_eur':cost,
   'stop_cost_risk_eur':total_loss,'modeled_pnl_eur':realized,'capital_after':equity,'source':'ORIGINAL_M5_OHLC_NOT_EXECUTABLE_BIDASK'})
 weeks=collections.defaultdict(list)
 for x in book:weeks[x['week']].append(x)
 # Zero real broker fills. Counterfactual fixed SEP-22 commission and USD->EUR can be future relative to historical outcome.
 result={
  'schema':'mxm.session-reopen-gap-partial-correction-first-price-development-v1',
  'policy':POLICY,'source_partition':'EXPOSED_DEVELOPMENT_ONLY_NOT_PROTECTED_CONFIRMATION',
  'fixed_window_utc':[START,END],
  'source':'157 ORIGINAL ANNUAL M5 timeseries, source-qualified broker metadata; ALL source broker identities examined before price signal',
  'fixed_rule':{'reopen_gap_min_minutes':60,'gap_min_bps':GAP_BPS_MIN,'first_m5_bar_gap_correction_fraction':CONFIRM_FRACTION,
   'one_delayed_bar_after_first_5min_bar':True,'hold_m5_bars':HOLD_M5,'stop_gap_fraction':MAX_STOP_GAP_FRACTION,
   'min_implied_gap_cash_after_cost_eur':MIN_EXPECTED_NET_CASH_SIGNAL,'max_stop_loss_plus_modeled_cost_eur':MAX_ENTRY_LOSS_EUR,'min_stop_frac_price':MIN_STOP_AS_FRACTION_OF_PRICE},
  'cost_declarations':{'round_trip_native_usd_type2_min_volume_fee':'BROKER_2026_09_22_POST_SAMPLE_DECLARATION_NOT_HISTORICAL_FEE','additional_hypothetical_bps':COST_BPS,'usd_eur_conversion':'0.90 HYPOTHETICAL','additional_slippage_allowance_eur':EXTRA_SLIPPAGE_EUR,'contract_payout':'UNVERIFIED_LINEAR_UNITS_X_USD_PRICE_PROXY','funding':'NOT_RECONCILED'},
  'funded_scenario':{'initial_cash_eur':INITIAL_EUR,'single_position':True,'ticket_margin_cap_eur':TICKET_MARGIN_CAP,'minimum_remaining_free_eur':FREE_RESERVE,
   'model_censored':censored,'source_price_eligible_series_by_asset_class':dict(eligible),'confirmed_gap_signals':int(signal_counts['confirmed_gap_signals']),
   'proposal_count':len(proposals),'evaluated_entries':len(book),'rejections':dict(reject),'ending_cash_eur':round(equity,6),
   'conditional_net_cash_eur':round(equity-INITIAL_EUR,6),'max_closed_equity_drawdown_eur':round(drawdown,6),
   'modeled_stops':sum(z['stop'] for z in book),'max_modeled_stop_plus_cost_eur':round(max((z['stop_cost_risk_eur'] for z in book),default=0),6),
   'modeled_weeks_with_at_least_21_entries':sum(len(v)>=21 for v in weeks.values()),'modeled_active_weeks':len(weeks),
   'positive_active_weeks':sum(sum(x['modeled_pnl_eur'] for x in v)>0 for v in weeks.values()),'distinct_instruments':len(set(x['sid'] for x in book)),
   'by_asset_class_conditional_pnl_eur':{c:round(sum(z['modeled_pnl_eur'] for z in book if z['asset_class']==c),6) for c in sorted(set(z['asset_class'] for z in book))}},
  'limitations':{'historical_executable_spread':False,'actual_broker_fees':False,'real_historical_fx':False,'contract_multiplier_verified':False,
    'stop_fill_order_execution_verified':False,'broker_actual_HARD21_entries':0,'native_cloud_reception':False,'predictive_Net_robust_certified':False,
    'all_broker_universe_restricted':False,'closed_models_rerun':0,'LIVE_DEMO_orders':0},
  'decision':'FIRST_FROZEN_FIRST_OUTCOME_NO_RETUNE_NO_PROFIT_CLAIM_POSTDATE_BROKER_TERMS_COUNTERFACTUAL_ONLY'
 }
 (ROOT/'MXM_SESSION_REOPEN_GAP_FIRST_PUBLIC_20261031.json').write_text(json.dumps(result,indent=2,sort_keys=True,default=lambda x: x.item() if isinstance(x,np.generic) else str(x))+'\n')
 (ROOT/'MXM_SESSION_REOPEN_GAP_FIRST_PRIVATE_20261031.json').write_text(json.dumps({'schema':POLICY,'episodes':book,'notes':'PRIVATE model returns not authentic fills'},indent=2,default=lambda x: x.item() if isinstance(x,np.generic) else str(x))+'\n')
 print(json.dumps({'policy':POLICY,'eligible':result['funded_scenario']['source_price_eligible_series_by_asset_class'],'stats':{k:v for k,v in result['funded_scenario'].items() if k not in ('source_price_eligible_series_by_asset_class','rejections','by_asset_class_conditional_pnl_eur')},'classes':result['funded_scenario']['by_asset_class_conditional_pnl_eur']},indent=2,default=lambda x: x.item() if isinstance(x,np.generic) else str(x)))
if __name__=='__main__':
 selftest()
 import sys
 if '--selftest' in sys.argv:print('MXM_SESSION_REOPEN_SOURCE_BLIND_RULES_PASS')
 else:evaluate()
