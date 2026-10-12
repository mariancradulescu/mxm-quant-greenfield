"""Bounded saved-entry exit diagnostic; ciphertext inputs and ciphertext-only outputs."""
import os,json,pathlib,tempfile,subprocess,bisect,statistics,math
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as a
from . import policy_v1 as p
from .collector_v1 import Collector
e=rt.e;P='research_core_v4/dynamic_exit_diagnostic_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def inventory(h):return dict(v.split('\t',1)[::-1] for v in subprocess.check_output(['git','ls-tree','-r',h],cwd=e.a.ROOT,text=True).splitlines())
def gate():
 head=os.environ['GITHUB_SHA'];auth=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text());e.w.v2.runtime(head)
 need(auth['authority']=='EXPLICIT_OWNER_DYNAMIC_EXIT_PIVOT_20261012','OWNER_SCOPE');need(not any(auth[n] for n in ('orders','protected_forward','cloud_changes','authentication_changes','closed_kernel_replay')),'SCOPE')
 need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-dynamic-exit-diagnostic-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE');need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'EXPIRED')
 for path,sha in auth['bindings'].items():need(e.w.old.filehash(path)==sha,'SOURCE_BINDING')
 e.a.ancestor(auth['base_head'],head);e.a.ancestor(auth['design_commit'],head);old=inventory(auth['base_head']);new=inventory(head);need(all(new.get(k)==v for k,v in old.items()),'OLD_FILES_PRESERVED');e.w.old.verify_science()
 run=e.w.old.api('actions/runs/38197915724');need(run['conclusion']=='success' and run['head_sha']==auth['base_head'],'SAVED_RUN')
 need(not e.w.v2.existing_ref(auth['one_use_ref']),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':head});return head,auth

def main():
 global PHASE
 os.umask(0o077);head,auth=gate()
 with tempfile.TemporaryDirectory(prefix='mxm-dynamic-exit-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='READ_SAVED_SIGNALS_AND_CHECKPOINTS'
  full,proof=load_asset(key,fp,tmp,auth['numeric_source']);need(full['summary']['source_head']==auth['base_head'],'NUMERIC_SOURCE');cat=full['catalog'];byid={r['sid']:r for r in full['all_identity_status']};graph=a.graph(list(byid.values()))
  saved=[r for r in full['events'] if r['family']=='NATIVE_NET_SIDE_COST_CONDITIONING_V1' and r['model_admit']];baseline_saved=[r for r in full['events'] if r['baseline_admit']];need(len(saved)==sum(v['model_entries'] for v in full['summary']['predictive']['NATIVE_NET_SIDE_COST_CONDITIONING_V1'].values()),'SAVED_ENTRY_COUNT')
  quotes={(int(q['symbol_id']),int(q['boundary_ms'])/1000):q for q in full['raw_quote_receipts']};needed_ids={r['sid'] for r in saved};bars=defaultdict(dict);provenance=[proof];asset_counts=Counter();m5_receipt_status=Counter();m5_segments_seen=set();m5_rows_unique_source=0
  def merge_segment(seg):
   nonlocal m5_rows_unique_source
   sid=int(seg['sid']);mark=(sid,int(seg['start']))
   if mark not in m5_segments_seen:m5_receipt_status[seg['status']]+=1;m5_segments_seen.add(mark)
   if sid not in needed_ids:return
   for t,z in seg.get('bars',{}).items():
    t=int(t);need(t not in bars[sid] or bars[sid][t]==z,'M5_CONFLICT');bars[sid][t]=z
  # Frozen asset id + ciphertext SHA verifies every checkpoint actually opened.
  for binding in auth['screen_sources']:
   cp,pr=load_asset(key,fp,tmp,binding);need(cp['source_head']==auth['base_head'],'SCREEN_HEAD');provenance.append(pr);asset_counts['screen']+=1
   for seg in cp['M5_segments']:merge_segment(seg)
   print(json.dumps({'phase':PHASE,'screen_checkpoint':asset_counts['screen'],'outcomes_public':False}),flush=True)
  deep=full['summary']['deep_identities'];ordinal={r['sid']:i+1 for i,r in enumerate(deep)}
  for binding in auth['history_sources']:
   if binding['ordinal'] not in {ordinal[sid] for sid in needed_ids}:continue
   cp,pr=load_asset(key,fp,tmp,binding);need(cp['source_head']==auth['base_head'],'HISTORY_HEAD');provenance.append(pr);asset_counts['history']+=1
   for seg in cp.get('M5_segments',[]):merge_segment(seg)
  native,npr=load_asset(key,fp,tmp,auth['native_history_source']);provenance.append(npr)
  for sid,z in native['bars'].items():
   sid=int(sid)
   if sid in needed_ids:
    for t,v in z.items():
     t=int(t);need(t not in bars[sid] or bars[sid][t]==v,'NATIVE_M5_CONFLICT');bars[sid][t]=v
  PHASE='FROZEN_ENTRY_ONLY_TICK_SELECTION';parameters={};candidates=[]
  for r in saved:
   par=p.params(r,bars[r['sid']],a.point(quotes.get((r['sid'],r['t']))));parameters[r['sid'],r['t'],r['h']]=par
   if par and par['stress_eligible']:candidates.append(r)
  # Four slots per original forecast horizon; diversity order uses no future bars or NET.
  pools={h:sorted([r for r in candidates if r['h']==h],key=lambda r:(r['class'],r['iso'],r['t'],r['sid'])) for h in (15,60,240)};selected=[];seen=set();used=Counter()
  while len(selected)<12:
   added=False
   for h in (15,60,240):
    if used[h]>=4:continue
    while pools[h] and (pools[h][0]['sid'],pools[h][0]['t']) in seen:pools[h].pop(0)
    if pools[h]:
     r=pools[h].pop(0);selected.append(r);seen.add((r['sid'],r['t']));used[h]+=1;added=True
   if not added:break
  selected_bind=e.a.sha(e.a.enc([{'sid':r['sid'],'t':r['t'],'h':r['h'],'side':r['model_side']} for r in selected]));selection_states=dict(Counter('STRESS_ELIGIBLE' if parameters[r['sid'],r['t'],r['h']] and parameters[r['sid'],r['t'],r['h']]['stress_eligible'] else 'STRESS_OR_ATR_NA' for r in saved))
  checkpoint=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');checkpoint.release=e.w.old.api('releases',{'tag_name':'mxm-dynamic-exit-checkpoints-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted causal dynamic exit checkpoints','prerelease':True,'body':'Private historical read-only exit diagnostic. No public prices, signals, outcomes, orders or Cloud changes.'});cpmeta=[]
  def persist(name,obj):cpmeta.append(checkpoint.encrypted(e.w.old.crypto.strict_json(e.a.enc(obj)),name+'.mxmenc'))
  persist('frozen-entry-only-selection',{'source_head':head,'source_provenance':provenance,'selected':selected,'selection_sha256':selected_bind,'parameters':[{**{'sid':r['sid'],'t':r['t'],'h':r['h']},'value':parameters[r['sid'],r['t'],r['h']]} for r in saved],'outcomes_used_for_selection':False})
  PHASE='EXISTING_M5_NUMERIC_EXIT_GEOMETRY';records=[]
  for r in saved:
   par=parameters[r['sid'],r['t'],r['h']];fixed=r['accounts']['S2_F010_DAY'];fixed=fixed[0 if r['model_side']>0 else 1] if fixed else None
   for name in p.POLICIES:
    geo=p.m5_geometry(r,bars[r['sid']],par,name);records.append({'sid':r['sid'],'symbol':byid[r['sid']]['symbol'],'class':r['class'],'t':r['t'],'h':r['h'],'side':r['model_side'],'policy':name,'M5':geo,'state':'NOT_SELECTED_TICK_TRANCHE','dynamic_net':None,'fixed_net':fixed['net_eur'] if fixed else None,'fixed_exit':r['exit'],'exit':None,'margin_eur':r['entry']['margin_eur'],'stress_risk_eur':par['stress_risk_eur'] if par else None,'stress_eligible':par['stress_eligible'] if par else False})
  persist('existing-M5-exit-geometry',{'records':records,'source_head':head,'broker_requests':0,'closed_kernel_calls':0})
  PHASE='BOUNDED_AUTHENTIC_BIDASK_EXIT_TRANCHE';col=Collector();auth_state='NOT_NEEDED_NO_STRESS_ELIGIBLE_ENTRIES';raw_paths=[];new_fx=[];tick_statuses=Counter();tick_rows=Counter();path_reports=[]
  if selected:
   try:
    col.connect();need(col.aid==int(cat['trader']['ctidTraderAccountId']),'SAME_BROKER_ACCOUNT');auth_state='PASS_EXISTING_VIEW_NATIVE_ACCOUNT'
    for ordinal,r in enumerate(selected):
     par=parameters[r['sid'],r['t'],r['h']];stream,raw,status=col.path(r['sid'],r['t'],r['t']+14400);complete=all(v=='COMPLETE_AUTHENTIC_WINDOW' for v in status.values());tick_statuses.update(status.values());tick_rows.update({side:len(v) for side,v in stream.items()});raw_paths.append({'sid':r['sid'],'t':r['t'],'h':r['h'],'status':status,'pages':raw,'selection_sha256':selected_bind});row=byid[r['sid']];f=cat['full'][str(r['sid'])];own=[z for z in records if (z['sid'],z['t'],z['h'])==(r['sid'],r['t'],r['h'])]
     for rec in own:
      ex=p.tick_exit(r,bars[r['sid']],par,rec['policy'],stream,complete,a.point(quotes.get((r['sid'],r['t']))));rec.update(ex)
      if 'quote' not in ex:continue
      t=ex['exit'];quotes[r['sid'],t]=p.quote_record(r['sid'],t,ex['quote']);curr=a.currencies(row,f);paths=[a.route(c,'EUR',graph) for c in curr]+([a.route(row['quote'],'USD',graph)] if int(f['commissionType'])==1 else []);need(all(path is not None for path in paths),'FROZEN_FX_ROUTE')
      fxids={sid for path in paths for sid,_ in path}
      for sid in sorted(fxids):
       if (sid,t) not in quotes:quotes[sid,t]=col.quote_ms(sid,int(round(t*1000)));new_fx.append(quotes[sid,t])
      values={}
      for scenario,(slip,fund,absolute) in a.SCENARIOS.items():values[scenario]=a.account(r['model_side'],row,f,r['t'],t,(t-r['t'])/3600,quotes,graph,slip,fund,absolute)
      rec['accounts']=values;rec['dynamic_net']=values['S2_F010_DAY']['net_eur'] if values['S2_F010_DAY'] else None
      if rec['dynamic_net'] is None:rec['state']='CAUSAL_TRIGGER_EXIT_FX_OR_COST_NA'
      rec['MFE_reference_eur']=rec.get('MFE_price',0)*par['eur_per_price'];rec['MAE_reference_eur']=rec.get('MAE_price',0)*par['eur_per_price']
     path_reports.append({'sid':r['sid'],'symbol':row['symbol'],'t':r['t'],'h':r['h'],'iso':r['iso'],'status':status,'tick_rows':{n:len(v) for n,v in stream.items()},'complete':complete})
     persist('tick-path-'+str(ordinal+1),{'source_head':head,'selection_sha256':selected_bind,'raw_path':raw_paths[-1],'new_FX_quotes':new_fx,'results':own,'requests':dict(col.counts),'wire_types':dict(col.wire_types)})
     new_fx=[];print(json.dumps({'phase':PHASE,'checkpoint':ordinal+1,'requests':dict(col.counts),'outcomes_public':False}),flush=True)
     e.w.old.budget(maxwall=3500,maxcpu=1500,maxkib=3145728)
   except Exception as exc:
    auth_state='FAIL_CLOSED_'+type(exc).__name__;persist('interrupted',{'failure_class':type(exc).__name__,'phase':PHASE,'requests':dict(col.counts),'raw_paths':raw_paths,'records':records})
   finally:col.close()
  PHASE='NET_ACCOUNTING_AND_STOP_GO';stats={str(h):{name:p.paired_stats(records,h,name) for name in p.POLICIES} for h in (15,60,240)};port={str(h):{name:{str(slots):{'dynamic':p.portfolio(records,h,name,slots),'fixed_same_entries_stress_policy':p.portfolio(records,h,name,slots,False)} for slots in (1,2,4)} for name in p.POLICIES} for h in (15,60,240)}
  scenarios={name:{sc:{'NET_eur':sum(r['accounts'][sc]['net_eur'] for r in records if r['policy']==name and r.get('accounts',{}).get(sc) is not None),'evaluable':sum(r['policy']==name and r.get('accounts',{}).get(sc) is not None for r in records)} for sc in a.SCENARIOS} for name in p.POLICIES}
  geometry={str(h):{name:dict(Counter(r['M5']['state'] for r in records if r['h']==h and r['policy']==name)) for name in p.POLICIES} for h in (15,60,240)}
  # The native reference archive is continuous, but the saved admission signals do not cover its clocks.
  native_support={}
  for sid,z in native['bars'].items():
   times=sorted(int(t) for t in z);weeks=sorted({p.iso(t) for t in times});native_support[sid]={'rows':len(times),'first':times[0] if times else None,'last':times[-1] if times else None,'ISO_weeks_with_rows':weeks}
  saved_weeks=sorted({r['iso'] for r in saved});complete_sampled=full['summary']['weeks'];source_frames=full['summary']['fixed_cohort_frames'];fixed_counts={str(h):{'admitted':sum(r['h']==h for r in saved),'fixed_NET_evaluable':sum(r['h']==h and r.get('fixed_net') is not None for r in records if r['policy']==p.POLICIES[0])} for h in (15,60,240)}
  wk={w:{'saved_admitted':sum(r['iso']==w for r in saved),'tick_tranche':sum(r['iso']==w for r in selected)} for w in complete_sampled}
  # Explicit consecutive-week table includes unsampled weeks as N/A, never zero candidates.
  first=datetime.fromisocalendar(2025,2,1).replace(tzinfo=timezone.utc);last=datetime.fromisocalendar(2026,28,1).replace(tzinfo=timezone.utc);calendar={};dt=first
  while dt<=last:
   w=p.iso(dt.timestamp());calendar[w]={'sampled_first_clock_cohort':w in complete_sampled,'all_continuous_candidate_clocks_known':False,'saved_admitted':wk[w]['saved_admitted'] if w in wk else None,'complete_strategy_NET':None,'HARD21':False};dt+=timedelta(days=7)
  summary={'schema':'mxm.private.dynamic.exit.diagnostic.v1','source_head':head,'design_commit':auth['design_commit'],'base_head':auth['base_head'],'classification':'DEVELOPMENT_PRIOR_ADAPTIVE_EXPOSURE','saved_entries':len(saved),'saved_baseline_entries':len(baseline_saved),'saved_unique_instrument_entry':len({(r['sid'],r['t']) for r in saved}),'saved_instruments':[{'sid':sid,'symbol':byid[sid]['symbol'],'class':byid[sid]['class']} for sid in sorted(needed_ids)],'fixed_entry_counts':fixed_counts,'M5_opened_checkpoints':dict(asset_counts),'M5_rows_loaded_on_saved_entry_instruments':sum(len(z) for z in bars.values()),'M5_segment_statuses':dict(m5_receipt_status),'M5_geometry':geometry,'entry_stress_states':selection_states,'tick_tranche_count':len(selected),'tick_selection_sha256':selected_bind,'tick_path_reports':path_reports,'tick_side_statuses':dict(tick_statuses),'tick_rows':dict(tick_rows),'auth_state':auth_state,'requests':{'H1':col.counts['H1'],'M5':col.counts['M5'],'BID_ASK':col.counts['BID_ASK']},'wire_requests_by_type':dict(col.wire_types),'new_predictive_kernel_calls':0,'closed_kernel_calls':0,'NET_comparisons':stats,'dynamic_sensitivity_totals':scenarios,'portfolio':port,'weekly_saved_support':wk,'consecutive_ISO_UTC_week_audit':calendar,'native_reference_support':native_support,'HARD21':False,'actual_orders':0,'actual_fills':0,'complete_continuous_signal_coverage':False,'missing_and_ambiguity':'NA_NO_FAVORABLE_INTRABAR_ORDER_NO_GUARANTEED_STOP_FILL','historical_costs_and_fills':'UNKNOWN_CURRENT_CONTRACT_SCENARIOS_ONLY','independent_N':'UNIDENTIFIED_PRIOR_ADAPTIVE_AND_SERIAL_CROSS_ASSET_DEPENDENCE','alpha_certified':False,'Cloud':{'changed':False,'package_sha256':'137259adc7d021272d2415f1887d3a5edb2310c0da8e611e3458690fe0d321a3','private_instance_log_access':'NO_AUTHENTICATED_CTRADER_CLOUD_LOG_CAPABILITY_EXPOSED_OR_VERIFIED','OpenAPI_or_GitHub_internal_cBot_log_read':False,'window_utc':['2026-10-12T12:00:00Z','2026-10-12T12:30:00Z']},'source_provenance':provenance,'checkpoint_release_id':checkpoint.release['id'],'checkpoint_assets':cpmeta,'stop_go':'STOP_NO_AUTOMATIC_EXPANSION_TOO_SPARSE_FOR26WEEK_CONFIRMATION_AND_CONTINUOUS_NET_HARD21','verdict':'INSUFICIENT_DATE','source_frames':source_frames,'immutable_old_files_preserved':True}
  full_result={'summary':summary,'records':records,'raw_tick_paths':raw_paths,'frozen_selection':selected,'source_parameters':[{**{'sid':r['sid'],'t':r['t'],'h':r['h']},'value':parameters[r['sid'],r['t'],r['h']]} for r in saved]};PHASE='ENCRYPTED_RESULT';rt.output(head,auth,tmp,key,'dynamicexit',full_result,summary)
  # Owner result keeps individual vectors; the relay contains only authenticated aggregates.
  compact={k:v for k,v in summary.items() if k not in ('checkpoint_assets','source_provenance','portfolio','consecutive_ISO_UTC_week_audit')};compact['source_provenance']=provenance;compact['portfolio']={h:{name:{slots:{which:{k:v for k,v in item.items() if k not in ('selected_by_week','closed_by_exit_week')} for which,item in pair.items()} for slots,pair in ss.items()} for name,ss in pp.items()} for h,pp in port.items()};compact['consecutive_weeks_total']=len(calendar);compact['consecutive_week_unknown_candidates']=len(calendar);relay(head,auth,tmp,compact)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
