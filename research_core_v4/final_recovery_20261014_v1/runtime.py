"""Separate bounded recovery, independent runner verification, and native continuation."""
import os,json,pathlib,tempfile,datetime,subprocess,base64,gzip,copy,re
from collections import Counter
from . import storage as io
from research_core_v4.critical_frontier_repair_20261014_v2 import storage_v2 as old,runner_v2 as runner,archive_v2 as ar
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as v1
E=v1.E;need=v1.need;P='research_core_v4/final_recovery_20261014_v1/'
REPORT_TAG='mxm-final-recovery-20261014-v1'

def gate():
    io.install();os.umask(0o077);a=json.loads((E.a.ROOT/(P+'AUTHORITY_V1.json')).read_text());head=os.environ['GITHUB_SHA']
    need(os.environ['GITHUB_RUN_ATTEMPT']=='1','NO_UNCONTROLLED_RERUN')
    need(os.environ['GITHUB_REPOSITORY']==E.w.old.REPO and os.environ['GITHUB_REF']=='refs/heads/'+E.w.old.BRANCH,'REPOSITORY_SCOPE')
    need(datetime.datetime.now(datetime.timezone.utc).isoformat()<a['expires_utc'],'AUTHORITY_EXPIRED')
    E.a.ancestor(a['base_head'],head)
    for path,digest in a['bindings'].items():need(E.w.old.filehash(path)==digest,'NEW_SOURCE_BINDING')
    for doc in (v1.P+'EXECUTION_V1.json',runner.P+'REPAIR_AUTHORITY_V2.json'):
        for path,digest in json.loads((E.a.ROOT/doc).read_text())['bindings'].items():need(E.w.old.filehash(path)==digest,'ACCEPTED_SOURCE_PRESERVED')
    need(io.api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']==head,'ACTIVE_HEAD_DRIFT')
    for run in (38580426196,38597145118):need(io.api('actions/runs/'+str(run))['status']=='completed','PREVIOUS_WRITER_ACTIVE')
    return head,a

def store_for(head,key,tmp,tag=old.ROOT_TAG):return io.Store(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,tag)

def synthetic_fault_proof(head,key,tmp):
    store=store_for(head,key,tmp,REPORT_TAG+'-synthetic-'+os.environ['GITHUB_RUN_ID']);value={'synthetic':True,'market_rows':0,'fault':'ACK_LOST_AFTER_SERVER_UPLOAD_COMMIT'}
    store.fault_after_upload=True;ref=store.encrypted(value,'lost-ack-proof.mxmenc');again=store.encrypted(value,'lost-ack-proof.mxmenc')
    need(ref==again and store.upload_posts==1,'IDEMPOTENT_UPLOAD_ONE_POST')
    value2={'synthetic':True,'market_rows':0,'rotation':1};store.limit=1;ref2=store.encrypted(value2,'rotation-proof.mxmenc')
    need(ref['release_id']!=ref2['release_id'],'ACTUAL_ROTATION_REQUIRED')
    loc=tmp/'cold-locators.json';loc.write_text(json.dumps([ref,ref2]))
    cmd=['python3','-m','research_core_v4.final_recovery_20261014_v1.runtime','synthetic-cold',str(loc),str(key)]
    need(subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=240).returncode==0,'INDEPENDENT_SYNTHETIC_COLD_READBACK')
    return {'state':'ACTUAL_REMOTE_UPLOAD_ACK_INTERRUPTION_RESOLVED_NO_DUPLICATE','upload_posts':1,'duplicate_posts':0,'synthetic_not_market':True,'actual_rotation_release_ids':[ref['release_id'],ref2['release_id']],'cold_process_readback':True,'refs':[ref,ref2]}

