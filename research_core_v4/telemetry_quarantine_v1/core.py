"""Inert telemetry prearm core. No network, secret, response or trading API."""
from __future__ import annotations
import ast
import base64
import hashlib
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

NAMESPACE = 'PILOT_TELEMETRY_QUARANTINE_V1'
MAGIC = b'MXM_TELEMETRY_QUARANTINE_V1\x00'
STOP_HASH = 'de227c5625d2e44e2a49e3dca0971cb0d86929f79c58a16a9c5b6c9dfc2a6330'
CRYPTO_HASH = 'b020790cfbd3aa4efb6bd1898e4b3b66395977334a37c68c8a5effe1fd23128d'
ARM_PATH = 'research_core_v4/state/TELEMETRY_QUARANTINE_EXECUTION_ARM_V1.json'
ALLOWED = frozenset({'ProtoOAApplicationAuthReq','ProtoOAAccountAuthReq',
    'ProtoOAGetAccountListByAccessTokenReq','ProtoOATraderReq',
    'ProtoOASubscribeSpotsReq','ProtoOASubscribeLiveTrendbarReq',
    'ProtoOAUnsubscribeSpotsReq','ProtoOAUnsubscribeLiveTrendbarReq','ProtoHeartbeatEvent'})

class Denied(ValueError): pass
def require(ok, reason):
    if not ok: raise Denied(reason)
