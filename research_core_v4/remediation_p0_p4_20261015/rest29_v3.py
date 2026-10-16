"""Targeted restoration of remaining receipts. No broker, writer or outcome replay.

Only GET can cross this process's HTTP boundary. Existing dataset/envelope bytes
remain immutable. All detailed locators, events and request evidence are encrypted.
"""
import ast
import base64
import concurrent.futures
import contextlib
import csv
import gzip
import io
import json
import os
import pathlib
import re
import struct
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter,defaultdict
from .safety import require,sha,canonical,strict_json,unpack,BRANCH,CANONICAL,JOURNAL,bind_failure,clean_tree

REPO='mariancradulescu/mxm-quant-greenfield'
ROOT=pathlib.Path(__file__).resolve().parents[2]
PREVIOUS='ca0853b5e491265048dbb23b8c61d452da367ee2'
ARTIFACT=12024388850
ARTIFACT_SHA='56fde470633fa08e8831c59b442a3a3f6a478fc0b926965cd349bf2586354ba4'
FP='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'
MAX_ASSETS=2048

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        require(urllib.parse.urlsplit(newurl).scheme=='https','REST29_REDIRECT_SCHEME')
        new=super().redirect_request(req,fp,code,msg,headers,newurl)
        if urllib.parse.urlsplit(newurl).hostname!='api.github.com':new.remove_header('Authorization')
        return new

class GetOnly:
    def __init__(self):self.methods=Counter();self.paths=Counter();self.lock=threading.Lock();self.opener=urllib.request.build_opener(Redirect())
    def open(self,req,timeout=60,**kwargs):
        if isinstance(req,str):req=urllib.request.Request(req)
        method=req.get_method();u=urllib.parse.urlsplit(req.full_url)
        require(method=='GET' and req.data is None,'REST29_READER_MUTATION_DENIED')
        require(u.scheme=='https' and u.hostname in ('api.github.com','github.com'),'REST29_HTTP_NAMESPACE')
        if u.hostname=='api.github.com':require(u.path.startswith('/repos/'+REPO+'/'),'REST29_API_NAMESPACE')
        else:require(u.path.startswith('/'+REPO+'/releases/download/'),'REST29_ASSET_NAMESPACE')
        with self.lock:self.methods[method]+=1;self.paths[u.path]+=1
        return self.opener.open(req,timeout=timeout)
    def data(self,path,limit=16*1024*1024):
        req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
        with self.open(req) as r:raw=r.read(limit+1)
        require(len(raw)<=limit,'REST29_HTTP_SIZE_LIMIT');return raw
    def json(self,path):return strict_json(self.data(path),max_elements=8000000)

def overlaps(a,b,c,d):return a<=d and c<=b

def raw_domain(raw):
    q=raw.get('request',{})
    if all(k in q for k in ('s','k','a','b')):return q
    return None

