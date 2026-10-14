"""Recover existing cause evidence and correct saved economic subset reporting."""
import os,json,pathlib,tempfile,datetime,base64,hashlib,re
from collections import Counter
from research_core_v4.final_recovery_20261014_v1 import storage as io
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as old
from research_core_v4.critical_frontier_repair_20261014_v2 import storage_v2 as snap,archive_v2 as ar
from research_core_v4.economic_process_reset_20261014_v1.frontier import distribution
E=old.E;P='research_core_v4/root_cause_economic_20261014_v1/';TAG='mxm-root-cause-economic-20261014-v1'
def main():
 io.install();os.umask(0o077);head=os.environ['GITHUB_SHA'];a=json.loads((E.a.ROOT/(P+'AUTHORITY_V1.json')).read_text());old.need(os.environ['GITHUB_REF']=='refs/heads/'+a['branch'] and os.environ['GITHUB_RUN_ATTEMPT']=='1','EXECUTION_SCOPE');E.a.ancestor(a['base'],head)
 old.need(datetime.datetime.now(datetime.timezone.utc).isoformat()<a['expires'],'EXPIRED')
 for p,h in a['bindings'].items():old.need(E.w.old.filehash(p)==h,'SOURCE_BINDING')
 with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);source=old.FrontierStore(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,'real');source.anchor={'body':json.dumps(a['snapshot'])}
  journal=source.restore(a['snapshot']['current_journal']);delta=source.restore(a['snapshot']['ledger_head'])
  cause={'last_checkpoint_generation':journal['generation'],'last_run':journal['last_run'],'last_delta':a['snapshot']['ledger_head'],'raw_records':delta.get('raw',[]),'journal_errors':journal.get('errors',[]),'pending_requests':journal.get('pending_requests',[]),'uncertain_wire':journal.get('uncertain_wire',[]),'recorded_exception_classes':dict(Counter(r.get('exception_class','NO_EXCEPTION') for r in delta.get('raw',[]))),'raw_preserved':True,'physical_cause_not_invented':True}
  accepted=source.restore(a['accepted_primary']);summary=accepted['summary'];events=[]
  for z in accepted['economic_reference_shards']:
   part=source.restore(z['asset']);old.need(part['start']==len(events) and len(part['economic_references'])==z['count'],'EXISTING_REFERENCE_ORDER');events.extend(part['economic_references'])
  old.need(len(events)==accepted['economic_reference_count'],'EXISTING_REFERENCE_COUNT')
  corrected={}
  for name,previous in summary['cases'].items():
   mode,h,slip=name.split('_');h=int(h[1:]);slip=slip[1:];cohort=[e for e in events if e['mode']==mode and e['h']==h]
   subsets={'all_cost_observable':cohort,'entry_feasible':[e for e in cohort if e['scenarios'][slip]['feasible']],'entry_feasible_exit_observed':[e for e in cohort if e['scenarios'][slip]['feasible'] and e['endpoint_cost_support']],'entry_feasible_path_complete':[e for e in cohort if e['scenarios'][slip]['feasible'] and e['continuous_bilateral_path_support']]}
   old.need(len(cohort)==previous['cohort'],'ACCEPTED_COHORT')
   corrected[name]={k:{'n':len(v),'identities':len(set(e['sid'] for e in v)),'dates':len(set(e['t']//86400 for e in v)),'weeks':dict(Counter(e['iso'] for e in v)),'cost_eur':distribution([e['scenarios'][slip]['cost_eur'] for e in v]),'break_even_bps':distribution([e['scenarios'][slip]['break_even_bps'] for e in v]),'risk_eur':distribution([e['scenarios'][slip]['risk_eur'] for e in v]),'margin_eur':distribution([e['margin_eur_current'] for e in v])} for k,v in subsets.items()}
  db=ar.dbopen(tmp/'native.sqlite');snap.track(db);st=snap.restore(db,source)
  info={'catalog':len(st['rows']),'structural_eligible':len(st['eligible']),'processed_collection_cursor':st['identity_cursor'],'native_M5_rows':db.execute('SELECT count(*) FROM bar').fetchone()[0],'native_M5_identities':db.execute('SELECT count(DISTINCT s) FROM bar').fetchone()[0],'native_quote_side_rows':db.execute('SELECT count(*) FROM tick').fetchone()[0],'native_quote_identities':db.execute('SELECT count(DISTINCT s) FROM tick').fetchone()[0],'native_tick_volume_rows':db.execute('SELECT count(*) FROM bar WHERE v>0').fetchone()[0],'database_tables':[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")],'accepted_manifest_states':dict(Counter(x['state'] for x in accepted['all5326_status_manifest'])),'eligible_with_cost_entry':sum(x['accepted_structural_eligible'] and x['state']=='ENTRY_ECONOMIC_FIELDS_OBSERVED' for x in accepted['all5326_status_manifest']),'missing_information_scope':'THIS_BOUND_SNAPSHOT_NOT_CLAIM_ABOUT_UNINSPECTED_CORPORA','prices_BBO_M5_activity_current_contract_available':True}
  result={'schema':'mxm.root.cause.and.corrected.subsets.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_head':head,'snapshot':a['snapshot'],'cause':cause,'information_inventory':info,'corrected_cost_populations':corrected,'accepted_result_reused_without_signal_replay':a['accepted_primary'],'new_directional_outcomes':0,'broker_requests':0,'orders':0,'protected_forward':False,'HARD21':False,'alpha_certified':False,'collection_write':False,'qualification_routing':'QUALIFIED_WRITES_READY_FOR_FROZEN_PILOT;UNQUALIFIED_WRITES_SPECIFIC_SUPPORT_STOP;NEITHER_IS_AN_ASSERTION_FAILURE','status':'EXISTING_CAUSE_RECOVERED_COST_POPULATIONS_CORRECTED'}
  out=io.Store(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,TAG);ref=out.encrypted(result,'cause-and-cost-populations-owner.mxmenc');relay=E.upload_extra(out.release,tmp,E.a.ROOT/'research_core_v4/final_recovery_20261014_v1/RECIPIENT_PUBLIC_KEY.pem',result,'cause-cost-session.mxmenc');relay['release_id']=out.release['id']
  safe={'state':result['status'],'run_id':result['run_id'],'source_head':head,'primary':ref,'recipient':relay,'OWNER_READBACK_SUCCESS':True,'recorded_exception_classes':cause['recorded_exception_classes'],'inventory_counts':{k:info[k] for k in ('catalog','structural_eligible','native_M5_rows','native_M5_identities','native_quote_side_rows','native_quote_identities','eligible_with_cost_entry')},'new_directional_outcomes':0,'broker_requests':0,'collection_write':False,'orders':0};out.commit(safe);print(json.dumps(safe,sort_keys=True),flush=True)
if __name__=='__main__':
 try:main()
 except Exception as ex:
  import traceback
  print(json.dumps({'safe_trace':[(pathlib.Path(x.filename).name,x.lineno,x.name) for x in traceback.extract_tb(ex.__traceback__)]}),flush=True);io.evidence(ex,'OWNER_CAUSE_RECOVERY');raise SystemExit(1) from None
