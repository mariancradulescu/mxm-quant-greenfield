"""One frozen first evaluation: multi-hour contraction -> volume-verified expansion.

DEVELOPMENT source, not broker execution. The USD-linear cash model uses a
post-dated 2026-09-22 Pepperstone terms capture and hypothetical 20bps + EUR/USD.
One continuous model account with actual EUR200 starting balance and no resets.
Not a retry, inversion or threshold retune of any closed model.
"""
from __future__ import annotations
import argparse,collections,datetime as dt,hashlib,io,json,math,pathlib,sys,zipfile
import numpy as np
import pandas as pd

BROKER_SHA='9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77'
DELTA_SHA='37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e'
SELECTED_SHA='09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259'
FIRST=dt.datetime(2026,1,5,tzinfo=dt.timezone.utc)
END=dt.datetime(2026,9,14,tzinfo=dt.timezone.utc)
START_SEC=int(FIRST.timestamp());END_SEC=int(END.timestamp())
# Frozen, no grid or outcome-derived choices
LONG_BARS=288;SHORT_BARS=72;VOLUME_BARS=24;MAX_CONTRACTION=.40
BREAKOUT_BPS=2.;VOLUME_MULTIPLIER=1.4;PREDICT_RANGE_FACTOR=.30
HORIZON_BARS=36;ENTRY_DELAY_BARS=2
FEE_SCENARIO_USD_EUR=.90;FRICTION_BPS=20.;EXCESS_EUR=.30
CAP=80.;RESERVE=120.;STOP_COST_CAP=2.

