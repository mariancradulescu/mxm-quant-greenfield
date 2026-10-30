"""One frozen broad original M5 conditional EUR200 cash policy (not native fills).

Distinct from closed PRIMARY145 H1 pooled Ridge/LightGBM, peer dislocation,
quote triangle, commodity carry and variance-onset studies: a predeclared
M5 wick-rejection policy choosing at most one OPEN position at a time by
available MINIMUM-TICKET EUR wick opportunity / hypothesized cash friction.
No parameter tuning, no symbol outcome-based selection. Single cost=10bps.
Not fully broker certified, never a replacement for actual BID/ASK or real fills.
"""
import argparse, collections, csv, hashlib, io, json, math, pathlib, zipfile
from datetime import datetime,timezone
import numpy as np
import pandas as pd

DIR=pathlib.Path('/mnt/data/files');OUT=pathlib.Path('/mnt/data')
BROKER_ZIP=DIR/'MXM_COMPETITION_BROKER_UNIVERSE_V2.zip'
ZIPS=[DIR/'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip',DIR/'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip']
BROKER_SHA='9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77'
FIRST_TEST_UTC='2026-01-05T00:00:00Z'; LAST_TEST_UTC='2026-09-14T00:00:00Z'
EUR_PER_USD=.90;COST_BPS_ROUNDTRIP=10.0;HOLD_BARS=12
MAX_MARGIN=80;FREE_RESERVE=120;MAX_ENTRY_RISK=1.8;INITIAL=200
# Local completed M5 candle last bar rejection: longest wick >= 55% of
# candle range, and close on other 25% end with candle body in direction.
WICK_MIN=.55;CLOSE_END=.25;FLOOR_CASH_EDGE=.20

def need(x,why):
 if not x:raise ValueError('MXM_WICK_'+why)

def selftest():
 need(EUR_PER_USD==.9 and COST_BPS_ROUNDTRIP==10 and HOLD_BARS==12,'SOURCE_BLIND_POLICY_ID')
 def direction(o,h,l,c):
  width=h-l
  if width<=0:return 0
  lower=min(o,c)-l; upper=h-max(o,c)
  if lower/width>=WICK_MIN and (h-c)/width<=CLOSE_END and c>o:return 1
  if upper/width>=WICK_MIN and (c-l)/width<=CLOSE_END and c<o:return -1
  return 0
 need(direction(10,11,8,10.7)==1,'LONG_WICK')
 need(direction(10,12,9,9.3)==-1,'SHORT_WICK')
 need(direction(10,11,9,10)==0,'NO_BAR_SIGNAL')
 return direction

def source():
 need(hashlib.sha256(BROKER_ZIP.read_bytes()).hexdigest()==BROKER_SHA,'BROKER_SHA')
 with zipfile.ZipFile(BROKER_ZIP) as z:
  name=[a for a in z.namelist() if a.endswith('BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V2.json')]
  need(len(name)==1,'BROKER_MEMBER')
  broker=json.loads(z.read(name[0]))
 need(broker['account_currency']=='EUR' and broker['starting_capital_eur']==200 and len(broker['symbols'])==5324,'BROKER_ACCOUNT')
 bmap={int(a['symbol_id']):a for a in broker['symbols']}
 for p in ZIPS:
  with zipfile.ZipFile(p) as z:
   cap=json.loads(z.read('CAPTURE_MANIFEST.json'));payraw=z.read('V3_CAPTURE_PAYLOAD.json')
   need(hashlib.sha256(payraw).hexdigest()==cap['sha256_per_canonical_payload']['V3_CAPTURE_PAYLOAD.json'],'CAPTURE_MANIFEST')
   pay=json.loads(payraw);need(pay['classification']=='DEVELOPMENT_ONLY' and not pay['protected_forward_opened'],'DEVELOPMENT_SOURCE')
   for item in pay['series']:
    sid=int(item['symbol_id']);b=bmap[sid]
    # frozen source-only qualification, no returns inspected yet
    if not (b['quote_asset']=='USD' and b['commission_type']==2 and b['min_commission_asset']=='USD' and b['min_commission_type']==1 and b['buy_eligible_current'] and b['sell_eligible_current']):continue
    margin=b['expected_margin_at_min_volume'];minvol=int(b['min_volume_cents'])
    if not (0<margin['buy_margin_eur']<=MAX_MARGIN and 0<margin['sell_margin_eur']<=MAX_MARGIN):continue
    raw=z.read(item['file']);need(hashlib.sha256(raw).hexdigest()==item['sha256'],'RAW_ARCHIVE_HASH')
    frame=pd.read_csv(io.BytesIO(raw),usecols=['time_utc','open','high','low','close'],dtype={'open':'float64','high':'float64','low':'float64','close':'float64'})
    need(len(frame)==int(item['row_count']),'SOURCE_COUNT')
    t=pd.to_datetime(frame['time_utc'],utc=True).to_numpy(dtype='datetime64[s]').astype('int64')
    prices=[frame[x].to_numpy() for x in ('open','high','low','close')]
    need(np.all(t[1:]>t[:-1]) and all(np.isfinite(x).all() and (x>0).all() for x in prices),'CAUSAL_TIMESTAMP_OHLC')
    yield sid,b,t,*prices

