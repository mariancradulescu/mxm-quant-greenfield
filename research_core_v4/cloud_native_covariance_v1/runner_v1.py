"""One-use authentic DEVELOPMENT. Native C# mapping is conditional, not Cloud verification."""
import os,json,math,tempfile,pathlib,time,hashlib,subprocess,gzip,base64
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
from m6.ctrader_transport import StdlibCTraderTransport
from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as enums
from m6.ctrader_capture import require_read_only_request
from m6.cost_evidence import decode_ctrader_tick_page
from research_core_v4.owner_recovery_v1.readback_v1 import iso
from research_core_v4.cloud_native_covariance_v1.kernel_v1 import feature,resample
from competition.friction_costs import type_aware_roundtrip_commission
e=rt.e;P='research_core_v4/cloud_native_covariance_v1/';PHASE='GATE'
START=1787184000;END=1789603200;H=3600

def need(v,code): e.w.old.need(bool(v),code)
def gate():
 h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
 need(not a['orders'] and not a['protected_forward'] and not a['cloud_deployment'],'SCOPE')
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-cloud-native-covariance-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
 need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h)
 for p,s in a['bindings'].items(): need(e.w.old.filehash(p)==s,'SOURCE_BINDING')
 original=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
 for p,s in original['bindings'].items():need(e.w.old.filehash(p)==s,'IMMUTABLE_SOURCE')
 tag='mxm-cloud-native-covariance-'+a['invocation_id'];need(not e.w.v2.existing_ref(tag),'ONE_USE_CONSUMED')
 e.w.old.api('git/refs',{'ref':'refs/tags/'+tag,'sha':h})
 return h,a
def grid():return [(b,START+b*604800+d*86400+h*3600+600) for b in range(4) for d in (1,4,5,6) for h in (4,8,13,17)]
def qualgrid():return [int(datetime(2026,8,d,h,10,tzinfo=timezone.utc).timestamp()) for d in (18,19) for h in (4,8,13,17)]
def universe(cost,master):
 ids={int(x['symbol_id']) for x in master};groups=defaultdict(list);ex=defaultdict(Counter)
 for row in cost['metadata_rows']:
  r=dict(row);c=r.get('asset_class') or 'UNKNOWN'
  if c=='Commodities (Cash)':r['product_type']='CASH_COMMODITY_CFD'
  ok,why=eligibility(r)
  if ok:groups[c].append(r)
  else:ex[c].update(why)
 # A reproducible outcome-blind, class-balanced *probe*, not exhaustive symbol ranking.
 nominees={c:sorted(rows,key=lambda r:hashlib.sha256(('MXM_NATIVE_COV_V1|'+str(r['symbol_id'])).encode()).hexdigest())[:2] for c,rows in sorted(groups.items())}
 return nominees,{'full_metadata_rows':len(cost['metadata_rows']),'classes':[{'class':c,'structurally_eligible':len(groups.get(c,[])),'nominees':[int(r['symbol_id']) for r in nominees.get(c,[])],'excluded':dict(ex[c])} for c in sorted(set(groups)|set(ex))],'selection':'TWO_FIXED_HASH_NOMINEES_PER_CLASS;NO_PROFIT_OR_MARGIN_RANKED_NOMINATION','breadth_limit':'ALL_CURRENT_CLASSES_SCREENED;ONLY_TWO_SYMBOLS_PER_ELIGIBLE_CLASS_LIQUIDITY_PROBED;NO_EXHAUSTIVE_OPTIMALITY_CLAIM','M5_archive_identity_present':{str(r['symbol_id']):int(r['symbol_id']) in ids for rows in nominees.values() for r in rows}}
def capture(tr,aid,rate,sid,t,counter,raw,cap):
 pages=[];sides={}
 for side,typ in (('bid',enums.BID),('ask',enums.ASK)):
  need(counter['requests']<cap,'REQUEST_BUDGET')
  q=m.ProtoOAGetTickDataReq(ctidTraderAccountId=aid,symbolId=sid,type=typ,fromTimestamp=t*1000-70000,toTimestamp=t*1000)
  require_read_only_request(type(q).__name__);rate.before_send();r=tr.request(q,timeout=25);counter['requests']+=1
  if isinstance(r,m.ProtoOAErrorRes):
   counter['provider_errors']+=1;pages.append({'side':side,'error_code':r.errorCode});sides[side]={'state':'PROVIDER_ERROR'};continue
  need(isinstance(r,m.ProtoOAGetTickDataRes),'RESPONSE_TYPE')
  encoded=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in r.tickData]
  dec=decode_ctrader_tick_page(encoded);need(all(t*1000-70000<=x.timestamp_ms<=t*1000 for x in dec),'SOURCE_TIMESTAMPS')
  pages.append({'side':side,'encoded':encoded,'hasMore':bool(r.hasMore)})
  state='INCOMPLETE_PAGE' if r.hasMore else 'NO_QUOTE' if not dec else 'VALID'
  sides[side]={'state':state}
  if state=='VALID':sides[side].update(price=dec[-1].raw_tick/100000,age_ms=t*1000-dec[-1].timestamp_ms)
  counter[side+'|'+state]+=1
 q={'symbol_id':sid,'boundary':t,'sides':sides,'raw_pages':pages};raw.append(q);return q