def recover(head,a,key,tmp):
    store=store_for(head,key,tmp);observed=json.loads(store.anchor['body'])
    need(observed['current_journal']['ciphertext_sha256']==a['snapshot']['current_journal']['ciphertext_sha256'],'RECOVERY_SNAPSHOT_CHANGED')
    db=ar.dbopen(tmp/'native.sqlite');old.track(db);st=old.restore(db,store)
    # The original before-quotes manifest is evidence of prepared requests, not dispatch.
    asset=io.api('releases/assets/'+str(a['orphan_asset_id']))
    need(asset['name']==a['orphan_name'] and asset['digest']=='sha256:'+a['orphan_ciphertext_sha256'],'ORPHAN_IDENTITY')
    raw=ar.read_raw(key,E.w.old.FP,tmp,asset,a['orphan_ciphertext_sha256']);uncommitted=E.w.old.crypto.strict_json(raw)
    need(v1.encode(uncommitted)==raw and uncommitted['generation']==691,'ORPHAN_CANONICAL')
    need(uncommitted['requests']==st['requests'],'UNCOMMITTED_REQUEST_COUNTER_DRIFT')
    need(uncommitted['identity_cursor']==st['identity_cursor'],'ORPHAN_CURSOR_DRIFT')
    need(uncommitted.get('ledger_head')==st.get('ledger_head'),'ORPHAN_LEDGER_DRIFT')
    prepared=uncommitted.get('pending_requests',[]);need(len(prepared)==16,'ORPHAN_PENDING_BINDING')
    known={tuple(r[x] for x in ('s','k','a','b')) for r in st.get('uncertain_wire',[])};resolved=0
    for req in prepared:
        z=db.execute('SELECT z FROM wire WHERE s=? AND k=? AND a=? AND b=?',tuple(req[x] for x in ('s','k','a','b'))).fetchone()
        if z and z[0] in ('CONFIRMED_COMPLETE','EMPTY_AUTHENTIC_RESPONSE','PARTIAL_HASMORE','PROVIDER_ERROR'):resolved+=1;continue
        if tuple(req[x] for x in ('s','k','a','b')) not in known:st['uncertain_wire'].append(req)
        ar.span(db,req['s'],req['k'],req['a'],req['b'],'UNCERTAIN_WIRE')
        runner.wire_record(db,req,'PREPARED_NO_DURABLE_DISPATCH_OR_RESPONSE_PROOF',E.a.sha(raw))
    inventory=io.assets(a['snapshot']['storage_release'])
    # Any unreferenced successor raw delta must be resolved before new broker IO.
    suspects=[z for z in inventory if z['name'].startswith('r38580426196-') and re.search(r'(delta|snapshot)-69[1-9]',z['name'])]
    need(not suspects,'UNRECONCILED_SUCCESSOR_RAW_ASSET_NO_NEW_BROKER')
    st['orphan_691_reconciliation']={'asset_id':asset['id'],'ciphertext_sha256':a['orphan_ciphertext_sha256'],'canonical_sha256':E.a.sha(raw),'same_requests':True,'same_cursor':True,'same_ledger':True,'prepared':len(prepared),'durable_responses_resolved':resolved,'fenced_uncertain':len(prepared)-resolved,'successor_raw_asset_candidates':len(suspects),'no_candidate_assumed_committed':True}
    synthetic=synthetic_fault_proof(head,key,tmp);st['storage_idempotency_proof']=synthetic
    st['phase']='CRASH_SAFE_RECOVERY_VERIFIED_AWAITING_COLD_RUNNER';before={'requests':copy.deepcopy(st['requests']),'identity_cursor':st['identity_cursor'],'generation':st['generation']}
    # Only this job owns the anchor; imported pending windows are explicitly fenced.
    io.persist(db,store,st,'orphan-reconciled')
    need(store.restore(json.loads(store.anchor['body'])['current_journal'])['requests']==before['requests'],'AUTHENTIC_RECOVERY_REQUESTS_CHANGED')
    proof={'state':'AUTHENTIC_CHECKPOINT690_691_RECOVERY_AND_ORPHAN_FENCE_PASS','source_head':head,'run_id':int(os.environ['GITHUB_RUN_ID']),'before':before,'after':json.loads(store.anchor['body']),'orphan':st['orphan_691_reconciliation'],'synthetic_proof':synthetic,'broker_requests':0,'historical_upload_cause':'UNIDENTIFIED_OLD_ERROR_DISCARDED_HTTP_EVIDENCE','prior_cold_http_error':'HTTPError_STATUS_NOT_RECORDED','safe_io_errors':io.ERRORS,'OWNER_READBACK_SUCCESS':True,'new_economic_pilot':False}
    report=store_for(head,key,tmp,REPORT_TAG);ref=report.encrypted(json.loads(v1.encode(proof)),'recovery-proof.mxmenc');report.commit({'state':proof['state'],'run_id':proof['run_id'],'source_head':head,'recovered_anchor':proof['after'],'orphan_fenced_count':len(prepared)-resolved,'owner_encrypted_proof':ref,'synthetic_fault_proof':synthetic,'historical_upload_cause':proof['historical_upload_cause'],'broker_requests':0,'OWNER_READBACK_SUCCESS':True})
    print(json.dumps({'recovery_state':proof['state'],'generation':st['generation'],'identities':st['identity_cursor'],'orphan_fenced':len(prepared)-resolved,'broker_requests':0}),flush=True)

