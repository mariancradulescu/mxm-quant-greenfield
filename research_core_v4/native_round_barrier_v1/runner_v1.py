"""New nominal-level reflection exact. Owner-encrypted DEVELOPMENT; no orders/deployment."""
import os,json,math,pathlib,tempfile,time,hashlib,subprocess,gzip,base64
from datetime import datetime,timezone
from collections import Counter,defaultdict
from statistics import median
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.multiscale_regime_v1.cost_universe_v1 import eligibility
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,RateLimiter
from research_core_v4.cloud_native_covariance_v1.runner_v1 import capture,fee
from research_core_v4.native_round_barrier_v1.kernel_v1 import feature,changed_point,allocate
from research_core_v4.owner_recovery_v1.readback_v1 import iso
from m6.ctrader_transport import StdlibCTraderTransport
e=rt.e;P='research_core_v4/native_round_barrier_v1/';PHASE='GATE';START=1787184000;END=1789603200
def need(x,c):e.w.old.need(bool(x),c)
def digest(x):return hashlib.sha256(x).hexdigest()
def clocks():
 return [((t-START)//604800,t) for day in range(28) for h in range(4,19,2) if datetime.fromtimestamp(t:=START+day*86400+h*3600+600,timezone.utc).weekday()<5]
def qualification_clocks():return [int(datetime(2026,8,d,h,10,tzinfo=timezone.utc).timestamp()) for d in (18,19) for h in range(4,19,2)]
def gate():
 h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
 need(not any(a[k] for k in ('orders','demo_orders','cloud_deployment','protected_forward')),'SCOPE')
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-native-round-barrier-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
 need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h)
 for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'SOURCE_BINDING')
 for p,s in json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())['bindings'].items():need(e.w.old.filehash(p)==s,'ORIGINAL_IMMUTABLE')
 for p,s in json.loads((e.a.ROOT/'research_core_v4/cloud_native_covariance_v1/EXECUTION_V1.json').read_text())['bindings'].items():need(e.w.old.filehash(p)==s,'CLOSED_EXACT_IMMUTABLE')
 tag='mxm-native-round-barrier-'+a['invocation_id'];need(not e.w.v2.existing_ref(tag),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+tag,'sha':h});return h,a
def universe(cost):
 native=cost['current_native_evidence']['private_native_evidence'];assets={str(a['assetId']):a['name'] for a in native['assets']};light={int(x['symbolId']):x for x in native['light']};groups=defaultdict(list);excluded=defaultdict(Counter);totals=Counter()
 for original in cost['metadata_rows']:
  row=dict(original);c=row.get('asset_class') or 'UNKNOWN';totals[c]+=1
  if c=='Commodities (Cash)':row['product_type']='CASH_COMMODITY_CFD'
  ok,reasons=eligibility(row)
  if not ok:excluded[c].update(reasons);continue
  sid=int(row['symbol_id']);li=light.get(sid,{});fu=native['full'].get(str(sid),{})
  quote=assets.get(str(li.get('quoteAssetId')));digits=fu.get('digits')
  if quote not in ('EUR','USD'):excluded[c]['QUOTE_CURRENCY_NO_FROZEN_EUR_CONVERSION_ROUTE']+=1;continue
  if digits is None or not 0<=int(digits)<=8:excluded[c]['NATIVE_DIGITS_UNAVAILABLE']+=1;continue
  if any(x not in fu for x in ('preciseTradingCommissionRate','preciseMinCommission','commissionType','minCommissionType','lotSize')):excluded[c]['CURRENT_FEE_FIELDS_MISSING']+=1;continue
  row.update(quote_currency=quote,digits=int(digits));groups[c].append(row)
 nominees={c:sorted(rows,key=lambda x:digest(('MXM_ROUND_BARRIER_V1|'+str(x['symbol_id'])).encode()))[:2] for c,rows in sorted(groups.items())}
 fx=[x for x in cost['metadata_rows'] if x['broker_symbol']=='EURUSD'];need(len(fx)==1,'UNIQUE_NATIVE_EURUSD')
 census={'rows':len(cost['metadata_rows']),'classes':[{'class':c,'total':totals[c],'eligible':len(groups.get(c,[])),'nominees':[int(x['symbol_id']) for x in nominees.get(c,[])],'excluded':dict(excluded[c])} for c in sorted(totals)],'selection':'ALL_CLASSES_STRUCTURAL_COST_CURRENCY_SCREEN;TWO_FIXED_HASH_NOMINEES_PER_CLASS;MAX_FOUR_DISTINCT_CLASSES_BY_PREOUTCOME_COST_LIQUIDITY_RISK'}
 return nominees,census,native,int(fx[0]['symbol_id'])