def point(q):
 if q is None or any(q['sides'][s]['state']!='VALID' for s in ('bid','ask')):return None
 b=q['sides']['bid'];a=q['sides']['ask']
 if not 0<b['price']<a['price']:return None
 return {'bid':b['price'],'ask':a['price'],'mid':(a['price']+b['price'])/2,'age_ms':max(a['age_ms'],b['age_ms']),'spread_bps':10000*math.log(a['price']/b['price'])}
def fee(row,native,mid):
 sid=int(row['symbol_id']);full=native.get('full',{}).get(str(sid),{});light=next((x for x in native.get('light',[]) if int(x['symbolId'])==sid),{})
 assets={str(x['assetId']):x['name'] for x in native.get('assets',[])}
 # Helper defaults are never used to turn absent fee fields into zero.
 if any(k not in full for k in ('preciseTradingCommissionRate','preciseMinCommission','commissionType','minCommissionType','lotSize')):return {'bps':None,'state':'CURRENT_TERMS_INCOMPLETE'}
 base=assets.get(str(light.get('baseAssetId')));quote=assets.get(str(light.get('quoteAssetId')))
 baseusd=mid if quote=='USD' else 1.0 if base=='USD' else None
 f=type_aware_roundtrip_commission(full,light,assets,mid=mid,min_volume_cents=int(row['min_volume_cents']),base_to_usd_rate=baseusd)
 v=f['roundtrip_commission_price_equivalent']
 return {'bps':10000*v/mid if v is not None else None,'state':f['cost_confidence_state'],'details':f,'scope':'CURRENT_CONTRACT_APPLIED_TO_HISTORICAL_REFERENCE_PRICE_SCENARIO_NOT_HISTORICAL_CHARGE'}
def qualify(nominees,quotes,native):
 selected=[];diag={}
 for c,rows in nominees.items():
  ratings=[]
  for row in rows:
   sid=int(row['symbol_id']);pts=[point(quotes.get((sid,t))) for t in qualgrid()];pts=[x for x in pts if x and x['age_ms']<=10000]
   fees=[fee(row,native,x['mid'])['bps'] for x in pts];known=bool(fees) and all(x is not None for x in fees)
   # Two distinct qualification dates are mandatory; one isolated liquidity print is insufficient.
   dates={datetime.fromtimestamp(t,timezone.utc).date().isoformat() for t in qualgrid() if (point(quotes.get((sid,t))) or {}).get('age_ms',10001)<=10000}
   eligible=len(pts)>=2 and len(dates)==2
   spread=median(x['spread_bps'] for x in pts) if eligible else None
   cost=(spread+median(fees)) if eligible and known else None
   ratings.append({'symbol_id':sid,'name':row['broker_symbol'],'qualification_pairs':len(pts),'qualification_dates':sorted(dates),'eligible':eligible,'median_spread_bps':spread,'current_contract_fee_scenario_bps':median(fees) if known else None,'spread_plus_current_fee_scenario_bps':cost,'margin_eur':max(float(row['buy_margin_eur']),float(row['sell_margin_eur']))})
  ranked=sorted([x for x in ratings if x['eligible']],key=lambda x:(x['spread_plus_current_fee_scenario_bps'] is None,x['spread_plus_current_fee_scenario_bps'] if x['spread_plus_current_fee_scenario_bps'] is not None else x['median_spread_bps'],x['margin_eur'],x['symbol_id']))
  if ranked:selected.append(next(r for r in rows if int(r['symbol_id'])==ranked[0]['symbol_id']))
  diag[c]={'all_nominees':ratings,'selected_id':ranked[0]['symbol_id'] if ranked else None,'rank':'FEE_SCENARIO_RESOLVABLE_THEN_SPREAD_PLUS_FEE_ELSE_SPREAD_THEN_MARGIN_THEN_ID','historical_costs_verified':False}
 return selected,diag