def cold(head,a,key,tmp):
    report=store_for(head,key,tmp,REPORT_TAG);proof_body=json.loads(report.anchor['body']);need(proof_body['state']=='AUTHENTIC_CHECKPOINT690_691_RECOVERY_AND_ORPHAN_FENCE_PASS','RECOVERY_PROOF_MISSING')
    store=store_for(head,key,tmp);body=json.loads(store.anchor['body']);need(body['current_journal']==proof_body['recovered_anchor']['current_journal'],'RECOVERY_HEAD_DRIFT')
    db=ar.dbopen(tmp/'cold.sqlite');old.track(db);st=old.restore(db,store)
    need(st['requests']==a['snapshot']['new_requests'] and st['identity_cursor']==61,'COLD_NATIVE_STATE_DRIFT')
    summary={'state':'INDEPENDENT_RUNNER_AUTHENTIC_COLD_RESUME_PASS','source_head':head,'run_id':int(os.environ['GITHUB_RUN_ID']),'generation':st['generation'],'bars':db.execute('SELECT count(*) FROM bar').fetchone()[0],'ticks':db.execute('SELECT count(*) FROM tick').fetchone()[0],'wire':db.execute('SELECT count(*) FROM wire').fetchone()[0],'coverage_states':ar.proof_table(db),'orphan_fence':st['orphan_691_reconciliation'],'requests':st['requests'],'broker_requests':0,'OWNER_READBACK_SUCCESS':True,'resume_from':body['current_journal']}
    ref=report.encrypted(json.loads(v1.encode(summary)),'authentic-cold-resume.mxmenc');report.commit({**proof_body,'state':summary['state'],'cold_proof':ref,'cold_summary':{k:summary[k] for k in ('generation','bars','ticks','wire','requests','coverage_states','broker_requests')}});print(json.dumps(summary),flush=True)

def coverage(head,a,key,tmp):
    body=json.loads(io.api('releases/tags/'+REPORT_TAG)['body']);need(body['state']=='INDEPENDENT_RUNNER_AUTHENTIC_COLD_RESUME_PASS','NO_COLD_PROOF_NO_BROKER')
    # Preserve original scientific design and resource caps. Only storage is replaced.
    runner.gate=lambda:(head,{**json.loads((E.a.ROOT/(v1.P+'EXECUTION_V1.json')).read_text()),**json.loads((E.a.ROOT/(runner.P+'REPAIR_AUTHORITY_V2.json')).read_text())})
    runner.DiagnosticRotatingStore=io.StoreAdapter
    runner.storage.persist=io.persist
    runner.configure()
    # No economic pilot or HEAD mutation inside the collection campaign.
    v1.pilot=lambda *args:None
    runner.main()

def main():
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='synthetic-cold':
        io.install()
        with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as td:
            store=v1.FrontierStore(os.environ['GITHUB_SHA'],pathlib.Path(sys.argv[3]),E.a.ROOT/E.w.old.PUBLIC_KEY,pathlib.Path(td),'real')
            for ref in json.loads(pathlib.Path(sys.argv[2]).read_text()):need(store.restore(ref)['synthetic'] is True,'SYNTHETIC_COLD_VALUE')
        return
    head,a=gate()
    with tempfile.TemporaryDirectory(prefix='mxm-final-recovery-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,'OWNER_KEY')
        {'recover':recover,'cold':cold,'coverage':coverage}[sys.argv[1]](head,a,key,tmp)
if __name__=='__main__':
    try:main()
    except Exception as ex:
        io.evidence(ex,'FINAL_RECOVERY_STOP');print('FAIL_CLOSED_FINAL_RECOVERY_'+(str(ex) if re.fullmatch('[A-Z0-9_]{1,120}',str(ex)) else type(ex).__name__),flush=True);raise SystemExit(1) from None
