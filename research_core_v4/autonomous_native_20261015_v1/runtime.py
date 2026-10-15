"""Finite generation-fenced workers. No broker retries; independent encrypted readers."""
import os,json,time,datetime,tempfile,pathlib,copy,re,base64,urllib.error
from collections import Counter
from research_core_v4.root_cause_economic_20261014_v1.continuation_1307 import BoundStore,exception_category
from research_core_v4.root_cause_economic_20261014_v1.evidence import E,old,io,snap,ar
from research_core_v4.critical_frontier_repair_20261014_v2 import runner_v2 as runner
from research_core_v4.cost_frequency_discovery_v1.collector_v1 import Collector
P='research_core_v4/autonomous_native_20261015_v1/'
WF='mxm-autonomous-native-20261015-v1.yml'
from research_core_v4.remediation_p0_p4_20261015.safety import terminal, bind_failure, request_identity
from research_core_v4.remediation_p0_p4_20261015.science import qualifying
need=old.need
class BatchComplete(Exception):pass

def gate():
    raise RuntimeError('EXPECTED_POLICY_STOP_REMEDIATION_NO_CAMPAIGN')
    io.install();os.umask(0o077)
    a=json.loads((E.a.ROOT/(P+'AUTHORITY.json')).read_text())
    need(os.environ['GITHUB_REF_NAME']==a['branch'] and os.environ['GITHUB_RUN_ATTEMPT']=='1','EXECUTION_SCOPE')
    need(datetime.datetime.now(datetime.timezone.utc).isoformat()<a['expires'],'AUTHORITY_EXPIRED')
    E.a.ancestor(a['prior_head'],os.environ['GITHUB_SHA'])
    for source in (old.P+'EXECUTION_V1.json',runner.P+'REPAIR_AUTHORITY_V2.json',P+'AUTHORITY.json'):
        for p,h in json.loads((E.a.ROOT/source).read_text())['bindings'].items():need(E.w.old.filehash(p)==h,'SOURCE_BINDING')
    need(io.api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']==a['base'],'CANONICAL_HEAD_DRIFT')
    need(io.api('git/ref/heads/'+a['branch'])['object']['sha']==os.environ['GITHUB_SHA'],'EXECUTION_HEAD_DRIFT')
    return a

def exclusive():
    for status in ('in_progress','queued','waiting','pending','requested'):
        page=1
        while True:
            runs=io.api('actions/runs?status='+status+'&per_page=100&page='+str(page))['workflow_runs']
            other=[r for r in runs if r['id']!=int(os.environ['GITHUB_RUN_ID']) and any(t in r['path'] for t in ('native-frontier','final-recovery','root-cause-resume','native-resume','autonomous-native'))]
            need(not other,'OTHER_COLLECTION_RUN_PRESENT')
            if len(runs)<100:break
            page+=1

def claim(name):
    # A consumed intent is never rearmed. Resolve lost create ACK by GET only.
    try:io.api('git/refs','POST',{'ref':'refs/tags/'+name,'sha':os.environ['GITHUB_SHA']})
    except Exception:
        try:observed=io.api('git/ref/tags/'+name)
        except Exception:raise RuntimeError('CLAIM_UNKNOWN_NO_RETRY') from None
        need(observed['object']['sha']==os.environ['GITHUB_SHA'],'CLAIM_CONFLICT')
        raise RuntimeError('STALLED_INTENT_STOP') from None
    need(io.api('git/ref/tags/'+name)['object']['sha']==os.environ['GITHUB_SHA'],'CLAIM_READBACK')

def dispatch(a,generation,sequence):
    token='mxm-auto-20261015-g'+str(generation)+'-s'+str(sequence)
    claim(token)
    ack='ACK_RECEIVED'
    try:io.api('actions/workflows/'+WF+'/dispatches','POST',{'ref':a['branch'],'inputs':{'generation':str(generation),'sequence':str(sequence),'claim':token}})
    except Exception:ack='DISPATCH_UNKNOWN'
    title='MXM autonomous g'+str(generation)+' s'+str(sequence)
    for attempt in range(12):
        matches=[];page=1
        while True:
            runs=io.api('actions/runs?branch='+a['branch']+'&event=workflow_dispatch&per_page=100&page='+str(page))['workflow_runs']
            matches.extend(r for r in runs if r['head_sha']==os.environ['GITHUB_SHA'] and r['display_title']==title)
            if len(runs)<100:break
            page+=1
            need(page<=100,'RUN_PAGINATION_LIMIT_UNKNOWN')
        matches=list({r['id']:r for r in matches}.values())
        if matches:
            need(len(matches)==1,'DISPATCH_DUPLICATE_RUNS')
            return {'state':'SUCCESSOR_RUN_OBSERVED','successor_run':matches[0]['id'],'generation':generation,'sequence':sequence,'claim':token,'ack':ack,'source_head':os.environ['GITHUB_SHA']}
        time.sleep(3)
    raise RuntimeError('STALLED_INTENT_STOP_DISPATCH_UNKNOWN')

class EvidenceCollector(Collector):
    def __init__(self,caps,guard):super().__init__(caps);self.guard=guard;self.last_evidence=None
    def send(self,req,historical=False):
        self.last_evidence=None
        self.guard()
        self.last_evidence={'request_type':type(req).__name__}
        try:
            result=super().send(req,historical)
            self.last_evidence.update(response_type=type(result).__name__,response_b64=base64.b64encode(result.SerializeToString()).decode())
            env=getattr(self.tr,'last_history_envelope',None)
            if type(req).__name__=='ProtoOAGetTrendbarsReq' and env is not None:self.last_evidence['response_envelope_b64']=base64.b64encode(env.SerializeToString()).decode()
            return result
        except Exception as ex:
            self.last_evidence.update(exception_class=type(ex).__name__,exception_category=exception_category(ex));raise

def remaining(st,a):
    reserve=Counter('M5' if q['k']=='M5' else 'BID_ASK' for q in st.get('uncertain_wire',[]))
    return {k:a['caps'][k]-st['requests'][k]-reserve[k] for k in a['caps']}

def support(db,st):
    events=[e for r in st['identity_records'].values() for e in r.get('events',[])]
    feasible=[e for e in events if e['entry'].get('eligible')]
    paired=[e for e in feasible if e.get('_native_accounting_context',{}).get('paired_reference')]
    continuous=[e for e in paired if all(not ar.missing(db,s,k,e['t']*1000,(e['t']+900)*1000) for s in e['_native_accounting_context']['quote_ids'] for k in ('bid','ask'))]
    def pop(es):return {'events':len(es),'identities':len({e['sid'] for e in es}),'dates':len({e['date'] for e in es}),'weeks':dict(Counter(e['iso'] for e in es))}
    return {'processed_identities':st['identity_cursor'],'M5_rows':db.execute('SELECT count(*) FROM bar').fetchone()[0],'M5_identities':db.execute('SELECT count(DISTINCT s) FROM bar').fetchone()[0],'quote_rows':db.execute('SELECT count(*) FROM tick').fetchone()[0],'quote_identities':db.execute('SELECT count(DISTINCT s) FROM tick').fetchone()[0],'all_events':pop(events),'entry_feasible':pop(feasible),'paired_endpoints':pop(paired),'continuous_paths':pop(continuous),'existing_frozen_candidate':qualifying(events),'outcomes_read':False}

def orphans(store,generation):
    # Scan every rotated shard, including a successor shard after a lost anchor ACK.
    for index in range(store.index+2):
        try:rel=io.api('releases/tags/'+snap.ROOT_TAG+'-shard-'+str(index))
        except urllib.error.HTTPError as ex:
            if ex.code==404 and index==store.index+1:continue
            raise
        for asset in io.assets(rel['id']):
            m=re.match(r'(?:manifest|delta)-(\d+)-',asset['name'])
            need(not m or int(m.group(1))<=generation,'UNRECONCILED_ORPHAN_NO_REQUEST')

def worker(a):
    exclusive();generation=int(os.environ['EXPECTED_GENERATION']);seq=int(os.environ['SEGMENT_SEQUENCE'])
    token='mxm-auto-20261015-g'+str(generation)+'-s'+str(seq)
    need(os.environ['DISPATCH_CLAIM']==token,'INPUT_CLAIM')
    need(io.api('git/ref/tags/'+token)['object']['sha']==os.environ['GITHUB_SHA'],'DISPATCH_CLAIM_BINDING')
    claim(token+'-consumed')
    need(1<=seq<=a['max_segments'],'FINITE_SEGMENT_COUNT')
    with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,'OWNER_KEY')
        store=BoundStore(os.environ['GITHUB_SHA'],key,tmp,a['base']);body=json.loads(store.anchor['body'])
        need(body['generation']==generation and body['pending_request_count']==0,'CHECKPOINT_GENERATION_OR_PENDING')
        need(body['run_id']!=int(os.environ['GITHUB_RUN_ID']),'SAME_RUN_CHECKPOINT')
        if seq==1:need(body['current_journal']==a['snapshot']['current_journal'],'INITIAL_SNAPSHOT_BINDING')
        else:need(body['state']=='BATCH_COMPLETE_READY_FOR_HANDOFF','PREDECESSOR_NOT_READY')
        orphans(store,generation)
        db=ar.dbopen(tmp/'native.sqlite');snap.track(db);st=snap.restore(db,store)
        need(st['generation']==generation and not st['pending_requests'],'COLD_STATE')
        if seq>1:need(st['autonomy']['sequence']==seq-1 and st['autonomy']['source_head']==os.environ['GITHUB_SHA'],'PREDECESSOR_SEQUENCE')
        before=support(db,st);before_req=copy.deepcopy(st['requests']);wire=db.execute('SELECT * FROM wire ORDER BY s,k,a,b').fetchall()
        need(len(st['resume_proofs'])<=a['max_total_cold_resumes'],'ORIGINAL_FINITE_WORKER_LIMIT')
        budget=remaining(st,a);need(all(v>0 for v in budget.values()),'GLOBAL_BUDGET_EXHAUSTED')
        st['campaign_tick_cap']=a['caps']['BID_ASK']-(a['caps']['BID_ASK']-st['requests']['BID_ASK']-budget['BID_ASK'])
        st['campaign_m5_cap']=a['caps']['M5']-(a['caps']['M5']-st['requests']['M5']-budget['M5'])
        deadline=time.monotonic()+a['worker_seconds'];runner.configure();runner.storage.persist=io.persist;old.persist=io.persist
        def valid():
            need(datetime.datetime.now(datetime.timezone.utc).isoformat()<a['expires'],'AUTHORITY_EXPIRED')
        def boundary():
            valid()
            if time.monotonic()>=deadline or sum(col.counts.values())>=a['worker_requests']:raise BatchComplete()
        col=EvidenceCollector({k:min(budget[k],a['worker_requests']) for k in budget},valid)
        raw_ops=runner.quote_ops;raw_check=runner.check_new_request
        def ops(db,keys):
            boundary();left=min(a['worker_requests']-sum(col.counts.values()),remaining(st,a)['BID_ASK'])
            need(left>0,'GLOBAL_BID_ASK_CAP');return raw_ops(db,keys)[:left]
        def check(db,req):
            boundary();need(remaining(st,a)['M5' if req['k']=='M5' else 'BID_ASK']>0,'GLOBAL_BUDGET_EXHAUSTED');return raw_check(db,req)
        runner.quote_ops=ops;runner.check_new_request=check
        base_persist=io.persist
        def persist(db,store,st,label,groups=()):
            for item in st.get('_raw',[]):
                if item.get('exception_class'):item['preserved_failure_evidence']=bind_failure(item,col.last_evidence or {})
            return base_persist(db,store,st,label,groups)
        runner.storage.persist=persist;old.persist=persist
        cfg={**json.loads((E.a.ROOT/(old.P+'EXECUTION_V1.json')).read_text()),**json.loads((E.a.ROOT/(runner.P+'REPAIR_AUTHORITY_V2.json')).read_text())}
        st['autonomy']={'sequence':seq,'source_head':os.environ['GITHUB_SHA'],'from_generation':generation,'claim':token};st['phase']='RUNNING_FINITE_AUTONOMOUS_BATCH';failed=None
        try:
            col.connect();need(col.aid==int(st['catalog']['trader']['ctidTraderAccountId']),'SAME_ACCOUNT')
            while st['identity_cursor']<len(st['eligible']):
                boundary();sid=st['eligible'][st['identity_cursor']]
                if not old.process_identity(db,sid,st,col,store,cfg,deadline):break
                st['identity_cursor']+=1;st.setdefault('_record_dirty_ids',set()).add(sid);persist(db,store,st,'autonomous-identity')
        except BatchComplete:pass
        except Exception as ex:
            failed={'exception_class':type(ex).__name__,'category':exception_category(ex)}
            st['errors'].append({'run':int(os.environ['GITHUB_RUN_ID']),'cause':'STOP_FAIL_CLOSED','evidence':failed})
        finally:col.close()
        unchanged=all(db.execute('SELECT * FROM wire WHERE s=? AND k=? AND a=? AND b=?',r[:4]).fetchone()==r for r in wire)
        need(unchanged,'PRIOR_ACCEPTED_WIRE_CHANGED');need(sum(col.counts.values())<=a['worker_requests'],'WORKER_CAP')
        progress=st['identity_cursor']>before['processed_identities'] or sum(st['requests'].values())>sum(before_req.values())
        st['phase']='STOP_FAIL_CLOSED' if failed else 'COLLECTION_COMPLETE' if st['identity_cursor']==len(st['eligible']) else 'STOP_NO_PROGRESS' if not progress else 'STOP_FINITE_CAMPAIGN_LIMIT' if seq>=a['max_segments'] or len(st['resume_proofs'])>=a['max_total_cold_resumes'] else 'BATCH_COMPLETE_READY_FOR_HANDOFF'
        stop=terminal(failed,remaining(st,a),st['phase']);st['phase']=stop['state'];st['terminal_causes']=stop['causes']
        st['autonomy_proof']={'prior_wire_unchanged':unchanged,'before_requests':before_req,'after_requests':copy.deepcopy(st['requests']),'new_requests':dict(col.counts),'failure':failed,'cold_restore_before_requests':True,'single_writer_claim':token+'-consumed','support_before':before,'support_after':support(db,st),'remaining_broker_budget':remaining(st,a)}
        persist(db,store,st,'autonomous-worker-end')
        current=json.loads(store.anchor['body']);need(store.restore(current['current_journal'])['requests']==st['requests'],'FINAL_OWNER_READBACK')
        need(io.api('releases/'+str(store.anchor['id']))['body']==store.anchor['body'],'FINAL_ANCHOR_READBACK')
        safe={'run_id':int(os.environ['GITHUB_RUN_ID']),'generation':st['generation'],'sequence':seq,'state':st['phase'],'remaining_broker_budget':remaining(st,a),'new_requests':dict(col.counts),'OWNER_READBACK_SUCCESS':True,'prior_wire_unchanged':unchanged,'economic_support_before':before,'economic_support_after':st['autonomy_proof']['support_after'],'orders':0,'NET':'NOT_EVALUATED_SUPPORT_ONLY'}
        out=io.Store(os.environ['GITHUB_SHA'],key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,'mxm-autonomous-native-proof-'+str(os.environ['GITHUB_RUN_ID']));ref=out.encrypted({'proof':st['autonomy_proof'],'checkpoint':current},'autonomous-proof.mxmenc');out.commit({**safe,'primary':ref})
        pathlib.Path(os.environ['GITHUB_OUTPUT']).open('a').write('generation='+str(st['generation'])+'\nready='+str(st['phase']=='BATCH_COMPLETE_READY_FOR_HANDOFF').lower()+'\n')
        print(json.dumps(safe),flush=True)
        if failed:raise RuntimeError('BROKER_OR_PROTOCOL_FAIL_CLOSED')