def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()
def atomic(path, raw):
    path=Path(path); tmp=path.with_name(path.name+'.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)
    d=os.open(path.parent,os.O_RDONLY)
    try: os.fsync(d)
    finally: os.close(d)

def check_partition(p, start_ns, end_ns, now_ns):
    require(p['namespace']==NAMESPACE,'NAMESPACE')
    require(p['purpose']=='OBSERVABILITY_ONLY_NO_SCIENTIFIC_READERS','PURPOSE')
    require(start_ns>now_ns and end_ns-start_ns==p['limits']['duration_ns'],'FUTURE_INTERVAL')
    ids=[x['symbol_id'] for x in p['roster']]
    require(len(ids)==len(set(ids))==3,'ROSTER')
    require(not set(ids)&set(p['reserved_identity_ids']),'RESERVED_IDENTITY')
    require(start_ns>=p['not_before_ns'],'OLD_INTERVAL')
    for a in p['assignments']:
        require(a['classification'] in {'CONFIRMATION','PROTECTED'},'AMBIGUOUS_ASSIGNMENT')
        # Missing end denotes open-ended reservation; missing identities denotes all.
        identity_overlap=not a['identity_ids'] or bool(set(ids)&set(a['identity_ids']))
        time_overlap=end_ns>a['start_ns'] and (a['end_ns'] is None or start_ns<a['end_ns'])
        require(not(identity_overlap and time_overlap),'ASSIGNMENT_OVERLAP')
    require(p['payload_readers']==['ISOLATED_CAPTURE_PROCESS','INDEPENDENT_QUARANTINE_CUSTODIAN'],'READERS')
    require(p['public_payload_export'] is False and p['scientific_ingestion'] is False,'ROUTE')
    return True

def arm_gate(arm, authorization, p, stop_raw, actual_head, actual_parent, changed_files, now_ns):
    require(isinstance(arm,dict) and isinstance(authorization,dict),'SEPARATE_ARM_REQUIRED')
    require(set(arm)=={'schema','scope_hash','authorization_hash','expected_source_head','start_ns','end_ns','pilot_id','key_sha256','account_fingerprint_sha256','provider_timestamp_unit'},'ARM_FIELDS')
    require(arm['schema']=='mxm.telemetry-quarantine.arm.v1','ARM_SCHEMA')
    require(sha(stop_raw)==STOP_HASH,'TERMINAL_STOP_BINDING')
    require(arm['scope_hash']==sha(canonical(p)),'PARTITION_BINDING')
    require(arm['authorization_hash']==sha(canonical(authorization)),'INDEPENDENT_AUTH_BINDING')
    require(authorization.get('status')=='INDEPENDENT_PREARM_AUDIT_ACCEPTED','AUDIT')
    require(authorization.get('scope_hash')==arm['scope_hash'],'AUDIT_SCOPE')
    require(authorization.get('STOP_sha256')==STOP_HASH,'AUDIT_STOP')
    require(authorization.get('SCOPE_VIEW_only') is True,'PERMISSION_SCOPE')
    require(authorization.get('payload_readers')==p['payload_readers'],'AUDIT_READERS')
    require(authorization.get('key_sha256')==arm['key_sha256'],'KEY_BINDING')
    require(authorization.get('account_fingerprint_sha256')==arm['account_fingerprint_sha256'],'ACCOUNT_BINDING')
    require(arm['provider_timestamp_unit']=='milliseconds' and authorization.get('provider_timestamp_unit_verified')=='milliseconds','TIMESTAMP_UNIT_UNCERTIFIED')
    require(actual_head and actual_parent==arm['expected_source_head'] and actual_head!=actual_parent,'EXACT_HEAD')
    require(changed_files==[ARM_PATH],'ARM_ONLY_COMMIT')
    require(authorization.get('source_head')==actual_parent,'AUDIT_HEAD')
    require(arm['pilot_id']==sha(canonical([arm['scope_hash'],arm['start_ns'],arm['end_ns']])),'PILOT_ID')
    check_partition(p,arm['start_ns'],arm['end_ns'],now_ns)
    hour=3_600_000_000_000
    expected=((authorization['frozen_at_ns']+hour+hour-1)//hour)*hour
    require(arm['start_ns']==expected,'SCHEDULE_RULE')
    return True

class Clock:
    """Attested UTC plus monotonic pair. No inferred historical timestamps."""
    def __init__(self): self.last=None
    def pair(self, before_ns, wall_ns, after_ns, witness):
        keys={'source','offset_ns','error_ns','sample_mono_ns','max_age_ns','drift_ppm','witness_sha256','synchronized'}
        require(set(witness)==keys,'CLOCK_WITNESS_FIELDS')
        require(witness['synchronized'] is True and witness['source']=='ATTESTED_SYNC_CLOCK_V1','CLOCK_SOURCE')
        require(len(witness['witness_sha256'])==64,'CLOCK_PROVENANCE')
        require(before_ns<=after_ns and after_ns-before_ns<=10_000_000,'CLOCK_BRACKET')
        mid=(before_ns+after_ns)//2; age=mid-witness['sample_mono_ns']
        require(0<=age<=min(witness['max_age_ns'],30_000_000_000),'CLOCK_STALE')
        require(0<=witness['drift_ppm']<=100 and witness['error_ns']>=0,'CLOCK_BOUND')
        error=witness['error_ns']+(after_ns-before_ns+1)//2+int(age*witness['drift_ppm']/1_000_000)+1
        require(error<=50_000_000,'CLOCK_UNCERTAINTY')
        utc=wall_ns-witness['offset_ns']
        if self.last:
            require(mid>self.last['mono_ns'],'MONOTONIC_ORDER')
            require(abs((utc-self.last['utc_ns'])-(mid-self.last['mono_ns']))<=error+self.last['uncertainty_ns'],'WALL_CLOCK_STEP')
        pair={'mono_ns':mid,'utc_ns':utc,'uncertainty_ns':error,'utc_lower_ns':utc-error,'utc_upper_ns':utc+error,'witness':dict(witness)}
        self.last=pair; return pair

def load_reused_crypto(source_path):
    """Reuse the exact frozen pure encryption functions without importing workers."""
    raw=Path(source_path).read_bytes(); require(sha(raw)==CRYPTO_HASH,'CRYPTO_SOURCE_BINDING')
    wanted={'sha256_bytes','sha256_file','_package_cipher','_unpackage_cipher','encrypt_shard','decrypt_synthetic_package'}
    nodes=[]
    for n in ast.parse(raw).body:
        if isinstance(n,ast.FunctionDef) and n.name in wanted: nodes.append(n)
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PACKAGE_MAGIC' for t in n.targets): nodes.append(n)
    require(len(nodes)==7,'CRYPTO_EXTRACTION')
    env=dict(base64=base64,hashlib=hashlib,os=os,struct=struct,subprocess=subprocess,tempfile=tempfile,Path=Path,CaptureError=Denied)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source_path),'exec'),env)
    return env

