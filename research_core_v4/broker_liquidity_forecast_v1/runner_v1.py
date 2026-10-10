"""Pre-frozen authentic broker-native next-5min quote spread cost discovery.
No directional trading signal, no account mutation, owner-encrypted outputs only.
"""
import os,json,math,tempfile,pathlib
from collections import defaultdict,Counter
from datetime import datetime,timezone
import numpy as np
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.multiscale_regime_v1.cost_universe_v1 import eligibility
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,RateLimiter
from m6.ctrader_transport import StdlibCTraderTransport
from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as enums
from m6.ctrader_capture import require_read_only_request
from m6.cost_evidence import decode_ctrader_tick_page
from research_core_v4.owner_recovery_v1.readback_v1 import iso
e=rt.e;P='research_core_v4/broker_liquidity_forecast_v1/';PHASE='GATE'
START=1787184000;END=1789603200;BLOCK=604800
def gate():
 h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
 e.w.old.need(a['orders'] is False and a['protected_forward'] is False and not a['independent_acceptance_claimed'],'LIQUIDITY_AUTHORIZATION')
 e.w.old.need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-broker-liquidity-forecast-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_GUARD')
 e.a.ancestor(a['base_head'],h)
 for p,v in a['bindings'].items():e.w.old.need(e.w.old.filehash(p)==v,'SOURCE_DRIFT')
 original=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
 for p,v in original['bindings'].items():e.w.old.need(e.w.old.filehash(p)==v,'ORIGINAL_SOURCE_DRIFT')
 e.w.old.need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED')
 tag='mxm-broker-native-liquidity-'+a['invocation_id']
 e.w.old.need(not e.w.v2.existing_ref(tag),'ALREADY_CONSUMED')
 e.w.old.api('git/refs',{'ref':'refs/tags/'+tag,'sha':h})
 return h,a
def shortlist(cost,master):
 universe={m['symbol_id']:m for m in master};valid=defaultdict(list);exclusion=Counter()
 mapping={'Commodities (Cash)':'CASH_COMMODITY_CFD','Currency Index (Spot)':'CURRENCY_INDEX_CFD','Forwards - Indices':'FORWARD_OR_FUTURES_STYLE_CFD','Forwards - Commodities':'FORWARD_OR_FUTURES_STYLE_CFD','Forwards - Treasuries':'FORWARD_OR_FUTURES_STYLE_CFD'}
 for raw in cost['metadata_rows']:
  sid=int(raw['symbol_id']);ms=universe.get(sid)
  if ms is None or raw['broker_symbol']!=ms['symbol'] or raw['asset_class']!=ms['asset_class']:
   exclusion['MASTER_IDENTITY_MISMATCH_OR_NOT_M5']+=1;continue
  r=dict(raw);r['product_type']=mapping.get(r['asset_class'],r['product_type'])
  good,why=eligibility(r)
  if not good:exclusion.update(why);continue
  valid[r['asset_class']].append(r)
 chosen=[];classes=set()
 for part,num in [('Forex',2),('Indices',1),('Metals',1),('Commodities',1)]:
  matching=sorted((c for c in valid if part.lower() in c.lower() and c not in classes),key=lambda c:(-len(valid[c]),c))
  if not matching:continue
  c=matching[0];classes.add(c)
  rank=sorted(valid[c],key=lambda r:(0 if r.get('commission_rate_normalized') is not None and r.get('min_commission_normalized') is not None else 1,max(float(r['buy_margin_eur']),float(r['sell_margin_eur'])),int(r['symbol_id'])))
  chosen.extend(rank[:num])
 return chosen,{'current_margin50_by_asset_class':{k:len(v) for k,v in sorted(valid.items())},'exclusion_reasons':dict(exclusion),'ranking':'PREOUTCOME_CLASS_COMMISSION_COMPLETENESS_MARGIN_SYMBOL_ID'}
def calendar():
 return [(b,START+b*BLOCK+d*86400+h*3600+600) for b in range(4) for d in (1,4,5,6) for h in (8,13)]
