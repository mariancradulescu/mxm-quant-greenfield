"""Prospective native coverage tranche; no predictor or closed-exact replay."""
import os,json,pathlib,tempfile,subprocess,math,statistics,base64,time
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.cost_frequency_discovery_v1.collector_v1 import Collector
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as fx
from research_core_v4.native_executable_qualification_v1.runner_v1 import schedule_state
from research_core_v4.quote_path_recipient_recovery_20261013_v1 import delivery_contract_v1 as custody
E=rt.e;P='research_core_v4/native_coverage_expansion_20261014_v1/';WF='.github/workflows/mxm-native-coverage-expansion-20261014-v1.yml'
def need(v,c):E.w.old.need(bool(v),c)
def stamp(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
def select(rows,cap):
 groups=defaultdict(list)
 for r in rows:groups[(r['class'],r['quote'],int(float(r['margin_eur'])//20))].append(r)
 for v in groups.values():v.sort(key=lambda r:(r['margin_eur'],r['sid']))
 out=[]
 for i in range(max(map(len,groups.values()),default=0)):
  for key in sorted(groups,key=str):
   if i<len(groups[key]) and len(out)<cap:out.append(groups[key][i])
 return out

def gate():
 head=os.environ['GITHUB_SHA'];a=json.loads((E.a.ROOT/(P+'EXECUTION_V1.json')).read_text());E.w.v2.runtime(head)
 need(a['authority']=='EXPLICIT_OWNER_NATIVE_COVERAGE_EXPANSION_20261014','OWNER_SCOPE')
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1','ONE_PUSH')
 need(os.environ['GITHUB_WORKFLOW_REF']==E.w.old.REPO+'/'+WF+'@refs/heads/'+E.w.old.BRANCH,'WORKFLOW')
 need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED')
 E.a.ancestor(a['base_head'],head)
 old=set(subprocess.check_output(['git','ls-tree','-r',a['base_head']],text=True).splitlines());new=set(subprocess.check_output(['git','ls-tree','-r',head],text=True).splitlines());need(old<=new,'OLD_FILE_DRIFT')
 for path,digest in a['bindings'].items():need(E.w.old.filehash(path)==digest,'SOURCE_BINDING')
 pub=(E.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem')).read_bytes();ready=json.loads((E.a.ROOT/(P+'RECIPIENT_READY_V1.json')).read_text());custody.require_ready(ready,pub,a['invocation_id'],datetime.fromisoformat(a['expires_utc']));need(custody.fingerprint(pub)==a['recipient_spki_sha256'],'RECIPIENT')
 need(not E.w.v2.existing_ref(a['one_use_ref']),'CONSUMED')
 need(E.w.old.api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']==head,'LIVE_HEAD')
 E.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':head})
 return head,a

def reference(row,f,t,quotes,g,slip):
 q=fx.point(quotes.get((row['sid'],t)))
 if not q:return {'state':'NATIVE_QUOTE_NOT_FRESH_COMPLETE','eligible':False}
 u=int(f['minVolume'])/100
 notional=fx.convert(-u*q['mid'],row['quote'],'EUR',t,quotes,g)
 spread=fx.convert(-u*(q['ask']-q['bid']),row['quote'],'EUR',t,quotes,g)
 fees=[fx.commission(row,f,u,q[side],t,quotes,g) for side in ('ask','bid')]
 if notional is None or spread is None or any(v is None for v in fees):return {'state':'NATIVE_FX_OR_COMMISSION_UNRESOLVED','eligible':False}
 notional=-notional;spread=-spread;slippage=notional*2*slip/10000;fund=.10*.25/24
 cost=spread+sum(fees)+slippage+fund;stop_risk=notional*5/10000;required_risk=cost+stop_risk
 schedule=schedule_state(t,f,{})
 return {'state':'REFERENCE_FEASIBLE' if required_risk<=2 and row['margin_eur']<=80 and schedule=='OPEN_CURRENT_SCHEDULE_PROXY' else 'REFERENCE_INFEASIBLE', 'eligible':required_risk<=2 and row['margin_eur']<=80 and schedule=='OPEN_CURRENT_SCHEDULE_PROXY','minimum_units':u,'notional_eur':notional,'spread_eur':spread,'commission_RT_eur':sum(fees),'slippage_RT_eur':slippage,'funding_stress_eur':fund,'break_even_eur':cost,'break_even_bps':cost/notional*10000 if notional>0 else None,'stop_reference_bps':5,'planned_risk_eur':required_risk,'margin_eur_current':row['margin_eur'],'reserve_eur_reference':200-row['margin_eur'],'schedule':schedule,'historical_fee_margin_funding_authority':'UNKNOWN_CURRENT_TERMS_PLUS_FROZEN_STRESS','native_financing_current_fields':{k:f[k] for k in ('swapLong','swapShort','swapCalculationType','swapRollover3Days','swapTime','swapPeriod','chargeSwapAtWeekends') if k in f},'realized_risk_eur':None,'stop_guaranteed':False}

def distribution(v):
 vv=sorted(x for x in v if x is not None and math.isfinite(x))
 return {'n':len(vv),'min':vv[0] if vv else None,'p25':vv[int((len(vv)-1)*.25)] if vv else None,'median':statistics.median(vv) if vv else None,'p75':vv[int((len(vv)-1)*.75)] if vv else None,'max':vv[-1] if vv else None}

def main():
 os.umask(0o077);head,a=gate()
 with tempfile.TemporaryDirectory(prefix='mxm-expand-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,'OWNER_KEY')
  pre,preproof=load_asset(key,fp,tmp,a['precheck']);source,catproof=load_asset(key,fp,tmp,a['catalog_source']);full,fullproof=load_asset(key,fp,tmp,a['quote_source'])
  status=pre['summary']['statuses'];rows={int(r['sid']):dict(r) for r in source['identities']};cat=source['catalog'];need(len(status)==len(rows)==5326,'CATALOG_DENOMINATOR')
  eligible=[s for s in status if s['structural_eligible'] and s['known_accepted_M5']];missing=[rows[s['sid']] for s in eligible if not s['saved_quote_pages']]
  need(len(eligible)==1549 and len(missing)==1488,'ACCEPTED_COUNTS')
  quotes={};archive_proofs=[preproof,catproof,fullproof];conflicts=[]
  def merge(q):
   k=(int(q['symbol_id']),int(q['boundary_ms'])//1000)
   if k in quotes and quotes[k]!=q:conflicts.append(k)
   else:quotes[k]=q
  for q in full['raw_quote_receipts']:merge(q)
  # Inspect all retained quote-bearing checkpoints, including screen pages omitted
  # from the historical final intersection. Do not equate the 61 with whole archive.
  for c in full['summary'].get('checkpoints',[]):
   if c['phase'] not in ('screen','quotes'):continue
   obj,proof=load_asset(key,fp,tmp,{'release_id':c['release_id'],'asset_id':c['id'],'ciphertext_sha256':c['ciphertext_sha256']});archive_proofs.append(proof)
   for q in obj.get('new_quotes',[])+obj.get('quotes',[]):merge(q)
  need(not conflicts,'ARCHIVE_CONFLICT')
  original_keys=set(quotes);archive_ids={sid for (sid,t),q in quotes.items() if q.get('pages')}
  # Prefer truly absent full-archive identities. Then deterministic class/currency/
  # margin round robin; no entry outcome, exit support or future return is read.
  unseen=[r for r in missing if r['sid'] not in archive_ids];seen=[r for r in missing if r['sid'] in archive_ids]
  broad=select(unseen,a['breadth_cap']);broad+=select(seen,a['breadth_cap']-len(broad));temporal=select(broad,a['temporal_cap'])
  selected_ids={r['sid'] for r in broad};g=fx.graph(list(rows.values()));events=[];route_unresolved=[]
  for r in broad:
   for clock in a['breadth_clocks']:events.append({'sid':r['sid'],'t':stamp(clock),'phase':'BREADTH'})
  for r in temporal:
   for week in a['weeks']:
    base=stamp(week)
    for day in a['temporal_days']:
     for hour in a['session_hours']:events.append({'sid':r['sid'],'t':base+day*86400+hour*3600+300,'phase':'CONSECUTIVE'})
  events=list({(z['sid'],z['t']):z for z in events}.values());events.sort(key=lambda z:(z['t'],z['sid']))
  required=set();cutoff=stamp('2026-09-17T00:00:00Z')
  for z in events:
   r=rows[z['sid']];f=cat['full'][str(r['sid'])];paths=[fx.route(c,'EUR',g) for c in fx.currencies(r,f)]
   if int(f['commissionType'])==1:paths.append(fx.route(r['quote'],'USD',g))
   ids={r['sid']}|{edge[0] for path in paths if path is not None for edge in path}
   if any(path is None for path in paths):route_unresolved.append((r['sid'],z['t']))
   for t in (z['t'],z['t']+900):
    need(t<cutoff,'PROTECTED_DOMAIN');required|={(sid,t) for sid in ids}
  keys=sorted(required-original_keys,key=lambda k:(k[1],k[0]));need(2*len(keys)<=a['max_tick_requests'],'PROSPECTIVE_TOTAL_BUDGET')
  store=E.w.old.GitHubStore(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,'real')
  store.release=E.w.old.api('releases',{'tag_name':'mxm-native-coverage-expansion-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted native economic coverage expansion','prerelease':True,'body':'Prospective DEVELOPMENT quote coverage. Encrypted broker data only; no orders or predictor replay.'})
  receipts=[];ordinal=0
  def persist(value,name):
   value=E.w.old.crypto.strict_json(E.a.enc(value));meta=store.encrypted(value,name);receipts.append(meta);return meta
  persist({'schema':'mxm.native.coverage.prospective.plan.v1','head':head,'policy':a,'all_statuses':status,'selected':broad,'temporal_selected':temporal,'events':events,'required':sorted(required),'archive_proofs':archive_proofs,'original_archive_ids':sorted(archive_ids),'request_count_planned':2*len(keys),'selection_before_new_quote_support':True},'prospective-plan.mxmenc')
  col=Collector({'BID_ASK':a['max_tick_requests']});batch=[];failures=[];beg=time.monotonic();transport_broken=False
  try:
   col.connect();need(col.aid==int(cat['trader']['ctidTraderAccountId']),'SAME_ACCOUNT')
   for sid,t in keys:
    if time.monotonic()-beg>a['max_capture_seconds']:failures.append({'state':'WALL_BUDGET_REMAINDER','remaining':len(keys)-ordinal});break
    q=col.quote(sid,t);quotes[sid,t]=q;batch.append(q);ordinal+=1
    if all(s.get('state')=='TRANSPORT_UNRESOLVED' for s in q['sides'].values()):transport_broken=True
    if len(batch)>=64 or ordinal==len(keys) or transport_broken:
     persist({'schema':'mxm.native.coverage.quote.checkpoint.v1','quotes':batch,'head':head,'requests':dict(col.counts),'wire_types':dict(col.wire_types),'ordinal':ordinal,'raw_receipts_authenticated_by_existing_transport':True},'quotes-'+str(ordinal)+'.mxmenc');batch=[]
     print(json.dumps({'phase':'NATIVE_COVERAGE_ACQUISITION','ordinal':ordinal,'planned':len(keys),'tick_requests':col.counts['BID_ASK']}),flush=True)
    if transport_broken:failures.append({'state':'TRANSPORT_BROKEN_REMAINDER_NOT_BROKER_UNAVAILABLE','remaining':len(keys)-ordinal});break
  except Exception as ex:failures.append({'state':'AUTH_OR_CAPTURE_UNRESOLVED','exception_class':type(ex).__name__})
  finally:
   col.close()
   if batch:persist({'quotes':batch,'head':head,'requests':dict(col.counts)},'quotes-final-partial.mxmenc')
  newq=[quotes[k] for k in keys if k in quotes];new_ids={int(q['symbol_id']) for q in newq if q.get('pages')};bilateral={int(q['symbol_id']) for q in newq if {p['side'] for p in q.get('pages',[])}=={'bid','ask'} and all(any(p['encoded'] for p in q['pages'] if p['side']==side) for side in ('bid','ask'))}
  fresh={int(q['symbol_id']) for q in newq if fx.point(q)};records=[]
  for z in events:
   r=rows[z['sid']];f=cat['full'][str(r['sid'])];references={str(s):reference(r,f,z['t'],quotes,g,s) for s in (0,2,5)};entry=fx.point(quotes.get((r['sid'],z['t'])));exit=fx.point(quotes.get((r['sid'],z['t']+900)));reasons=[]
   if not entry:reasons.append('ENTRY_NATIVE_FRESH_QUOTE_NA')
   if not exit:reasons.append('EXIT_NATIVE_FRESH_QUOTE_NA')
   # paired support measured without generating future-return labels or directions.
   accounts=[fx.account(d,r,f,z['t'],z['t']+900,.25,quotes,g,2,.10) for d in (1,-1)] if entry and exit else [None,None]
   if entry and exit and any(v is None for v in accounts):reasons.append('PAIRED_NATIVE_FX_OR_FEES_NA')
   records.append({**z,'iso':iso(z['t']),'class':r['class'],'quote':r['quote'],'session_hour':datetime.fromtimestamp(z['t'],timezone.utc).hour,'reference':references,'paired_native_support':not reasons,'missing_reasons':reasons,'funding_current_fields':references['2'].get('native_financing_current_fields',{})})
  def stats(rr):
   known=[r['reference']['2'] for r in rr if 'break_even_eur' in r['reference']['2']]
   return {'opportunities':len(rr),'entry_cost_known':len(known),'paired_native_support':sum(r['paired_native_support'] for r in rr),'reference_feasible':sum(r['reference']['2']['eligible'] for r in rr),'break_even_eur':distribution([r['break_even_eur'] for r in known]),'break_even_bps':distribution([r['break_even_bps'] for r in known]),'planned_risk_eur':distribution([r['planned_risk_eur'] for r in known]),'reasons':dict(Counter(r['reference']['2']['state'] for r in rr))}
  grouped={}
  for dim in ('sid','class','quote','session_hour','iso'):
   groups=defaultdict(list)
   for z in records:groups[str(z[dim])].append(z)
   grouped[dim]={k:stats(v) for k,v in groups.items()}
  weekly={}
  for week in a['weeks']:
   w=iso(stamp(week));rr=[r for r in records if r['phase']=='CONSECUTIVE' and r['iso']==w];equity=200.;active=[];accepted=[];collisions=Counter()
   for z in sorted(rr,key=lambda z:(z['t'],z['sid'])):
    active=[v for v in active if v['exit']>z['t']];ref=z['reference']['2'];sid=z['sid']
    if not ref['eligible']:collisions['ENTRY_COST_RISK_OR_QUOTE_NA']+=1;continue
    if any(v['sid']==sid for v in active):collisions['SAME_SYMBOL_POSITION']+=1;continue
    if sum(v['risk'] for v in active)+ref['planned_risk_eur']>equity*.01:collisions['AGGREGATE_RISK']+=1;continue
    if sum(v['margin'] for v in active)+ref['margin_eur_current']>equity*.4:collisions['AGGREGATE_MARGIN']+=1;continue
    active.append({'sid':sid,'exit':z['t']+900,'risk':ref['planned_risk_eur'],'margin':ref['margin_eur_current']});accepted.append(z)
   weekly[w]={'fixed_grid_opportunities':len(rr),'entry_reference_allocatable':len(accepted),'entry_exit_accounting_supported':sum(z['paired_native_support'] for z in accepted),'collision_reasons':dict(collisions),'actual_entries':0,'equity_assumption':200,'dynamic_equity_NA_without_strategy_cashflows':True,'continuous_week_supported':False}
  # Missing duration is based on observed freshness coverage only; unsampled times
  # stay UNKNOWN, never count as a confirmed quote outage.
  observed=[]
  for q in newq:
   for side in q['sides'].values():
    if side.get('state')=='AUTHENTIC_CAUSAL_QUOTE':observed.append(side['age_ms'])
  summary={'schema':'mxm.native.coverage.expansion.summary.v1','source_head':head,'run_id':int(os.environ['GITHUB_RUN_ID']),'catalog':5326,'structural_eligible':1562,'eligible_M5':1549,'baseline_saved_quote_intersection':61,'eligible_missing_baseline':1488,'breadth_selected':len(broad),'temporal_selected':len(temporal),'whole_archive_preexisting_ids':len(archive_ids),'selected_whole_archive_previously_absent':sum(r['sid'] not in archive_ids for r in broad),'new_page_identities':len(new_ids),'new_bilateral_nonempty_identities':len(bilateral),'new_fresh_identities':len(fresh),'new_bilateral_eligible_baseline_uncovered':len(bilateral&selected_ids),'new_bilateral_whole_archive_uncovered':len(bilateral&selected_ids-archive_ids),'eligible_M5_saved_intersection_after':61+len(new_ids&selected_ids),'eligible_baseline_still_without_saved_quotes':1488-len(new_ids&selected_ids),'new_boundary_windows':len(newq),'new_nonempty_bilateral_windows':sum({p['side'] for p in q.get('pages',[]) if p['encoded']}=={'bid','ask'} for q in newq),'fresh_complete_windows':sum(fx.point(q) is not None for q in newq),'reused_boundaries':len(required&original_keys),'historical_tick_requests':col.counts['BID_ASK'],'wire_types':dict(col.wire_types),'side_states':dict(Counter(s['state'] for q in newq for s in q['sides'].values())),'quote_age_ms':distribution(observed),'economics':stats(records),'consecutive_week_reference_capacity':weekly,'unknown_unsampled_time_seconds':'NOT_MEASURED_NO_FULL_WEEK_CAPTURE','historical_financing_slippage_fills':'UNKNOWN;CURRENT_NATIVE_TERMS_REFERENCE_AND_STRESS_ONLY','full_historical_NET':None,'new_predictor':False,'pilot_executed':False,'pilot_reason':'SPARSE_PROSPECTIVE_COVERAGE_DOES_NOT_ESTABLISH_CAUSAL_INCREMENT_OR_CONTIGUOUS_EVENT_HISTORY;NO_CANDIDATE_QUALIFIED_BY_COVERAGE_ALONE','next_decision':'USE_NEW_ARCHIVED_IDENTITY_WINDOWS_FOR_NEXT_PROSPECTIVE_HISTORY_AND_CAUSAL_MECHANISM_QUALIFICATION' if new_ids else 'RESOLVE_SPECIFIC_AUTH_TRANSPORT_OR_PROTOCOL_LIMIT_FROM_ENCRYPTED_RECEIPTS','failures':failures,'orders':0,'Cloud_parity':'NOT_CERTIFIED','HARD21':False,'cap_is_tranche_budget_not_universe_limit':True,'checks':{'old_files_preserved':True,'no_protected_forward':True,'closed_exact_calls':0,'returns_used_for_selection':False,'owner_remote_decryption':True}}
  result={'summary':summary,'per_dimension':grouped,'records':records,'all_catalog_status':status,'new_identity_ids':sorted(new_ids),'new_bilateral_ids':sorted(bilateral),'new_boundary_index':[(q['symbol_id'],q['boundary_ms']) for q in newq],'archive_proofs':archive_proofs,'checkpoints':receipts}
  summary.update(per_dimension=grouped,new_identity_ids=sorted(new_ids),new_bilateral_ids=sorted(bilateral),selected_identities=broad)
  primary=persist(result,'coverage-economic-result.mxmenc');summary.update(primary=primary,release_id=store.release['id']);relay=E.upload_extra(store.release,tmp,E.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem'),summary,'coverage-recipient-summary.mxmenc')
  safe={k:summary[k] for k in ('schema','source_head','run_id','catalog','structural_eligible','eligible_M5','baseline_saved_quote_intersection','eligible_missing_baseline','breadth_selected','temporal_selected','whole_archive_preexisting_ids','selected_whole_archive_previously_absent','new_page_identities','new_bilateral_nonempty_identities','new_fresh_identities','new_bilateral_eligible_baseline_uncovered','new_bilateral_whole_archive_uncovered','eligible_M5_saved_intersection_after','eligible_baseline_still_without_saved_quotes','new_boundary_windows','new_nonempty_bilateral_windows','fresh_complete_windows','reused_boundaries','historical_tick_requests','new_predictor','pilot_executed','pilot_reason','next_decision','orders','HARD21','cap_is_tranche_budget_not_universe_limit')};safe.update(release_id=store.release['id'],primary_asset=primary,recipient_asset=relay,OWNER_READBACK_SUCCESS=True,DELIVERY_SUCCESS=False)
  E.w.old.api('releases/'+str(store.release['id']),{'body':json.dumps(safe,sort_keys=True)},method='PATCH');need(json.loads(E.w.old.api('releases/'+str(store.release['id']))['body'])==safe,'RELEASE_READBACK');
  # Recipient ciphertext is retained as UTF-8 base64 for connector-only recovery.
  cipher=E.w.old.download(next(x for x in E.w.old.api('releases/'+str(store.release['id'])+'/assets?per_page=100') if x['id']==relay['id'])['browser_download_url'],relay['size']);need(E.a.sha(cipher)==relay['ciphertext_sha256'],'RECIPIENT_CIPHER')
  entries=[]
  for path,content in [(P+'RECIPIENT_SUMMARY_V1.mxmenc.b64',base64.b64encode(cipher).decode()+'\n'),(P+'RESULT_PUBLIC_SAFE_V1.json',json.dumps(safe,sort_keys=True,indent=2)+'\n')]:
   blob=E.w.old.api('git/blobs',{'content':content,'encoding':'utf-8'});entries.append({'path':path,'mode':'100644','type':'blob','sha':blob['sha']})
  need(E.w.old.api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']==head,'DELIVERY_HEAD_DRIFT')
  tree=E.w.old.api('git/trees',{'base_tree':E.w.old.api('git/commits/'+head)['tree']['sha'],'tree':entries});commit=E.w.old.api('git/commits',{'message':'Preserve encrypted native coverage delivery and verified safe counts [skip ci]','parents':[head],'tree':tree['sha']});E.w.old.api('git/refs/heads/'+E.w.old.BRANCH,{'sha':commit['sha'],'force':False},method='PATCH');safe['delivery_head']=commit['sha'];print(json.dumps(safe,sort_keys=True),flush=True)
if __name__=='__main__':
 try:main()
 except Exception as ex:
  print('FAIL_CLOSED_NATIVE_COVERAGE_'+type(ex).__name__,flush=True);raise SystemExit(1) from None