class Sealer:
    def __init__(self, source_path, public_key, expected_key_hash):
        self.crypto=load_reused_crypto(source_path); self.public_key=Path(public_key)
        require(sha(self.public_key.read_bytes())==expected_key_hash,'PUBLIC_KEY_HASH')
    def __call__(self, raw, dest):
        tmp=Path(dest).with_suffix('.inner')
        try:
            self.crypto['encrypt_shard'](raw,public_key=self.public_key,output=tmp)
            atomic(dest,MAGIC+tmp.read_bytes())
        finally:
            if tmp.exists(): tmp.unlink()

class Store:
    """Encrypted append-only batches; recover durable batches, never reacquire."""
    def __init__(self, root, repo_root, scope_hash, pilot_id, sealer, max_bytes):
        self.root=Path(root).resolve(); repo=Path(repo_root).resolve()
        require(not(self.root==repo or repo in self.root.parents),'STORAGE_INSIDE_REPO')
        require(NAMESPACE in self.root.parts,'STORAGE_NAMESPACE')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        require(self.root.stat().st_uid==os.getuid() and self.root.stat().st_mode&0o077==0,'STORAGE_OWNER_MODE')
        self.scope=scope_hash; self.pilot_id=pilot_id; self.sealer=sealer; self.max_bytes=max_bytes
        self.active=False
        self.state={'namespace':NAMESPACE,'scope_hash':scope_hash,'pilot_id':pilot_id,'batches':[],'cipher_bytes':0,'last_ordinal':0}
    def claim(self):
        p=self.root/'attempt.intent'
        try: fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError: raise Denied('REPEATED_ARM') from None
        with os.fdopen(fd,'wb') as f:
            f.write(canonical({'scope_hash':self.scope,'pilot_id':self.pilot_id,'live_attempts':1}));f.flush();os.fsync(f.fileno())
        atomic(self.root/'checkpoint.json',canonical(self.state));self.active=True
    def commit(self,records):
        require(self.active,'ATTEMPT_NOT_ACTIVE');require(records,'EMPTY_BATCH'); i=len(self.state['batches'])+1
        require(records[0]['arrival_ordinal']==self.state['last_ordinal']+1,'DURABLE_ORDINAL')
        require([r['arrival_ordinal'] for r in records]==list(range(records[0]['arrival_ordinal'],records[-1]['arrival_ordinal']+1)),'BATCH_ORDER')
        raw=canonical({'namespace':NAMESPACE,'scope_hash':self.scope,'records':records})
        dest=self.root/f'{i:06d}.telemetry-sealed'
        require(not dest.exists(),'SEALED_OVERWRITE')
        self.sealer(raw,dest)
        ciphertext=dest.read_bytes(); require(ciphertext.startswith(MAGIC),'QUARANTINE_MAGIC')
        require(self.state['cipher_bytes']+len(ciphertext)<=self.max_bytes,'CIPHER_BYTE_BUDGET')
        entry={'index':i,'cipher_sha256':sha(ciphertext),'cipher_bytes':len(ciphertext),'raw_sha256':sha(raw),'last_ordinal':records[-1]['arrival_ordinal'],'previous':sha(canonical(self.state))}
        # Journal is commit authority; checkpoint may be safely rebuilt from it.
        atomic(self.root/f'{i:06d}.journal',canonical(entry))
        self.state['batches'].append(entry);self.state['cipher_bytes']+=len(ciphertext);self.state['last_ordinal']=entry['last_ordinal']
        atomic(self.root/'checkpoint.json',canonical(self.state))
    def recover(self):
        self.active=False
        intent=json.loads((self.root/'attempt.intent').read_bytes())
        require(intent=={'scope_hash':self.scope,'pilot_id':self.pilot_id,'live_attempts':1},'INTENT_BINDING')
        for journal in sorted(self.root.glob('*.journal')):
            e=json.loads(journal.read_bytes()); i=len(self.state['batches'])+1
            require(journal.name==f'{i:06d}.journal' and e['index']==i,'JOURNAL_GAP')
            require(e['previous']==sha(canonical(self.state)),'JOURNAL_CHAIN')
            c=(self.root/f'{i:06d}.telemetry-sealed').read_bytes()
            require(c.startswith(MAGIC) and sha(c)==e['cipher_sha256'] and len(c)==e['cipher_bytes'],'CIPHERTEXT_CORRUPT')
            require(e['last_ordinal']>self.state['last_ordinal'],'RECOVERY_ORDER')
            self.state['batches'].append(e);self.state['cipher_bytes']+=len(c);self.state['last_ordinal']=e['last_ordinal']
        require(len(list(self.root.glob('*.telemetry-sealed')))==len(self.state['batches']),'UNCOMMITTED_CIPHERTEXT')
        require(self.state['cipher_bytes']<=self.max_bytes,'RECOVERY_BUDGET')
        atomic(self.root/'checkpoint.json',canonical(self.state))
        return dict(self.state,network_resume_authorized=False,unflushed_records='UNKNOWN_LOST_IF_PROCESS_CRASHED')