def evaluate(selected,quotes,native):
 trials=[];samples=[];cal=grid()
 for row in selected:
  sid=int(row['symbol_id'])
  for block,t in cal:
   q=quotes.get((sid,t));f=quotes.get((sid,t+H));entry=point(q);future=point(f)
   sample,reason=resample(q['raw_pages'],t*1000) if q else (None,'ENTRY_MISSING')
   val=feature([x['bid'] for x in sample],[x['ask'] for x in sample]) if sample else None
   if sample:samples.append({'bids':[x['bid'] for x in sample],'asks':[x['ask'] for x in sample],'python':val})
   sig=val['direction'] if val else 0;ref=0;model=baseline=gross=cost=None
   if sample:
    ref=(sample[-1]['bid']+sample[-1]['ask']>sample[0]['bid']+sample[0]['ask'])-(sample[-1]['bid']+sample[-1]['ask']<sample[0]['bid']+sample[0]['ask'])
    reason='MODEL_ABSTENTION_'+val['reason'] if sig==0 else 'BASELINE_FLAT' if ref==0 else 'EXIT_MISSING_OR_STALE' if future is None or future['age_ms']>10000 else 'SUPPORTED'
   if reason=='SUPPORTED':
    model=10000*math.log(future['bid']/entry['ask']) if sig>0 else 10000*math.log(entry['bid']/future['ask'])
    baseline=10000*math.log(future['bid']/entry['ask']) if ref>0 else 10000*math.log(entry['bid']/future['ask'])
    gross=sig*10000*math.log(future['mid']/entry['mid'])
    f1=fee(row,native,entry['mid']);f2=fee(row,native,future['mid']);cost=(f1['bps']+f2['bps'])/2 if f1['bps'] is not None and f2['bps'] is not None else None
   trials.append({'sid':sid,'symbol':row['broker_symbol'],'class':row['asset_class'],'block':block,'iso_utc':iso(t),'action':t,'exit':t+H,'reason':reason,'feature':val,'baseline_direction':ref,'quote_side_model_bps':model,'quote_side_baseline_bps':baseline,'model_gross_bps':gross,'current_contract_fee_scenario_bps':cost,'max_feature_changed_quote_age_ms':max(x[s+'_age_ms'] for x in sample for s in ('bid','ask')) if sample else None,'entry_exit_age_ms':max(entry['age_ms'],future['age_ms']) if entry and future else None})
 return trials,samples
def stats(rows):
 supported=[x for x in rows if x['reason']=='SUPPORTED'];n=len(supported)
 mean=lambda key:sum(x[key] for x in supported)/n if n else None
 scenario=[x for x in supported if x['current_contract_fee_scenario_bps'] is not None]
 return {'scheduled':len(rows),'paired':n,'reason_counts':dict(Counter(x['reason'] for x in rows)),'mean_quote_side_model_bps':mean('quote_side_model_bps'),'mean_paired_baseline_bps':mean('quote_side_baseline_bps'),'paired_increment_bps':sum(x['quote_side_model_bps']-x['quote_side_baseline_bps'] for x in supported)/n if n else None,'mean_midpoint_gross_bps':mean('model_gross_bps'),'current_fee_scenario_supported':len(scenario),'mean_after_current_fee_scenario_bps':sum(x['quote_side_model_bps']-x['current_contract_fee_scenario_bps'] for x in scenario)/len(scenario) if scenario else None,'after_quote_side_2_5_10bps_sensitivity':{str(k):mean('quote_side_model_bps')-k if n else None for k in (2,5,10)},'fresh_feature_and_entry_exit_le5s_pairs':sum(max(x['max_feature_changed_quote_age_ms'],x['entry_exit_age_ms'])<=5000 for x in supported),'fills':0,'actual_historical_all_cost_NET':'UNKNOWN'}
