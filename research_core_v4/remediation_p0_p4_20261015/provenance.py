"""Typed source bindings for preserved data, never inferred from release names."""
from dataclasses import dataclass
import datetime as dt
import math
from .safety import require, canonical, sha

FAMILIES={'M5':'ProtoOAGetTrendbarsRes','BID':'ProtoOAGetTickDataRes','ASK':'ProtoOAGetTickDataRes','DOM':'ProtoOADepthEvent','ACTUAL_FILL':'ProtoOAExecutionEvent','TICK_VOLUME':'ProtoOATrendbar.volume'}

def timestamp(value,unit='seconds'):
    require(unit in ('seconds','milliseconds'),'TIME_UNIT_UNKNOWN')
    if isinstance(value,str):
        x=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        require(x.tzinfo is not None and x.utcoffset() is not None,'TIMEZONE_REQUIRED')
        value=x.timestamp()*(1000 if unit=='milliseconds' else 1)
    require(not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value) and int(value)==value,'TIME_PRECISION')
    seconds=value/(1000 if unit=='milliseconds' else 1)
    require(946684800<=seconds<4102444800,'TIME_UNIT_OR_DOMAIN')
    return int(value)

@dataclass(frozen=True)
class Envelope:
    account: str
    server: str
    environment: str
    symbol: int
    family: str
    unit: str
    clock: str
    transform: str
    source_hash: str
    request_hash: str
    protocol: str
    def validate(self,expected):
        require(self.family in FAMILIES and self.protocol==FAMILIES[self.family],'SEMANTIC_TYPE_MISMATCH')
        require(all((self.account,self.server,self.unit,self.transform)) and self.clock=='UTC','PROVENANCE_MISSING')
        require(self.environment=='LIVE','WRONG_ENVIRONMENT')
        require((self.account,self.server,self.symbol)==expected,'SOURCE_IDENTITY_MISMATCH')
        require(len(self.source_hash)==64 and len(self.request_hash)==64,'SOURCE_HASH_MISSING')
        return self
    def as_type(self,family):
        require(family==self.family,'SEMANTIC_SUBSTITUTION_DENIED');return self

def coverage(has_more,rows,authenticated=False):
    if not authenticated:return 'UNKNOWN_TRANSPORT'
    if type(has_more) is not bool:return 'UNKNOWN_TRANSPORT_HASMORE_FIELD_ABSENT'
    if has_more:return 'PARTIAL_HASMORE'
    return 'CONFIRMED_COMPLETE' if rows else 'EMPTY_AUTHENTIC_RESPONSE'

def reconcile_response(request,response):
    keys=('account','clientMsgId','payloadType','request_hash')
    return 'BOUND' if all(k in request and request[k]==response.get(k) for k in keys) else 'EVIDENCE_UNBOUND'

def atomic_ingest(db,envelope,expected,raw,rows,has_more,start,end):
    """Only admitted rows with a caller-verified immutable receipt enter this path.

    Envelope provenance is structural; cryptographic OWNER decoding must be done
    by the runner before this function. This API cannot certify broker origin.
    """
    from research_core_v4.critical_frontier_repair_20261014_v2 import archive_v2 as ar
    envelope.validate(expected);require(sha(raw)==envelope.source_hash,'RAW_DIGEST_MISMATCH')
    require(envelope.family=='M5' and start<end and start%300==0 and end%300==0,'M5_GRID')
    db.execute('SAVEPOINT native_ingest')
    try:
        db.execute('CREATE TABLE IF NOT EXISTS source_receipt(h TEXT PRIMARY KEY,envelope TEXT,raw_hash TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS row_source(s INTEGER,t INTEGER,h TEXT,PRIMARY KEY(s,t))')
        for t,values in rows:
            require(start<=t<end,'ROW_WINDOW')
            ar.putbar(db,envelope.symbol,t,values)
            old=db.execute('SELECT h FROM row_source WHERE s=? AND t=?',(envelope.symbol,t)).fetchone()
            require(old is None or old[0]==envelope.source_hash,'ROW_SOURCE_CONFLICT')
            db.execute('INSERT OR IGNORE INTO row_source VALUES(?,?,?)',(envelope.symbol,t,envelope.source_hash))
        db.execute('INSERT OR IGNORE INTO source_receipt VALUES(?,?,?)',(envelope.source_hash,canonical(envelope.__dict__).decode(),sha(raw)))
        state=coverage(has_more,rows,True)
        ar.span(db,envelope.symbol,'M5',start*1000,end*1000-1,state)
        db.execute('RELEASE native_ingest')
        return state
    except BaseException:
        db.execute('ROLLBACK TO native_ingest');db.execute('RELEASE native_ingest');raise

def time_evidence(value,unit='seconds'):
    """Preserve declared source zone/unit alongside one canonical instant."""
    instant=timestamp(value,unit)
    if isinstance(value,str):
        original=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        offset=int(original.utcoffset().total_seconds());source_zone='Z' if value.endswith('Z') else original.isoformat()[-6:]
    else:offset=0;source_zone='UTC_EPOCH_DECLARED'
    return {'utc_ms':instant*1000 if unit=='seconds' else instant,'source_unit':unit,'source_precision':'INTEGER','source_zone':source_zone,'source_offset_seconds':offset}
