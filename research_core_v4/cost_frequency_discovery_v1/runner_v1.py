"""One bounded outcome-blind economic discovery and distinct new predictive wave."""
import os,json,pathlib,tempfile,subprocess,math,gzip,bisect
from datetime import datetime,timezone,timedelta
from collections import Counter,defaultdict
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.native_executable_qualification_v1.runner_v1 import schedule_state
from .collector_v1 import Collector
from . import kernel_v1 as k,accounts_v1 as a
e=rt.e;P='research_core_v4/cost_frequency_discovery_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def inventory(ref):return dict(z.split('\t',1)[::-1] for z in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
def gate():
 h=os.environ['GITHUB_SHA'];auth=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text());e.w.v2.runtime(h)
 need(auth['authority']=='EXPLICIT_OWNER_BROKER_WIDE_ECONOMIC_DISCOVERY_20261012','OWNER_AUTHORITY')
 need(not any(auth[n] for n in ('orders','protected_forward','cloud_deployment','closed_exact_replay','authentication_changes')),'SCOPE')
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-cost-frequency-discovery-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
 need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'EXPIRED')
 for n,sha in auth['bindings'].items():need(e.w.old.filehash(n)==sha,'SOURCE_BINDING')
 e.a.ancestor(auth['base_head'],h);e.a.ancestor(auth['design_commit'],h);old=inventory(auth['base_head']);new=inventory(h);need(all(new.get(p)==v for p,v in old.items()),'ALL_OLD_FILES_PRESERVED');e.w.old.verify_science()
 need(not e.w.v2.existing_ref(auth['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':h});return h,auth
def stratified(rows,cap,previous,quality=None):
 groups=defaultdict(list)
 for r in rows:
  if r['research_contract_eligible'] and (quality is None or quality[r['sid']]['four_period_support']):groups[(r['class'],r['quote'])].append(r)
 for vv in groups.values():vv.sort(key=lambda r:(r['sid'] in previous,quality[r['sid']]['cost_range_ratio'] if quality else r['margin_eur'],r['margin_eur'],r['sid']))
 out=[]
 for j in range(8):
  for key in sorted(groups,key=str):
   if j<len(groups[key]) and len(out)<cap:out.append(groups[key][j])
 return out
def clocks(bars,start,row,f):
 out=[];counts={h:0 for h in k.HORIZONS};times=sorted(bars)
 for t in range(start,start+7*86400,300):
  if t-300 not in bars:continue
  # Exactly completed causal active bars; no exit availability or future prices are read.
  i=bisect.bisect_left(times,t);first=bisect.bisect_left(times,t-5*86400)
  if i-first<48 or schedule_state(t+60,f,{})!='OPEN_CURRENT_SCHEDULE_PROXY':continue
  opened=[h for h in k.HORIZONS if schedule_state(t+60+h*60,f,{})=='OPEN_CURRENT_SCHEDULE_PROXY']
  for h in opened:counts[h]+=1
  if len(opened)==len(k.HORIZONS) and not out:
   pr=k.prior(bars,t,times)
   if pr is not None:out.append({'sid':row['sid'],'t':t+60,'grid':t,'iso':k.iso(t),'class':row['class'],'prior':pr})
 return out,counts
def main():
 global PHASE
 os.umask(0o077);head,auth=gate();design=json.loads((e.a.ROOT/(P+'DESIGN_FREEZE_V1.json')).read_text())
 with tempfile.TemporaryDirectory(prefix='mxm-cost-frequency-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'EXISTING_OWNER_KEY')
  PHASE='AUTHENTIC_EXISTING_SOURCE_RECONCILIATION';source,catproof=load_asset(key,fp,tmp,auth['catalog_source']);cat=source['catalog'];rows=source['identities'];g=a.graph(rows);original_eligible=sum(r['research_contract_eligible'] for r in rows)
  for row in rows:
   row['reasons']=[x for x in row['reasons'] if x!='CURRENT_NATIVE_FX_GRAPH_NO_ROUTE'];f=cat['full'].get(str(row['sid']));row['research_contract_eligible']=not row['reasons']
   if row['research_contract_eligible']:
    cc=a.currencies(row,f);paths=[a.route(x,'EUR',g) for x in cc]+([a.route(row['quote'],'USD',g)] if int(f['commissionType'])==1 else [])
    if any(z is None for z in paths):row['reasons'].append('NATIVE_FX_ROUTE_UP_TO4_UNRESOLVED');row['research_contract_eligible']=False
  previous_obj,previous_proof=load_asset(key,fp,tmp,auth['completed_previous_source']);previous={r['sid'] for r in previous_obj['summary']['research_identities']}
  quotes={(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in previous_obj['completed_frozen_quotes']};del previous_obj
  oldcost,costproof=load_asset(key,fp,tmp,auth['fullcost_source']);quotes.update({(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in oldcost['private_boundary_receipts'] if (int(q['symbol_id']),int(q['boundary_ms'])//1000) not in quotes});del oldcost
  native_obj,nativeproof=load_asset(key,fp,tmp,auth['native_history_source']);native={int(s):{int(t):z for t,z in v.items()} for s,v in native_obj['bars'].items()};del native_obj
  beginning=int(datetime(2025,1,6,tzinfo=timezone.utc).timestamp());starts=[beginning+14*86400*i for i in range(40)];weeks=[k.iso(t) for t in starts];probe_starts=[starts[i] for i in (0,10,20,30)]
  byid={r['sid']:r for r in rows};stage_a=stratified(rows,192,previous);quality={};segments={};checkpoint_receipts=[];catalog_snapshot={'offered':len(rows),'archived':len(cat['archived']),'classes':dict(Counter(r['class'] for r in rows)),'eligible_original':original_eligible,'reassessed_route4_eligible':sum(r['research_contract_eligible'] for r in rows),'reasons_overlapping':dict(Counter(v for r in rows for v in r['reasons']))};col=Collector(design['acquisition']['request_caps']);reused_quote_keys=set(quotes);quote_resource_limited=[];known_segments={};raw_m5=[];checkpoint_count=Counter();stores={}
  def store_for(phase):
   if phase not in stores:
    s=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');s.release=e.w.old.api('releases',{'tag_name':'mxm-cost-frequency-'+phase+'-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted cost frequency '+phase+' checkpoints','prerelease':True,'body':'Authenticated encrypted historical read-only checkpoints. No public market vectors, orders, forward or new deployment.'});stores[phase]=s
   return stores[phase]
  def persist(phase,value):
   checkpoint_count[phase]+=1;s=store_for(phase);value=e.w.old.crypto.strict_json(e.a.enc(value));meta=s.encrypted(value,phase+'-'+str(checkpoint_count[phase])+'.mxmenc');checkpoint_receipts.append({'phase':phase,'release_id':s.release['id'],**meta});return meta
  def progress(phase,ordinal):print(json.dumps({'phase':phase,'ordinal':ordinal,'requests':dict(col.counts),'outcomes_public':False}),flush=True)
  def get_segment(row,start):
   sid=row['sid'];frm=start-5*86400;to=start+7*86400;cache=(sid,start)
   if cache in known_segments:return known_segments[cache]
   if sid in native and native[sid] and frm>=min(native[sid]) and to<=max(native[sid])+300:
    vv={t:z for t,z in native[sid].items() if frm<=t<to};rec=[];status='REUSED_AUTHENTIC_NATIVE_M5_INTERVAL'
   else:vv,rec,status=col.m5(sid,int(cat['full'][str(sid)]['digits']),frm,to)
   known_segments[cache]=(vv,status);raw_m5.append({'sid':sid,'start':start,'status':status,'receipts':rec,'reused':status.startswith('REUSED'),'bars':{str(t):z for t,z in vv.items()}});return vv,status
  def required_keys(ev,horizons):
   row=byid[ev['sid']];f=cat['full'][str(row['sid'])];cc=a.currencies(row,f);paths=[a.route(x,'EUR',g) for x in cc]+([a.route(row['quote'],'USD',g)] if int(f['commissionType'])==1 else [])
   if any(z is None for z in paths):return None
   ids={row['sid']}|{edge[0] for path in paths for edge in path};times={ev['t']}|{ev['t']+h*60 for h in horizons};return {(sid,t) for sid in ids for t in times}
  def acquire(keys):
   missing=keys-set(quotes)
   if col.counts['BID_ASK']+2*len(missing)>col.caps['BID_ASK']:return False
   for sid,t in sorted(missing,key=lambda z:(z[1],z[0])):
    need(t+60<int(datetime(2026,9,17,tzinfo=timezone.utc).timestamp()),'PROTECTED_FORWARD_BOUNDARY');quotes[sid,t]=col.quote(sid,t)
   return True
  try:
   col.connect();need(col.aid==int(cat['trader']['ctidTraderAccountId']),'SAME_AUTHENTIC_CATALOG_ACCOUNT');PHASE='OUTCOME_BLIND192_COST_AND_M5_SUPPORT'
   batch=[]
   for ordinal,row in enumerate(stage_a):
    sid=row['sid'];f=cat['full'][str(sid)];periods=[];ratios=[];liquidity=[];probe_events=[]
    for start in probe_starts:
     bars,status=get_segment(row,start);ee,frequency=clocks(bars,start,row,f);ev=ee[0] if ee else None
     periods.append({'week':k.iso(start),'rows':len(bars),'status':status,'feature_and_schedule_clock':bool(ev),'frequency_proxy':frequency})
     if ev:
      kk=required_keys(ev,());need(kk is not None,'SCREEN_FX_ROUTE');got=acquire(kk)
      en=k.entry(ev,row,f,quotes,g,60) if got else {'state':'LOCAL_BID_ASK_BUDGET','eligible':False}
      if 'cost_eur' in en:ratios.append(en['cost_eur']/max(1e-9,en['notional_eur']*ev['prior']['range_bps']/10000*math.sqrt(12)));liquidity.append(ev['prior']['activity'])
      probe_events.append({'event':ev,'entry':en,'required':sorted(kk)})
    quality[sid]={'sid':sid,'symbol':row['symbol'],'class':row['class'],'quote':row['quote'],'periods':periods,'four_period_support':all(z['feature_and_schedule_clock'] and z['status'] in ('COMPLETE_EXACT_WINDOW','REUSED_AUTHENTIC_NATIVE_M5_INTERVAL') for z in periods),'cost_range_ratio':statistics_median(ratios) if ratios else 1e12,'cost_observed_periods':len(ratios),'liquidity_ratio':statistics_median(liquidity) if liquidity else None,'cost_probes':probe_events};batch.append(sid)
    if len(batch)==8 or ordinal+1==len(stage_a):
     qq=[q for (s,t),q in quotes.items() if (s,t) not in reused_quote_keys];persist('screen',{'schema':'mxm.private.cost.frequency.screen.checkpoint.v1','source_head':head,'catalog_provenance':catproof,'quality':[quality[s] for s in batch],'M5_segments':raw_m5,'new_quotes':qq,'requests':dict(col.counts),'wire_requests':dict(col.wire_types)});raw_m5=[];batch=[];progress(PHASE,ordinal+1)
   deep=stratified(stage_a,64,previous,quality);need(bool(deep),'NO_FOUR_PERIOD_M5_COST_SUPPORT');PHASE='PREOUTCOME_DEEP_M5_AND_FIXED_COHORT';frames=[];frequency={};data_support={}
   # All below selection uses only support and entry cost, never any future NET or sign outcome.
   for ordinal,row in enumerate(deep):
    sid=row['sid'];f=cat['full'][str(sid)];counts={};support={}
    for start in starts:
     bars,status=get_segment(row,start);ee,fr=clocks(bars,start,row,f);counts[k.iso(start)]=fr;support[k.iso(start)]={'rows':len(bars),'status':status,'cohort':len(ee)}
     if ee:frames.extend(ee)
    frequency[str(sid)]=counts;data_support[str(sid)]={'identity':row,'weeks':support};persist('history',{'schema':'mxm.private.cost.frequency.deep.checkpoint.v1','source_head':head,'identity':row,'M5_segments':raw_m5,'frames':[x for x in frames if x['sid']==sid],'frequency_proxy':counts,'support':support,'requests':dict(col.counts)});raw_m5=[]
    # Raw quality windows are kept for other identities; newly deep intervals are durable then released.
    for cache in list(known_segments):
     if cache[0]==sid and cache[1] not in probe_starts:del known_segments[cache]
    progress(PHASE,ordinal+1);e.w.old.budget(maxwall=14000,maxcpu=10000,maxkib=3145728)
   persist('history',{'schema':'mxm.private.cost.frequency.preoutcome.cohort.v1','source_head':head,'design_commit':auth['design_commit'],'deep_identities':deep,'frames':frames,'frequency_proxy':frequency,'M5_support':data_support,'requests':dict(col.counts),'selection_without_exit_outcomes':True})
   PHASE='FROZEN_NATIVE_QUOTES_BEFORE_PREDICTIVE_COMPARISONS';required=set();accepted=[]
   # Round-robin week x class x quote ordering avoids exhausting only early dates when cap binds.
   groups=defaultdict(list)
   for ev in frames:groups[(ev['iso'],ev['class'],byid[ev['sid']]['quote'])].append(ev)
   for vv in groups.values():vv.sort(key=lambda z:(z['t'],z['sid']))
   ordered=[]
   for i in range(max((len(v) for v in groups.values()),default=0)):
    for stratum in sorted(groups,key=str):
     if i<len(groups[stratum]):ordered.append(groups[stratum][i])
   for ev in ordered:
    kk=required_keys(ev,k.HORIZONS);new=(required|kk)-set(quotes) if kk is not None else set()
    if kk is None:quote_resource_limited.append({'sid':ev['sid'],'t':ev['t'],'reason':'NATIVE_FX_UNRESOLVED'});continue
    if col.counts['BID_ASK']+2*len(new)>col.caps['BID_ASK']:quote_resource_limited.append({'sid':ev['sid'],'t':ev['t'],'reason':'LOCAL_FIXED_WHOLE_COHORT_QUOTE_CAP'});continue
    required|=kk;accepted.append(ev)
   needed=sorted(required-set(quotes),key=lambda z:(z[1],z[0]));batch=[]
   for ordinal,(sid,t) in enumerate(needed):
    need(t<int(datetime(2026,9,17,tzinfo=timezone.utc).timestamp()),'PROTECTED_FORWARD_BOUNDARY');quotes[sid,t]=col.quote(sid,t);batch.append(quotes[sid,t])
    if len(batch)==200 or ordinal+1==len(needed):persist('quotes',{'schema':'mxm.private.cost.frequency.quote.checkpoint.v1','source_head':head,'new_quotes':batch,'requests':dict(col.counts),'wire_requests':dict(col.wire_types),'cohort_sha256':e.a.sha(e.a.enc(accepted))});batch=[];progress(PHASE,ordinal+1)
   persist('quotes',{'schema':'mxm.private.cost.frequency.complete.quote.cohort.v1','source_head':head,'accepted_frames':accepted,'resource_limited_frames':quote_resource_limited,'required':sorted(required),'quotes':[quotes[z] for z in sorted(required)],'requests':dict(col.counts),'wire_requests':dict(col.wire_types),'no_outcome_selection':True})
  finally:col.close()
  PHASE='NEW_NATIVE_NET_PREDICTIVE_NUMERIC_EXECUTION';events=[]
  for ev in accepted:
   row=byid[ev['sid']];f=cat['full'][str(ev['sid'])]
   for h in k.HORIZONS:
    en=k.entry(ev,row,f,quotes,g,h);accounts={name:[a.account(d,row,f,ev['t'],ev['t']+h*60,h/60,quotes,g,slip,fund,absolute) for d in (1,-1)] for name,(slip,fund,absolute) in a.SCENARIOS.items()};nets=accounts['S2_F010_DAY'];nets=[v['net_eur'] for v in nets] if all(v is not None for v in nets) and 'features' in en else None
    events.append({**ev,'h':h,'exit':ev['t']+h*60,'entry':en,'accounts':accounts,'net_sides':nets})
  evaluated=k.causal_evaluate(events);results={fam:{str(h):k.report([r for r in evaluated if r['family']==fam and r['h']==h],weeks) for h in k.HORIZONS} for fam in k.FAMILIES};portfolios={fam:{str(h):{str(slots):{'model':k.portfolio([r for r in evaluated if r['family']==fam and r['h']==h],weeks,slots),'baseline':k.portfolio([r for r in evaluated if r['family']==fam and r['h']==h],weeks,slots,True)} for slots in (1,2,4)} for h in k.HORIZONS} for fam in k.FAMILIES}
  feasibility={}
  for h in k.HORIZONS:
   rr=[r for r in events if r['h']==h];sc={}
   for name in a.SCENARIOS:
    z=[r['accounts'][name] for r in rr if all(v is not None for v in r['accounts'][name])];sc[name]={'priced':len(z),'long_net_eur':sum(x[0]['net_eur'] for x in z) if z else None,'short_net_eur':sum(x[1]['net_eur'] for x in z) if z else None,'hindsight_best_side_upper_eur_DIAGNOSTIC':sum(max(x[0]['net_eur'],x[1]['net_eur']) for x in z) if z else None,'fraction_one_positive_side':sum(max(x[0]['net_eur'],x[1]['net_eur'])>0 for x in z)/len(z) if z else None}
   feasibility[str(h)]={'entry_proxy_eligible':sum(r['entry'].get('eligible',False) for r in rr),'entry_cost_bps_median':statistics_median([r['entry']['cost_bps'] for r in rr if 'cost_bps' in r['entry']]),'entry_risk_eur_median':statistics_median([r['entry']['risk_eur'] for r in rr if 'risk_eur' in r['entry']]),'unresolved_entry_reasons':dict(Counter(r['entry']['state'] for r in rr)),'scenarios':sc}
  summary={'schema':'mxm.private.broker.wide.cost.frequency.summary.v1','source_head':head,'design_commit':auth['design_commit'],'classification':design['classification'],'catalog':catalog_snapshot,'stage_a_count':len(stage_a),'stage_a_four_period_pass':sum(z['four_period_support'] for z in quality.values()),'stage_a_cost_observed_four_periods':sum(z['cost_observed_periods']==4 for z in quality.values()),'deep_count':len(deep),'deep_new_to_previous51':sum(r['sid'] not in previous for r in deep),'deep_identities':deep,'unevaluated_contract_eligible':sum(r['research_contract_eligible'] for r in rows)-len(stage_a),'M5_data_support':data_support,'fixed_cohort_frames':len(frames),'quote_accepted_frames':len(accepted),'resource_limited_frames':len(quote_resource_limited),'quote_required_boundaries':len(required),'quote_valid_fresh_complete':sum(a.point(quotes[z]) is not None for z in required),'quote_side_states':dict(Counter(s.get('state') for z in required for s in quotes[z]['sides'].values())),'requests':dict(col.counts),'wire_requests_by_type':dict(col.wire_types),'old_H1_or_magnitude_kernel_calls':0,'new_predictive_events':len(events),'weeks':weeks,'feasibility':feasibility,'predictive':results,'portfolios':portfolios,'frequency_proxy_global':{str(h):{w:sum(frequency[str(r['sid'])][w][h] for r in deep) for w in weeks} for h in k.HORIZONS},'HARD21':{'demonstrated':False,'actual_orders':0,'actual_fills':0,'single_position_geometric_weekly_upper':{str(h):10080//h for h in k.HORIZONS},'concurrency':(1,2,4),'frequency_proxy_not_orders_or_certification':True},'dated_contract_terms':'CATALOG_2026OCT11_CURRENT_REFERENCE;HISTORICAL_COMMISSION_MARGIN_FUNDING_AND_REAL_FILLS_UNKNOWN','source_provenance':[catproof,previous_proof,costproof,nativeproof],'checkpoints':checkpoint_receipts,'selection_and_M5_quality_probes_use_no_future_NET':True,'independent_acceptance_claimed':False,'orders':0,'fills':0,'protected_forward':False,'cloud_changes':False,'scientific_bindings':auth['bindings']}
  full={'summary':summary,'screen':quality,'catalog':cat,'all_identity_status':rows,'events':evaluated,'raw_quote_receipts':[quotes[z] for z in sorted(required)],'resource_limited_frames':quote_resource_limited,'all_original_exacts_unchanged':True};PHASE='ENCRYPTED_FINAL_PUBLICATION';rt.output(head,auth,tmp,key,'costfrequency',full,summary)
  compact={n:v for n,v in summary.items() if n not in ('checkpoints','M5_data_support','portfolios','frequency_proxy_global','scientific_bindings')};compact['portfolios']={fam:{h:{slot:{which:{n:v for n,v in r.items() if n!='selected_receipts'} for which,r in item.items()} for slot,item in hs.items()} for h,hs in views.items()} for fam,views in portfolios.items()};compact['data_checkpoint_releases']={n:s.release['id'] for n,s in stores.items()};relay(head,auth,tmp,compact)
def statistics_median(v):
 import statistics
 return statistics.median(v) if v else None
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