def aggregate(rows):
 out={'global':stats(rows),'blocks':[{'block':b,**stats([x for x in rows if x['block']==b])} for b in range(4)],'iso_weeks':[{'iso_week':w,'complete':w in ('2026-W35','2026-W36','2026-W37'),**stats([x for x in rows if x['iso_utc']==w])} for w in sorted(set(x['iso_utc'] for x in rows))],'classes':[{'class':c,**stats([x for x in rows if x['class']==c])} for c in sorted(set(x['class'] for x in rows))]}
 n=out['global']['paired'];valid=n>=64 and all(x['paired']>=12 for x in out['blocks']) and all(x['paired']>=12 for x in out['iso_weeks'] if x['complete'])
 positive=valid and all((x['mean_quote_side_model_bps'] or -1)>0 and (x['paired_increment_bps'] or -1)>0 for x in out['blocks']+out['iso_weeks'] if x.get('complete',True))
 out['descriptive_minimum_support_gate']=valid;out['predeclared_positive_temporal_gate']=positive
 out['decision']='NO_PROMOTION_INSUFFICIENT_SUPPORT' if not valid else 'NO_PROMOTION_DIRECTIONAL_OR_TEMPORAL_FAIL' if not positive else 'POSITIVE_DEVELOPMENT_ONLY_CLOUD_AND_COST_PROOF_REQUIRED'
 out['power']='FOUR_DEPENDENT_ORIGINAL_BLOCKS_AND_THREE_COMPLETE_ISO_WEEKS_CANNOT_CERTIFY_FAMILYWISE_ALPHA;ADAPTIVELY_EXPOSED_DEVELOPMENT'
 return out
