"""Hash-bound bounded historical transport. No evaluator/return computation."""
import collections,gzip,hashlib,json,os,time
from pathlib import Path
from research_core_v4.quote_probe_plan_v1 import canonical,sha
from research_core_v4.quote_metadata_android_v1 import MetadataTransport

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.partial')
    with open(tmp,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def decode_ticks(ticks,lo,hi):
    rows=[];t=None
    for index,x in enumerate(ticks):
        t=int(x.timestamp) if index==0 else t-int(x.timestamp)
        if (index and int(x.timestamp)<0) or not lo<=t<=hi or int(x.tick)<=0:raise PermissionError('malformed historical ticks')
        rows.append([t,int(x.tick)])
    return list(reversed(rows))

class ProbeTransport:
    def __init__(self,metadata,slots,account,workdir,clock=time.monotonic,sleep=time.sleep):
        from m6.ctrader_proto import OpenApiMessages_pb2 as oa
        if not metadata.scope_view_verified or not metadata.account_auth_verified:raise PermissionError('read-only account gate before ticks')
        self.oa=oa;self.meta=metadata;self._account=account;self.slots={x['request_id']:x for x in slots if x['status']=='PLANNED'}
        self.workdir=Path(workdir);self.clock=clock;self.sleep=sleep;self.last=None
        self.active=None;self._authorized_ranges=set();self.started=clock()
        self.journal=self.workdir/'wire_attempts.jsonl';self.workdir.mkdir(parents=True,exist_ok=True)
        self.local_bytes=sum(p.stat().st_size for p in self.workdir.rglob('*') if p.is_file())
        self.attempts=[]
        if self.journal.exists():
            for line in self.journal.read_text().splitlines():self.attempts.append(json.loads(line))
        outcomes=self.workdir/'wire_outcomes.jsonl'
        if outcomes.exists():
            for line in outcomes.read_text().splitlines():
                item=json.loads(line);self.attempts[item['attempt_index']].update(item)
    def __repr__(self):return '<bounded probe; private account withheld>'
    def _trace(self,item):
        raw=canonical(item)+b'\n'
        with open(self.journal,'ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        self.attempts.append(item);self.local_bytes+=len(raw)
    def _validate(self,msg):
        if type(msg) is not self.oa.ProtoOAGetTickDataReq or not msg.IsInitialized() or int(msg.payloadType)!=int(self.oa.ProtoOAGetTickDataReq().payloadType):raise PermissionError('probe accepts only exact tick request type')
        if self.active is None or self.active not in self.slots:raise PermissionError('no bound logical request')
        s=self.slots[self.active]
        if int(msg.ctidTraderAccountId)!=self._account or int(msg.symbolId)!=s['symbol_id'] or int(msg.type)!={'BID':1,'ASK':2}[s['side']]:raise PermissionError('identity/side/account outside probe')
        lo,hi=int(msg.fromTimestamp),int(msg.toTimestamp)
        if (lo,hi) not in self._authorized_ranges or not s['from_ms']<=lo<=hi<=s['to_ms']:raise PermissionError('window outside exact probe split tree')
    def _outcome(self,item):
        with open(self.workdir/'wire_outcomes.jsonl','ab') as f:f.write(canonical(item)+b'\n');f.flush();os.fsync(f.fileno())
        self.attempts[item['attempt_index']].update(item);self.local_bytes+=len(canonical(item))+1
    def request(self,msg,depth):
        self._validate(msg)
        from m6.ctrader_transport import TransportError
        for retry in range(3):
            if len(self.attempts)>=11200 or self.clock()-self.started>=7200:raise PermissionError('hard probe wire/time budget')
            delay=0.22-(self.clock()-self.last) if self.last is not None else 0
            if delay>0:self.sleep(delay)
            self.last=self.clock();start=self.clock()
            trace={'request_id':self.active,'from_ms':int(msg.fromTimestamp),'to_ms':int(msg.toTimestamp),'depth':depth,'retry_index':retry,'status':'SENT_OR_ACK_UNKNOWN','attempt_index':len(self.attempts)}
            self._trace(trace) # durable attempt fence, including acknowledgement loss
            try:
                res=self.meta._inner.request(msg)
            except PermissionError:raise
            except (TransportError,OSError,TimeoutError):
                self._outcome({'attempt_index':trace['attempt_index'],'status':'TRANSPORT_FAILURE_OR_ACK_LOSS','latency_seconds':self.clock()-start})
                if retry==2:raise RuntimeError('probe transport interrupted safely') from None
                self.sleep(retry+1);self.meta._restore();continue
            trace['latency_seconds']=self.clock()-start
            if type(res).__name__ in {'ProtoOAErrorRes','ProtoCHErrorRes'}:
                code=str(getattr(res,'errorCode','')).upper()
                if any(x in code for x in ['AUTH','TOKEN','PERMISSION','SCOPE']):raise PermissionError('historical read-only authentication rejected')
                trace['status']='ENDPOINT_UNAVAILABLE';self._outcome(trace);return None,trace
            if type(res) is not self.oa.ProtoOAGetTickDataRes or not res.IsInitialized() or int(res.ctidTraderAccountId)!=self._account:raise PermissionError('wrong historical response binding')
            if 'symbolId' in res.DESCRIPTOR.fields_by_name and res.HasField('symbolId') and int(res.symbolId)!=int(msg.symbolId):raise PermissionError('historical symbol mismatch')
            trace.update(status='RECEIVED',returned_ticks=len(res.tickData),has_more=bool(res.hasMore));self._outcome(trace);return res,trace
        raise RuntimeError('unreachable')
    def capture(self,slot):
        if slot['request_id'] not in self.slots or slot!=self.slots[slot['request_id']]:raise PermissionError('unbound slot')
        self.active=slot['request_id'];self._authorized_ranges={(slot['from_ms'],slot['to_ms'])}
        return self._node(slot['from_ms'],slot['to_ms'],0)
    def _node(self,lo,hi,depth):
        path=self.workdir/'nodes'/self.active/f'{lo}_{hi}.json.gz'
        if path.exists():
            raw=gzip.decompress(path.read_bytes());record=json.loads(raw)
            if record['request_id']!=self.active or record['from_ms']!=lo or record['to_ms']!=hi:raise PermissionError('checkpoint mismatch')
        else:
            s=self.slots[self.active];req=self.oa.ProtoOAGetTickDataReq(ctidTraderAccountId=self._account,symbolId=s['symbol_id'],type={'BID':1,'ASK':2}[s['side']],fromTimestamp=lo,toTimestamp=hi)
            res,trace=self.request(req,depth)
            record={'request_id':self.active,'from_ms':lo,'to_ms':hi,'trace':trace,'status':'UNAVAILABLE' if res is None else 'SPLIT' if res.hasMore else 'LEAF'}
            if res is not None:
                rows=decode_ticks(res.tickData,lo,hi)
                if not res.hasMore:record['rows']=rows
                elif lo>=hi:raise PermissionError('saturated one-millisecond interval; no lossy truncate')
            encoded=gzip.compress(canonical(record),compresslevel=9,mtime=0)
            used=self.local_bytes
            if used+len(encoded)>2000000000:raise PermissionError('hard local raw storage budget')
            atomic(path,encoded);self.local_bytes+=len(encoded)
        status=record['status'];trace=[record['trace']]
        if status=='UNAVAILABLE':return None,trace
        if status=='LEAF':return record['rows'],trace
        if status!='SPLIT' or lo>=hi:raise PermissionError('invalid split checkpoint')
        mid=(lo+hi)//2;self._authorized_ranges.update({(lo,mid),(mid+1,hi)})
        left,lt=self._node(lo,mid,depth+1);right,rt=self._node(mid+1,hi,depth+1)
        if left is None or right is None:return None,trace+lt+rt
        if left and right and left[-1][0]>=right[0][0]:raise PermissionError('disjoint split chronology failed')
        return left+right,trace+lt+rt
