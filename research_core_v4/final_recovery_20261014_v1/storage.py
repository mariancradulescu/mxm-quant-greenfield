"""Bounded idempotent ciphertext publication; never log bodies, URLs or credentials."""
import os,json,gzip,time,pathlib,urllib.request,urllib.error,copy,re
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as v1
from research_core_v4.critical_frontier_repair_20261014_v2 import storage_v2 as old,archive_v2 as ar
E=v1.E;need=v1.need;encode=v1.encode
from research_core_v4.shallow_m5_support_v2_production import encrypt_shard
from research_core_v4.remediation_p0_p4_20261015.safety import unpack, strict_json
ERRORS=[]
ORIGINAL_PERSIST=old.persist

def evidence(exc,phase):
    z={'phase':phase,'exception_class':type(exc).__name__}
    if isinstance(exc,urllib.error.HTTPError):
        z['http_status']=exc.code
        for k in ('X-RateLimit-Remaining','X-RateLimit-Reset','Retry-After'):
            q=exc.headers.get(k) if exc.headers else None
            if q and re.fullmatch('[0-9]{1,16}',q):z[k.lower()]=int(q)
    ERRORS.append(z);print(json.dumps({'safe_io_error':z}),flush=True);return z

def transient(exc):
    if isinstance(exc,urllib.error.HTTPError):return exc.code in (429,500,502,503,504)
    return isinstance(exc,(urllib.error.URLError,TimeoutError,ConnectionError))

def api(path,method='GET',data=None):
    # Mutation retries are resolved by each caller using durable identity, never here.
    for attempt in range(3 if method=='GET' else 1):
        try:
            req=urllib.request.Request('https://api.github.com/repos/'+E.w.old.REPO+'/'+path,
                data=None if data is None else encode(data),method=method,
                headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'})
            with urllib.request.urlopen(req,timeout=45) as res:raw=res.read()
            return json.loads(raw) if raw else None
        except Exception as ex:
            info=evidence(ex,'API_'+method+'_'+path.split('/')[0].upper())
            if method!='GET' or attempt==2 or not transient(ex) or info.get('retry-after',0)>10:raise
            time.sleep(max(2**attempt,info.get('retry-after',0)))

def legacy_api(path,body=None,method=None):return api(path,method or ('POST' if body is not None else 'GET'),body)

def download(url,maxbytes):
    need(url.startswith('https://github.com/'+E.w.old.REPO+'/releases/download/'),'REMOTE_URL_SCOPE')
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=90) as res:blob=res.read(maxbytes+1)
            need(len(blob)<=maxbytes,'REMOTE_ASSET_BUDGET');return blob
        except Exception as ex:
            info=evidence(ex,'CIPHERTEXT_DOWNLOAD')
            if attempt==2 or not transient(ex) or info.get('retry-after',0)>10:raise
            time.sleep(max(2**attempt,info.get('retry-after',0)))

def install():
    E.w.old.api=legacy_api;E.w.old.download=download
    old.api=api

def assets(rid):
    vv=[];page=1
    while True:
        batch=api('releases/'+str(rid)+'/assets?per_page=100&page='+str(page));vv+=batch
        if len(batch)<100:return vv
        page+=1

def release(tag,head):
    try:return api('releases/tags/'+tag)
    except urllib.error.HTTPError as ex:
        if ex.code!=404:raise
    try:return api('releases','POST',{'tag_name':tag,'target_commitish':head,'name':'MXM bounded OWNER encrypted evidence','prerelease':True,'body':'{"state":"UNCOMMITTED"}'})
    except Exception:
        # A create may have committed despite loss of its response.
        return api('releases/tags/'+tag)

