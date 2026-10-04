"""Hash-bound bounded historical transport. No evaluator/return computation."""
import collections,gzip,hashlib,json,os,time
from pathlib import Path
from research_core_v4.quote_probe_plan_v1 import canonical,sha
from research_core_v4.quote_metadata_android_v1 import MetadataTransport

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.partial')
    with open(tmp,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def seal(record):
    if 'checkpoint_sha256' in record:raise PermissionError('already sealed checkpoint')
    return dict(record,checkpoint_sha256=sha(canonical(record)))

def unseal(record):
    if not isinstance(record,dict):raise PermissionError('checkpoint object')
    body=dict(record);h=body.pop('checkpoint_sha256',None)
    if h!=sha(canonical(body)):raise PermissionError('checkpoint integrity')
    return body

EVENT_ORDER='CHRONOLOGICAL_REVERSED_BROKER_REPEATED_SEQUENCE_LAST_EVENT_WINS_TIES'

def validate_rows(rows,lo,hi):
    if not isinstance(rows,list):raise PermissionError('ordered rows required')
    previous=None
    for row in rows:
        if not isinstance(row,list) or len(row)!=2 or any(type(v) is not int for v in row) or not lo<=row[0]<=hi or row[1]<=0 or previous is not None and row[0]<previous:raise PermissionError('raw event order/range')
        previous=row[0]

def decode_ticks(ticks,lo,hi):
    # First event is absolute; subsequent timestamp AND price fields are signed
    # differences from the immediately preceding encoded event. Add both.
    rows=[];t=None;price=None
    for index,x in enumerate(ticks):
        dt=int(x.timestamp);dp=int(x.tick)
        if index==0:t,price=dt,dp
        else:
            if dt>0:raise PermissionError('TICK_TIME_DELTA_POSITIVE')
            t+=dt;price+=dp
        if not lo<=t<=hi:raise PermissionError('TICK_TIMESTAMP_OUTSIDE_FROZEN_WINDOW')
        if price<=0:raise PermissionError('TICK_RECONSTRUCTED_PRICE_NONPOSITIVE')
        rows.append([t,price])
    # Reverse the repeated sequence, never sort/deduplicate same-ms events.
    out=list(reversed(rows));validate_rows(out,lo,hi);return out


RECOVERY_REL='research_core_v4/state/DECODER_RECOVERY_AUTHORITY_V1.json'
RECOVERY_ID='6eed644c4506f73218ccf7df8e978b157447aeced6340935b7b9d67b696a477e'

def recovery_gate(root,workdir,private_root,plan):
    """Local control evidence only; called before OAuth/network. Never read quotes."""
    root=Path(root);w=Path(workdir)
    if w.is_symlink() or any(p.is_symlink() for p in w.rglob('*')):raise PermissionError('recovery checkpoint symlink')
    authority_raw=(root/RECOVERY_REL).read_bytes();a=json.loads(authority_raw)
    first=next(x for x in plan['slots'] if x['status']=='PLANNED')
    if any(first.get(k)!=v for k,v in a['request'].items()):raise PermissionError('recovery first slot mismatch')
    registry=Path(private_root)/('v4_probe_'+a['plan_sha256']+'.json')
    expected={'plan_sha256':a['plan_sha256'],'folder_sha256':sha(str(root.resolve()).encode()),'logical_execution_count':1}
    if registry.is_symlink() or unseal(json.loads(registry.read_bytes()))!=expected:raise PermissionError('recovery requires existing same folder registry')
    if sha((root/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json').read_bytes())!=a['plan_sha256']:raise PermissionError('recovery plan mismatch')
    def persist(path,data):
        used=sum(p.stat().st_size for p in w.rglob('*') if p.is_file())
        old=path.stat().st_size if path.exists() else 0
        if used+len(data)-old>2000000000:raise PermissionError('recovery evidence storage cap')
        atomic(path,data)
    def read(name):
        path=w/name
        if path.is_symlink():raise PermissionError('recovery evidence symlink')
        return path.read_bytes()
    stop=read('terminal_transport_stop.json')
    if sha(stop)!=a['original_stop_sha256']:raise PermissionError('original STOP mismatch')
    unseal(json.loads(stop))
    if (w/'terminal_recovery_stop.json').exists():raise PermissionError('later STOP no recovery authority')
    statepath=w/'decoder_recovery_binding.json'
    attempts=read('wire_attempts.jsonl');outcomes=read('wire_outcomes.jsonl')
    aa=[unseal(json.loads(x)) for x in attempts.splitlines()];oo=[unseal(json.loads(x)) for x in outcomes.splitlines()]
    def original_check(initial=False):
        if len(aa)!=1 or len(oo)!=1:raise PermissionError('one original attempt/outcome required')
        q=aa[0];o=oo[0]
        for k,v in {'attempt_index':0,'request_id':RECOVERY_ID,'from_ms':first['from_ms'],'to_ms':first['to_ms'],'depth':0,'retry_index':0}.items():
            if q.get(k)!=v or (k in o and o[k]!=v):raise PermissionError('original request scope mismatch')
        if o.get('attempt_index')!=0 or o.get('status')!='RECEIVED' or o.get('returned_ticks')!=66 or o.get('has_more') is not False:raise PermissionError('original outcome mismatch')
        if q.get('status')!='SENT_OR_ACK_UNKNOWN':raise PermissionError('original attempt status')
        schedule=unseal(json.loads(read('current_schedule_preflight.json')))
        if schedule.get('status')!='EXACT_FROZEN_WINDOWS_MATCH' or schedule.get('mismatches')!=[] or schedule.get('identities_checked')!=56 or schedule.get('base_slot_count')!=1120 or schedule.get('identity_week_windows_checked')!=560:raise PermissionError('original schedule mismatch')
        elapsed=unseal(json.loads(read('active_seconds.json')))
        if initial and elapsed!={'active_seconds':5.56}:raise PermissionError('original active seconds mismatch')
        for directory in ['completed','raw','nodes']:
            if any(x.is_file() for x in (w/directory).rglob('*')):raise PermissionError('unpersisted original page required')
    if not statepath.exists():
        original_check(initial=True)
        evidence={n:read(n) for n in ['terminal_transport_stop.json','wire_attempts.jsonl','wire_outcomes.jsonl','current_schedule_preflight.json','active_seconds.json']}
        archive=w/'ORIGINAL_DECODER_STOP_EVIDENCE'
        for n,b in evidence.items():
            target=archive/n
            if target.exists() and target.read_bytes()!=b:raise PermissionError('immutable original evidence mismatch')
            if not target.exists():persist(target,b)
        state={'authority_sha256':sha(authority_raw),'folder_binding':expected,'original_file_sha256':{n:sha(b) for n,b in evidence.items()},'replacement_consumed':False,'original_attempts_charged':1,'original_active_seconds_charged':5.56,'payload_equality_proven':False}
        persist(statepath,canonical(seal(state)))
    state=unseal(json.loads(statepath.read_bytes()))
    if state.get('authority_sha256')!=sha(authority_raw) or state.get('folder_binding')!=expected:raise PermissionError('recovery authority binding')
    for n,h in state['original_file_sha256'].items():
        if sha((w/'ORIGINAL_DECODER_STOP_EVIDENCE'/n).read_bytes())!=h:raise PermissionError('original evidence changed')
    for n,current in [('wire_attempts.jsonl',attempts),('wire_outcomes.jsonl',outcomes)]:
        original=(w/'ORIGINAL_DECODER_STOP_EVIDENCE'/n).read_bytes()
        if not current.startswith(original):raise PermissionError('journal original prefix changed')
    elapsed=unseal(json.loads(read('active_seconds.json')))['active_seconds']
    if not 5.56<=elapsed<=7200:raise PermissionError('cumulative active time')
    if not state['replacement_consumed']:
        original_check()
    else:
        # A consumed grant without a persisted page may never send again, even
        # after an acknowledgement loss or crash between fence and node write.
        node=w/'nodes'/RECOVERY_ID/f"{first['from_ms']}_{first['to_ms']}.json.gz"
        if not node.is_file() or node.is_symlink() or len(aa)<2:raise PermissionError('consumed recovery page unavailable; review required')
        replacement=aa[1];received=[x for x in oo if x.get('attempt_index')==1]
        if len(received)!=1 or received[0].get('status')!='RECEIVED' or received[0].get('returned_ticks')!=66 or received[0].get('has_more') is not False:raise PermissionError('replacement shape evidence')
        for k,v in {'request_id':RECOVERY_ID,'from_ms':first['from_ms'],'to_ms':first['to_ms'],'depth':0,'attempt_index':1}.items():
            if replacement.get(k)!=v:raise PermissionError('replacement request scope')
    if sum(p.stat().st_size for p in w.rglob('*') if p.is_file())>2000000000:raise PermissionError('recovery storage cap')
    return state

class ProbeTransport:
    def __init__(self,metadata,slots,account,workdir,clock=time.monotonic,sleep=time.sleep,recovery=None):
        from m6.ctrader_proto import OpenApiMessages_pb2 as oa
        if not metadata.scope_view_verified or not metadata.account_auth_verified:raise PermissionError('read-only account gate before ticks')
        self.oa=oa;self.meta=metadata;self._account=account;self.slots={x['request_id']:x for x in slots if x['status']=='PLANNED'}
        self.workdir=Path(workdir)
        self.recovery=recovery
        if (self.workdir/'terminal_recovery_stop.json').exists():raise PermissionError('later terminal STOP')
        if recovery is None and (self.workdir/'terminal_transport_stop.json').exists():
            unseal(json.loads((self.workdir/'terminal_transport_stop.json').read_bytes()))
            raise PermissionError('durable terminal transport STOP; no retry authority')
        self.clock=clock;self.sleep=sleep;self.last=None
        self.replay_only=False;self.active=None;self._authorized_ranges=set();self.started=clock()
        self.budget_check=lambda:None
        self.journal=self.workdir/'wire_attempts.jsonl';self.workdir.mkdir(parents=True,exist_ok=True)
        self.local_bytes=sum(p.stat().st_size for p in self.workdir.rglob('*') if p.is_file())
        if self.local_bytes>2000000000:raise PermissionError('resumed storage budget')
        self.attempts=[]
        if self.journal.exists():
            for line in self.journal.read_text().splitlines():
                item=unseal(json.loads(line))
                if item.get('attempt_index')!=len(self.attempts) or item.get('request_id') not in self.slots:raise PermissionError('wire journal index/scope')
                self.attempts.append(item)
        outcomes=self.workdir/'wire_outcomes.jsonl'
        if outcomes.exists():
            seen=set()
            for line in outcomes.read_text().splitlines():
                item=unseal(json.loads(line));index=item.get('attempt_index')
                if type(index) is not int or not 0<=index<len(self.attempts) or index in seen:raise PermissionError('wire outcome index/integrity')
                seen.add(index);self.attempts[index].update(item)
        if len(self.attempts)>11200:raise PermissionError('resumed wire budget')
    def __repr__(self):return '<bounded probe; private account withheld>'
    def _trace(self,item):
        raw=canonical(seal(item))+b'\n'
        if self.local_bytes+len(raw)>2000000000:raise PermissionError('wire journal storage cap')
        atomic(self.journal,(self.journal.read_bytes() if self.journal.exists() else b'')+raw)
        self.attempts.append(item);self.local_bytes+=len(raw)
    def _validate(self,msg):
        if type(msg) is not self.oa.ProtoOAGetTickDataReq or not msg.IsInitialized() or int(msg.payloadType)!=int(self.oa.ProtoOAGetTickDataReq().payloadType):raise PermissionError('probe accepts only exact tick request type')
        if self.active is None or self.active not in self.slots:raise PermissionError('no bound logical request')
        s=self.slots[self.active]
        if int(msg.ctidTraderAccountId)!=self._account or int(msg.symbolId)!=s['symbol_id'] or int(msg.type)!={'BID':1,'ASK':2}[s['side']]:raise PermissionError('identity/side/account outside probe')
        lo,hi=int(msg.fromTimestamp),int(msg.toTimestamp)
        if (lo,hi) not in self._authorized_ranges or not s['from_ms']<=lo<=hi<=s['to_ms']:raise PermissionError('window outside exact probe split tree')
    def _outcome(self,item):
        path=self.workdir/'wire_outcomes.jsonl'
        if self.local_bytes+len(canonical(seal(item)))+1>2000000000:raise PermissionError('outcome journal storage cap')
        atomic(path,(path.read_bytes() if path.exists() else b'')+canonical(seal(item))+b'\n')
        self.attempts[item['attempt_index']].update(item);self.local_bytes+=len(canonical(seal(item)))+1
    def request(self,msg,depth):
        self._validate(msg)
        from m6.ctrader_transport import TransportError
        if self.recovery is not None and self.active==RECOVERY_ID and len(self.attempts)!=1:raise PermissionError('no additional replacement authorized')
        replacement=self.recovery is not None and self.active==RECOVERY_ID and len(self.attempts)==1
        if replacement:
            if self.recovery['replacement_consumed']:raise PermissionError('replacement already consumed')
            self.recovery['replacement_consumed']=True
            self.recovery['replacement_request_sha256']=sha(msg.SerializeToString(deterministic=True))
            binding_path=self.workdir/'decoder_recovery_binding.json';encoded=canonical(seal(self.recovery));delta=len(encoded)-binding_path.stat().st_size
            if self.local_bytes+delta>2000000000:raise PermissionError('recovery fence storage cap')
            atomic(binding_path,encoded);self.local_bytes+=delta
        for retry in range(1 if replacement else 3):
            self.budget_check()
            if len(self.attempts)>=11200 or self.clock()-self.started>=7200:raise PermissionError('hard probe wire/time budget')
            delay=0.22-(self.clock()-self.last) if self.last is not None else 0
            if delay>0:self.sleep(delay)
            self.budget_check()
            if self.clock()-self.started>=7200:raise PermissionError('time budget after spacing')
            self.last=self.clock();start=self.clock()
            trace={'request_id':self.active,'from_ms':int(msg.fromTimestamp),'to_ms':int(msg.toTimestamp),'depth':depth,'retry_index':retry,'status':'SENT_OR_ACK_UNKNOWN','attempt_index':len(self.attempts)}
            self._trace(trace) # durable attempt fence, including acknowledgement loss
            try:
                res=self.meta._inner.request(msg)
            except PermissionError:raise
            except (TransportError,OSError,TimeoutError):
                self._outcome({'attempt_index':trace['attempt_index'],'status':'TRANSPORT_FAILURE_OR_ACK_LOSS','latency_seconds':self.clock()-start})
                if replacement:raise PermissionError('replacement transport failure; no second replacement') from None
                if retry==2:raise RuntimeError('probe transport interrupted safely') from None
                self.sleep(retry+1);self.meta._restore();continue
            self.budget_check()
            trace['latency_seconds']=self.clock()-start
            if type(res).__name__ in {'ProtoOAErrorRes','ProtoCHErrorRes','ProtoErrorRes'}:
                code=str(getattr(res,'errorCode','')).upper()
                # Every broker error is transport failure, never support absence.
                trace['status']='BROKER_ERROR_FAIL_CLOSED';trace['broker_error_code']=code if code in {'BLOCKED_PAYLOAD_TYPE','REQUEST_FREQUENCY_EXCEEDED','SERVER_UNAVAILABLE','MAINTENANCE','SYMBOL_NOT_FOUND','INCORRECT_BOUNDARIES','ACCOUNT_NOT_AUTHORIZED','OA_AUTH_TOKEN_EXPIRED'} else 'UNRECOGNIZED_ERROR'
                self._outcome(trace)
                # Deliberately fail closed for rate-limit and maintenance too.
                # No undocumented/default backoff and no false EMPTY evidence.
                raise PermissionError('historical broker error; transport failed closed') from None
            if type(res) is not self.oa.ProtoOAGetTickDataRes or not res.IsInitialized() or int(res.ctidTraderAccountId)!=self._account:raise PermissionError('wrong historical response binding')
            if 'symbolId' in res.DESCRIPTOR.fields_by_name and res.HasField('symbolId') and int(res.symbolId)!=int(msg.symbolId):raise PermissionError('historical symbol mismatch')
            trace.update(status='RECEIVED',returned_ticks=len(res.tickData),has_more=bool(res.hasMore));self._outcome(trace)
            if replacement and (len(res.tickData)!=66 or bool(res.hasMore)):raise PermissionError('replacement shape differs; independent review required')
            return res,trace
        raise RuntimeError('unreachable')
    def capture(self,slot):
        if slot['request_id'] not in self.slots or slot!=self.slots[slot['request_id']]:raise PermissionError('unbound slot')
        self.active=slot['request_id'];self._authorized_ranges={(slot['from_ms'],slot['to_ms'])}
        try:return self._node(slot['from_ms'],slot['to_ms'],0)
        except PermissionError:
            atomic(self.workdir/('terminal_recovery_stop.json' if self.recovery is not None else 'terminal_transport_stop.json'),canonical(seal({'status':'TRANSPORT_ARCHITECTURE_NOT_FEASIBLE_AS_CURRENTLY_CONFIGURED','request_id':self.active,'automatic_retry_authorized':False})))
            raise
    def capture_cached(self,slot):
        self.replay_only=True
        try:return self.capture(slot)
        finally:self.replay_only=False
    def _node(self,lo,hi,depth):
        path=self.workdir/'nodes'/self.active/f'{lo}_{hi}.json.gz'
        if path.exists():
            raw=gzip.decompress(path.read_bytes());record=unseal(json.loads(raw))
            if record['request_id']!=self.active or record['from_ms']!=lo or record['to_ms']!=hi:raise PermissionError('checkpoint mismatch')
        else:
            if self.replay_only:raise PermissionError('missing cached node; no re-download authorized')
            s=self.slots[self.active];req=self.oa.ProtoOAGetTickDataReq(ctidTraderAccountId=self._account,symbolId=s['symbol_id'],type={'BID':1,'ASK':2}[s['side']],fromTimestamp=lo,toTimestamp=hi)
            res,trace=self.request(req,depth)
            record={'request_id':self.active,'from_ms':lo,'to_ms':hi,'trace':trace,'depth':depth,'event_order':EVENT_ORDER,'status':'SPLIT' if res.hasMore else 'LEAF'}
            if res is not None:
                rows=decode_ticks(res.tickData,lo,hi)
                if not res.hasMore:record['rows']=rows
                elif lo>=hi:raise PermissionError('saturated one-millisecond interval; no lossy truncate')
            encoded=gzip.compress(canonical(seal(record)),compresslevel=9,mtime=0)
            used=self.local_bytes
            if used+len(encoded)>2000000000:raise PermissionError('hard local raw storage budget')
            atomic(path,encoded);self.local_bytes+=len(encoded)
        if record.get('depth')!=depth or record.get('event_order')!=EVENT_ORDER:raise PermissionError('node depth/order binding')
        t=record['trace']
        if any(t.get(k)!=v for k,v in [('request_id',self.active),('from_ms',lo),('to_ms',hi),('depth',depth),('status','RECEIVED')]):raise PermissionError('node trace binding')
        if type(t.get('attempt_index')) is not int or not 0<=t['attempt_index']<len(self.attempts) or self.attempts[t['attempt_index']]!=t:raise PermissionError('node durable wire trace mismatch')
        status=record['status'];trace=[t]
        if status=='LEAF':
            validate_rows(record['rows'],lo,hi)
            if t.get('has_more') is not False or t.get('returned_ticks')!=len(record['rows']):raise PermissionError('leaf completeness')
            return record['rows'],trace
        if t.get('has_more') is not True or 'rows' in record:raise PermissionError('split completeness')
        if status!='SPLIT' or lo>=hi:raise PermissionError('invalid split checkpoint')
        mid=(lo+hi)//2;self._authorized_ranges.update({(lo,mid),(mid+1,hi)})
        left,lt=self._node(lo,mid,depth+1);right,rt=self._node(mid+1,hi,depth+1)
        if left is None or right is None:return None,trace+lt+rt
        if left and right and left[-1][0]>=right[0][0]:raise PermissionError('disjoint split chronology failed')
        return left+right,trace+lt+rt
