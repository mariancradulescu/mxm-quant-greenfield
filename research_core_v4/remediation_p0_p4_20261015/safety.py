"""Fail-closed primitives; pure functions except explicit local SQLite fencing."""
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import re
import sqlite3
import subprocess

BRANCH = 'mxm-remediation-p0-p4-20261015-v1'
BASE = '3cb073e54fe3189063c2737c6337d3404b713710'
CANONICAL = '9c5f9f1b7f2d73f98bb188a2651fd9a3c00df6b9'
JOURNAL = 'ea93f6c38768824521d4ad3e316c0cd507c837e5c089c5e3b6f63d20d79e7470'

def require(ok, code):
    if not ok:
        raise ValueError(code)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def strict_json(raw, max_depth=64, max_elements=2000000):
    def pairs(kv):
        d = {}
        for k,v in kv:
            require(k not in d, 'DUPLICATE_JSON_KEY');d[k]=v
        return d
    x=json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: require(False,'NONFINITE_JSON'))
    stack=[(x,0)];n=0
    while stack:
        v,d=stack.pop();n+=1
        require(d<=max_depth and n<=max_elements,'JSON_STRUCTURE_LIMIT')
        if isinstance(v,float):require(math.isfinite(v),'NONFINITE_JSON')
        if isinstance(v,dict):stack.extend((z,d+1) for z in v.values())
        elif isinstance(v,list):stack.extend((z,d+1) for z in v)
    return x

def unpack(packed, max_bytes=128*1024*1024, max_ratio=1000):
    limit=min(max_bytes,max(1,len(packed))*max_ratio)
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as f:
        raw=f.read(limit+1)
        require(len(raw)<=limit,'DECOMPRESSION_LIMIT')
        require(not f.read(1),'DECOMPRESSION_LIMIT')
    return raw

def safe_error(exc):
    # Do not copy exception text, protocol bodies, stack locals or secrets.
    allowed={'TimeoutError':'RESPONSE_DEADLINE','ConnectionError':'CONNECTION_UNKNOWN','ValueError':'VALIDATION_REJECTED'}
    return {'category':allowed.get(type(exc).__name__,'UNCLASSIFIED_EXCEPTION')}

def terminal(failed,budgets,normal='BATCH_COMPLETE_READY_FOR_HANDOFF',other=()):
    causes=list(other)
    if failed:causes.insert(0,'STOP_FAIL_CLOSED')
    if min(budgets.values())<=0:causes.append('STOP_GLOBAL_BUDGET')
    return {'state':causes[0] if causes else normal,'causes':list(dict.fromkeys(causes)),'failure':failed,'ready':not causes and normal=='BATCH_COMPLETE_READY_FOR_HANDOFF'}

def request_identity(req):
    fields=('account','server','s','k','a','b','sequence')
    require(all(k in req for k in fields),'REQUEST_IDENTITY_MISSING')
    return sha(canonical({k:req[k] for k in fields}))

def bind_failure(item,evidence):
    # Equality of the full identity, never last_evidence or symbol alone.
    try:
        h=request_identity(item['request']);e=request_identity(evidence['request'])
        require(h==e and evidence.get('request_hash')==h,'EVIDENCE_UNBOUND')
        return {'state':'REQUEST_BOUND','request_hash':h,'evidence':evidence}
    except (ValueError,KeyError,TypeError):
        return {'state':'EVIDENCE_UNBOUND'}

class ReadOnlyAPI:
    def __init__(self,api,release_ids):self.api=api;self.ids=set(map(str,release_ids))
    def __call__(self,path,method='GET',data=None):
        require(method in ('GET','HEAD') and data is None,'READER_MUTATION_DENIED')
        m=re.fullmatch(r'releases/(\d+)(?:/assets(?:\?per_page=100&page=\d+)?)?',path)
        a=re.fullmatch(r'releases/assets/(\d+)',path)
        require(m is not None and m[1] in self.ids or a is not None and a[1] in self.ids,'READER_NAMESPACE_DENIED')
        return self.api(path,method,data)

def clean_tree(root):
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root,text=True)
    require(not dirty,'DIRTY_SOURCE_BEFORE_SECRET')

class Fence:
    """Local durable CAS oracle. Production release PATCH is NOT an atomic CAS.

    This is the transaction used by offline successors. Live anchor writes remain
    prohibited; no claim that SQLite fences unrelated legacy GitHub credentials.
    """
    def __init__(self,path):
        self.db=sqlite3.connect(path,timeout=5)
        self.db.execute('CREATE TABLE IF NOT EXISTS fence(id INTEGER PRIMARY KEY CHECK(id=1),generation INTEGER,hash TEXT,epoch INTEGER,claim TEXT)')
        self.db.commit()
    def initialize(self,g,h):
        self.db.execute('INSERT OR IGNORE INTO fence VALUES(1,?,?,0,NULL)',(g,h));self.db.commit()
    def claim(self,g,h,writer):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            r=self.db.execute('SELECT generation,hash,epoch,claim FROM fence').fetchone()
            require(r and r[0]==g and r[1]==h and r[3] is None,'STALE_OR_CLAIMED_FENCE')
            self.db.execute('UPDATE fence SET epoch=epoch+1,claim=? WHERE id=1',(writer,))
            return r[2]+1
    def commit(self,g,h,epoch,writer,new_hash):
        with self.db:
            c=self.db.execute('UPDATE fence SET generation=generation+1,hash=?,claim=NULL WHERE generation=? AND hash=? AND epoch=? AND claim=?',(new_hash,g,h,epoch,writer))
            require(c.rowcount==1,'FENCE_CAS_REJECTED')

# Broker grants cannot be inferred from historical flags or compile SUCCESS.
def authorize(action,authority,context):
    allowed={'offline_tests','owner_readback','successor_patch'}
    require(action in allowed and authority.get('role')=='REMEDIATION_ONLY','ACTION_DENIED')
    require(context['branch']==BRANCH and context['attempt']==1,'SCOPE_DENIED')
    require(dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(authority['expires']),'AUTHORITY_EXPIRED')
    require(authority.get('head')==context.get('head'),'HEAD_DENIED')
    return True
