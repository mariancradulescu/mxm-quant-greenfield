"""Authentic Pepperstone read-only directional quote-side event-rate discovery.
Frozen before any new outcomes. No trades or private plaintext publication.
"""
import os,json,math,tempfile,pathlib,time
from datetime import datetime,timezone
from collections import Counter,defaultdict
from statistics import median
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.multiscale_regime_v1.cost_universe_v1 import eligibility
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,RateLimiter
from m6.ctrader_transport import StdlibCTraderTransport
from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as enums
from m6.ctrader_capture import require_read_only_request
from m6.cost_evidence import decode_ctrader_tick_page
from research_core_v4.owner_recovery_v1.readback_v1 import iso
e=rt.e;P='research_core_v4/native_update_asymmetry_v1/';PHASE='GATE'
START=1787184000;END=1789603200;WEEK=604800;HORIZON=14400
NOMINEES={
 'FOREX_MAJOR':('EURUSD','USDJPY','GBPUSD','AUDUSD','EURJPY','GBPJPY','USDCHF','NZDUSD'),
 'INDEX_SPOT':('NAS100','US500','GER40','US400','UK100'),
 'METAL_SPOT':('XAUUSD','XAGUSD','XPTUSD'),
 'ENERGY_CFD':('USOIL','UKOIL','WTI','Brent')
}
CAP_BY_GROUP={'FOREX_MAJOR':2,'INDEX_SPOT':1,'METAL_SPOT':1,'ENERGY_CFD':1}
def stop(test,label):e.w.old.need(bool(test),label)
def gate():
 h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
 stop(a['orders'] is False and a['protected_forward'] is False and a['independent_confirmation'] is False,'NO_ORDERS_OR_PROTECTED')
 stop(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_WORKFLOW_REF')==e.w.old.REPO+'/.github/workflows/mxm-authentic-update-asymmetry-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
 e.a.ancestor(a['base_head'],h)
 for path,v in a['bindings'].items():stop(e.w.old.filehash(path)==v,'NEW_SOURCE_BINDING')
 old=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
 for path,v in old['bindings'].items():stop(e.w.old.filehash(path)==v,'HISTORICAL_FROZEN_SOURCE')
 stop(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED')
 claim='mxm-native-update-asymmetry-'+a['invocation_id'];stop(not e.w.v2.existing_ref(claim),'ONE_USE_ALREADY_CLAIMED')
 e.w.old.api('git/refs',{'ref':'refs/tags/'+claim,'sha':h})
 return h,a
def grid():
 return [(b,START+b*WEEK+d*86400+h*3600+600) for b in range(4) for d in (1,4,5,6) for h in (8,13)]
def group(name,clazz):
 if clazz=='Forex (Spot)' and name in NOMINEES['FOREX_MAJOR']:return 'FOREX_MAJOR'
 if 'Indices' in clazz and name in NOMINEES['INDEX_SPOT']:return 'INDEX_SPOT'
 if 'Metals' in clazz and name in NOMINEES['METAL_SPOT']:return 'METAL_SPOT'
 if ('Commodities' in clazz or 'Energy' in clazz) and name in NOMINEES['ENERGY_CFD']:return 'ENERGY_CFD'
 return None
def candidate_universe(cost,master):
 ids={int(a['symbol_id']) for a in master};scanned=Counter();eligible=defaultdict(list);excluded=[]
 for raw in cost['metadata_rows']:
  scanned['full_current_snapshot']+=1
  g=group(raw['broker_symbol'],raw['asset_class'])
  if g is None:continue
  r=dict(raw)
  if r['asset_class']=='Commodities (Cash)':r['product_type']='CASH_COMMODITY_CFD'
  ok,why=eligibility(r)
  if not ok:
   excluded.append({'broker_symbol':r['broker_symbol'],'asset_class':r['asset_class'],'reasons':why});continue
  r['archive_M5_identity_present']=int(r['symbol_id']) in ids
  eligible[g].append(r)
 for group_name in NOMINEES:eligible[group_name].sort(key=lambda x:(NOMINEES[group_name].index(x['broker_symbol']),int(x['symbol_id'])))
 return eligible,{'metadata_scanned':scanned['full_current_snapshot'],'current_eligibility_exclusions':excluded,'M5_archive_identity_rule':'RECORDED_NOT_REQUIRED_FOR_AUTHENTIC_TICK_EXACT','nominees_fixed_prior_to_quote_outcomes':NOMINEES}
def qualgrid():
 from datetime import datetime,timezone
 return [int(datetime(2026,8,d,h,10,tzinfo=timezone.utc).timestamp()) for d in (18,19) for h in (8,13)]
def quote(tr,account,limiter,sid,t,digits,counters,raw,limit):
 sides={};pages=[]
 for name,typ in (('bid',enums.BID),('ask',enums.ASK)):
  stop(counters['requests']<limit,'MAX_READ_ONLY_REQUESTS')
  req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,type=typ,fromTimestamp=t*1000-60000,toTimestamp=t*1000)
  require_read_only_request(type(req).__name__);limiter.before_send()
  result=tr.request(req,timeout=25);counters['requests']+=1
  if isinstance(result,m.ProtoOAErrorRes):
   counters['provider_errors']+=1;sides[name]={'state':'PROVIDER_ERROR','error_code':result.errorCode};pages.append({'side':name,'error_code':result.errorCode});continue
  stop(isinstance(result,m.ProtoOAGetTickDataRes),'HISTORICAL_RESPONSE_TYPE')
  encoded=[{'timestamp':int(v.timestamp),'tick':int(v.tick)} for v in result.tickData]
  decoded=decode_ctrader_tick_page(encoded)
  stop(all(t*1000-60000<=v.timestamp_ms<=t*1000 for v in decoded),'QUOTE_TS_DOMAIN')
  flag=bool(result.hasMore)
  pages.append({'side':name,'encoded':encoded,'hasMore':flag,'boundary_ms':t*1000})
  if flag:
   counters['incomplete_pages']+=1;sides[name]={'state':'PAGINATION_UNRESOLVED','n':len(decoded)}
  elif not decoded:
   counters['no_quote_pages']+=1;sides[name]={'state':'NO_QUOTE'}
  else:
   z=decoded[-1]
   sides[name]={'state':'VALID','price':round(z.raw_tick/100000,digits[sid]),'age_ms':t*1000-z.timestamp_ms,'updates60':len(decoded)}
 valid=all(sides[k]['state']=='VALID' for k in ('bid','ask'))
 if valid and not 0<sides['bid']['price']<sides['ask']['price']:
  counters['invalid_spread']+=1;valid=False
 if valid:counters['valid_two_sided_boundaries']+=1
 entry={'symbol_id':sid,'utc':datetime.fromtimestamp(t,timezone.utc).isoformat(),'sides':sides,'valid':valid,'raw_pages':pages}
 raw.append(entry)
 return entry
def z(q):
 if not q or not q['valid']:return None
 b=q['sides']['bid'];a=q['sides']['ask']
 return {'mid':(a['price']+b['price'])/2,'bid':b['price'],'ask':a['price'],'spread_bps':10000*math.log(a['price']/b['price']),'max_age_ms':max(b['age_ms'],a['age_ms']),'count_bid':b['updates60'],'count_ask':a['updates60']}
def select(groups,quotes):
 selection=[];diagnostics={}
 for g in NOMINEES:
  cands=groups.get(g,[])
  ratings=[]
  for r in cands:
   pts=[z(quotes.get((int(r['symbol_id']),t))) for t in qualgrid()]
   ok=[x for x in pts if x and x['max_age_ms']<=10000]
   spread=median(x['spread_bps'] for x in ok) if len(ok)>=3 else None
   minmar=max(float(r['buy_margin_eur']),float(r['sell_margin_eur']))
   known_fee=all(r.get(k) is not None for k in ('commission_rate_normalized','commission_rate_unit','min_commission_normalized','min_commission_type'))
   ratings.append({'symbol_id':int(r['symbol_id']),'broker_symbol':r['broker_symbol'],'qual_pairs':len(ok),'median_qual_spread_bps':spread,'current_margin_eur':minmar,'current_fee_contract_complete':known_fee,'current_fee_conversion_historical':'UNKNOWN','M5_archive_identity_present':r['archive_M5_identity_present']})
  ranks=sorted([x for x in ratings if x['median_qual_spread_bps'] is not None],key=lambda x:(not x['current_fee_contract_complete'],x['median_qual_spread_bps'],x['current_margin_eur'],x['symbol_id']))
  winners=ranks[:CAP_BY_GROUP[g]]
  selection.extend([next(r for r in cands if int(r['symbol_id'])==x['symbol_id']) for x in winners])
  diagnostics[g]={'nominees':ratings,'chosen_ids':[x['symbol_id'] for x in winners],'qualifier':'AT_LEAST3_OF4_NONCENSORED_FRESH10SEC_QUOTE_PAIRS','ranking':'CURRENT_FEE_CONTRACT_COMPLETENESS_THEN_OBSERVED_QUAL_SPREAD_THEN_MARGIN_THEN_SYMBOLID','outcome_leakage':False}
 return selection,diagnostics
def evaluate(selected,grid,quotes):
 trials=[]
 for r in selected:
  sid=int(r['symbol_id'])
  for block,t in grid:
   previous=z(quotes.get((sid,t-300)));entry=z(quotes.get((sid,t)));future=z(quotes.get((sid,t+HORIZON)))
   sig=0;ref=0;reason='SUPPORTED'
   if previous is None or entry is None:reason='ENTRY_OR_FEATURE_QUOTE_MISSING'
   elif future is None:reason='EXIT_QUOTE_MISSING'
   elif max(previous['max_age_ms'],entry['max_age_ms'],future['max_age_ms'])>10000:reason='STALE_OVER10SECONDS'
   else:
    diff=entry['count_bid']-entry['count_ask']
    sig=(diff>0)-(diff<0)
    ref=(entry['mid']>previous['mid'])-(entry['mid']<previous['mid'])
    if sig==0:reason='NATIVE_SIDE_ACTIVITY_TIE'
    elif ref==0:reason='CAUSAL_MOMENTUM_BASELINE_FLAT'
   paired=reason=='SUPPORTED'
   model=baseline=None;gross=None;midmove=None;spreaddrag=None
   if paired:
    model=10000*math.log(future['bid']/entry['ask']) if sig>0 else 10000*math.log(entry['bid']/future['ask'])
    baseline=10000*math.log(future['bid']/entry['ask']) if ref>0 else 10000*math.log(entry['bid']/future['ask'])
    midmove=10000*math.log(future['mid']/entry['mid'])
    gross=sig*midmove;spreaddrag=gross-model
   trials.append({'sid':sid,'name':r['broker_symbol'],'class':r['asset_class'],'block':block,'iso_utc':iso(t),'action':t,'exit':t+HORIZON,'reason':reason,'signal_direction':sig if paired else None,'baseline_direction':ref if paired else None,'bid_vs_ask_updates':(entry['count_bid']-entry['count_ask']) if entry else None,'signed_quote_side_model_bps':model,'paired_quote_side_baseline_bps':baseline,'model_gross_midpoint_bps':gross,'spread_drag_bps':spreaddrag,'max_age_ms':max(previous['max_age_ms'],entry['max_age_ms'],future['max_age_ms']) if previous and entry and future else None})
 return trials
def aggregate(trials):
 def report(rows):
  s=Counter(x['reason'] for x in rows);pairs=[x for x in rows if x['reason']=='SUPPORTED']
  model=[x['signed_quote_side_model_bps'] for x in pairs];ref=[x['paired_quote_side_baseline_bps'] for x in pairs]
  return {'scheduled':len(rows),'supported':len(pairs),'reason_counts':dict(s),'mean_model_authentic_quote_side_bps':sum(model)/len(model) if model else None,'mean_same_pair_baseline_quote_side_bps':sum(ref)/len(ref) if ref else None,'paired_increment_quote_side_bps':sum(a-b for a,b in zip(model,ref))/len(model) if model else None,'positive_model_realizations':sum(v>0 for v in model),'mean_gross_midpoint_bps':sum(x['model_gross_midpoint_bps'] for x in pairs)/len(pairs) if pairs else None,'mean_spread_drag_bps':sum(x['spread_drag_bps'] for x in pairs)/len(pairs) if pairs else None,'fresh_all3_quotes_le5s':sum(x['max_age_ms']<=5000 for x in pairs),'gross_over_10bps':sum(x['model_gross_midpoint_bps']>10 for x in pairs),'actual_fills':0,'commission_conversion_swap_slippage':'UNKNOWN'}
 return {'global':report(trials),'four_original_blocks':[{'block':i,**report([x for x in trials if x['block']==i])} for i in range(4)],'complete_iso_utc_weeks':[{'iso_week':w,'full_iso_utc_week':w in ('2026-W35','2026-W36','2026-W37'),**report([x for x in trials if x['iso_utc']==w])} for w in sorted(set(x['iso_utc'] for x in trials))],'asset_classes':[{'asset_class':c,**report([x for x in trials if x['class']==c])} for c in sorted(set(x['class'] for x in trials))],'per_symbol':[{'symbol_id':sid,**report([x for x in trials if x['sid']==sid])} for sid in sorted(set(x['sid'] for x in trials))],'inference':'FOUR_SHARED_DEPENDENT_CALENDAR_BLOCKS;NO_IID_OR_MULTIPLICITY_CERTIFICATION'}
def main():
 global PHASE
 os.umask(0o077);head,auth=gate();master,entries,digits,_=e.w.old.verify_science()
 start,grid0=START,grid()
 stop(len(grid0)==32 and all(START<=t-300<t+HORIZON<END for _,t in grid0),'FROZEN_ACTION_DOMAIN')
 with tempfile.TemporaryDirectory(prefix='mxm-native-directional-',dir=os.environ['RUNNER_TEMP']) as directory:
  tmp=pathlib.Path(directory);key,fp=e.w.old._private_key_from_secret(tmp);stop(fp==e.w.old.FP,'PRIVATE_KEY')
  PHASE='CURRENT_CONTRACT_UNIVERSE';cost,cprov=load_asset(key,fp,tmp,auth['cost_source']);groups,u=candidate_universe(cost,master)
  selected=[];qualification={};quotes={};all_raw=[];counter=Counter();state='NOT_AUTHENTICATED';failure=None
  full=(cost.get('current_native_evidence') or {}).get('private_native_evidence',{}).get('full',{})
  digits_actual={}
  for grp in groups.values():
   for row in grp:
    sid=int(row['symbol_id']);v=full.get(str(sid),full.get(sid,{})).get('digits')
    if v is not None and 0<=int(v)<=10:digits_actual[sid]=int(v)
  for sid,v in digits.items():digits_actual.setdefault(sid,v)
  for grp in list(groups):
   groups[grp]=[row for row in groups[grp] if int(row['symbol_id']) in digits_actual]
  if not all(os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')):
   state='READ_ONLY_BROKER_CREDENTIAL_MISSING'
  else:
   tr=StdlibCTraderTransport()
   try:
    PHASE='READ_ONLY_BROKER_VIEW';tr.connect();account=authenticate_segment(tr,*[os.environ[k] for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')]);limiter=RateLimiter(min_interval=.25)
    PHASE='PRE_OUTCOME_QUOTE_COST_QUALIFICATION'
    for g in NOMINEES:
     for r in groups.get(g,[]):
      sid=int(r['symbol_id'])
      for t in qualgrid():quotes[sid,t]=quote(tr,account,limiter,sid,t,digits_actual,counter,all_raw,auth['request_cap'])
    selected,qualification=select(groups,quotes)
    stop(len(selected)>0,'NO_QUALIFIED_LIQUID_FX_OR_NONFX')
    PHASE='FOUR_ORIGINAL_BLOCKS_NEW_DIRECTIONAL_QUOTES'
    for r in selected:
     sid=int(r['symbol_id'])
     for b,t in grid0:
      for boundary in (t-300,t,t+HORIZON):
       quotes[sid,boundary]=quote(tr,account,limiter,sid,boundary,digits_actual,counter,all_raw,auth['request_cap'])
    state='AUTHENTIC_READ_ONLY_HISTORICAL_CAPTURE_COMPLETE'
   except Exception as exc:
    state='PARTIAL_OR_ACCESS_BLOCKED';failure=type(exc).__name__
   finally:tr.close()
  PHASE='PAIRED_AUTHENTIC_QUOTE_SIDE_DIRECTIONAL_ESTIMANDS'
  trials=evaluate(selected,grid0,quotes);stats=aggregate(trials)
  econ={'selected_current_contracts':[{'symbol_id':int(r['symbol_id']),'symbol':r['broker_symbol'],'asset_class':r['asset_class'],'archive_M5_present':r['archive_M5_identity_present'],'current_margin_worst_eur':max(float(r['buy_margin_eur']),float(r['sell_margin_eur'])),'min_volume_cents':r.get('min_volume_cents'),'lot_size':r.get('lot_size'),'commission_rate_normalized':r.get('commission_rate_normalized'),'commission_rate_unit':r.get('commission_rate_unit'),'min_commission_normalized':r.get('min_commission_normalized'),'min_commission_type':r.get('min_commission_type'),'swap_long_current':r.get('swap_long'),'swap_short_current':r.get('swap_short')} for r in selected],
        'capital_eur':200,'reserved_free_buffer_eur':50,'per_ticket_margin_le50_only_not_portfolio_risk_proof':True,'historical_fee_schedules_and_trade_conversion':'UNKNOWN','historical_swaps_and_real_fills':'UNKNOWN','slippage_bps_sensitivity':'SUBTRACT_2_5_10_FROM_AUTHENTIC_QUOTE_SIDE_REFERENCE_BEFORE_FEES_ONLY','simultaneous_position_feasibility':'NOT_EXECUTED_OR_CERTIFIED'}
  summary={'schema':'mxm.private.authentic.native.update.asymmetry.directional.development.v1','source_head':head,'status':state,'failure_class':failure,'design_sha256':auth['bindings'][P+'DESIGN_V1.json'],'ex_ante_universe':u,'cost_before_directional_selection':qualification,'native_broker_requests':counter['requests'],'native_broker_coverage':dict(counter),'quote_boundaries_attempted':len(all_raw),'selected_count':len(selected),'economics':econ,'real_directional_numeric':stats,'historical_M5_archives_replayed':False,'new_signed_directional_quote_results_are_fills':False,'historical_net_certification':False,'HARD21_certified':False,'real_orders':0,'demo_orders':0,'protected_forward':False,'independent_confirmation':False,'missing_fee_not_zero':True,'previous_closed_exacts_preserved':True}
  PHASE='ENCRYPTED_PRIVATE_DELIVERY';rt.output(head,auth,tmp,key,'nativeasymmetry',{'summary':summary,'private_fixed_event_outcomes':trials,'private_original_bid_ask_tick_pages':all_raw,'private_qualifier_candidates':{k:[{n:r.get(n) for n in ('symbol_id','broker_symbol','asset_class','buy_margin_eur','sell_margin_eur','min_volume_cents','commission_rate_normalized','min_commission_normalized')} for r in v] for k,v in groups.items()}},summary)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