def risk(row,entry,f,fx):
 if entry is None or fx is None:return None
 fe=fee(row,f,entry['mid'])['bps']
 if fe is None:return None
 v=int(row['min_volume_cents'])/100;vstep=int(row['step_volume_cents'])/100
 if v<=0 or vstep<=0:return None
 kernel=feature(entry['bid'],entry['ask'],row['digits']);route=fx['bid'] if row['quote_currency']=='USD' else 1.
 stopcash=v*(kernel['stop_distance']+entry['mid']*(fe+2)/10000)/route
 return {'fee_bps':fe,'risk_eur':stopcash,'volume_units':v,'volume_step_units':vstep,'potential_headroom_bps':kernel['headroom_bps'],'spread_plus_fee_bps':entry['spread_bps']+fe,'EUR_conversion_bid':route,'minimum_ticket_only':True}
def qualify(nominees,quotes,native,fxid):
 diag={};candidates=[]
 for c,rows in nominees.items():
  ratings=[]
  for row in rows:
   good=[];dates=set();why=Counter()
   for t in qualification_clocks():
    x,reason=changed_point(quotes.get((int(row['symbol_id']),t)));fx,fr=changed_point(quotes.get((fxid,t)));z=risk(row,x,native,fx)
    if x is None or fx is None:why['NATIVE_FRESHNESS_OR_PAGE_GAP']+=1;continue
    if z is None:why['FEE_OR_CONVERSION_UNRESOLVED']+=1;continue
    good.append(z);dates.add(datetime.fromtimestamp(t,timezone.utc).date().isoformat())
   eligible=len(good)>=8 and len(dates)==2
   ratings.append({'sid':int(row['symbol_id']),'symbol':row['broker_symbol'],'class':c,'qualification_supported':len(good),'dates':sorted(dates),'eligible':eligible,'median_spread_plus_fee_bps':median(x['spread_plus_fee_bps'] for x in good) if good else None,'median_min_ticket_stop_risk_eur':median(x['risk_eur'] for x in good) if good else None,'risk_eur_le2_observations':sum(x['risk_eur']<=2 for x in good),'margin_eur':max(float(row['buy_margin_eur']),float(row['sell_margin_eur'])),'missingness':dict(why)})
  ranked=sorted([x for x in ratings if x['eligible'] and x['risk_eur_le2_observations']>=4],key=lambda x:(x['median_spread_plus_fee_bps'],x['median_min_ticket_stop_risk_eur'],x['sid']))
  if ranked:candidates.append(ranked[0])
  diag[c]={'nominees':ratings,'class_best':ranked[0]['sid'] if ranked else None}
 panel=sorted(candidates,key=lambda x:(x['median_spread_plus_fee_bps'],x['median_min_ticket_stop_risk_eur'],x['class'],x['sid']))[:4]
 selected=[next(row for row in nominees[x['class']] if int(row['symbol_id'])==x['sid']) for x in panel]
 return selected,diag,panel
