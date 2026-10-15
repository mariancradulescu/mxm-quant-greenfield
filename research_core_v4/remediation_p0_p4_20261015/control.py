"""Explicit successor state machines. All fixtures are synthetic, all IO local."""
import json
import pathlib
import sqlite3
from .safety import require,canonical,sha,JOURNAL

def resolve(authorities,stage,head):
    require(stage in ('readiness','discovery','confirmation','economic','execution','Cloud','Stage8','protected_forward'),'UNKNOWN_STAGE')
    current=[a for a in authorities if a.get('current') is True and a.get('head')==head and a.get('scope')==stage]
    if len(current)!=1:return {'state':'DENY_CONFLICT_OR_MISSING','refs':[a.get('digest') for a in authorities],'alpha_certified':False,'Cloud_deployed':False}
    a=current[0]
    # Remediation acceptance never grants research or execution, including stale ARM.
    deny=stage!='readiness' or a.get('expired') or a.get('consumed') or a.get('state')!='REMEDIATION_ONLY'
    return {'state':'STOP' if deny else 'READINESS_ONLY','refs':[x.get('digest') for x in authorities],'alpha_certified':False,'Cloud_deployed':False}

class RequestLedger:
    def __init__(self,path):
        self.db=sqlite3.connect(path);self.db.execute('CREATE TABLE IF NOT EXISTS request(h TEXT PRIMARY KEY,identity BLOB,state TEXT,receipt TEXT,phase TEXT)');self.db.commit()
    def prepare(self,identity):
        from .safety import request_identity
        h=request_identity(identity)
        with self.db:self.db.execute('INSERT INTO request VALUES(?,?,?,NULL,?)',(h,canonical(identity),'NOT_SENT','prepare'))
        return h
    def send_boundary(self,h):
        # Commit uncertainty BEFORE a transport can observe the request. A crash
        # in this gap is ambiguous, never declared definitely sent or replayable.
        with self.db:
            n=self.db.execute("UPDATE request SET state='SENT_UNKNOWN',phase='send_boundary' WHERE h=? AND state='NOT_SENT'",(h,)).rowcount
            require(n==1,'REQUEST_REPLAY_DENIED')
    def accept(self,h,response_hash):
        require(isinstance(response_hash,str) and len(response_hash)==64,'RECEIPT_HASH_REQUIRED')
        with self.db:
            n=self.db.execute("UPDATE request SET state='RESPONSE_ACCEPTED',receipt=?,phase='receipt' WHERE h=? AND state='SENT_UNKNOWN'",(response_hash,h)).rowcount
            require(n==1,'RECEIPT_TRANSITION_DENIED')
    def counters(self):
        rows=self.db.execute('SELECT state FROM request').fetchall();states=[r[0] for r in rows]
        return {'attempted':len(rows),'sent_or_uncertain':sum(z!='NOT_SENT' for z in states),'acknowledged':states.count('RESPONSE_ACCEPTED'),'uncertain':states.count('SENT_UNKNOWN'),'definitely_sent':None}

def segment_budget(sequence,already_sent,expires,now):
    require(type(sequence) is int and 1<=sequence<=26,'STOP_FINITE_SEGMENT')
    require(now<expires,'AUTHORITY_EXPIRED')
    require(type(already_sent) is int and 0<=already_sent<6656,'STOP_GLOBAL_BUDGET')
    return min(256,6656-already_sent)

def job_milestone(x):
    required=('observed_at_utc','run_id','attempt','HEAD','generation','anchor_sha','state')
    require(all(k in x for k in required),'REPORT_BINDING_MISSING')
    from .provenance import timestamp
    timestamp(x['observed_at_utc'])
    if x.get('run_status')!='completed' or x.get('pending',1)!=0:return 'IN_FLIGHT'
    require(x.get('anchor_after')==x['anchor_sha'] and x.get('matched_get') is True,'UNSTABLE_ANCHOR')
    return 'TERMINAL'

def lookup(api,release_id,asset_id,digest):
    inventory=[];page=1
    while True:
        rows=api(f'releases/{release_id}/assets?per_page=100&page={page}')
        require(isinstance(rows,list),'INVENTORY_MALFORMED')
        inventory+=rows
        if len(rows)<100:break
        page+=1;require(page<=100,'INVENTORY_LIMIT_UNKNOWN')
    found=[a for a in inventory if a['id']==asset_id]
    require(len(found)==1,'ASSET_ABSENT_OR_AMBIGUOUS')
    a=found[0];require(a.get('digest')=='sha256:'+digest,'ASSET_DIGEST_MISMATCH')
    require(len([v for v in inventory if v.get('name')==a.get('name')])==1,'AMBIGUOUS_ASSET')
    return a

