"""One bounded continuation. Preserve error categories before legacy catch discards them."""
import os,json,pathlib,tempfile,time,datetime,re,base64,copy
from collections import Counter
from .evidence import E,old,io,snap,ar,P
from research_core_v4.critical_frontier_repair_20261014_v2 import runner_v2 as runner
from research_core_v4.cost_frequency_discovery_v1.collector_v1 import Collector
TAG='mxm-root-cause-resume-proof-20261014-v1'

def exception_category(exc):
    # Never publish exception strings. Categories correspond to specific transport raise sites.
    text=str(exc)
    for needle,label in [('timed out','RESPONSE_DEADLINE'),('response timeout','RESPONSE_DEADLINE'),('send failed','TLS_SEND_FAILURE'),('receive failed','TLS_RECEIVE_FAILURE'),('closed by peer','TLS_PEER_CLOSED'),('not connected','SOCKET_NOT_CONNECTED'),('frame length','PROTOCOL_FRAME_LENGTH'),('unsupported cTrader payload','PROTOCOL_PAYLOAD_REGISTRY')]:
        if needle in text:return label
    return 'UNCLASSIFIED_EXCEPTION'

class EvidenceCollector(Collector):
    def __init__(self,caps):super().__init__(caps);self.last_evidence=None
    def send(self,req,historical=False):
        old.need(sum(self.counts.values())<64,'FINITE_NEW_HISTORY_REQUEST_CAP')
        self.last_evidence={'request_type':type(req).__name__,'started_monotonic':time.monotonic()}
        try:
            result=super().send(req,historical)
            self.last_evidence.update(response_type=type(result).__name__,response_b64=base64.b64encode(result.SerializeToString()).decode())
            envelope=getattr(self.tr,'last_history_envelope',None)
            if type(req).__name__=='ProtoOAGetTrendbarsReq' and envelope is not None:self.last_evidence['response_envelope_b64']=base64.b64encode(envelope.SerializeToString()).decode()
            return result
        except Exception as ex:
            self.last_evidence.update(exception_class=type(ex).__name__,exception_category=exception_category(ex),elapsed_seconds=time.monotonic()-self.last_evidence['started_monotonic'])
            raise

class BoundStore(io.Store):
    def __init__(self,head,key,tmp,base):
        self.execution_head=head;self.base=base
        super().__init__(base,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,snap.ROOT_TAG)
    def commit(self,body):
        old.need(io.api('git/ref/heads/'+os.environ['GITHUB_REF_NAME'])['object']['sha']==self.execution_head,'EXECUTION_HEAD_DRIFT')
        body={**body,'execution_source_head':self.execution_head,'canonical_source_head':self.base}
        super().commit(body)