def quote_return(direction,entry,exit):return 10000*math.log(exit['bid']/entry['ask']) if direction>0 else 10000*math.log(entry['bid']/exit['ask'])
def evaluate(selected,quotes,native,fxid):
 events=[];samples=[]
 for row in selected:
  sid=int(row['symbol_id'])
  for block,t in clocks():
   points={};missing={}
   for delta in (-3600,0,900,1800,2700,3600):points[delta],missing[delta]=changed_point(quotes.get((sid,t+delta)))
   fx,fr=changed_point(quotes.get((fxid,t)));fxexit,fre=changed_point(quotes.get((fxid,t+3600)))
   ent=points[0];previous=points[-3600];ex=points[3600];v=feature(ent['bid'],ent['ask'],row['digits']) if ent else None
   if v:samples.append({'bid':ent['bid'],'ask':ent['ask'],'digits':row['digits'],'python':v})
   rc=risk(row,ent,native,fx);baseline=(ent['mid']>previous['mid'])-(ent['mid']<previous['mid']) if ent and previous else 0
   causal_eligible=bool(ent and previous and v['direction'] and baseline and rc and rc['risk_eur']<=2 and v['headroom_bps']>rc['spread_plus_fee_bps']+5)
   reason='ENTRY_NATIVE_QUOTE_GAP' if ent is None else 'BASELINE_NATIVE_QUOTE_GAP' if previous is None else 'NOMINAL_'+v['reason'] if not v['direction'] else 'BASELINE_FLAT' if not baseline else 'COST_OR_EUR_CONVERSION_UNRESOLVED' if rc is None or fxexit is None else 'MIN_TICKET_STOP_RISK_GT2EUR' if rc['risk_eur']>2 else 'HEADROOM_LE_SPREAD_FEE_PLUS5BPS' if v['headroom_bps']<=rc['spread_plus_fee_bps']+5 else 'EXIT_NATIVE_QUOTE_GAP' if ex is None else 'SUPPORTED'
   model=base=None;fexit=None;cash=None;excursion=None;allpaths=all(points[x] for x in (900,1800,2700,3600))
   if reason=='SUPPORTED':
    model=quote_return(v['direction'],ent,ex);base=quote_return(baseline,ent,ex);fexit=fee(row,native,ex['mid'])['bps']
    if fexit is None:reason='EXIT_CURRENT_FEE_UNRESOLVED';model=base=None
    else:
     fcurrent=(rc['fee_bps']+fexit)/2;route=fxexit['bid'] if row['quote_currency']=='USD' else 1.
     pricepnl=v['direction']*((ex['bid']-ent['ask']) if v['direction']>0 else (ex['ask']-ent['bid']))
     cash=rc['volume_units']*(pricepnl-ent['mid']*fcurrent/10000)/route
     vals=[quote_return(v['direction'],ent,points[x]) for x in (900,1800,2700,3600) if points[x]];excursion=min(vals) if vals else None
   events.append({'sid':sid,'symbol':row['broker_symbol'],'class':row['asset_class'],'block':block,'iso':iso(t),'action':t,'exit':t+3600,'reason':reason,'causal_eligible':causal_eligible,'feature':v,'baseline_direction':baseline,'economics':rc,'model_bps':model,'baseline_bps':base,'current_fee_scenario_bps':(rc['fee_bps']+fexit)/2 if model is not None else None,'cash_EUR_current_fee_quote_scenario':cash,'sampled_path_complete':allpaths,'sampled_adverse_markout_bps':excursion,'path_missingness':missing,'entry_age_ms':ent['age_ms'] if ent else None,'exit_age_ms':ex['age_ms'] if ex else None,'fills':0})
 return events,samples,allocate(events,[t for _,t in clocks()])

def stats(rows):
 valid=[x for x in rows if x['reason']=='SUPPORTED'];n=len(valid);mean=lambda fn:sum(fn(x) for x in valid)/n if n else None
 cash=[x['cash_EUR_current_fee_quote_scenario'] for x in sorted(valid,key=lambda x:(x['action'],x['sid']))];equity=peak=200.;dd=0.
 for y in cash:equity+=y;peak=max(peak,equity);dd=max(dd,peak-equity)
 return {'scheduled':len(rows),'paired':n,'reasons':dict(Counter(x['reason'] for x in rows)),'model_quote_bps':mean(lambda x:x['model_bps']),'baseline_quote_bps':mean(lambda x:x['baseline_bps']),'paired_increment_bps':mean(lambda x:x['model_bps']-x['baseline_bps']),'mean_current_fee_bps':mean(lambda x:x['current_fee_scenario_bps']),'model_after_current_fee_bps':mean(lambda x:x['model_bps']-x['current_fee_scenario_bps']),'baseline_after_current_fee_bps':mean(lambda x:x['baseline_bps']-x['current_fee_scenario_bps']),'after_current_fee_plus_2_5_10_bps':{str(k):mean(lambda x:x['model_bps']-x['current_fee_scenario_bps']-k) for k in (2,5,10)},'sampled_path_complete':sum(x['sampled_path_complete'] for x in valid),'sampled_worst_adverse_markout_bps':min((x['sampled_adverse_markout_bps'] for x in valid if x['sampled_adverse_markout_bps'] is not None),default=None),'indicative_min_ticket_quote_cash_EUR_sum':sum(cash),'indicative_markout_cash_drawdown_EUR':dd if len({x['action'] for x in valid})==n else None,'cash_scope':'PANEL_SUM_NOT_PORTFOLIO;DRAWDOWN_ONLY_WHEN_ONE_ROW_PER_CLOCK;CURRENT_FEE_SCENARIO_QUOTES_NO_ACTUAL_FILLS_NO_INTRAPATH_STOP_EXECUTION_NOT_CERTIFIED_EQUITY','actual_historical_NET':'UNKNOWN','fills':0}