def raw_receipt(raw,asset_id):
    """Decode preserved bytes only; no reconstructed broker response or request."""
    from research_core_v4 import shallow_m5_support_v2 as protocol
    from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAGetTickDataRes
    d={'asset_id':asset_id,'raw_sha256':sha(canonical(raw)),'request':raw.get('request'),'recorded_state':raw.get('state'),'recorded_exception':raw.get('exception_class'),'dispatch_binding':'UNKNOWN_LEGACY_NO_CLIENT_REQUEST_ENVELOPE','original_changed':False}
    evidence=raw.get('preserved_failure_evidence')
    if evidence is not None:
        ev=evidence.get('evidence',evidence) if isinstance(evidence,dict) else {}
        d['failure_binding']=bind_failure(raw,ev)['state'];d['preserved_failure_evidence']=evidence
        d['physical_cause']='UNKNOWN' if d['failure_binding']!='REQUEST_BOUND' else 'BOUND_RECORDED_EXCEPTION_NOT_ROOT_CAUSE_CERTIFICATION'
    try:
        if raw.get('response_envelope_b64'):
            blob=base64.b64decode(raw['response_envelope_b64'],validate=True);env=protocol.ProtoMessage.FromString(blob)
            require(env.payloadType==protocol.PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE,'REST29_RAW_PAYLOAD_TYPE')
            res=protocol.ProtoOAGetTrendbarsResV2.FromString(env.payload)
            d.update(response_sha256=sha(blob),response_account=int(res.ctidTraderAccountId),response_symbol=int(res.symbolId) if res.HasField('symbolId') else None,response_period=int(res.period),has_more_present=res.HasField('hasMore'),has_more=bool(res.hasMore) if res.HasField('hasMore') else None,native_rows=len(res.trendbar),native_minutes=[int(x.utcTimestampInMinutes) for x in res.trendbar],client_msg_present=env.HasField('clientMsgId'))
        elif raw.get('response_b64'):
            blob=base64.b64decode(raw['response_b64'],validate=True);res=ProtoOAGetTickDataRes.FromString(blob)
            d.update(response_sha256=sha(blob),response_account=int(res.ctidTraderAccountId),has_more_present=res.HasField('hasMore'),has_more=bool(res.hasMore) if res.HasField('hasMore') else None,native_rows=len(res.tickData))
            from m6.cost_evidence import decode_ctrader_tick_page
            decoded=decode_ctrader_tick_page([{'timestamp':x.timestamp,'tick':x.tick} for x in res.tickData])
            d['native_tick_times_ms']=[x.timestamp_ms for x in decoded]
        else:d['response_state']='NO_PRESERVED_NATIVE_RESPONSE'
    except Exception as ex:d['response_state']='UNKNOWN_NATIVE_DECODE_'+type(ex).__name__
    q=d.get('request') or {}
    d['complete_source_identity']=all(q.get(k) is not None for k in ('account','server','s','k','a','b','sequence')) and bool(q.get('server'))
    d['promote_coverage']=False
    return d

def contact(event,conflicts,kind='campaign'):
    """Dependency envelope only. Never recompute a predictor, exit or PnL.

    M5 feature uses up to192 prior bars and prior sessions; without a stored
    exact input mask, a wall-clock short lookback would produce false no-impact.
    """
    ev=event.get('event',event)
    if not isinstance(ev,dict) or type(ev.get('sid')) is not int or type(ev.get('t')) is not int:return {'state':'UNKNOWN_EVENT_IDENTITY','event_sha256':sha(canonical(event))}
    sid,t=ev['sid'],ev['t']*1000
    known_ids='quote_ids' in ev.get('_native_accounting_context',{}) or 'ids' in ev
    ids=set(ev.get('_native_accounting_context',{}).get('quote_ids',ev.get('ids',[sid])))|{sid}
    hits=[];unknown=[]
    for i,c in enumerate(conflicts):
        cs,ck=c['key'];a,b=c['a'],c['b']
        if ck=='M5':hit=cs==sid and a<=t-305000
        else:
            in_time=overlaps(t-1800000,t+max(900000,int(ev.get('h',15))*60000),a,b)
            hit=cs in ids and in_time
            if not known_ids and cs!=sid and in_time:unknown.append(i)
        if hit:hits.append(i)
    return {'state':'POTENTIAL_INPUT_CONTACT_NOT_RECOMPUTED' if hits else 'UNKNOWN_FX_DEPENDENCY_MASK' if unknown else 'NO_CONFLICT_DOMAIN_CONTACT_WITHIN_DECLARED_DEPENDENCIES','event_sha256':sha(canonical(event)),'sid':sid,'t':ev['t'],'conflicts':hits,'unknown_dependency_conflicts':unknown,'dependency_mask':'CONSERVATIVE_HISTORICAL_INPUT_ENVELOPE;NOT_PROOF_OF_ACTUAL_VALUE_CHANGE','kind':kind,'old_entry_state':ev.get('entry',{}).get('state'),'old_net_unchanged':True}