def evaluate():
 direction=selftest(); proposals=[];eligible_sources=0;eligible_groups=collections.Counter();source_processed=set()
 left=int(pd.Timestamp(FIRST_TEST_UTC).timestamp());right=int(pd.Timestamp(LAST_TEST_UTC).timestamp())
 for sid,b,t,o,h,l,c in source():
  need(sid not in source_processed,'SOURCE_ID_DUPLICATED');source_processed.add(sid)
  eligible_sources+=1;eligible_groups[b['asset_class']]+=1
  units=int(b['min_volume_cents'])/100;price_per_unit_eur=units*EUR_PER_USD
  declared_fee_eur=2*max((int(b['min_volume_cents'])/int(b['lot_size']))*(int(b['precise_trading_commission_rate'])/1e8),int(b['precise_min_commission'])/1e8)*EUR_PER_USD
  # decision hourly 13..19 UTC weekdays; 13-week past source burn-in already frozen.
  for i in range(12,len(t)-2):
   epoch=t[i]
   if epoch<left or epoch>=right:continue
   if (epoch%3600!=0) or ((epoch//86400 + 3)%7)>=5 or (epoch//3600%24 not in (13,14,15,16,17,18,19)):continue
   # exact prior 12 completed M5 bars ending t; no backwards healed gaps
   if t[i]-t[i-12]!=3600:continue
   k=i-1;sig=direction(o[k],h[k],l[k],c[k])
   if not sig:continue
   past_range=max(h[i-12:i])-min(l[i-12:i]);need(past_range>=0,'RANGE')
   # dated broker fee + 10bps cash slippage/spread; no cost regarded as zero
   cost=declared_fee_eur+COST_BPS_ROUNDTRIP/10000*price_per_unit_eur*o[k]
   wick=(min(o[k],c[k])-l[k]) if sig>0 else (h[k]-max(o[k],c[k]))
   prior_wick_eur=price_per_unit_eur*wick
   # required observable positive cash-scale headroom: not a predicted edge.
   if prior_wick_eur<=cost+FLOOR_CASH_EDGE:continue
   stop_distance=min(.60*past_range,MAX_ENTRY_RISK/price_per_unit_eur)
   if stop_distance<=0 or stop_distance*price_per_unit_eur<=cost:continue
   score=(prior_wick_eur-cost)/max(cost,.001)
   # quote from NEXT genuine M5 open; contract multiplier and actual FX unverified
   proposals.append({'i':i,'sid':sid,'asset_class':b['asset_class'],'t':int(epoch),'score':score,'direction':sig,'units':units,
    'price_per_unit_eur':price_per_unit_eur,'fee_eur':declared_fee_eur,'stop_distance':stop_distance,'cost_bps':COST_BPS_ROUNDTRIP,
    'margin':max(float(b['expected_margin_at_min_volume']['buy_margin_eur']),float(b['expected_margin_at_min_volume']['sell_margin_eur'])),
    'time':t,'open':o,'high':h,'low':l,'close':c})
 # Every candidate was constructed from past-only facts and unmodified frozen roster.
 proposals.sort(key=lambda z:(z['t'],-z['score'],z['sid']))
 portfolio_equity=float(INITIAL);peak=INITIAL;maxdd=0;trades=[];rejections=collections.Counter();censored=0
 closed_at=left; considered=0
 for e in proposals:
  if e['t']<closed_at:continue
  considered+=1
  if e['margin']+e['fee_eur']/2+FREE_RESERVE>portfolio_equity:
   rejections['minimum_ticket_cash_and_120_reserve']+=1;continue
  idx=e['i'];t=e['time'];o=e['open'];hi=e['high'];lo=e['low'];direction=e['direction'];ppu=e['price_per_unit_eur'];entry=idx+1
  # prohibit using future observability as a criterion to cherry-pick a signal
  if entry+HOLD_BARS>=len(t) or t[entry]!=e['t']+300 or t[entry+HOLD_BARS]!=e['t']+300*(HOLD_BARS+1):
   censored+=1;rejections['future_source_unobservable_ACCOUNT_PATH_INVALID']+=1;break
  buy=float(o[entry]);last=float(o[entry+HOLD_BARS]);stop=buy-direction*e['stop_distance'];hit=False
  for j in range(entry,entry+HOLD_BARS):
   if direction>0 and lo[j]<=stop:hit=True;break
   if direction<0 and hi[j]>=stop:hit=True;break
  exit_price=stop if hit else last
  cost_eur=e['fee_eur']+COST_BPS_ROUNDTRIP/10000*ppu*buy
  net=ppu*direction*(exit_price-buy)-cost_eur
  portfolio_equity+=net;peak=max(peak,portfolio_equity);maxdd=max(maxdd,peak-portfolio_equity)
  closed_at=int(t[entry+HOLD_BARS])
  trades.append({'week':pd.Timestamp(e['t'],unit='s',tz='UTC').strftime('%G-W%V'),'pnl_eur':net,'symbol_id':e['sid'],'asset_class':e['asset_class'],'stopped':hit,'cash_before':portfolio_equity-net,'cash_after':portfolio_equity,'cost_eur':cost_eur,'entry_t':int(t[entry]),'exit_t':int(t[entry+HOLD_BARS])})
 weeks=collections.defaultdict(lambda:{'proposals':0,'net_eur':0,'stopped':0})
 for a in trades:
  d=weeks[a['week']];d['proposals']+=1;d['net_eur']+=a['pnl_eur'];d['stopped']+=int(a['stopped'])
 out={'schema':'mxm.broad-157-original-m5-wick-rejection-single-eur200-development-first.v1',
  'policy':'Fixed causal last-completed M5 wick rejection + past 60m USD min-ticket wick cash headroom; one shared EUR200 account, strict 5m later original open, fixed 60m holding with first adverse native OHLC stop. ONE first outcome, NO retune.',
  'source':'Original DELTA128 + SELECTED29 annual M5, 157 broker ID mapping; source eligibility USD quoted, commission type2 USD and minimum EUR80 margin is CAUSAL PRICE-BLIND.',
  'sample':{'start_utc':FIRST_TEST_UTC,'end_utc':LAST_TEST_UTC,'eligible_broker_only_sources':eligible_sources,'by_class':dict(eligible_groups)},
  'cost_assumption':{'roundtrip_spread_slippage_bps':10,'eur_per_usd':.9,'fee':'Declared captured per-side minimum USD 2026-09-22 (NOT actual historical charge)','cash_floor_extra_eur':FLOOR_CASH_EDGE},
  'capital':{'initial_eur':200,'continuous':True,'minimum_reserve_eur':FREE_RESERVE,'margin_cap_eur':MAX_MARGIN,'stop_risk_limit_eur':MAX_ENTRY_RISK,'single_position':True},
  'forward_account_result':{'source_supported_proposals':len(proposals),'considered_decisions':considered,'evaluated_episodes':len(trades),'account_path_censored':censored,'rejections':dict(rejections),'final_cash_eur':round(portfolio_equity,6),'net_cash_eur':round(portfolio_equity-INITIAL,6),'max_closed_equity_drawdown_eur':round(maxdd,6),'winning_weeks':sum(1 for x in weeks.values() if x['net_eur']>0),'weeks_with_21_model_entries':sum(1 for x in weeks.values() if x['proposals']>=21),'evaluated_weeks':len(weeks),'stop_count':sum(x['stopped'] for x in trades),'cash_summary_by_asset_class':{k:round(sum(x['pnl_eur'] for x in trades if x['asset_class']==k),6) for k in sorted(set(x['asset_class'] for x in trades))}},
  'limitations':{'actual_historical_bid_ask_spread_slippage':False,'broker_fills':0,'product_payoff_multiplier_verified':False,'broker_contract_settlement_verified':False,'source_usd_eur_time_aligned':False,'commission_historical_certified':False,'historical_margin_certified':False,'stops_broker_filled':False,'native_cloud_certified':False,'HARD21_proven':False,'net_edge_robust_or_independently_confirmed':False},
  'closed_originals_reused_or_retuned':False,'orders':0,'protected_source_opened':False}
 private={'schema':'mxm.private.first-broad-conditional-eur-account-ledger.v1','episode_ledger':trades,'source_support_rejections':dict(rejections)}
 out['private_ledger_sha256']=hashlib.sha256(json.dumps(private,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return out,private

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['selftest','evaluate']);args=parser.parse_args();selftest()
 if args.mode=='selftest':print('MXM_BROAD_CASH_WICK_FROZEN_SELFTEST_PASS')
 else:
  r,p=evaluate();(OUT/'MXM_BROAD_WICK_FIRST_CASH_PUBLIC.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');(OUT/'MXM_BROAD_WICK_FIRST_CASH_PRIVATE.json').write_text(json.dumps(p,sort_keys=True,separators=(',',':'))+'\n');print(json.dumps(r['forward_account_result'],indent=2))