def aggregate(events,chosen):
 out={'global':stats(events),'blocks':[{'block':b,**stats([x for x in events if x['block']==b])} for b in range(4)],'ISO_weeks':[{'week':w,'complete':w in ('2026-W35','2026-W36','2026-W37'),**stats([x for x in events if x['iso']==w])} for w in ('2026-W34','2026-W35','2026-W36','2026-W37','2026-W38')],'symbols':[{'sid':s,**stats([x for x in events if x['sid']==s])} for s in sorted({x['sid'] for x in events})],'single_candidate_clock_allocation':{'clock_denominator':len(clocks()),'causally_allocated':len(chosen),'supported_selected':sum(x['reason']=='SUPPORTED' for x in chosen),'stats':stats(chosen),'complete_week_selection_counts':{w:sum(x['iso']==w and x['reason']=='SUPPORTED' for x in chosen) for w in ('2026-W35','2026-W36','2026-W37')},'actual_entries':0}}
 support=out['global']['paired']>=80 and all(x['paired']>=16 for x in out['blocks']) and all(x['paired']>=16 for x in out['ISO_weeks'] if x['complete'])
 passed=support and all(x['model_after_current_fee_bps'] is not None and x['model_after_current_fee_bps']>2 and x['paired_increment_bps']>0 for x in out['blocks']+out['ISO_weeks'] if x.get('complete',True))
 out.update(descriptive_support_gate=support,economic_temporal_gate=passed,decision='NO_PROMOTION_DATA_LIMITED' if not support else 'NO_PROMOTION_ECONOMIC_OR_TEMPORAL_FAIL' if not passed else 'POSITIVE_DEVELOPMENT_ONLY_CLOUD_HISTORICAL_COST_CONFIRMATION_PENDING',independent_confirmation=False,HARD21=False)
 return out
def parity(samples):
 if not samples:return {'status':'NO_AUTHENTIC_INPUT','samples':0}
 payload=''.join(json.dumps({k:x[k] for k in ('bid','ask','digits')})+'\n' for x in samples)
 proc=subprocess.run(['dotnet',str(e.a.ROOT/(P+'csharp/bin/Release/net8.0/Parity.dll'))],input=payload.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90);need(proc.returncode==0,'CSHARP_PROCESS');lines=proc.stdout.decode().splitlines();need(len(lines)==len(samples),'PARITY_COUNT');err=0.
 for x,line in zip(samples,lines):
  py=x['python'];cs=json.loads(line);need(py['direction']==cs['direction'] and py['reason']==cs['reason'],'PARITY_DIRECTION_REASON')
  for k in ('level','distance','headroom_bps','stop_distance'):
   delta=abs(py[k]-cs[k]);err=max(err,delta);need(delta<=1e-9*max(1.,abs(py[k])),'PARITY_NUMERIC')
 return {'status':'PASS_AUTHENTIC_CAUSAL_NATIVE_INPUTS','samples':len(samples),'max_absolute_difference':err,'actual_Cloud_delivery_verified':False}