def read_source(api,path):
    import urllib.error
    try:
        result=api(path)
        if isinstance(result,str):result=json.loads(result)
        require(isinstance(result,dict),'SOURCE_MALFORMED');return {'state':'AVAILABLE','value':result}
    except urllib.error.HTTPError as ex:return {'state':'SOURCE_ABSENT' if ex.code==404 else 'NETWORK_UNKNOWN'}
    except (ValueError,TypeError):return {'state':'SOURCE_MALFORMED'}
    except Exception:return {'state':'NETWORK_UNKNOWN'}

def quote_observed(db,sid,t,ttl=300000):
    from research_core_v4.critical_frontier_repair_20261014_v2 import archive_v2 as ar
    if ar.missing(db,sid,'bid',t,t) or ar.missing(db,sid,'ask',t,t):return {'state':'UNKNOWN_COVERAGE','observed':False}
    values={}
    for side in ('bid','ask'):
        rows=db.execute('SELECT t,p FROM tick WHERE s=? AND k=? AND t<=? ORDER BY t DESC',(sid,side,t)).fetchall()
        if not rows:return {'state':'EMPTY','observed':False}
        tm=rows[0][0];prices={p for tt,p in rows if tt==tm}
        if len(prices)!=1:return {'state':'CONFLICTED','observed':False}
        if t-tm>ttl:return {'state':'STALE','observed':False}
        values[side]=next(iter(prices))
    if values['bid']<=0 or values['bid']>values['ask']:return {'state':'INVALID_CROSSED','observed':False}
    return {'state':'QUOTE_OBSERVED_NOT_FILL','observed':True}

def domain_event(t,h,start,end):
    require(start<=t<end,'ENTRY_OUTSIDE_DOMAIN')
    return 'DOMAIN_CENSORED' if t+h>=end else 'IN_DOMAIN'

def cohorts(rows,horizon,slippage):
    rows=[r for r in rows if r['h']==horizon and r['slip']==slippage]
    def pop(items):return {'n':len(items),'row_set_sha256':sha(canonical(sorted(r['id'] for r in items)))}
    cost=[r for r in rows if r.get('cost_known')];entry=[r for r in cost if r.get('entry')];exit=[r for r in entry if r.get('exit')];path=[r for r in exit if r.get('path')]
    return {'horizon':horizon,'slippage':slippage,'all_cost_observable':pop(cost),'entry_feasible':pop(entry),'exit_observed':pop(exit),'path_complete':pop(path),'missing_outcome':'NOT_EVALUATED','NET':None}

def provenance_predicates(cipher=False,owner=False,producer=False,broker=False):
    return {'cipher_integrity':cipher,'OWNER_readback':owner,'authenticated_producer':producer,'broker_semantics':broker,'NET_true':False,'alpha_certified':False}

def exposure(kind,authentic=False):
    allowed={'market_data','personal_info','credentials','synthetic_private_key_header'}
    require(kind in allowed,'EXPOSURE_CLASS_UNKNOWN')
    return {'class':kind,'confirmed_compromise':kind=='credentials' and authentic,'action':'STOP_REPORT_NO_ROTATION' if kind=='credentials' and authentic else 'RESTRICTED_REVIEW_REQUIRED' if kind!='synthetic_private_key_header' else 'SYNTHETIC_NOT_INCIDENT','rotate_authorized':False}

def source_inventory(root):
    # Scan every file, including proto, dynamic helper and binaries, not just imports.
    return {p.relative_to(root).as_posix():sha(p.read_bytes()) for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}

def compare_inventory(root,expected):
    actual=source_inventory(root);require(actual==expected,'SOURCE_OR_DEPENDENCY_DIGEST_DRIFT');return actual

def exact_state(record):
    require(record.get('spec_id') and record.get('family_id'),'EXACT_ID_MISSING')
    if record.get('closed_exact'):return 'CLOSED_EXACT_BROADER_UNTESTED'
    if record.get('outcome') is None:return 'PLANNED_NOT_TESTED'
    require(all(record.get(k) for k in ('design_sha256','run_id','job_id','artifact_sha256')),'EXECUTION_LINEAGE_MISSING')
    require(record['freeze_time']<record['outcome_time'],'OUTCOME_BEFORE_FREEZE')
    return 'EXECUTED_NOT_INDEPENDENTLY_AUDITED'