class Capture:
    """One-way recorder. Public diagnostics contain counts only, never prices."""
    def __init__(self,p,start_ns,end_ns,store):
        self.p=p;self.start=start_ns;self.end=end_ns;self.store=store
        self.ordinal=0;self.bytes=0;self.requests=0;self.buffer=[];self.clock=Clock()
        self.seen=set();self.events={};self.bars={};self.sides={};self.initial=set();self.counts={}
        self.request_sequence=0;self.last_pair=None;self.closed=False
    def count(self,k): self.counts[k]=self.counts.get(k,0)+1
    def request(self,name):
        require(not self.closed,'CLOSED')
        require(name in ALLOWED,'REQUEST_NOT_ALLOWED')
        require(self.requests<self.p['limits']['max_requests'],'REQUEST_BUDGET')
        self.requests+=1
    def mark_connection_loss(self): self.count('CONNECTION_LOSS_INCOMPLETE');self.closed=True
    def ingest(self,raw,event,pair):
        require(not self.closed,'CLOSED')
        require(set(pair)=={'mono_ns','utc_ns','uncertainty_ns','utc_lower_ns','utc_upper_ns','witness'},'PAIR_FIELDS')
        require(pair==self.clock.last,'UNPAIRED_CLOCK')
        require(0<=pair['uncertainty_ns']<=50_000_000,'CLOCK_UNCERTAINTY')
        require(pair['utc_lower_ns']>=self.start and pair['utc_upper_ns']<self.end,'RECEIPT_OUTSIDE_SCOPE')
        if self.last_pair:
            require(pair['mono_ns']>self.last_pair['mono_ns'],'ARRIVAL_MONOTONIC')
            require(pair['mono_ns']-self.last_pair['mono_ns']<=self.p['limits']['max_idle_ns'],'IDLE_TIMEOUT')
        self.last_pair=pair
        require(len(raw)<=self.p['limits']['max_frame_bytes'],'FRAME_BUDGET')
        require(self.ordinal<self.p['limits']['max_messages'],'MESSAGE_BUDGET')
        require(self.bytes+len(raw)<=self.p['limits']['max_raw_bytes'],'RAW_BYTE_BUDGET')
        require(set(event)<= {'kind','symbol_id','provider_ms','bid','ask','bars'},'UNEXPECTED_FIELDS')
        require(event.get('kind')=='SPOT','EVENT_TYPE')
        sid=event['symbol_id'];require(sid in {x['symbol_id'] for x in self.p['roster']},'IDENTITY_OUTSIDE_SCOPE')
        require(type(event.get('provider_ms')) is int,'PROVIDER_TIMESTAMP_MISSING')
        et=event['provider_ms']*1_000_000
        require(self.start<=et<self.end,'EVENT_OUTSIDE_SCOPE')
        require(et<=pair['utc_upper_ns'],'EVENT_AFTER_RECEIPT_BOUND')
        flags=[]
        if sid not in self.initial:
            self.initial.add(sid);flags.append('INITIAL_SNAPSHOT_UNTRUSTED_FRESHNESS')
        h=sha(raw)
        if h in self.seen: flags.append('PAYLOAD_DUPLICATE_NOT_PROVIDER_ID_PROOF')
        self.seen.add(h)
        previous=self.events.get(sid)
        if previous is not None and et<previous: flags.append('OUT_OF_ORDER_PROVIDER_TIME')
        if pair['utc_lower_ns']-et>self.p['limits']['max_side_age_ns']: flags.append('LATE_OR_STALE')
        self.events[sid]=max(et,previous or et)
        for bar in event.get('bars',[]):
            require(set(bar)=={'open_minute','period','low','deltaOpen','deltaHigh','deltaClose','volume'},'BAR_FIELDS')
            require(all(type(bar[k]) is int and bar[k]>=0 for k in ['open_minute','low','deltaOpen','deltaHigh','deltaClose','volume']),'BAR_INTEGERS')
            require(bar['low']>0 and max(bar['deltaOpen'],bar['deltaClose'])<=bar['deltaHigh'],'BAR_OHLC')
            require(bar['period']=='M5','BAR_PERIOD'); opening=bar['open_minute']*60_000_000_000
            close=opening+300_000_000_000
            require(opening%300_000_000_000==0 and self.start<=opening<self.end,'BAR_SCOPE')
            require(close<=pair['utc_lower_ns'],'INCOMPLETE_BAR')
            bh=sha(canonical(bar));key=(sid,opening)
            if key in self.bars and self.bars[key]!=bh:flags.append('OBSERVED_BAR_REVISION')
            elif key in self.bars: flags.append('REPEATED_BAR_DELIVERY')
            self.bars[key]=bh
        sides=self.sides.setdefault(sid,{})
        for side in ['bid','ask']:
            if side in event:
                require(type(event[side]) is int and event[side]>0,'INVALID_QUOTE')
                # A delayed side never overwrites a causally newer state.
                if side not in sides or et>=sides[side]['event_ns']:
                    sides[side]={'raw':event[side],'event_ns':et,'receipt_upper_ns':pair['utc_upper_ns'],'initial':len(flags)>0 and flags[0]=='INITIAL_SNAPSHOT_UNTRUSTED_FRESHNESS'}
        valid=all(k in sides for k in ['bid','ask'])
        valid=valid and all(not s['initial'] and 0<=pair['utc_upper_ns']-s['event_ns']<=self.p['limits']['max_side_age_ns'] for s in sides.values())
        valid=valid and sides['ask']['raw']>=sides['bid']['raw'] if valid else False
        if not valid: flags.append('SPREAD_UNAVAILABLE_OR_STALE_OR_CROSSED')
        record={'namespace':NAMESPACE,'arrival_ordinal':self.ordinal+1,'receipt':pair,'provider_fields':event,'raw_envelope_b64':base64.b64encode(raw).decode(),'payload_sha256':h,'flags':flags,'quoted_spread_raw':sides['ask']['raw']-sides['bid']['raw'] if valid else None,'fill_or_slippage_claim':False,'original_historical_available_at':'NOT_APPLICABLE_LIVE_ONLY'}
        self.ordinal+=1;self.bytes+=len(raw);self.buffer.append(record)
        for f in flags:self.count(f)
        if len(self.buffer)>=self.p['limits']['batch_messages']:self.flush()
        return flags  # No price values in diagnostics.
    def flush(self):
        if self.buffer:self.store.commit(self.buffer);self.buffer=[]
    def finish(self):
        self.flush();self.closed=True
        expected=set(range(self.start,self.end-300_000_000_000,300_000_000_000))
        missing=sum(len(expected-{opening for sid2,opening in self.bars if sid2==sid}) for sid in {x['symbol_id'] for x in self.p['roster']})
        self.counts['EXPECTED_GRID_BARS_NOT_OBSERVED']=missing
        return {'namespace':NAMESPACE,'messages':self.ordinal,'raw_bytes':self.bytes,'requests':self.requests,'counts':dict(self.counts),'upstream_completeness_proven':False,'payload_values_exported':False,'economic_response_access':False}