def relay(head,auth,summary):
 pubbytes=(e.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem')).read_bytes();need(digest(pubbytes)==auth['recipient_public_key_sha256'],'RECIPIENT');pub=serialization.load_pem_public_key(pubbytes);need(pub.key_size>=3072,'KEY_STRENGTH');z=gzip.compress(e.a.enc(summary),mtime=0);key=os.urandom(32);nonce=os.urandom(12);wrapped=pub.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None));b64=lambda x:base64.b64encode(x).decode();envelope={'version':'MXM_NATIVE_ROUND_PRIVATE_V1','head':head,'wrapped_key_b64':b64(wrapped),'nonce_b64':b64(nonce),'ciphertext_b64':b64(AESGCM(key).encrypt(nonce,z,head.encode())),'compressed_plain_sha256':digest(z),'recipient_pub_sha256':digest(pubbytes)};body=e.a.enc(envelope).decode();need(len(body)<160000,'RELAY_BUDGET')
 rel=e.w.old.api('releases',{'tag_name':'mxm-native-round-private-aggregate-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted new nominal-level native DEVELOPMENT aggregates','body':body,'prerelease':True});need(e.w.old.api('releases/'+str(rel['id']))['body']==body,'RELAY_REMOTE_READBACK');print(json.dumps({'status':'PASS','run':int(os.environ['GITHUB_RUN_ID']),'head':head,'release':rel['id'],'envelope_sha256':digest(body.encode()),'numeric_outcomes_public':False,'orders':0}),flush=True)
def main():
 global PHASE
 os.umask(0o077);head,auth=gate();e.w.old.verify_science();need(len(clocks())==160 and all(START<t-3600<t+3600<END for _,t in clocks()),'ORIGINAL_DOMAIN');began=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='mxm-round-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='AUTHENTIC_COST_CENSUS';cost,cp=load_asset(key,fp,tmp,auth['cost_source']);nominees,census,native,fxid=universe(cost);need(len(nominees)<=32,'CLASS_CAP');raw=[];quotes={};counter=Counter();selected=[];qual={};panel=[];capture_status='NOT_STARTED';error=None;tr=StdlibCTraderTransport()
  try:
   PHASE='READ_ONLY_AUTH';creds=[os.environ.get(x) for x in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')];need(all(creds),'NO_CREDENTIALS');tr.connect();aid=authenticate_segment(tr,*creds);rate=RateLimiter(min_interval=.25)
   def get(sid,t):
    if (sid,t) not in quotes:
     need(time.monotonic()-began<4200,'WALL_LIMIT');quotes[sid,t]=capture(tr,aid,rate,sid,t,counter,raw,auth['request_cap'])
   PHASE='NEW_PREOUTCOME_ECONOMIC_LIQUIDITY_QUALIFICATION'
   for t in qualification_clocks():get(fxid,t)
   for rows in nominees.values():
    for row in rows:
     for t in qualification_clocks():get(int(row['symbol_id']),t)
   selected,qual,panel=qualify(nominees,quotes,native,fxid)
   need(counter['requests']+len(selected)*160*12+160*4<=auth['request_cap'],'FIXED_COMPLETE_CAPTURE_BUDGET')
   PHASE='NEW_AUTHENTIC_DEVELOPMENT_QUOTES'
   for _,t in clocks():
    for bound in (t,t+3600):get(fxid,bound)
   for row in selected:
    for _,t in clocks():
     for delta in (-3600,0,900,1800,2700,3600):get(int(row['symbol_id']),t+delta)
   capture_status='AUTHENTIC_CAPTURE_COMPLETE'
  except Exception as exc:capture_status='PARTIAL_OR_BLOCKED';error=type(exc).__name__
  finally:tr.close()
  PHASE='NEW_FEATURE_NUMERIC_AUTHENTIC_CSHARP_PARITY';events,samples,chosen=evaluate(selected,quotes,native,fxid);pp=parity(samples);numeric=aggregate(events,chosen)
  summary={'schema':'mxm.private.native.nominal.round.barrier.reflection.v1','source_head':head,'source_design_sha256':auth['bindings'][P+'DESIGN_V1.json'],'capture_status':capture_status,'failure':error,'cost_provenance':cp,'universe':census,'qualification':qual,'selected_panel_preoutcome':panel,'selected_current_contracts':selected,'EUR_conversion_native_symbol_id':fxid,'native_requests':counter['requests'],'native_coverage':dict(counter),'numeric':numeric,'CSharp_Python_parity':pp,'native_runtime':'DOCUMENTED_MAPPING_LINUX_BUILD_ONLY_ACTUAL_CLOUD_UNVERIFIED','production_eligibility':'RESEARCH_ONLY_UNTIL_ACTUAL_CLOUD_DELIVERY_AND_HISTORY_PARITY','economics':{'capital_EUR':200,'max_min_ticket_margin_EUR':50,'minimum_free_buffer_EUR':50,'initial_stop_plus_current_fee_plus_2bps_limit_EUR':2,'max_concurrent_research_candidate':1,'40_complete_week_clocks_not_entries':True,'stop_fills_intraperiod_prices_and_historical_margin':'UNKNOWN','actual_historical_fees_swap_financing_rollover_slippage':'UNKNOWN_NEVER_ZERO','drawdown':'INDICATIVE_MIN_TICKET_QUOTE_CASH_PATH_ONLY_NOT_CERTIFIED_EQUITY','profit_conversion':'CAUSAL_NATIVE_EURUSD_BID_OR_DIRECT_EUR_AT_EXIT;CURRENT_PRICE_EQUIVALENT_FEE_SCENARIO_ONLY'},'selection_history':'ADAPTIVELY_EXPOSED_DEVELOPMENT;NO_OLD_WINNER_SELECTION;NO_RETUNING','orders':0,'demo_orders':0,'cloud_deployment':False,'protected_forward':False,'robust_positive_NET':False,'HARD21':False,'independent_confirmation':False}
  full={'summary':summary,'private_new_events':events,'private_native_quote_pages':raw,'private_authentic_parity_samples':samples,'private_single_clock_selection':chosen}
  PHASE='OWNER_ENCRYPTED_NEW_PRIMARY';rt.output(head,auth,tmp,key,'nativeround',full,summary);PHASE='PRIVATE_RELAY';relay(head,auth,summary)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