class Store(v1.FrontierStore):
    def __init__(self,head,key,public,tmp,tag,limit=750):
        need(tag!=old.ROOT_TAG,'EXPECTED_POLICY_STOP_ORIGINAL_ANCHOR_READ_ONLY')
        super().__init__(head,key,public,tmp,'real');self.tag=tag;self.limit=limit
        self.anchor=release(tag,head);body=json.loads(self.anchor['body']);self.index=int(body.get('storage_index',0))
        self.release=release(tag+'-shard-'+str(self.index),head);self.inventory=assets(self.release['id'])
        self.fault_after_upload=False;self.upload_posts=0

    def decoded(self,meta,require_packed=True):
        asset=api('releases/assets/'+str(meta['id']))
        need(asset['name']==meta['name'] and asset['size']==meta['size'] and asset['digest']=='sha256:'+meta['ciphertext_sha256'],'REMOTE_ASSET_METADATA')
        if 'release_id' in meta:
            matched=[a for a in assets(meta['release_id']) if a['id']==meta['id']]
            need(len(matched)==1 and matched[0]['digest']==asset['digest'],'ASSET_RELEASE_BINDING')
        blob=download(asset['browser_download_url'],meta['size']);need(E.a.sha(blob)==meta['ciphertext_sha256'],'REMOTE_CIPHER_SHA')
        packed=E.w.old.crypto.decrypt_package(blob,private_key=self.key,expected_public_spki_sha256=E.w.old.FP,temp_parent=self.tmp)
        if require_packed:need('gzip_sha256' in meta and E.a.sha(packed)==meta['gzip_sha256'],'PACKED_DIGEST_MISMATCH')
        raw=unpack(packed);need(E.a.sha(raw)==meta['canonical_sha256'],'REMOTE_CANONICAL_SHA')
        obj=strict_json(raw);need(encode(obj)==raw,'REMOTE_CANONICAL')
        return obj,E.a.sha(packed)

    def restore(self,meta):
        return self.decoded(meta)[0]

    def encrypted(self,value,label):
        value=json.loads(encode(value));raw=encode(value);need(len(raw)<128*1024*1024,'CHECKPOINT_PLAIN_BUDGET')
        digest=E.a.sha(raw);packed=gzip.compress(raw,mtime=0)
        name=label.removesuffix('.mxmenc')+'-'+digest+'.mxmenc'
        need(bool(re.fullmatch(r'[a-z0-9-]+\.mxmenc',name)),'ASSET_NAME')
        # Content address survives caller retry and randomized envelope generation.
        existing=[a for a in self.inventory if a['name']==name]
        if not existing and len(self.inventory)>=self.limit:
            self.index+=1;self.release=release(self.tag+'-shard-'+str(self.index),self.head);self.inventory=assets(self.release['id'])
            need(len(self.inventory)<self.limit,'ROTATED_RELEASE_FULL');existing=[a for a in self.inventory if a['name']==name]
        if existing:
            need(len(existing)==1 and existing[0]['state']=='uploaded','ASSET_NAME_AMBIGUOUS_OR_INCOMPLETE');a=existing[0]
            meta={'id':a['id'],'name':name,'size':a['size'],'url':a['browser_download_url'],'ciphertext_sha256':a['digest'].removeprefix('sha256:'),'canonical_sha256':digest,'release_id':self.release['id']}
            originals=[m for m in self.uploaded if m['id']==a['id'] and m.get('gzip_sha256')]
            need(len(originals)==1,'EXISTING_PACKED_MANIFEST_REQUIRED')
            meta['gzip_sha256']=originals[0]['gzip_sha256']
            need(self.restore(meta)==value,'EXISTING_CONTENT_ADDRESS_DRIFT')
            return meta
        spool=pathlib.Path(os.environ['RUNNER_TEMP'])/'mxm-encrypted-outbox';spool.mkdir(mode=0o700,exist_ok=True)
        dest=spool/name
        if not dest.exists():encrypt_shard(packed,public_key=self.public,output=dest)
        ciphertext=dest.read_bytes();cipher=E.a.sha(ciphertext);need(len(ciphertext)<128*1024*1024,'CHECKPOINT_CIPHER_BUDGET')
        a=None
        try:
            req=urllib.request.Request('https://uploads.github.com/repos/'+E.w.old.REPO+'/releases/'+str(self.release['id'])+'/assets?name='+name,data=ciphertext,method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Content-Type':'application/octet-stream','Accept':'application/vnd.github+json'})
            self.upload_posts+=1
            with urllib.request.urlopen(req,timeout=120) as res:a=json.load(res)
            if self.fault_after_upload:self.fault_after_upload=False;raise ConnectionError('SYNTHETIC_LOST_UPLOAD_ACK')
        except Exception as ex:
            evidence(ex,'UPLOAD_ACK_OR_TRANSPORT')
            # No second POST. Resolve a possibly committed upload by exact remote digest.
            for attempt in range(2):
                self.inventory=assets(self.release['id']);found=[z for z in self.inventory if z['name']==name]
                if found:
                    need(len(found)==1 and found[0]['state']=='uploaded','PARTIAL_UPLOAD_PRESERVED_STOP')
                    a=found[0];break
                if attempt==0:time.sleep(2)
            if a is None:raise RuntimeError('UPLOAD_UNCOMMITTED_OUTBOX_PRESERVED_NO_BLIND_RETRY') from None
        need(a['size']==len(ciphertext) and a.get('digest')=='sha256:'+cipher,'UPLOAD_DIGEST')
        meta={'id':a['id'],'name':name,'size':len(ciphertext),'url':a['browser_download_url'],'ciphertext_sha256':cipher,'canonical_sha256':digest,'gzip_sha256':E.a.sha(packed),'release_id':self.release['id']}
        need(self.restore(meta)==value,'OWNER_PLAINTEXT_READBACK')
        self.inventory=[z for z in self.inventory if z['id']!=a['id']]+[a];self.uploaded.append(meta)
        # Ciphertext only remains until workflow retention cleanup; can be artifact fallback.
        return meta

    def commit(self,body):
        need(self.tag!=old.ROOT_TAG,'EXPECTED_POLICY_STOP_ORIGINAL_ANCHOR_READ_ONLY')
        if self.tag==old.ROOT_TAG:need(api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']==self.head,'ACTIVE_COLLECTION_HEAD_DRIFT')
        body=json.loads(encode(body));body.update(storage_index=self.index,storage_release=self.release['id'],max_assets_per_release=self.limit)
        try:api('releases/'+str(self.anchor['id']),'PATCH',{'body':json.dumps(body,sort_keys=True)})
        except Exception:
            observed=api('releases/'+str(self.anchor['id']))
            need(json.loads(observed['body'])==body,'ANCHOR_MUTATION_UNRESOLVED_NO_RETRY')
        observed=api('releases/'+str(self.anchor['id']));need(json.loads(observed['body'])==body,'ANCHOR_COMMIT_READBACK')
        self.anchor=observed

def persist(db,store,st,label,groups=()):
    # Original persist mutates the in-memory ledger before upload/commit succeeds.
    # Preserve raw broker receipts and dirty rows until durable commit verification.
    before=copy.deepcopy(st)
    try:return ORIGINAL_PERSIST(db,store,st,label,groups)
    except Exception:
        st.clear();st.update(before);raise

def restore_snapshot(db,store,body):
    store.anchor={**store.anchor,'body':json.dumps(body)}
    return old.restore(db,store)

class StoreAdapter(Store):
    def __init__(self,head,key,public,tmp):super().__init__(head,key,public,tmp,old.ROOT_TAG)