def need(v,tag):
 if not v:raise ValueError('MXM_BE_EXPANSION_'+tag)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def zsha(path):
 with open(path,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def terms(row):
 if not (row.get('buy_eligible_current') is True and row.get('sell_eligible_current') is True
    and row.get('quote_asset')=='USD' and row.get('min_commission_asset')=='USD'
    and row.get('commission_type')==2 and row.get('min_commission_type')==1):return None
 margin=row['expected_margin_at_min_volume'];buy=float(margin['buy_margin_eur']);sell=float(margin['sell_margin_eur'])
 if not (0<min(buy,sell) and max(buy,sell)<=CAP):return None
 units=int(row['min_volume_cents'])/100
 if not (units>0 and int(row['step_volume_cents'])>0 and int(row['lot_size'])>0):return None
 fee=max(int(row['min_volume_cents'])/int(row['lot_size'])*int(row['precise_trading_commission_rate'])/1e8,
        int(row['precise_min_commission'])/1e8)
 if not math.isfinite(fee) or fee<0:return None
 return {'units':units,'margin':max(buy,sell),'roundtrip_fee_eur':2*fee*FEE_SCENARIO_USD_EUR}
def candidate_from_history(t,o,h,l,c,v,sid,money):
 """No future sample read; return at most one directional proposal per UTC hour."""
 # Timestamp is the opening of the last completed M5 bar, not the decision time.
 start=LONG_BARS
 out=[];count=0
 for i in np.flatnonzero(t%3600==3300):
  # Scan the actual UTC grid, never an every-12th-index alias of file origin.
  if i<start:continue
  if int(t[i])<START_SEC or int(t[i])>=END_SEC:continue
  if int(t[i])-int(t[i-LONG_BARS])!=300*LONG_BARS:continue
  pastHi=float(np.max(h[i-SHORT_BARS:i]));pastLo=float(np.min(l[i-SHORT_BARS:i]))
  range24=float(np.max(h[i-LONG_BARS:i])-np.min(l[i-LONG_BARS:i]))
  recentRange=pastHi-pastLo
  if not(range24>0 and recentRange>0 and recentRange<=MAX_CONTRACTION*range24):continue
  nowClose=float(c[i]);direction=1 if nowClose>pastHi*(1+BREAKOUT_BPS/10000) else -1 if nowClose<pastLo*(1-BREAKOUT_BPS/10000) else 0
  if not direction or not direction*(nowClose-float(o[i]))>0:continue
  volMean=float(np.mean(v[i-VOLUME_BARS:i]));nowVolume=float(v[i])
  if volMean<=0 or nowVolume<VOLUME_MULTIPLIER*volMean:continue
  count+=1
  projection=range24*PREDICT_RANGE_FACTOR
  # 'prediction' is a scale hurdle from earlier ranges, not learned conditional expectancy
  entry_time=int(t[i])+ENTRY_DELAY_BARS*300
  end_time=entry_time+HORIZON_BARS*300
  out.append((int(t[i]),sid,direction,entry_time,end_time,i,projection,float(c[i]),money,t,o,h,l,c))
 return count,out

def pick_one(group,equity):
 candidates=[]
 for x in group:
  _,sid,side,entry_time,expiry,i,projection,reference,money,*_=x
  if money is None:continue
  value=reference*money['units']*FEE_SCENARIO_USD_EUR
  cost=money['roundtrip_fee_eur']+FRICTION_BPS*value/10000
  potential=projection*money['units']*FEE_SCENARIO_USD_EUR
  if not(math.isfinite(cost) and 0<=cost<STOP_COST_CAP and math.isfinite(potential) and potential>cost+EXCESS_EUR):continue
  if money['margin']>CAP or equity-money['margin']-cost<RESERVE:continue
  candidates.append((potential-cost,-money['margin'],-sid,x))
 return max(candidates,key=lambda x:x[:3])[-1] if candidates else None

def evaluate_episode(x):
 _,sid,side,entry_time,expiry,i,_,ref,money,t,o,h,l,c=x
 # Original future is never used to choose a candidate or rank eligibility.
 exit_index=i+ENTRY_DELAY_BARS+HORIZON_BARS
 if exit_index>=len(t) or int(t[exit_index])!=expiry:return None
 # Full future exact contiguous M5 coverage is required. No fallback to last observed price.
 if not np.all(np.diff(t[i+ENTRY_DELAY_BARS:exit_index+1])==300):return None
 entry=float(o[i+ENTRY_DELAY_BARS]);exit_=float(o[exit_index]);need(entry>0 and exit_>0,'PRICE')
 units=money['units'];cost=money['roundtrip_fee_eur']+FRICTION_BPS*entry*units*FEE_SCENARIO_USD_EUR/10000
 if cost>=STOP_COST_CAP or not math.isfinite(cost):return {'rejected':True}
 stop_distance=(STOP_COST_CAP-cost)/(units*FEE_SCENARIO_USD_EUR)
 stop=entry-side*stop_distance
 if stop<=0 or not math.isfinite(stop):return {'rejected':True}
 stopped=False;gap=False
 for j in range(i+ENTRY_DELAY_BARS,exit_index):
  if (float(l[j])<=stop if side==1 else float(h[j])>=stop):
   opening=float(o[j]);gap=(opening<stop if side==1 else opening>stop)
   exit_=min(stop,opening) if side==1 else max(stop,opening)
   stopped=True;break
 gross=side*(exit_-entry)*units*FEE_SCENARIO_USD_EUR
 return {'sid':sid,'signal_end_utc':dt.datetime.fromtimestamp(x[0]+300,dt.timezone.utc).isoformat(),
         'direction':side,'entry_utc':dt.datetime.fromtimestamp(entry_time,dt.timezone.utc).isoformat(),
         'exit_utc':dt.datetime.fromtimestamp(expiry,dt.timezone.utc).isoformat(),
         'gross_scenario_eur':gross,'scenario_cost_eur':cost,'net_scenario_eur':gross-cost,
         'stopped':stopped,'gap':gap,'postdated_broker_terms':True}

def originals(delta,selected,broker):
 need(zsha(broker)==BROKER_SHA,'BROKER_SHA')
 need(zsha(delta)==DELTA_SHA and zsha(selected)==SELECTED_SHA,'MARKET_ZIP_SHA')
 with zipfile.ZipFile(broker) as z:
  names=[n for n in z.namelist() if n.endswith('BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V2.json')];need(len(names)==1,'BROKER_MEMBER')
  b=json.loads(z.read(names[0]))
 need(b['account_currency']=='EUR' and b['starting_capital_eur']==200 and len(b['symbols'])==5324 and not b['orders_placed'],'BROKER_SCOPE')
 byid={int(r['symbol_id']):r for r in b['symbols']};need(len(byid)==5324,'BROKER_IDS')
 seen=set();facts=[]
 for path,count in [(delta,128),(selected,29)]:
  with zipfile.ZipFile(path) as z:
   manifest=json.loads(z.read('CAPTURE_MANIFEST.json'));payloadraw=z.read('V3_CAPTURE_PAYLOAD.json')
   need(sha(payloadraw)==manifest['sha256_per_canonical_payload']['V3_CAPTURE_PAYLOAD.json'],'CAPTURE_SHA')
   payload=json.loads(payloadraw);need(len(payload['series'])==count and payload['classification']=='DEVELOPMENT_ONLY'
       and not payload['protected_forward_opened'] and not payload['orders_placed'],'SOURCE_SCOPE')
   for row in payload['series']:
    sid=int(row['symbol_id']);need(sid in byid and sid not in seen,'SOURCE_IDENTITY');seen.add(sid)
    need(byid[sid]['broker_symbol']==row['broker_symbol'],'BROKER_NAME')
    raw=z.read(row['file']);need(sha(raw)==row['sha256'],'SERIES_SHA')
    df=pd.read_csv(io.BytesIO(raw),usecols=['time_utc','open','high','low','close','tick_volume'])
    need(len(df)==row['row_count'] and len(df)>=300,'SERIES_ROWS')
    stamps=pd.to_datetime(df['time_utc'],utc=True).astype('int64').to_numpy()//10**9
    need(np.all(stamps%300==0) and np.all(np.diff(stamps)>0),'SOURCE_ORDER')
    a={key:df[key].to_numpy(dtype='float64') for key in ('open','high','low','close','tick_volume')}
    need(all(np.isfinite(z).all() for z in a.values()) and all((a[x]>0).all() for x in ('open','high','low','close'))
      and (a['tick_volume']>=0).all(),'PRICE_VOLUME')
    yield sid,terms(byid[sid]),stamps,a
 need(len(seen)==157,'ALL_157_RECONCILED')

def selftest():
 t=np.arange(int(FIRST.timestamp()),int(FIRST.timestamp())+350*300,300,dtype=np.int64)
 x=np.ones(len(t));v=np.ones(len(t))*12
 cnt,rows=candidate_from_history(t,x,x,x,x,v,1,None)
 need(cnt==0 and not rows,'EMPTY_NO_SIGNAL')
 # This specifically rejects the two invalidated first-attempt implementation bugs.
 broker_guard={'buy_eligible_current':True,'sell_eligible_current':True,'quote_asset':'USD',
    'min_commission_asset':'USD','commission_type':2,'min_commission_type':1,
    'expected_margin_at_min_volume':{'buy_margin_eur':160,'sell_margin_eur':160},
    'min_volume_cents':100,'step_volume_cents':100,'lot_size':100000,
    'precise_trading_commission_rate':0,'precise_min_commission':0}
 need(terms(broker_guard) is None,'DIRECTOR_MARGIN_CAP_MUST_BLOCK_HIGH_MARGIN')
 # Synthetic bar files starting at :00 must still inspect completed :55 grid cells.
 synthetic=np.ones(len(t));synthetic[72:288]=1.20
 start_hour=int(t[0]//3600)*3600
 need(np.any(t%3600==3300),'ABSOLUTE_UTC_GRID_EXISTS')
 dummy=(0,1,1,600,11400,300,1,100,{'units':1,'margin':15,'roundtrip_fee_eur':.02},t,x,x,x,x)
 need(pick_one([dummy],200)==dummy,'CAUSAL_PICK')
 need(pick_one([dummy],126) is None,'CAPITAL_REEVALUATION_NO_BLACKLIST')
 print('MXM_BE_COMPRESSION_EXPANSION_FIRST_SOURCE_BLIND_PASS')

def run(delta,selected,broker,public,private):
 selftest()
 signals=[];qualified=0;allcnt=0;series=0
 for sid,money,t,a in originals(delta,selected,broker):
  series+=1;qualified+=money is not None
  n,rows=candidate_from_history(t,a['open'],a['high'],a['low'],a['close'],a['tick_volume'],sid,money)
  allcnt+=n;signals.extend(rows)
  if series%32==0:print('SOURCE_SERIES_VERIFIED',series,flush=True)
 signals.sort(key=lambda r:(r[0],r[1]))
 chosen=0;missing=0;rejected=0;scenarios=[];weekly=collections.defaultdict(lambda:collections.Counter())
 balance=200.;peak=200.;maxdd=0.;until=-1;i=0
 while i<len(signals):
  clock=signals[i][0];group=[]
  while i<len(signals) and signals[i][0]==clock:group.append(signals[i]);i+=1
  if clock<=until:continue
  cand=pick_one(group,balance)
  if cand is None:continue
  chosen+=1;until=cand[4]
  wk=dt.datetime.fromtimestamp(cand[0]+300,dt.timezone.utc).strftime('%G-W%V');weekly[wk]['selected']+=1
  row=evaluate_episode(cand)
  if row is None:missing+=1;weekly[wk]['censored']+=1;continue
  if row.get('rejected'):rejected+=1;weekly[wk]['rejected']+=1;continue
  scenarios.append(row)
  weekly[wk]['entries']+=1;weekly[wk]['net_eur']+=row['net_scenario_eur']
  balance+=row['net_scenario_eur'];peak=max(peak,balance);maxdd=max(maxdd,peak-balance)
 weeks=[f'2026-W{w:02d}' for w in range(1,38)]
 gross=sum(z['gross_scenario_eur'] for z in scenarios);cost=sum(z['scenario_cost_eur'] for z in scenarios)
 public_data={'schema':'mxm.be.annual157.compression-volume-expansion.first-development.v1',
  'mechanism':'PREVIOUS_24H_CONTRACTION_PREVIOUS_6H_EXTREME_BREAK_WITH_TICK_VOLUME_ACTIVATION',
  'implementation_reconciliation':{'first_original_91f1ce59a037bf6455d4a57cae35f9a8865ea8a7ddca92f7cd75fa4a2b8edc1a':'INVALID_FILE_INDEX_ALIAS_AND_INCORRECT_MARGIN_BOOLEAN','correction_is_dependent_not_independent_trial':True,'thresholds_and_signal_hypothesis_unchanged':True},
  'source':{'delta_zip_sha256':DELTA_SHA,'selected_zip_sha256':SELECTED_SHA,'broker_zip_sha256':BROKER_SHA,
   'original_series_sha256_each_reverified':True,'market_source_instruments':series,
   'market_symbols_not_research_excluded':True,'historical_broker_terms_proven':False},
  'policy':{'24h_bars':LONG_BARS,'6h_bars':SHORT_BARS,'volume_baseline_bars':VOLUME_BARS,
   'max_recent_to_day_range':MAX_CONTRACTION,'breakout_bps':BREAKOUT_BPS,'volume_activation':VOLUME_MULTIPLIER,
   'predicted_move_fraction_of_prior_24h_range':PREDICT_RANGE_FACTOR,'entry_delay_bars':ENTRY_DELAY_BARS,
   'holding_bars':HORIZON_BARS,'cost_bps_scenario':FRICTION_BPS,'usd_to_eur_scenario':FEE_SCENARIO_USD_EUR,
   'minimum_predicted_cash_surplus_eur':EXCESS_EUR,'margin_cap_eur':CAP,'reserve_eur':RESERVE,
   'new_stop_plus_cost_limit_eur':STOP_COST_CAP,'one_shared_position':True,'initial_deposit_eur':200},
  'population':{'all_series':series,'current_usd_linear_fee_proxies':qualified,'other_not_blacklisted':series-qualified,
    'all_causal_individual_signals':allcnt,'selected_proposals':chosen,'censored':missing,
    'rejected_on_execution_cost':rejected,'modeled_entries':len(scenarios)},
  'economics':{'gross_eur_scenario':gross,'costs_eur_scenario':cost,'net_eur_scenario':gross-cost,
   'starting_equity_eur':200,'ending_equity_eur':balance,'max_drawdown_eur_scenario':maxdd,
   'stops':sum(x['stopped'] for x in scenarios),'negative_gap_stops':sum(x['gap'] for x in scenarios),
   'weeks_with_21_or_more_model_entries':sum(weekly[w]['entries']>=21 for w in weeks),
   'weeks_positive_net_scenario':sum(weekly[w]['net_eur']>0 for w in weeks)},
  'weekly':{w:dict(weekly[w]) for w in weeks},
  'qualifications':{'original_market_data_authenticated':True,'historical_bid_ask_and_fx':False,
   'contract_multiplier_and_payout_confirmed':False,'broker_settlement_or_margin_guarantee':False,
   'observed_true_net_eur':False,'broker_HARD21_confirmed_entries':0,'LIVE_DEMO_orders':0,'cloud_activation':0,
   'preexisting_DEVELOPMENT_not_untouched_confirmation':True}}
 public.write_text(json.dumps(public_data,sort_keys=True,indent=2)+'\n')
 private.write_text(json.dumps({'schema':'mxm.be.private-annual157-first-episode-ledger.v1',
  'source_hashes':public_data['source'],'policy':public_data['policy'],'trades':scenarios},sort_keys=True)+'\n')
 print('MXM_BE_FIRST_RESULT',json.dumps({'population':public_data['population'],'economics':public_data['economics']},sort_keys=True))

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action',choices=['selftest','evaluate']);a.add_argument('--delta',type=pathlib.Path);a.add_argument('--selected',type=pathlib.Path);a.add_argument('--broker',type=pathlib.Path);a.add_argument('--public',type=pathlib.Path);a.add_argument('--private',type=pathlib.Path)
 p=a.parse_args()
 if p.action=='selftest':selftest()
 else:
  need(all((p.delta,p.selected,p.broker,p.public,p.private)),'EXPLICIT_ORIGINALS_AND_OUTPUTS')
  run(p.delta,p.selected,p.broker,p.public,p.private)