def acquire(chosen,grid,digits,budget):
 quotes={};counts=Counter();requests=0;state='ACCESS_NOT_TESTED';failure=None
 creds=[os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')]
 if not all(creds):return quotes,{'state':'CREDENTIALS_UNAVAILABLE','requests':0,'counts':{}}
 tr=StdlibCTraderTransport()
 try:
  tr.connect();account=authenticate_segment(tr,*creds);limiter=RateLimiter(min_interval=.25)
  for row in chosen:
   sid=int(row['symbol_id'])
   for _,t in grid:
    for t0 in (t-300,t,t+300):
     sides={};raw_pages=[]
     for name,kind in (('bid',enums.BID),('ask',enums.ASK)):
      e.w.old.need(requests<budget,'QUOTE_REQUEST_CAP')
      req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,type=kind,fromTimestamp=t0*1000-60000,toTimestamp=t0*1000)
      require_read_only_request(type(req).__name__);limiter.before_send();res=tr.request(req,timeout=25);requests+=1
      if isinstance(res,m.ProtoOAErrorRes):
       counts['PROVIDER_ERROR']+=1;sides[name]={'state':'PROVIDER_ERROR','code':res.errorCode};raw_pages.append({'side':name,'error_code':res.errorCode});continue
      e.w.old.need(isinstance(res,m.ProtoOAGetTickDataRes),'TICK_RESPONSE_TYPE')
      enc=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in res.tickData]
      page=decode_ctrader_tick_page(enc)
      e.w.old.need(all(t0*1000-60000<=x.timestamp_ms<=t0*1000 for x in page),'TICK_TIMESTAMP_DOMAIN')
      raw_pages.append({'side':name,'encoded_ticks':enc,'hasMore':bool(res.hasMore),'from_ms':t0*1000-60000,'to_ms':t0*1000})
      if res.hasMore:counts['PAGINATION_UNRESOLVED']+=1;sides[name]={'state':'PAGINATION_UNRESOLVED','rows':len(page)}
      elif not page:counts['NO_QUOTE']+=1;sides[name]={'state':'NO_QUOTE'}
      else:
       last=page[-1];sides[name]={'state':'VALID','price':round(last.raw_tick/100000,digits[sid]),'age_ms':t0*1000-last.timestamp_ms,'count60':len(page)}
     ok=all(sides[z].get('state')=='VALID' for z in ('bid','ask'))
     if ok and not 0<sides['bid']['price']<sides['ask']['price']:ok=False;counts['CROSSED_OR_ZERO_SPREAD']+=1
     quotes[(sid,t0)]={'valid':ok,'sides':sides,'raw_pages':raw_pages};counts['BOUNDARIES_ATTEMPTED']+=1;counts['VALID_TWO_SIDED']+=int(ok)
  state='CAPTURE_COMPLETE_WITH_MISSINGNESS_PRESERVED'
 except Exception as exc:
  state='PARTIAL_OR_ACCESS_FAILURE';failure=type(exc).__name__
 finally:tr.close()
 return quotes,{'state':state,'failure_class':failure,'requests':requests,'counts':dict(counts)}
def quote_state(q):
 if not q or not q['valid']:return None
 ask=q['sides']['ask'];bid=q['sides']['bid'];spread=10000*math.log(ask['price']/bid['price'])
 if not math.isfinite(spread) or spread<=0:return None
 return {'spread':spread,'bid_count':bid['count60'],'ask_count':ask['count60'],'bid_age':bid['age_ms'],'ask_age':ask['age_ms']}
def feature(old,cur):
 return [cur['spread'],cur['spread']-old['spread'],math.log1p(cur['bid_count']+cur['ask_count']),math.log1p(old['bid_count']+old['ask_count']),(cur['bid_age']+cur['ask_age'])/1000,(cur['bid_age']-cur['ask_age'])/1000]
def ridge(train,x):
 X=np.asarray([row[0] for row in train],float);Y=np.asarray([row[1] for row in train],float)
 mu=X.mean(axis=0);sd=np.maximum(X.std(axis=0),1e-9);A=(X-mu)/sd
 return float(Y.mean()+((np.asarray(x)-mu)/sd)@np.linalg.solve(A.T@A+25*np.eye(6),A.T@(Y-Y.mean())))
def numerical(chosen,grid,quotes):
 trials=[]
 for r in chosen:
  sid=int(r['symbol_id']);train=[]
  for block,t in grid:
   old=quote_state(quotes.get((sid,t-300)));cur=quote_state(quotes.get((sid,t)));future=quote_state(quotes.get((sid,t+300)))
   x=feature(old,cur) if old and cur else None
   y=future['spread'] if future else None
   eligible=x is not None and len(train)>=6
   pred=ridge(train,x) if eligible else None
   reason='FEATURE_QUOTE_MISSING' if x is None else 'TRAINING_UNDER6' if not eligible else 'FUTURE_QUOTE_MISSING' if y is None else 'PAIRED_SUPPORTED'
   trials.append({'symbol_id':sid,'asset_class':r['asset_class'],'block':block,'action_utc':datetime.fromtimestamp(t,timezone.utc).isoformat(),'iso_utc':iso(t),'train_size':len(train),'reason':reason,'baseline_spread_bps':cur['spread'] if eligible else None,'model_spread_bps':pred,'future_authentic_spread_bps':y,'all_quote_ages_le5sec':bool(old and cur and future and all(a['bid_age']<=5000 and a['ask_age']<=5000 for a in (old,cur,future)))})
   if x is not None and y is not None:train.append((x,y))
 return trials