def partition_population(parent,parts):
    parent=set(parent);seen=set()
    for name,ids in parts.items():
        ids=set(ids);require(not (seen&ids),'POPULATION_OVERLAP');require(ids<=parent,'POPULATION_FOREIGN_ID');seen|=ids
    require(seen==parent,'POPULATION_DISAPPEARED')
    return {name:{'n':len(ids),'membership_sha256':sha(canonical(sorted(ids)))} for name,ids in parts.items()}

def calendar_range(start,end,regime,first_seen):
    from .provenance import timestamp
    a,b=timestamp(start),timestamp(end);require(a<b and first_seen<=a,'CALENDAR_CHRONOLOGY')
    require(regime in ('ALTERNATE_40_WEEKS','THU_TO_THU_4_BLOCKS','ISO_W35_W37_DEVELOPMENT'),'CALENDAR_REGIME_UNKNOWN')
    return {'from_utc':a,'to_exclusive_utc':b,'regime':regime,'use':'DEVELOPMENT','confirmation_eligible':False}

def executable_inventory(root):
    import ast,subprocess,sys
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
    sources={};imports=[];missing=[]
    for rel in tracked:
        if not rel:continue
        path=root/rel
        if not path.is_file():missing.append({'path':rel,'state':'TRACKED_SOURCE_ABSENT'});continue
        if path.suffix in ('.py','.proto','.cs','.csproj','.json','.yml','.yaml','.dll','.algo','.lock'):
            sources[rel]=sha(path.read_bytes())
        if path.suffix=='.py':
            try:tree=ast.parse(path.read_bytes())
            except SyntaxError:missing.append({'path':rel,'state':'LEGACY_SYNTAX_ERROR_INERT'});continue
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):imports.extend({'from':rel,'import':a.name,'state':'STATIC_REFERENCE'} for a in node.names)
                elif isinstance(node,ast.ImportFrom):imports.append({'from':rel,'import':'.'*node.level+(node.module or ''),'state':'STATIC_REFERENCE'})
                elif isinstance(node,ast.Call) and isinstance(node.func,(ast.Name,ast.Attribute)) and getattr(node.func,'id',getattr(node.func,'attr','')) in ('exec','eval','__import__','import_module'):
                    missing.append({'path':rel,'line':node.lineno,'state':'DYNAMIC_EDGE_REQUIRES_REVIEW_NO_EXHAUSTIVE_GRAPH_CLAIM'})
    loaded={}
    for name,module in list(sys.modules.items()):
        p=getattr(module,'__file__',None)
        if p:
            try:rel=pathlib.Path(p).resolve().relative_to(root.resolve()).as_posix()
            except ValueError:continue
            path=root/rel
            if path.is_file():loaded[rel]=sha(path.read_bytes())
    return {'source_sha256':sources,'static_import_edges':imports,'loaded_runtime_sha256':loaded,'unresolved':missing,'external_build_dependencies':'requirements.lock;CSharp_Contract_no_NuGet_dependencies','scope':'ALL_TRACKED_EXECUTABLE_AND_STRUCTURED_SOURCES;DYNAMIC_EDGES_FLAGGED_NOT_ASSUMED_CLOSED'}

def artifact_chain(producer,consumer,ancestor):
    required=('head','run_id','job_id','artifact_sha256','artifact_size','artifact_name')
    require(all(k in producer and k in consumer for k in required),'ARTIFACT_CHAIN_MISSING')
    require(all(producer[k]==consumer[k] for k in ('artifact_sha256','artifact_size','artifact_name')) and producer['artifact_size']>0,'ARTIFACT_CHAIN_DIGEST')
    require(ancestor(producer['head'],consumer['head']),'ARTIFACT_CHAIN_ANCESTRY')
    return {'producer_job_id':producer['job_id'],'consumer_job_id':consumer['job_id'],'state':'PACKAGE_READY_ONLY','cloud_executed':False}

def segment_chain(entries,max_segments=26):
    by={e['sequence']:e for e in entries};require(len(by)==len(entries),'DUPLICATE_SEGMENT_RECEIPT')
    result=[]
    for i in range(1,max_segments+1):
        e=by.get(i)
        if e is None:result.append({'sequence':i,'state':'ABSENT'});continue
        require(all(e.get(k) for k in ('run_id','journal_sha256','postsegment_sha256')),'SEGMENT_EVIDENCE_MISSING')
        result.append({**e,'state':'OBSERVED_RECEIPT_NOT_ALPHA'})
    return result