def verify_chain(head,byid):
    seen=set();rows=[];meta=head
    while meta:
        aid=meta['id']
        require(aid not in seen,'REST29_LEDGER_CYCLE');seen.add(aid)
        if aid not in byid:return {'complete':False,'reason':'PARENT_ASSET_NOT_RECOVERED','missing_asset_id':aid,'nodes':rows}
        item=byid[aid]
        if item.get('state')!='OWNER_DECODED':return {'complete':False,'reason':'PARENT_NOT_OWNER_VERIFIED','missing_asset_id':aid,'nodes':rows}
        for field in ('ciphertext_sha256','gzip_sha256','canonical_sha256'):
            if field in meta:require(meta[field]==item['meta'][field],'REST29_PARENT_DIGEST_MISMATCH')
        rows.append(aid);meta=item.get('parent_ledger')
        require(len(rows)<=MAX_ASSETS,'REST29_CHAIN_LIMIT')
    return {'complete':True,'reason':'AUTHENTIC_PARENT_CHAIN_TERMINATES','nodes':rows}

def asset_rows(v):
    counts={k:len(v.get(k,[])) if isinstance(v.get(k,[]),(dict,list)) else None for k in ('bars','ticks','wire','spans','records')}
    bad=Counter()
    for row in v.get('bars',[]):
        if not isinstance(row,list) or len(row)!=7:bad['bar_schema']+=1
        elif type(row[1]) is not int or row[1]%300:bad['bar_time']+=1
    for row in v.get('ticks',[]):
        if not isinstance(row,list) or len(row)!=4:bad['tick_schema']+=1
        elif type(row[2]) is not int:bad['tick_time']+=1
    return {'rows':counts,'time_schema_errors':dict(bad),'transformed_rows':0,'original_changed':False,'missing_per_row_provenance':not bool(v.get('source_receipt'))}