def handoff(a):
    exclusive()
    with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,'OWNER_KEY')
        store=BoundStore(os.environ['GITHUB_SHA'],key,tmp,a['base']);body=json.loads(store.anchor['body']);st=store.restore(body['current_journal'])
        need(body['generation']==int(os.environ['EXPECTED_GENERATION']) and body['state']=='BATCH_COMPLETE_READY_FOR_HANDOFF','HANDOFF_STATE')
        need(body['run_id']==int(os.environ['GITHUB_RUN_ID']) and not st['pending_requests'],'HANDOFF_OWNER_RUN')
        need(st['autonomy_proof']['failure'] is None and st['autonomy_proof']['prior_wire_unchanged'],'HANDOFF_PROOF')
        need(min(remaining(st,a).values())>0,'HANDOFF_BUDGET')
        dispatch(a,body['generation'],st['autonomy']['sequence']+1)

def economic(a):
    # Source is initialized with no publishing constructor and all paths are GET.
    from research_core_v4.remediation_p0_p4_20261015.owner import main as owner_readback
    return owner_readback()

def main():
    a=gate();mode=os.environ['MODE']
    if mode=='bootstrap':
        exclusive();body=json.loads(io.api('releases/412686323')['body']);need(body['current_journal']==a['snapshot']['current_journal'],'BOOTSTRAP_CHECKPOINT');dispatch(a,body['generation'],1)
    elif mode=='worker':worker(a)
    elif mode=='handoff':handoff(a)
    elif mode=='economic':economic(a)
    else:raise RuntimeError('UNKNOWN_MODE')
if __name__=='__main__':
    try:main()
    except Exception as ex:
        import traceback
        print(json.dumps({'state':'STOP_FAIL_CLOSED','exception_class':type(ex).__name__,'safe_code':str(ex) if re.fullmatch('[A-Z0-9_]{1,100}',str(ex)) else 'REDACTED','trace':[(pathlib.Path(x.filename).name,x.lineno,x.name) for x in traceback.extract_tb(ex.__traceback__)]}),flush=True);raise SystemExit(1) from None