def parity(samples):
 if not samples:return {'status':'NO_AUTHENTIC_SUPPORTED_FEATURE_INPUT','samples':0}
 lines=''.join(json.dumps({k:s[k] for k in ('bids','asks')},allow_nan=False)+'\n' for s in samples)
 dll=e.a.ROOT/(P+'csharp/bin/Release/net8.0/Parity.dll')
 result=subprocess.run(['dotnet',str(dll)],input=lines.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
 need(result.returncode==0,'CSHARP_PRIVATE_PARITY_PROCESS');out=result.stdout.decode().splitlines();need(len(out)==len(samples),'CSHARP_PARITY_COUNT')
 maxdiff=0.0
 for s,line in zip(samples,out):
  py=s['python'];cs=json.loads(line);err=abs(cs['correlation']-py['correlation']);maxdiff=max(maxdiff,err)
  need(cs['direction']==py['direction'] and cs['reason']==py['reason'] and err<=1e-10,'CSHARP_MATH_PARITY')
 return {'status':'PASS_AUTHENTIC_IDENTICAL_CAUSAL_INPUTS','samples':len(samples),'max_correlation_absolute_difference':maxdiff,'cloud_delivery_verified':False}
def relay(head,auth,summary):
 recipient=(e.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem')).read_bytes();need(hashlib.sha256(recipient).hexdigest()==auth['recipient_public_key_sha256'],'RECIPIENT')
 pub=serialization.load_pem_public_key(recipient);need(pub.key_size>=3072,'KEY_STRENGTH')
 raw=e.a.enc(summary);need(len(raw)<300000,'AGGREGATE_BUDGET');packed=gzip.compress(raw,mtime=0);key=os.urandom(32);nonce=os.urandom(12)
 ct=AESGCM(key).encrypt(nonce,packed,head.encode());wrapped=pub.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
 b64=lambda x:base64.b64encode(x).decode();envelope={'version':'MXM_PRIVATE_CLOUD_NATIVE_V1','head':head,'recipient_pub_sha256':hashlib.sha256(recipient).hexdigest(),'nonce_b64':b64(nonce),'wrapped_key_b64':b64(wrapped),'ciphertext_b64':b64(ct),'compressed_plain_sha256':hashlib.sha256(packed).hexdigest()}
 body=e.a.enc(envelope).decode();need(len(body)<160000,'CIPHERTEXT_BODY_BUDGET')
 rel=e.w.old.api('releases',{'tag_name':'mxm-cloud-native-private-aggregate-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted native runtime research aggregates','body':body,'prerelease':True})
 need(e.w.old.api('releases/'+str(rel['id']))['body']==body,'ENVELOPE_READBACK')
 print(json.dumps({'status':'PASS','run_id':int(os.environ['GITHUB_RUN_ID']),'release_id':rel['id'],'head':head,'ciphertext_envelope_sha256':hashlib.sha256(body.encode()).hexdigest(),'public_numeric_outcomes':False,'orders':0}),flush=True)
def main():
 global PHASE
 os.umask(0o077);head,auth=gate();master,*_=e.w.old.verify_science();need(all(START<=t-70<t+H<END for _,t in grid()),'DEVELOPMENT_DOMAIN')
 started=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='mxm-native-cov-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY')
  PHASE='AUTHENTIC_CURRENT_CONTRACT';cost,cp=load_asset(key,fp,tmp,auth['cost_source']);nominees,u=universe(cost,master)
  native=(cost.get('current_native_evidence') or {}).get('private_native_evidence',{})
  need(native and len(nominees)<=32,'NATIVE_CENSUS_OR_CLASS_CAP')
  raw=[];quotes={};counter=Counter();selected=[];qualification={};state='NO_BROKER_ACCESS';failure=None
  tr=StdlibCTraderTransport()
  try:
   PHASE='READ_ONLY_AUTHENTICATION';creds=[os.environ.get(x) for x in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')];need(all(creds),'CREDENTIALS_MISSING')
   tr.connect();aid=authenticate_segment(tr,*creds);rate=RateLimiter(min_interval=.25)
   PHASE='PREOUTCOME_CLASS_BALANCED_LIQUIDITY_AND_FEES'
   for rows in nominees.values():
    for r in rows:
     sid=int(r['symbol_id'])
     for t in qualgrid():quotes[sid,t]=capture(tr,aid,rate,sid,t,counter,raw,auth['request_cap'])
   selected,qualification=qualify(nominees,quotes,native)
   need(counter['requests']+len(selected)*len(grid())*4<=auth['request_cap'],'FROZEN_ALL_CLASSES_REQUEST_BUDGET')
   PHASE='AUTHENTIC_NEW_DIRECTIONAL_OUTCOMES'
   for r in selected:
    sid=int(r['symbol_id'])
    for b,t in grid():
     need(time.monotonic()-started<4200,'WALL_BUDGET')
     for bound in (t,t+H):quotes[sid,bound]=capture(tr,aid,rate,sid,bound,counter,raw,auth['request_cap'])
   state='AUTHENTIC_CAPTURE_COMPLETE'
  except Exception as exc:state='PARTIAL_OR_BLOCKED';failure=type(exc).__name__
  finally:tr.close()
  PHASE='CAUSAL_NUMERIC_AND_AUTHENTIC_CSHARP_PARITY';trials,samples=evaluate(selected,quotes,native);pp=parity(samples);numbers=aggregate(trials)
  summary={'schema':'mxm.private.cloud.native.spread.midpoint.covariance.v1','source_head':head,'source_design_sha256':auth['bindings'][P+'DESIGN_V1.json'],'capture_status':state,'capture_failure':failure,'contract_provenance':cp,'universe':u,'qualification':qualification,'native_requests':counter['requests'],'native_coverage':dict(counter),'selected_contracts':selected,'numeric':numbers,'csharp_python_parity':pp,'cloud_runtime_delivery':'NOT_VERIFIED_DEPLOYMENT_NOT_AUTHORIZED','runtime_information_parity':'DOCUMENTED_NATIVE_MAPPING_AND_COMPILED_PROBE_ONLY;HISTORICAL_VS_CLOUD_DELIVERY_NOT_PROVEN','production_eligibility':'RESEARCH_ONLY_PENDING_ACTUAL_CLOUD_INFORMATION_PARITY','economics':{'capital_eur':200,'current_min_ticket_margin_limit_eur':50,'minimum_free_buffer_eur':50,'maximum_aggregate_margin_eur':150,'portfolio_allocation':'NOT_SIMULATED;CLASS_SIGNALS_MAY_OVERLAP;NOT_EXECUTED_ENTRIES','single_position_test_clock_cap_per_complete_week':16,'min_stop_exposure':'UNRESOLVED_NO_RISK_CERTIFICATION','historical_fee_schedule':'UNKNOWN_CURRENT_TERMS_SCENARIO_ONLY','EUR_PNL_CONVERSION':'UNKNOWN_UNLESS_EVENT_CURRENCY_CONVERSION_CAPTURED','swap_financing_rollover':'NOT_ASSUMED_ZERO;NO_HISTORICAL_SCHEDULE_PROOF','slippage_and_fill_uncertainty':'UNKNOWN;2_5_10BPS_SENSITIVITY_ONLY'},'selection_history':'ADAPTIVE_SHARED_DEVELOPMENT;ALL_OLD_EXACTS_IMMUTABLE;NO_TICKER_RETURN_SELECTION','orders':0,'demo_orders':0,'cloud_deployment':False,'protected_forward':False,'independent_confirmation':False,'robust_positive_NET':False,'HARD21':False}
  PHASE='DURABLE_ENCRYPTED_PRIMARY_AND_ATTESTATION';rt.output(head,auth,tmp,key,'cloudcovariance',{'summary':summary,'private_event_outcomes':trials,'private_bid_ask_pages':raw,'private_identical_csharp_python_samples':samples},summary)
  PHASE='OWNER_ONLY_PRIVATE_AGGREGATE_RELAY';relay(head,auth,summary)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