def decrypt_artifact(transport,key,tmp,owner):
    from cryptography.hazmat.primitives import serialization,hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    blob=transport.data('actions/artifacts/'+str(ARTIFACT)+'/zip',limit=8*1024*1024);require(sha(blob)==ARTIFACT_SHA,'REST29_PRIOR_ARTIFACT_DIGEST')
    z=zipfile.ZipFile(io.BytesIO(blob));att=strict_json(z.read('owner-attestation.json'));statement=att['statement']
    pub=serialization.load_pem_public_key((ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem').read_bytes())
    pub.verify(base64.b64decode(att['signature_b64']),canonical(statement),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
    for name,digest in statement['evidence_digests'].items():require(sha(z.read(name))==digest,'REST29_PRIOR_SIGNED_FILE_DIGEST')
    summary=strict_json(z.read('resolution-summary.json'));proof=summary['private_evidence'];cipher=z.read(proof['file']);require(sha(cipher)==proof['ciphertext_sha256'],'REST29_PRIVATE_CIPHER')
    packed=owner.bounded_decrypt(cipher,key,tmp);require(sha(packed)==proof['gzip_sha256'],'REST29_PRIVATE_PACKED')
    raw=unpack(packed);require(sha(raw)==proof['canonical_sha256'],'REST29_PRIVATE_PLAIN')
    return strict_json(raw,max_elements=8000000),{'artifact_id':ARTIFACT,'artifact_sha256':ARTIFACT_SHA,'signature_verified':True,'canonical_sha256':sha(raw),'independent_acceptance':False}

def loose_read(asset,rid,key,tmp,owner,transport):
    """Authenticated release-cipher read; expected parent hashes checked later.

    A filename is only a discovery hint. It never establishes native provenance.
    """
    meta={'id':asset['id'],'name':asset['name'],'release_id':rid,'size':asset['size'],'ciphertext_sha256':asset.get('digest','').removeprefix('sha256:')}
    try:
        require(0<asset['size']<=128*1024*1024 and re.fullmatch('[0-9a-f]{64}',meta['ciphertext_sha256']),'REST29_ASSET_SIZE_OR_DIGEST')
        with transport.open(asset['browser_download_url'],timeout=90) as r:blob=r.read(asset['size']+1)
        require(len(blob)==asset['size'] and sha(blob)==meta['ciphertext_sha256'],'REST29_CIPHER_DIGEST')
        packed=owner.bounded_decrypt(blob,key,tmp);raw=unpack(packed) if packed.startswith(b'\x1f\x8b') else packed
        meta.update(gzip_sha256=sha(packed),canonical_sha256=sha(raw));v=strict_json(raw,max_elements=8000000)
        return {'state':'OWNER_DECODED','meta':meta,'value':v}
    except Exception as ex:
        return {'state':'EVIDENCE_UNAVAILABLE','meta':meta,'reason':str(ex) if isinstance(ex,ValueError) and re.fullmatch('REST29_[A-Z0-9_]+',str(ex)) else type(ex).__name__}

def seal(value,key,tmp,owner,name):
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard
    out=ROOT/'verification';out.mkdir(exist_ok=True)
    raw=canonical(value);packed=gzip.compress(raw,mtime=0);p=out/name
    encrypt_shard(packed,public_key=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem',output=p)
    require(owner.bounded_decrypt(p.read_bytes(),key,tmp)==packed,'REST29_OUTPUT_OWNER_READBACK')
    return {'file':name,'ciphertext_sha256':sha(p.read_bytes()),'gzip_sha256':sha(packed),'canonical_sha256':sha(raw),'OWNER_readback':True}

def source_routes():
    rows=[]
    # All historical routes are catalogued as DENIED on this successor. The
    # active reader follows one explicit GET-only transport, no store constructor.
    catalog=strict_json((pathlib.Path(__file__).parent/'workflow_catalog.json').read_bytes())
    for w in catalog['workflows']:rows.append({'entrypoint':w['path'],'resolved_helper':'DENIED_HISTORICAL_WORKFLOW_STUB','REST':'NONE','scope':'SUCCESSOR_ONLY'})
    rows.append({'entrypoint':'rest29_v3.main','resolved_helper':'GetOnly.open -> urllib.request.OpenerDirector.open','REST':'GET_ONLY;NO_POST_PATCH_PUT_DELETE','scope':'ACTIVE_REMAINING_RECEIPT_READER'})
    return rows

def p0_limits(transport):
    endpoint='branches/'+BRANCH+'/protection'
    try:protection=transport.json(endpoint);admin={'state':'VISIBLE','digest':sha(canonical(protection))}
    except urllib.error.HTTPError as ex:admin={'state':'AUTHORITY_UNAVAILABLE','http_status':ex.code,'endpoint':endpoint}
    catalog=strict_json((pathlib.Path(__file__).parent/'workflow_catalog.json').read_bytes())
    writers=[{k:w.get(k) for k in ('path','original_permissions','original_job_permissions','original_concurrency','original_secrets','successor_state')} for w in catalog['workflows'] if 'write' in json.dumps([w.get('original_permissions'),w.get('original_job_permissions')])]
    return {'O04.1':{'status':'BLOCKED','classification':'AUTHORIZATION_NEEDED','reason':'Historical cross-branch writers retain their original source/authority. Releases PATCH has no expected-generation/hash atomic conditional commit; local SQLite and successor concurrency do not fence predecessor credentials. Global remedy requires authorized predecessor writer migration/disable and effective administrative access; neither is granted. No writer was activated.','historical_writer_paths':writers,'single_writer_global_demonstrated':False},'N10':admin,'G03.2':{'status':'BLOCKED','classification':'AUTHORIZATION_NEEDED','reason':'No independently administered auditor public key/ACL trust root is installed. Existing OWNER key cannot represent a distinct auditor.'},'O05.2':{'status':'BLOCKED','classification':'AUTHORIZATION_NEEDED','reason':'No independently received signed supersession beyond P0-P4 remediation-only authority. Historical V4 authority remains unchanged.'}}

def scan_main(transport,key,tmp,owner,journal,previous):
    from .resolution import unique_metadata
    conflicts=previous['span_conflicts'];require(len(conflicts)==4,'REST29_EXPECTED_CONFLICT_SET')
    current=[];records={};wire={};wire_conflicts=[];raws=[]
    metas=unique_metadata(journal)
    for ix,meta in enumerate(metas.values()):
        v=owner.read_asset(meta,key,tmp);before=sha(canonical(v));stat=asset_rows(v)
        for row in v.get('wire',[]):
            k=tuple(row[:4]);val=tuple(row[4:]);old=wire.get(k)
            if old and old['value']!=val:wire_conflicts.append({'key':k,'before':old,'after':{'asset_id':meta['id'],'value':val}})
            else:wire[k]={'asset_id':meta['id'],'value':val}
        records.update(v.get('records',{}))
        for raw in v.get('raw',[]):raws.append(raw_receipt(raw,meta['id']))
        require(before==sha(canonical(v)),'REST29_SOURCE_CHANGED')
        current.append({'meta':meta,'before_sha256':before,'after_sha256':before,**stat})
        if ix%20==0:print(json.dumps({'phase':'REST29_CURRENT_RECEIPTS','inspected':ix+1,'total':len(metas)}),flush=True)
    events=[e for r in records.values() for e in r.get('events',[])]
    campaign=[contact(e,conflicts) for e in events]
    # Enumerate every existing native delta in the four authenticated storage
    # shards. Parallel decoding is read-only; parent hashes establish membership.
    assets=[];release_metadata=[]
    for index in range(4):
        rel=transport.json('releases/tags/mxm-native-frontier-repaired-20261014-v2-shard-'+str(index));rid=rel['id'];page=1;all_assets=[]
        while True:
            batch=transport.json(f'releases/{rid}/assets?per_page=100&page={page}');all_assets+=batch
            if len(batch)<100:break
            page+=1;require(page<=100,'REST29_PAGINATION_LIMIT')
        release_metadata.append({'id':rid,'tag_name':rel['tag_name'],'target_commitish':rel['target_commitish'],'author':rel['author']['login'],'created_at':rel['created_at'],'published_at':rel['published_at'],'asset_count':len(all_assets)})
        for a in all_assets:
            if re.search(r'(?:^|-)delta-\d+-',a['name']) and a['name'].endswith('.mxmenc'):assets.append((a,rid))
    require(len(assets)<=MAX_ASSETS,'REST29_DELTA_UNIVERSE_LIMIT')
    byid={};candidate_raw=[];delta_stats=[]
    def one(pair):
        a,rid=pair;rr=loose_read(a,rid,key,tmp,owner,transport)
        if rr['state']!='OWNER_DECODED':return {**rr,'parent_ledger':None,'raw':[],'spans':[],'wire':[]}
        v=rr.pop('value');matched=[]
        for raw in v.get('raw',[]):
            q=raw_domain(raw)
            if q and any(q['s']==c['key'][0] and q['k']==c['key'][1] and overlaps(q['a'],q['b'],c['a'],c['b']) for c in conflicts):matched.append(raw_receipt(raw,a['id']))
            elif raw.get('exception_class'):matched.append(raw_receipt(raw,a['id']))
        return {**rr,'parent_ledger':v.get('parent_ledger'),'raw':matched,'spans':[r for r in v.get('spans',[]) if any(r[0]==c['key'][0] and r[1]==c['key'][1] and overlaps(r[2],r[3],c['a'],c['b']) for c in conflicts)],'wire':[r for r in v.get('wire',[]) if any(r[0]==c['key'][0] and r[1]==c['key'][1] and overlaps(r[2],r[3],c['a'],c['b']) for c in conflicts)],'counts':asset_rows(v)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for ix,item in enumerate(pool.map(one,assets)):
            aid=item['meta']['id'];byid[aid]=item
            if ix%100==0:print(json.dumps({'phase':'REST29_PRESERVED_DELTA_READBACK','inspected':ix+1,'total':len(assets)}),flush=True)
    chain=verify_chain(journal.get('ledger_head'),byid)
    linked=set(chain['nodes']);matching=[]
    for item in byid.values():
        item['on_current_parent_chain']=item['meta']['id'] in linked
        if item['on_current_parent_chain']:matching+=item['raw']
    investigation=[]
    for ix,c in enumerate(conflicts):
        receipts=[r for r in matching+raws if (q:=r.get('request')) and q.get('s')==c['key'][0] and q.get('k')==c['key'][1] and overlaps(q['a'],q['b'],c['a'],c['b'])]
        unique={r['raw_sha256']:r for r in receipts}
        investigation.append({'conflict_id':ix,'original':c,'native_receipts':list(unique.values()),'native_receipt_count':len(unique),'disposition':'KEEP_UNKNOWN_QUARANTINE_NO_HISTORICAL_REWRITE','reason':'A later complete-looking receipt cannot erase an older uncertainty without complete causal identity and native pagination binding. Explicitly preserve all original source IDs/ranges.','chain_complete':chain['complete']})
    failures=[r for r in matching+raws if r.get('failure_binding')=='EVIDENCE_UNBOUND']
    # Correlate preserved historical result rows, not their numerical outcomes.
    pins=strict_json((pathlib.Path(__file__).parent/'resolution_sources.json').read_bytes())
    historical_meta=pins['historical_order']['body']['primary'];historical=owner.read_asset(historical_meta,key,tmp)
    historical_contacts=[contact(r,conflicts,'ACCEPTED_HISTORICAL_ORDER_RESULT') for r in historical.get('records',[])]
    accepted_meta=strict_json((ROOT/'research_core_v4/root_cause_economic_20261014_v1/AUTHORITY_V1.json').read_bytes())['accepted_primary'];accepted=owner.read_asset(accepted_meta,key,tmp)
    reference_contacts=[];reference_sources=[]
    for ref in accepted.get('economic_reference_shards',[]):
        m=ref['asset'];v=owner.read_asset(m,key,tmp);reference_sources.append({'meta':m,'rows':len(v.get('economic_references',[]))})
        reference_contacts.extend(contact(e,conflicts,'SAVED_COST_REFERENCE_NO_OUTCOME_REPLAY') for e in v.get('economic_references',[]))
    report={'schema':'mxm.rest29.OWNER.investigation.v3','source_head':os.environ['GITHUB_SHA'],'journal_sha256':JOURNAL,'current_sources':current,'current_wire_keys':len(wire),'current_wire_conflicts':wire_conflicts,'campaign_event_contacts':campaign,'raw_receipts':raws,'conflict_investigations':investigation,'unbound_failure_investigations':failures,'native_storage_releases':release_metadata,'delta_inventory':list(byid.values()),'parent_chain':chain,'historical_contacts':historical_contacts,'cost_reference_contacts':reference_contacts,'cost_reference_sources':reference_sources,'historical_outcomes_recomputed':False,'historical_results_modified':False,'historical_full_impact_closed':False,'all_world_sources_claim':False,'new_broker_requests':0,'orders':0}
    return report

def main():
    from . import owner
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    clean_tree(ROOT);require(os.environ['GITHUB_REF_NAME']==BRANCH and os.environ['GITHUB_RUN_ATTEMPT']=='1','REST29_SCOPE')
    transport=GetOnly();before=transport.json('releases/412686323');body=strict_json(before['body']);require(body['generation']==1807 and body['state']=='STOP_FAIL_CLOSED' and body['current_journal']['canonical_sha256']==JOURNAL,'REST29_ANCHOR_PIN')
    require(transport.json('git/ref/heads/'+BRANCH)['object']['sha']==os.environ['GITHUB_SHA'],'REST29_HEAD_DRIFT')
    require(transport.json('git/ref/heads/performance-research-v3-20260922')['object']['sha']==CANONICAL,'REST29_CANONICAL_DRIFT')
    out=ROOT/'verification';out.mkdir(exist_ok=True);os.umask(0o077)
    old_get=owner.get;old_urlopen=urllib.request.urlopen
    # Applies even to imported legacy IO paths. GET source404/malformed must
    # remain a read failure; any get-or-create POST is rejected before IO.
    owner.get=transport.json;urllib.request.urlopen=transport.open
    try:
        with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as t:
            tmp=pathlib.Path(t);key,fp=_private_key_from_secret(tmp);require(fp==FP,'REST29_OWNER_KEY')
            previous,prior_receipt=decrypt_artifact(transport,key,tmp,owner)
            journal=owner.read_asset(body['current_journal'],key,tmp)
            limits=p0_limits(transport)
            private=scan_main(transport,key,tmp,owner,journal,previous)
            proof=seal(private,key,tmp,owner,'rest29-owner-investigation.mxmenc')
            count=lambda rows:dict(Counter(x['state'] for x in rows))
            summary={'schema':private['schema'],'run_id':os.environ['GITHUB_RUN_ID'],'source_head':os.environ['GITHUB_SHA'],'generation':1807,'journal_sha256':JOURNAL,'prior_receipt':prior_receipt,'private_evidence':proof,'current_sources':len(private['current_sources']),'current_wire_keys':private['current_wire_keys'],'current_wire_conflicts':len(private['current_wire_conflicts']),'campaign_events':len(private['campaign_event_contacts']),'campaign_contacts':count(private['campaign_event_contacts']),'historical_order_contacts':count(private['historical_contacts']),'cost_reference_contacts':count(private['cost_reference_contacts']),'cost_reference_sources':len(private['cost_reference_sources']),'delta_assets_examined':len(private['delta_inventory']),'delta_assets_verified':sum(r['state']=='OWNER_DECODED' for r in private['delta_inventory']),'parent_chain_complete':private['parent_chain']['complete'],'parent_chain_nodes':len(private['parent_chain']['nodes']),'conflicts':[{'id':c['conflict_id'],'native_receipt_count':c['native_receipt_count'],'disposition':c['disposition']} for c in private['conflict_investigations']],'unbound_failures':len({r['raw_sha256'] for r in private['unbound_failure_investigations']}),'historical_full_impact_closed':False,'original_checkpoint_changed':False,'outcomes_recomputed':False,'new_broker_requests':0,'orders':0,'alpha_certified':False,'HARD21':False,'independent_acceptance':False,'P0_limits':limits,'HTTP_methods':dict(transport.methods)}
            from cryptography.hazmat.primitives import serialization,hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            signer=serialization.load_pem_private_key(key.read_bytes(),password=None)
            statement={'schema':'mxm.rest29.OWNER.attestation.v3','summary_sha256':sha(canonical(summary)),'source_head':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'private_evidence':proof,'independent_auditor':False}
            sig=signer.sign(canonical(statement),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
            signer.public_key().verify(sig,canonical(statement),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
            (out/'rest29-attestation.json').write_text(json.dumps({'statement':statement,'signature_b64':base64.b64encode(sig).decode(),'owner_spki_sha256':FP},sort_keys=True)+'\n')
    finally:owner.get=old_get;urllib.request.urlopen=old_urlopen
    require(transport.json('releases/412686323')['body']==before['body'],'REST29_ANCHOR_CHANGED')
    (out/'rest29-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    rows=source_routes()
    with (out/'rest29-reader-routes.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['entrypoint','resolved_helper','REST','scope']);writer.writeheader();writer.writerows(rows)
    print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':
    try:main()
    except Exception as ex:
        # Known require() codes only. Never emit broker bodies, key or trace locals.
        code=str(ex) if isinstance(ex,ValueError) and re.fullmatch('REST29_[A-Z0-9_]+',str(ex)) else type(ex).__name__
        print(json.dumps({'state':'REST29_BLOCKED','safe_code':code}));raise SystemExit(1) from None
