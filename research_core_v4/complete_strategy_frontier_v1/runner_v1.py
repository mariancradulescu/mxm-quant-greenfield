"""Frozen full paired strategy, existing-source reconciliation then bounded read-only data."""
import json,os,pathlib,tempfile,subprocess
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as a
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import decode_ctrader_tick_page
from .collector_v1 import Collector
from . import strategy_v1 as k
e=rt.e;P='research_core_v4/complete_strategy_frontier_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def main():
 global PHASE
 os.umask(0o077);head=os.environ['GITHUB_SHA'];auth=json.loads((e.a.ROOT/(P+'STRATEGY_EXECUTION_V1.json')).read_text());e.w.v2.runtime(head);need(auth['authority']=='EXPLICIT_OWNER_COMPLETE_STRATEGY_FRONTIER_20261012','OWNER_SCOPE');need(not any(auth[n] for n in ('orders','protected_forward','closed_kernel_replay','Cloud_changes','authentication_changes')),'SCOPE');need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-complete-strategy-frontier-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW');need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'EXPIRED')
 for p,h in auth['bindings'].items():need(e.w.old.filehash(p)==h,'SOURCE_BINDING')
 e.a.ancestor(auth['base_head'],head);e.a.ancestor(auth['design_commit'],head);old=subprocess.check_output(['git','ls-tree','-r',auth['base_head']],cwd=e.a.ROOT,text=True).splitlines();new=set(subprocess.check_output(['git','ls-tree','-r',head],cwd=e.a.ROOT,text=True).splitlines());need(all(v in new for v in old),'OLD_FILES_PRESERVED');e.w.old.verify_science();need(not e.w.v2.existing_ref(auth['one_use_ref']),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':head})
 with tempfile.TemporaryDirectory(prefix='mxm-complete-strategy-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'EXISTING_OWNER_KEY');PHASE='EXISTING_AUTHENTIC_SOURCE_RECONCILIATION';full,proof=load_asset(key,fp,tmp,auth['cost_frequency_source']);cat=full['catalog'];rows={r['sid']:r for r in full['all_identity_status']};graph=a.graph(list(rows.values()));quotes={(int(q['symbol_id']),int(q['boundary_ms'])/1000):q for q in full['raw_quote_receipts']};provenance=[proof];oldquote_counts={'cost_frequency':len(quotes)}
  feasibility,feasproof=load_asset(key,fp,tmp,auth['stage_A_source']);provenance.append(feasproof);need(feasibility['summary']['source_head']==auth['stage_A_head'],'STAGE_A_HEAD');need(all(feasibility['summary']['pair_economics'][name]['go'] for name in ('ETHAUD_ETHEUR','ETHGBP_ETHEUR')),'ECONOMIC_INFORMATIONAL_GATE')
  for name,binding,field in [('wide_completed',auth['wide_completed_source'],'completed_frozen_quotes'),('fullcost',auth['fullcost_source'],'private_boundary_receipts')]:
   source,pr=load_asset(key,fp,tmp,binding);need(field in source,'EXISTING_QUOTE_SCHEMA');provenance.append(pr);oldquote_counts[name]=len(source[field])
   for q in source[field]:quotes.setdefault((int(q['symbol_id']),int(q['boundary_ms'])/1000),q)
  native_light={int(v['symbolId']):v for v in cat['light']};warm=defaultdict(dict)
  for A,B in k.PAIRS:
   need(native_light[A]['baseAssetId']==native_light[B]['baseAssetId'] and str(native_light[A]['baseAssetId'])=='206','NATIVE_SHARED_BASE_IDENTITY')
   for sid in (A,B):
    f=cat['full'][str(sid)];need(rows[sid]['research_contract_eligible'] and int(f['minVolume'])<=1<=int(f['maxVolume']) and 1%int(f['stepVolume'])==0,'MATCHED_BASE_UNIT_LATTICE');need(k.needed(rows[sid],f,graph) is not None and k.needed(rows[sid],f,graph)<=set(k.IDS),'FROZEN_FX_ROUTE_SUPPORT')
  for binding in auth['M5_sources']:
   hist,pr=load_asset(key,fp,tmp,binding);provenance.append(pr)
   for seg in hist['M5_segments']:
    sid=int(seg['sid'])
    if sid in (2742,2744,2746):
     for t,z in seg.get('bars',{}).items():
      t=int(t);need(t not in warm[sid] or warm[sid][t]==z,'AUTHENTIC_M5_CONFLICT');warm[sid][t]=z
  # Prior complete tick paths are examined only for overlap, not for their old outcomes.
  existing_paths,pr=load_asset(key,fp,tmp,auth['old_tick_paths_source']);provenance.append(pr);raw_prior=existing_paths['raw_tick_paths'];dates=[int(datetime.fromisocalendar(2026,w,d).replace(tzinfo=timezone.utc,hour=8).timestamp()) for w in (12,13) for d in range(1,6)];prior_windows=0
  for path in raw_prior:
   sid=int(path['sid'])
   if sid not in k.IDS:continue
   for page in path['pages']:
    if 'encoded' not in page or page.get('hasMore') is not False:continue
    lo=page['from_ms'];hi=page['to_ms']
    if not any(lo<=(start+2100)*1000 and hi>=start*1000-60000 for start in dates):continue
    prior_windows+=1
    # Valid prior full intervals become a page in the existing quote index; same raw codec.
    q={'symbol_id':sid,'boundary_ms':hi,'sides':{},'pages':[{'side':page['side'],'encoded':page['encoded'],'hasMore':False,'request_from_ms':lo,'request_to_ms':hi}]};quotes.setdefault((sid,hi/1000),q)
  store=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');store.release=e.w.old.api('releases',{'tag_name':'mxm-complete-strategy-data-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted prospective paired strategy data','prerelease':True,'body':'Prospectively frozen historical native data. No public prices, outcomes, orders, protected forward or Cloud changes.'});receipts=[]
  def persist(name,value):receipts.append(store.encrypted(e.w.old.crypto.strict_json(e.a.enc(value)),name+'.mxmenc'))
  cohort_sha=e.a.sha(e.a.enc({'dates':dates,'pairs':k.PAIRS,'ids':k.IDS,'cadence':5,'strategy_design_sha256':auth['bindings'][P+'STRATEGY_DESIGN_V1.json']}));persist('prospective-source-reconciliation',{'source_head':head,'cohort_sha256':cohort_sha,'input_provenance':provenance,'existing_quote_counts':oldquote_counts,'existing_full_tick_paths_overlap_pages':prior_windows,'all_old_exact_outcomes_ignored':True,'new_requests':0});col=Collector();days=[];warmup_reused=0;warmup_new=0;auth_state='NOT_ATTEMPTED';PHASE='FROZEN_DATA_ACQUISITION_BEFORE_STRATEGY_OUTCOMES'
  try:
   col.connect();need(col.aid==int(cat['trader']['ctidTraderAccountId']),'SAME_AUTHENTIC_ACCOUNT');auth_state='PASS_EXISTING_EXPLICIT_VIEW_NATIVE_ACCOUNT'
   for ordinal,start in enumerate(dates):
    need(start+2100<int(datetime(2026,9,17,tzinfo=timezone.utc).timestamp()),'PROTECTED_FORWARD_BOUNDARY');ATRs={};warm_receipts=[]
    for sid in (2742,2744,2746):
     prior=list(range(start-4500,start,300));selected={t:warm[sid][t] for t in prior if t in warm[sid]};status='REUSED_AUTHENTIC_NATIVE_M5' if len(selected)==15 else None
     if status:warmup_reused+=1
     elif col.counts['M5']<12:
      data,raw,status=col.m5(sid,int(cat['full'][str(sid)]['digits']),start-4500,start);warmup_new+=1;warm_receipts.append({'sid':sid,'raw':raw,'status':status,'bars':data});selected={t:data[t] for t in prior if t in data}
     else:status='LOCAL_M5_CAP'
     ATRs[sid]=k.atr15(selected,start) if status in ('REUSED_AUTHENTIC_NATIVE_M5','COMPLETE_EXACT_WINDOW') else None
    streams={};raw_profiles=[];status_all={};reuse={}
    for sid in k.IDS:
     stream,raw,status,audit=col.path(sid,start,start+2100,quotes);streams[sid]=stream;raw_profiles.append({'sid':sid,'raw_pages':raw,'status':status,'reuse':audit});status_all.update({str(sid)+'_'+side:v for side,v in status.items()});reuse[sid]=audit
    day={'start':start,'streams':streams,'status':status_all,'ATRs':ATRs,'warmup_receipts':warm_receipts,'raw_profiles':raw_profiles,'reuse_audit':reuse};days.append(day);persist('session-'+str(ordinal+1),{'schema':'mxm.private.complete.strategy.day.data.v1','source_head':head,'cohort_sha256':cohort_sha,**day,'requests':dict(col.counts),'wire_types':dict(col.wire_types),'no_strategy_outcomes_read':True});print(json.dumps({'phase':PHASE,'checkpoint':ordinal+1,'requests':dict(col.counts),'outcomes_public':False}),flush=True);e.w.old.budget(maxwall=4500,maxcpu=1800,maxkib=3145728)
  finally:col.close()
  PHASE='NEW_COMPLETE_STRATEGY_NUMERIC_EXECUTION';result,summary=k.evaluate(days,rows,cat,graph);summary.update(source_head=head,design_commit=auth['design_commit'],classification='DEVELOPMENT_PRIOR_ADAPTIVE_NO_INDEPENDENT_CONFIRMATION',cohort_sha256=cohort_sha,input_provenance=provenance,requests={'H1':col.counts['H1'],'M5':col.counts['M5'],'BID_ASK':col.counts['BID_ASK']},wire_requests_by_type=dict(col.wire_types),auth_state=auth_state,warmup_reused=warmup_reused,warmup_new_target_segments=warmup_new,checkpoint_release_id=store.release['id'],checkpoint_assets=receipts,trace_sessions=len(days),complete_tick_sessions=sum(all(v=='COMPLETE_AUTHENTIC_WINDOW' for v in day['status'].values()) for day in days),tick_rows={side:sum(len(rows[side]) for day in days for rows in day['streams'].values()) for side in ('bid','ask')},native_M5_prior_rows_used=sum(15 for day in days for v in day['ATRs'].values() if v is not None),existing_quote_counts=oldquote_counts,old_tick_overlap_pages=prior_windows,closed_predictive_or_exit_kernel_calls=0,mechanism_count=1,Cloud_changes=False,Cloud_package_sha256='137259adc7d021272d2415f1887d3a5edb2310c0da8e611e3458690fe0d321a3',all_previous_files_preserved=True)
  result.update(data_days=days,summary=summary);PHASE='ENCRYPTED_NUMERIC_RESULT';rt.output(head,auth,tmp,key,'completestrategy',result,summary);compact={n:v for n,v in summary.items() if n not in ('checkpoint_assets',)};relay(head,auth,tmp,compact)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
