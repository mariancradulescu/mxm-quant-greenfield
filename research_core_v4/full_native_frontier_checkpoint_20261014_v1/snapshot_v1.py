"""Read-only economic progress receipt. No broker API, prediction or orders."""
import os,json,pathlib,tempfile,subprocess,collections,statistics,base64
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as r,archive_v1 as ar
P='research_core_v4/full_native_frontier_checkpoint_20261014_v1/'

def stats(values):
 values=sorted(v for v in values if isinstance(v,(int,float)))
 return {'n':len(values),'min':values[0] if values else None,'median':statistics.median(values) if values else None,'max':values[-1] if values else None}

def load_db(store,st,path):
 db=ar.dbopen(path)
 for meta in st['shards'].values():
  obj=store.restore(meta)
  db.executemany('INSERT INTO bar VALUES(?,?,?,?,?,?,?)',obj['bars'])
  db.executemany('INSERT INTO tick VALUES(?,?,?,?)',obj['ticks'])
  db.executemany('INSERT INTO span VALUES(?,?,?,?,?)',obj['spans'])
 db.commit();return db

def coverage(db,eligible):
 saved={s for s, in db.execute("SELECT DISTINCT s FROM span WHERE k IN ('bid','ask')")} & eligible
 sides={s:ks for s,ks in db.execute("SELECT s,count(DISTINCT k) FROM tick GROUP BY s")}
 bilateral={s for s,n in sides.items() if n==2} & eligible
 return {'eligible_saved_page_identities':len(saved),'eligible_bilateral_nonempty_relevant_domain':len(bilateral),'eligible_with_M5_relevant_domain':sum(s in eligible for s, in db.execute('SELECT DISTINCT s FROM bar')),'ticks_relevant_domain':db.execute('SELECT count(*) FROM tick').fetchone()[0],'M5_rows_relevant_domain':db.execute('SELECT count(*) FROM bar').fetchone()[0]},saved,bilateral