def diagnostics(trials):
 def calc(rows):
  counts=Counter(x['reason'] for x in rows);a=[x for x in rows if x['reason']=='PAIRED_SUPPORTED']
  B=[(x['baseline_spread_bps']-x['future_authentic_spread_bps'])**2 for x in a]
  M=[(x['model_spread_bps']-x['future_authentic_spread_bps'])**2 for x in a]
  return {'scheduled':len(rows),'paired_supported':len(a),'reasons':dict(counts),'baseline_mse_bps2':sum(B)/len(a) if a else None,'model_mse_bps2':sum(M)/len(a) if a else None,'paired_increment_mse_bps2':sum(b-m for b,m in zip(B,M))/len(a) if a else None,'mean_future_broker_spread_bps':sum(x['future_authentic_spread_bps'] for x in a)/len(a) if a else None,'all_quotes_age_le5s_pairs':sum(x['all_quote_ages_le5sec'] for x in a)}
 return {'global':calc(trials),'four_original_blocks':[{'block':b,**calc([x for x in trials if x['block']==b])} for b in range(4)],'iso_utc':[{'week':w,'complete_iso_week':w in ('2026-W35','2026-W36','2026-W37'),**calc([x for x in trials if x['iso_utc']==w])} for w in sorted({x['iso_utc'] for x in trials})],'asset_classes':[{'class':c,**calc([x for x in trials if x['asset_class']==c])} for c in sorted({x['asset_class'] for x in trials})],'symbols':[{'symbol_id':sid,**calc([x for x in trials if x['symbol_id']==sid])} for sid in sorted({x['symbol_id'] for x in trials})],'dependence':'DESCRIPTIVE_FOUR_BLOCKS_NONINDEPENDENT_NO_IID_INFERENCE_OR_FAMILYWISE_PROMOTION'}
def main():
 global PHASE
 os.umask(0o077);head,a=gate();grid=calendar();e.w.old.need(len(grid)==32 and START+4*BLOCK==END and all(START<=t-360<t+300<END for _,t in grid),'FIXED_CALENDAR')
 master,_,digits,_=e.w.old.verify_science()
 with tempfile.TemporaryDirectory(prefix='mxm-liquidity-',dir=os.environ['RUNNER_TEMP']) as dirname:
  tmp=pathlib.Path(dirname);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'PRIVATE_KEY_BINDING')
  PHASE='PRICE_BLIND_COST_SELECTION';cost,costsource=load_asset(key,fp,tmp,a['cost_source']);chosen,universe=shortlist(cost,master)
  e.w.old.need(2<=len(chosen)<=5,'MINIMUM_CROSS_CLASS_SHORTLIST')
  PHASE='AUTHENTIC_BROKER_TICK_ACQUISITION';quotes,acquired=acquire(chosen,grid,digits,960)
  PHASE='ACTUAL_NUMERIC_DEVELOPMENT';trials=numerical(chosen,grid,quotes);stats=diagnostics(trials)
  summary={'schema':'mxm.private.broker.future.spread.cost.development.v1','source_head':head,'state':'NUMERIC_EXECUTED_ON_ACQUIRED_QUOTES' if acquired['state'].startswith('CAPTURE_COMPLETE') else 'PARTIAL_OR_BLOCKED','design_sha256':a['bindings'][P+'DESIGN_V1.json'],'previous_scientific_exacts_replayed':False,'native_cost_provenance':costsource,'price_blind_universe':universe,'native_capture':acquired,'current_contracts':[{'symbol_id':int(r['symbol_id']),'broker_symbol':r['broker_symbol'],'asset_class':r['asset_class'],'minimum_margin_eur':max(float(r['buy_margin_eur']),float(r['sell_margin_eur'])),'min_volume_cents':r['min_volume_cents'],'commission_unit_current':r.get('commission_rate_unit')} for r in chosen],'new_experiment':stats,'historical_commission_financing_swap_conversion':'UNKNOWN','spread_cannot_certify_fills':True,'slippage':'UNKNOWN','eur200_free_capital_reserve_eur':50,'orders':0,'protected_forward':False,'actual_trades':0,'net_edge_certified':False,'HARD21_certified':False,'independent_confirmation':False}
  PHASE='ENCRYPTED_OWNER_RESULT';rt.output(head,a,tmp,key,'brokerliquidity',{'summary':summary,'all_predeclared_events':trials,'private_historical_ticks':[{'symbol_id':sid,'timestamp_utc':datetime.fromtimestamp(t,timezone.utc).isoformat(),**v} for (sid,t),v in sorted(quotes.items())],'private_current_contract_metadata':chosen},summary)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