def main():
    io.install();os.umask(0o077);head=os.environ['GITHUB_SHA'];a=json.loads((E.a.ROOT/(P+'RESUME_AUTHORITY_V1.json')).read_text())
    old.need(os.environ['GITHUB_REF_NAME']==a['branch'] and os.environ['GITHUB_RUN_ATTEMPT']=='1','SCOPE')
    old.need(datetime.datetime.now(datetime.timezone.utc).isoformat()<a['expires'],'EXPIRED');E.a.ancestor(a['base'],head)
    for p,h in a['bindings'].items():old.need(E.w.old.filehash(p)==h,'SOURCE_BINDING')
    old.need(io.api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']==a['base'],'CANONICAL_HEAD_CHANGED')
    for status in ('in_progress','queued','waiting','pending','requested'):
        active=io.api('actions/runs?status='+status+'&per_page=100')['workflow_runs']
        others=[r for r in active if r['id']!=int(os.environ['GITHUB_RUN_ID']) and ('native-frontier' in r['path'] or 'final-recovery' in r['path'] or 'root-cause-resume' in r['path'])]
        old.need(not others,'CONCURRENT_COLLECTION_WRITER')
    with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);old.need(fp==E.w.old.FP,'OWNER_KEY')
        store=BoundStore(head,key,tmp,a['base']);body=json.loads(store.anchor['body']);old.need(body['current_journal']==a['snapshot']['current_journal'],'CHECKPOINT_DRIFT')
        suspects=[x['id'] for x in store.inventory if (m:=re.match(r'(?:manifest|delta)-(\d+)-',x['name'])) and int(m.group(1))>1293]
        old.need(not suspects,'UNRECONCILED_ORPHAN_NO_REQUEST')
        db=ar.dbopen(tmp/'native.sqlite');snap.track(db);st=snap.restore(db,store)
        old.need(st['generation']==1293 and st['identity_cursor']==95 and not st['pending_requests'],'COLD_STATE')
        frozen_wire=db.execute('SELECT * FROM wire ORDER BY s,k,a,b').fetchall();before={'generation':st['generation'],'requests':copy.deepcopy(st['requests']),'cursor':st['identity_cursor'],'ticks':db.execute('SELECT count(*) FROM tick').fetchone()[0],'bars':db.execute('SELECT count(*) FROM bar').fetchone()[0]}
        col=EvidenceCollector({'BID_ASK':64,'M5':64});runner.configure();old.pilot=lambda *args:None
        real_persist=io.persist
        def persist(db,store,st,label,groups=()):
            for item in st.get('_raw',[]):
                if item.get('exception_class') and col.last_evidence:item['preserved_failure_evidence']=copy.deepcopy(col.last_evidence)
            return real_persist(db,store,st,label,groups)
        runner.storage.persist=persist;old.persist=persist
        # Cap is checked before preparation and before any new broker request; no retries.
        q=runner.acquire_quotes;m=runner.acquire_m5
        def bounded_q(db,keys,col,st,store,deadline):
            if sum(col.counts.values())>=48:return False
            return q(db,keys,col,st,store,deadline)
        # Each q invocation can contain multiple batches. Deadline plus send cap is insufficient:
        # quote_ops ends work exactly at the cap without preparing another request.
        raw_ops=runner.quote_ops
        def ops(db,keys):
            result=raw_ops(db,keys)
            return result[:max(0,64-sum(col.counts.values()))]
        runner.quote_ops=ops
        def bounded_m(db,sid,f,col,st,store,deadline):
            if sum(col.counts.values())>=64:return False,[],set()
            return m(db,sid,f,col,st,store,deadline)
        old.acquire_quotes=bounded_q;old.acquire_m5=bounded_m
        st['campaign_tick_cap']=st['requests']['BID_ASK']+64;st['campaign_m5_cap']=st['requests']['M5']+64
        st['bounded_recovery_execution']={'head':head,'base':a['base'],'old_checkpoint':a['snapshot']['current_journal'],'historical_exception':'TransportError','historical_physical_cause':'NOT_RECORDED','new_request_cap':64,'no_automatic_retry':True}
        st['phase']='RUNNING_ONE_BOUNDED_NATIVE_RESUME';failed=None;deadline=time.monotonic()+240
        cfg={**json.loads((E.a.ROOT/(old.P+'EXECUTION_V1.json')).read_text()),**json.loads((E.a.ROOT/(runner.P+'REPAIR_AUTHORITY_V2.json')).read_text())}
        try:
            col.connect();old.need(col.aid==int(st['catalog']['trader']['ctidTraderAccountId']),'SAME_ACCOUNT')
            while st['identity_cursor']<len(st['eligible']) and time.monotonic()<deadline and sum(col.counts.values())<64:
                sid=st['eligible'][st['identity_cursor']]
                if not old.process_identity(db,sid,st,col,store,cfg,deadline):break
                # Do not label an identity complete when quote_ops stopped at the finite cap.
                if sum(col.counts.values())>=64:break
                st['identity_cursor']+=1;st.setdefault('_record_dirty_ids',set()).add(sid);persist(db,store,st,'bounded-identity')
        except Exception as ex:
            failed={'exception_class':type(ex).__name__,'category':exception_category(ex),'last_request_evidence':col.last_evidence}
            st['errors'].append({'run':int(os.environ['GITHUB_RUN_ID']),'job':os.environ['GITHUB_JOB'],'cause':'BOUNDED_RESUME_STOP','evidence':failed})
        finally:
            col.close();st['phase']='STOP_BOUNDED_REQUEST_OR_TIME_LIMIT' if failed is None else 'STOP_BOUNDED_ERROR_NO_RETRY';persist(db,store,st,'bounded-worker-end')
        unchanged=all(db.execute('SELECT * FROM wire WHERE s=? AND k=? AND a=? AND b=?',r[:4]).fetchone()==r for r in frozen_wire)
        old.need(unchanged,'PRIOR_WIRE_CHANGED');old.need(sum(col.counts.values())<=64,'FINITE_CAP')
        final_body=json.loads(store.anchor['body']);readback=store.restore(final_body['current_journal']);old.need(readback['requests']==st['requests'],'FINAL_OWNER_READBACK')
        result={'schema':'mxm.bounded.recovery.proof.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_head':head,'before':before,'after':final_body,'new_requests':dict(col.counts),'new_ticks':db.execute('SELECT count(*) FROM tick').fetchone()[0]-before['ticks'],'new_bars':db.execute('SELECT count(*) FROM bar').fetchone()[0]-before['bars'],'prior_wire_records_unchanged':unchanged,'prior_wire_records':len(frozen_wire),'failure':failed,'historical_cause':'TransportError;subtype_and_message_discarded_by_original_catch;physical_cause_not_recoverable','fix':'PRESERVE_ALLOWLIST_TRANSPORT_CATEGORY_AND_SERIALIZED_RESPONSE_BEFORE_LEGACY_VALIDATION','physical_cause_fixed':False,'automatic_retries':0,'orders':0,'OWNER_READBACK_SUCCESS':True,'cold_restore_before_requests':True}
        output=io.Store(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,TAG);ref=output.encrypted(result,'bounded-recovery-owner.mxmenc');relay=E.upload_extra(output.release,tmp,E.a.ROOT/'research_core_v4/final_recovery_20261014_v1/RECIPIENT_PUBLIC_KEY.pem',result,'bounded-recovery-session.mxmenc');relay['release_id']=output.release['id']
        output.commit({'state':st['phase'],'run_id':result['run_id'],'primary':ref,'recipient':relay,'new_requests':result['new_requests'],'new_ticks':result['new_ticks'],'new_bars':result['new_bars'],'prior_wire_records_unchanged':unchanged,'OWNER_READBACK_SUCCESS':True,'physical_cause_fixed':False,'orders':0})
if __name__=='__main__':
    try:main()
    except Exception as ex:io.evidence(ex,'BOUNDED_RESUME');raise SystemExit(1) from None