def main():
 os.umask(0o077);a=json.loads((r.E.a.ROOT/(P+'EXECUTION_V1.json')).read_text());head=os.environ['GITHUB_SHA']
 r.need(os.environ['GITHUB_REF']=='refs/heads/'+a['observer_branch'] and os.environ['GITHUB_RUN_ATTEMPT']=='1','READBACK_SCOPE')
 r.need(os.environ['GITHUB_WORKFLOW_REF']==r.E.w.old.REPO+'/'+a['workflow']+'@refs/heads/'+a['observer_branch'],'READBACK_WORKFLOW')
 r.need(a['authority']=='EXPLICIT_OWNER_FULL_NATIVE_FRONTIER_AUTONOMOUS_20261014' and a['broker_requests']==0,'READBACK_AUTHORITY')
 r.E.a.ancestor(a['source_head'],head)
 for p,sha in a['bindings'].items():r.need(r.E.w.old.filehash(p)==sha,'READBACK_SOURCE_BINDING')
 original=json.loads((r.E.a.ROOT/(r.P+'EXECUTION_V1.json')).read_text())
 for p,sha in original['bindings'].items():r.need(r.E.w.old.filehash(p)==sha,'FROZEN_CAPTURE_SOURCE')
 claim='mxm-full-frontier-readback-'+os.environ['GITHUB_RUN_ID'];r.need(not r.E.w.v2.existing_ref(claim),'READBACK_ALREADY_CONSUMED');r.E.w.old.api('git/refs',{'ref':'refs/tags/'+claim,'sha':head})
 with tempfile.TemporaryDirectory(prefix='mxm-frontier-readback-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=r.E.w.old._private_key_from_secret(tmp);r.need(fp==r.E.w.old.FP,'OWNER_KEY')
  store=r.FrontierStore(head,key,r.E.a.ROOT/r.E.w.old.PUBLIC_KEY,tmp,'real');store.release=r.E.w.old.api('releases/'+str(a['campaign_release']))
  body=json.loads(store.release['body']);r.need(body.get('source_head')==a['source_head'],'CAPTURE_HEAD')
  r.need('current_journal' in body,'ACTIVE_JOURNAL_REQUIRED');latest_meta=body['current_journal'];current=store.restore(latest_meta);baseline=store.restore(a['baseline_journal']);eligible=set(current['eligible']);r.need(len(eligible)==1562,'FULL_ELIGIBLE_UNIVERSE')
  before=load_db(store,baseline,tmp/'before.sqlite');after=load_db(store,current,tmp/'after.sqlite')
  b,bs,bb=coverage(before,eligible);c,cs,cb=coverage(after,eligible)
  prior_spans=set(before.execute("SELECT s,k,a,b FROM span WHERE k IN ('bid','ask')"));new=[z for z in after.execute("SELECT s,k,a,b,z FROM span WHERE k IN ('bid','ask')") if z[:4] not in prior_spans]
  records={}
  for meta in current.get('record_shards',{}).values():records.update(store.restore(meta)['records'])
  events=[e for rec in records.values() for e in rec.get('events',[])];known=[e for e in events if e['entry'].get('break_even_eur') is not None];paired=[e for e in known if e.get('_native_accounting_context',{}).get('paired_reference')]
  groups={}
  for name,group in [('all',events)]+[('class:'+cl,[e for e in events if e['class']==cl]) for cl in sorted({e['class'] for e in events})]+[('week:'+w,[e for e in events if e['iso']==w]) for w in ('2026-W35','2026-W36','2026-W37')]:
   valid=[e for e in group if e['entry'].get('break_even_eur') is not None]
   groups[name]={'events':len(group),'entry_state_counts':dict(collections.Counter(e['entry']['state'] for e in group)),'strict_entry_exit_bilateral':sum(e['strict_entry']['valid'] and e['strict_exit']['valid'] for e in group),'causal_entry_exit_bilateral':sum(e['quote_state']['valid'] and e['exit_quote_state']['valid'] for e in group),'economic_entry_reference_known':len(valid),'exante_reference_feasible':sum(e['entry'].get('eligible',False) for e in group),'break_even_eur':stats([e['entry']['break_even_eur'] for e in valid]),'break_even_bps':stats([e['entry']['break_even_bps'] for e in valid]),'planned_reference_risk_eur':stats([e['entry']['planned_risk_eur'] for e in valid])}
  qualification=r.qualifying(events)
  summary={'schema':'mxm.full.frontier.readonly.economic.progress.v1','observer_head':head,'capture_head':a['source_head'],'run_id':int(os.environ['GITHUB_RUN_ID']),'campaign_run_id':a['campaign_run'],'campaign_release':a['campaign_release'],'baseline_journal':a['baseline_journal'],'current_journal':latest_meta,'generation':current['generation'],'catalog':5326,'eligible':1562,'identities_completed':current['identity_cursor'],'remaining':1562-current['identity_cursor'],'new_authenticated_requests':current['requests'],'before':b,'after':c,'incremental_eligible_saved_page_identities':len(cs-bs),'incremental_eligible_bilateral_nonempty_identities':len(cb-bb),'new_side_intervals':len(new),'new_side_interval_states':dict(collections.Counter(z[4] for z in new)),'processed_event_support_and_costs':groups,'paired_cost_reference_events':len(paired),'candidate_qualification':qualification,'pilot_executed':current.get('pilot') is not None,'cold_resume_proofs':current['resume_proofs'],'reconciliation_sources':len(current['archive']['asset_receipts']),'archive_limits':dict(collections.Counter(z['state'] for z in current['archive']['asset_receipts'])),'original_report_preserved_sha256':original['original_report_sha256'],'observer_broker_requests':0,'actual_orders':0,'actual_fills':0,'alpha_certified':False,'HARD21':False,'actual_cloud_parity':False,'limitations':['SNAPSHOT_IN_PROGRESS_NOT_FULL_UNIVERSE_COMPLETION','CURRENT_CONTRACT_SCHEDULE_AND_FUNDING_TERMS_NOT_HISTORICAL_ASOF','REFERENCE_COST_AND_GAP_STRESS_NOT_REALIZED_EXECUTION_OR_GUARANTEED_MAXIMUM_LOSS','BILATERAL_NONEMPTY_SAVED_DATA_NOT_COMPLETE_NET_SUPPORT','NO_HISTORICAL_SOURCE_ABSENCE_INFERRED_FROM_UNPARSED_ARCHIVE']}
  private={'summary':summary,'newly_bilateral_eligible_ids':sorted(cb-bb),'newly_saved_eligible_ids':sorted(cs-bs),'new_side_intervals':new,'identity_reason_counts':{s:rec.get('reason_counts',{}) for s,rec in records.items()},'archive':current['archive']}
  release=r.E.w.old.api('releases',{'tag_name':claim+'-result','target_commitish':head,'name':'MXM authenticated incremental economic coverage receipt','prerelease':True,'body':json.dumps({'state':'OWNER_READBACK_PENDING','observer_broker_requests':0})});store.release=release
  primary=r.asset_value(store,private,'incremental-economic-progress-owner.mxmenc');raw=r.encode(summary);signer=serialization.load_pem_private_key(key.read_bytes(),password=None);sig=signer.sign(raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256());signer.public_key().verify(sig,raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
  signed={'summary':summary,'summary_canonical_sha256':r.E.a.sha(raw),'owner_signature_b64':base64.b64encode(sig).decode(),'owner_spki_sha256':fp,'complete_primary':primary,'release_id':release['id']};owner=r.asset_value(store,signed,'incremental-signed-summary-owner.mxmenc');recipient=r.E.upload_extra(release,tmp,r.E.a.ROOT/(r.P+'RECIPIENT_PUBLIC_KEY.pem'),signed,'incremental-recipient-summary.mxmenc')
  safe={k:v for k,v in summary.items() if k not in ('cold_resume_proofs',)};safe.update(state='VERIFIED_INCREMENTAL_SNAPSHOT',release_id=release['id'],primary=primary,signed_owner=owner,recipient=recipient,OWNER_READBACK_SUCCESS=True,DELIVERY_SUCCESS=False)
  r.update_body(store,safe);print(json.dumps(safe,sort_keys=True),flush=True)

if __name__=='__main__':
 try:main()
 except Exception as ex:
  import re
  code=str(ex) if re.fullmatch('[A-Z0-9_]{1,100}',str(ex)) else type(ex).__name__
  print('FAIL_CLOSED_READONLY_FRONTIER_'+code,flush=True);raise SystemExit(1) from None
