"""Dedicated resumable device probe, compact return only. No full capture path."""
import base64,collections,errno,fcntl,gzip,json,math,os,threading,time,zipfile
from pathlib import Path
import importlib
from research_core_v4.quote_probe_plan_v1 import canonical,sha,STATE
from research_core_v4.quote_probe_transport_v1 import ProbeTransport,atomic,seal,unseal,EVENT_ORDER,validate_rows,recovery_gate
from research_core_v4.quote_probe_support_v1 import count_support
from research_core_v4.quote_probe_schedule_preflight_v1 import preflight
from research_core_v4.quote_metadata_android_v1 import Secrets,MetadataTransport,reject_sensitive_keys,verify_runtime,load_frontier
PLAN_REL=STATE+'NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json'
PLAN_SHA='e60b2dcb6cac33fd0f419daf0263d0003beaf1a0d77e7842a5ae690ff855bb16'
RETURN_NAME='MXM_V4_QUOTE_SUPPORT_TRANSPORT_PROBE_RETURN_V1.zip'
_DEVICE_LOCK_GUARD=threading.Lock()
_DEVICE_LOCK_PATHS=set()

def verify(root):
    root=Path(root);p=json.loads((root/'PACKAGE_MANIFEST.json').read_bytes())
    if p.get('schema')!='mxm.v4.quote-support-probe-source-package.v1':raise PermissionError('wrong probe package')
    for rel,h in p['file_sha256'].items():
        f=root/rel
        if Path(rel).is_absolute() or '..' in Path(rel).parts or f.is_symlink() or sha(f.read_bytes())!=h:raise PermissionError('source tamper')
    if sha((root/PLAN_REL).read_bytes())!=PLAN_SHA:raise PermissionError('probe plan binding')
    authority_path='research_core_v4/state/NEXT_QUOTE_SEQUENCE_DEVICE_AUTHORITY_SCOPE_V1.json'
    authority_raw=(root/authority_path).read_bytes();authority=json.loads(authority_raw)
    if sha(authority_raw)!=p.get('device_authority_scope_sha256') or authority.get('one_logical_resumable_device_execution') is not True or authority.get('work_execution_authorized') is not False or authority.get('full_capture_authorized') is not False or authority.get('scientific_response_authorized') is not False:raise PermissionError('device authority boundary')
    for rel,h in authority['source_file_sha256'].items():
        if p['file_sha256'].get(rel)!=h or sha((root/rel).read_bytes())!=h:raise PermissionError('device authority implementation hash')

    plan=json.loads((root/PLAN_REL).read_bytes());front=load_frontier(root)
    ids={r['symbol_id']:r for r in front}
    if len(plan['identities'])!=56 or len({i['symbol_id'] for i in plan['identities']})!=56 or len({i['asset_class'] for i in plan['identities']})!=29 or plan['week_indices']!=[0,6,12,18,24,30,36,42,48,51]:raise PermissionError('probe census/calendar')
    for i in plan['identities']:
        if any(i[k]!=ids[i['symbol_id']][k] for k in ids[i['symbol_id']]):raise PermissionError('probe identity')
    if len(plan['slots'])!=1120 or plan['base_request_count']!=sum(s['status']=='PLANNED' for s in plan['slots']) or plan['base_request_count']>1120 or len({s['request_id'] for s in plan['slots']})!=1120:raise PermissionError('base request budget')
    for key in ['full_census_capture_authorized','scientific_response_authorized','historical_capture_by_Work_authorized']:
        if plan[key] is not False:raise PermissionError('unsupported authority')
    return p,plan

def reject_quote_export(value):
    if isinstance(value,dict):
        for k,v in value.items():
            if str(k).lower() in {'tick','price','bid','ask','rows','response_price','future_price','bid_price','ask_price'}:raise PermissionError('price-bearing return rejected')
            reject_quote_export(v)
    elif isinstance(value,list):
        for v in value:reject_quote_export(v)

def acquire_device_lock(private_root):
    # Android shared storage may return ENOSYS for flock. POSIX record locks
    # live only in the app-private registry, and are held for the entire run.
    private_root=Path(private_root)
    if not private_root.is_absolute():raise PermissionError('absolute private device registry required')
    private_root.mkdir(parents=True,exist_ok=True)
    path=private_root/('v4_probe_'+PLAN_SHA+'.lock')
    if path.is_symlink():raise PermissionError('private lock symlink rejected')
    key=str(path.resolve())
    with _DEVICE_LOCK_GUARD:
        if key in _DEVICE_LOCK_PATHS:raise BlockingIOError(errno.EAGAIN,'device probe already running in this process')
        _DEVICE_LOCK_PATHS.add(key)
    lock=None
    try:
        lock=open(path,'a+b')
        fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB,0,0,os.SEEK_SET)
    except BaseException:
        if lock is not None:lock.close()
        with _DEVICE_LOCK_GUARD:_DEVICE_LOCK_PATHS.discard(key)
        raise
    return lock

def release_device_lock(lock):
    key=str(Path(lock.name).resolve())
    try:fcntl.lockf(lock,fcntl.LOCK_UN,0,0,os.SEEK_SET)
    finally:
        lock.close()
        with _DEVICE_LOCK_GUARD:_DEVICE_LOCK_PATHS.discard(key)

def claim_device_execution(private_root,root,plan,*,held_lock=None):
    private_root=Path(private_root)
    lock=held_lock if held_lock is not None else acquire_device_lock(private_root)
    try:
        path=private_root/('v4_probe_'+PLAN_SHA+'.json')
        if path.is_symlink():raise PermissionError('private registry symlink rejected')
        binding={'plan_sha256':PLAN_SHA,'folder_sha256':sha(str(Path(root).resolve()).encode()),'logical_execution_count':1}
        if path.exists():
            if unseal(json.loads(path.read_bytes()))!=binding:raise PermissionError('one logical probe already bound to another folder')
        else:atomic(path,canonical(seal(binding)))
    finally:
        if held_lock is None:release_device_lock(lock)

def schedule_mismatch_return(root,report,secrets):
    files={'SCHEDULE_PREFLIGHT.json':canonical(report)+b'\n','PROBE_EXECUTION_MANIFEST.json':canonical({'status':'STOP_BEFORE_HISTORICAL_SCHEDULE_MISMATCH','historical_requests_sent':0,'orders_sent':0,'response_values_computed':False})+b'\n'}
    for raw in files.values():secrets.scan(raw);reject_sensitive_keys(json.loads(raw));reject_quote_export(json.loads(raw))
    files['CHECKSUMS.sha256']=''.join(f'{sha(b)}  {n}\n' for n,b in sorted(files.items())).encode()
    path=Path(root)/'RETURN_TO_CHATGPT'/RETURN_NAME;path.parent.mkdir(exist_ok=True)
    tmp=path.with_suffix('.partial')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(files.items()):z.writestr(n,b)
    os.replace(tmp,path);return path

class Heartbeat:
    def __init__(self,total,done,progress,clock=time.monotonic):
        self.total=total;self.done=done;self.initial=done;self.start=clock();self.clock=clock;self.progress=progress;self.stop=threading.Event();self.thread=None
    def show(self):
        elapsed=self.clock()-self.start;n=self.done-self.initial
        eta=(self.total-self.done)*elapsed/n if n else None
        self.progress(f'[PROBA] {self.done}/{self.total} cereri de bază finalizate ({100*self.done/self.total:.1f}%); ETA '+(f'{eta/60:.1f} min' if eta is not None else 'în estimare'))
    def __enter__(self):
        def loop():
            while not self.stop.wait(10):self.show()
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();self.show();return self
    def __exit__(self,*_):self.stop.set();self.thread.join();self.show()

def authenticate(meta,app,access,plan):
    from m6.ctrader_proto import OpenApiMessages_pb2 as oa
    from research_core_v4.quote_scope_metadata_v1 import FINGERPRINT
    from m6.ctrader_capture import account_fingerprint
    meta.connect();send=lambda n,**kw:meta.request(getattr(oa,n)(**kw))
    send('ProtoOAApplicationAuthReq',clientId=app['client_id'],clientSecret=app['client_secret'])
    accounts=send('ProtoOAGetAccountListByAccessTokenReq',accessToken=access)
    bound=[a for a in accounts.ctidTraderAccount if a.isLive and account_fingerprint(int(a.ctidTraderAccountId))==FINGERPRINT]
    if len(bound)!=1 or not meta.scope_view_verified:raise PermissionError('scope/LIVE account')
    aid=int(bound[0].ctidTraderAccountId);send('ProtoOAAccountAuthReq',ctidTraderAccountId=aid,accessToken=access)
    trader=send('ProtoOATraderReq',ctidTraderAccountId=aid).trader
    if 'pepperstone' not in trader.brokerName.lower():raise PermissionError('broker')
    assets=send('ProtoOAAssetListReq',ctidTraderAccountId=aid).asset
    if [a.name for a in assets if int(a.assetId)==int(trader.depositAssetId)]!=['EUR']:raise PermissionError('EUR')
    light=send('ProtoOASymbolsListReq',ctidTraderAccountId=aid,includeArchivedSymbols=False).symbol
    lookup={int(x.symbolId):x for x in light}
    for ident in plan['identities']:
        x=lookup.get(ident['symbol_id'])
        if x is None or x.symbolName!=ident['symbol'] or not x.HasField('enabled') or not x.enabled:raise PermissionError('probe current identity changed')
    return aid

def logical_capture(tr,slot,workdir):
    rawpath=workdir/'raw'/f"{slot['request_id']}.json.gz";recordpath=workdir/'completed'/f"{slot['request_id']}.json"
    if recordpath.exists():
        r=unseal(json.loads(recordpath.read_bytes()))
        raw=rawpath.read_bytes()
        if sha(raw)!=r['raw_sha256']:raise PermissionError('completed chunk checksum')
        plain=gzip.decompress(raw);payload=unseal(json.loads(plain))
        if r['raw_path']!=rawpath.relative_to(workdir).as_posix() or r['request_id']!=slot['request_id'] or r['plan_sha256']!=PLAN_SHA or sha(raw)!=r['raw_sha256'] or payload['request_id']!=slot['request_id'] or payload['plan_sha256']!=PLAN_SHA:raise PermissionError('completed chunk checksum/binding')
        if r['compressed_bytes']!=len(raw) or r['uncompressed_bytes']!=len(plain) or r['ticks']!=len(payload['rows'] or []) or r['status']!=payload['status'] or r['traces']!=payload['traces']:raise PermissionError('completed transport metrics changed')
        validate_rows(payload['rows'],slot['from_ms'],slot['to_ms'])
        if payload.get('event_order')!=EVENT_ORDER or payload['status']!=('EMPTY' if not payload['rows'] else 'COMPLETE'):raise PermissionError('completed tie order/status')
        check,traces=tr.capture_cached(slot)
        if check!=payload['rows'] or traces!=payload['traces']:raise PermissionError('completed node reconstruction mismatch')
        return r
    if rawpath.exists(): # crash after atomic raw write but before acknowledgement
        data=unseal(json.loads(gzip.decompress(rawpath.read_bytes())))
        if data['request_id']!=slot['request_id'] or data['plan_sha256']!=PLAN_SHA:raise PermissionError('orphan raw binding')
    else:
        rows,traces=tr.capture(slot)
        data={'request_id':slot['request_id'],'plan_sha256':PLAN_SHA,'status':'EMPTY' if not rows else 'COMPLETE','event_order':EVENT_ORDER,'rows':rows,'traces':traces}
        encoded=gzip.compress(canonical(seal(data)),compresslevel=9,mtime=0)
        if tr.local_bytes+len(encoded)>2000000000:raise PermissionError('hard local storage budget')
        atomic(rawpath,encoded);tr.local_bytes+=len(encoded)
    validate_rows(data['rows'],slot['from_ms'],slot['to_ms'])
    if data.get('event_order')!=EVENT_ORDER or data['status']!=('EMPTY' if not data['rows'] else 'COMPLETE'):raise PermissionError('orphan ordered chunk semantics')
    # Reconstruct only from integrity-verified existing nodes; cached completed
    # leaves perform no requests. Orphan/completed raw cannot bypass node checks.
    check,traces=tr.capture_cached(slot)
    if check!=data['rows'] or traces!=data['traces']:raise PermissionError('orphan node/raw reconstruction mismatch')
    raw=rawpath.read_bytes();plain=gzip.decompress(raw);traces=data['traces']
    record={'request_id':slot['request_id'],'plan_sha256':PLAN_SHA,'raw_path':rawpath.relative_to(workdir).as_posix(),'raw_sha256':sha(raw),'compressed_bytes':len(raw),'uncompressed_bytes':len(plain),'ticks':len(data['rows'] or []),'status':data['status'],'traces':traces,'has_more_count':sum(t.get('has_more',False) for t in traces),'split_depth_max':max((t['depth'] for t in traces),default=0),'latency_seconds_received_pages':sum(t.get('latency_seconds',0) for t in traces)}
    encoded=canonical(seal(record))
    if tr.local_bytes+len(encoded)>2000000000:raise PermissionError('hard local storage budget')
    atomic(recordpath,encoded);tr.local_bytes+=len(encoded);return record

def compact_return(root,workdir,plan,package,records,secrets,elapsed,wire_attempts,progress,schedule_report=None,budget_check=lambda:None):
    byid={r['request_id']:r for r in records};slot_byid={s['request_id']:s for s in plan['slots']};support=[];groups=collections.defaultdict(dict)
    for slot in plan['slots']:groups[(slot['symbol_id'],slot['week_index'])][slot['side']]=slot
    for (sid,wi),sides in sorted(groups.items()):
        budget_check()
        bid,ask=sides['BID'],sides['ASK'];entry={'symbol_id':sid,'asset_class':bid['asset_class'],'week_index':wi,'singleton_transport_only':bid['transport_only_singleton']}
        if bid['transport_only_singleton']:entry['status']='SINGLETON_TRANSPORT_ONLY_NO_FEATURE_COUNTS'
        elif bid['status']=='NO_WINDOW':entry['status']='NO_WINDOW'
        else:
            def rows(s):return json.loads(gzip.decompress((workdir/byid[s['request_id']]['raw_path']).read_bytes()))['rows']
            entry['status']='SUPPORT_COUNTS_ONLY';entry['support']=count_support(rows(bid),rows(ask),bid['signal_from_ms'],bid['signal_to_ms'])
        if 'support' not in entry:
            entry['support']={'cells':[{'cell_id':f'L{l}_I{i}_H{h}_{d}','nonoverlap_attempts':None,'timestamp_completable_attempts':None,'status':'UNOBSERVED_'+entry['status']} for l in [10,30] for i in [0.6,0.8] for h in [10,30,90] for d in ['CONTINUATION','REVERSION']],'response_values_read':False}
        support.append(entry)
    totals={'compressed_bytes':sum(r['compressed_bytes'] for r in records),'uncompressed_bytes':sum(r['uncompressed_bytes'] for r in records),'ticks':sum(r['ticks'] for r in records),'all_local_files_bytes':sum(p.stat().st_size for p in workdir.rglob('*') if p.is_file())}
    # Context-stratified plug-in projection; range is transparent engineering
    # sensitivity (0.5x/3x), not an empirical confidence/power guarantee.
    projected={};fullbase=0
    for ident in plan['identities']:
        ctx=ident['asset_class']
        if ctx in projected:continue
        rs=[r for r in records if slot_byid[r['request_id']]['asset_class']==ctx]
        members=sum(i['asset_class']==ctx for i in plan['identities']);count=ident['context_census_count'];fullbase+=count*104
        comp=sum(r['compressed_bytes'] for r in rs)/(members*10*2);unc=sum(r['uncompressed_bytes'] for r in rs)/(members*10*2)
        projected[ctx]={'census_count':count,'probe_base_requests':len(rs),'compressed_bytes_per_side_window':comp,'uncompressed_bytes_per_side_window':unc,'projected_52_week_base_requests_upper_bound':count*104,'projected_compressed_bytes_point':comp*count*104}
    point=sum(x['projected_compressed_bytes_point'] for x in projected.values());rate=len(wire_attempts)/elapsed if elapsed else None;mult=len(wire_attempts)/len(records) if records else None
    timepoint=fullbase*mult/rate if rate and mult else None
    requested_hours=sum((s['to_ms']-s['from_ms']+1)/3600000 for s in plan['slots'] if s['status']=='PLANNED')
    manifest={'ticks_per_requested_side_hour':totals['ticks']/requested_hours,'compressed_bytes_per_requested_side_hour':totals['compressed_bytes']/requested_hours,'uncompressed_bytes_per_requested_side_hour':totals['uncompressed_bytes']/requested_hours,'empty_base_requests':sum(r['status']=='EMPTY' for r in records),'endpoint_unavailable_base_requests':sum(r['status']=='ENDPOINT_UNAVAILABLE' for r in records),'schema':'mxm.v4.quote-support-transport-probe-execution.v1','status':'PROBE_COMPLETED_SUPPORT_TRANSPORT_ONLY','source_head_binding':package['source_head'],'device_authority_scope_sha256':package['device_authority_scope_sha256'],'source_file_sha256':package['file_sha256'],'plan_sha256':PLAN_SHA,'frontier_identity_sha256':plan['frontier_identity_sha256'],'base_requests_completed':len(records),'base_request_total':plan['base_request_count'],'no_window_side_slots':plan['no_window_side_slots'],'historical_wire_attempts_including_retry':len(wire_attempts),'pagination_multiplier_including_retry':mult,'wire_attempts_per_second_including_support_overhead':rate,'elapsed_active_seconds_all_resumes':elapsed,'requested_side_hours':sum((s['to_ms']-s['from_ms']+1)/3600000 for s in plan['slots'] if s['status']=='PLANNED'),'local_totals':totals,'projection_by_context':projected,'projection_full_census_upper_base_requests':fullbase,'projected_compressed_storage_range_bytes':[0.5*point,3*point],'projected_wall_seconds_range':[max(fullbase*0.22,0.5*timepoint),max(fullbase*0.22,3*timepoint)] if timepoint else None,'projection_is_planning_sensitivity_not_confidence_interval':True,'projection_does_not_authorize_full_capture':True,'response_values_computed':False,'response_values_exported_as_statistics':False,'scientific_support_or_power_certified':False,'pnl_computed':False,'orders_sent':0,'full_capture_started':False,'private_cache_exported':False,'scope_view_verified':True,'raw_quote_prices_exported':False,'raw_audit_contains_quotes_not_authorized_for_response_analysis':False,'preserve_full_raw_locally_upload_not_required':True,'singleton_contexts_transport_only':['Energies (Spot)','Forwards - Commodities']}
    files={'PROBE_EXECUTION_MANIFEST.json':canonical(manifest)+b'\n','TRANSPORT_METRICS.json':canonical({'logical_requests':records,'wire_attempts':wire_attempts})+b'\n','SUPPORT_ONLY_MATRIX.json':canonical(support)+b'\n','LOCAL_RAW_CHUNK_SHA256_MANIFEST.json':canonical([{k:v for k,v in r.items() if k in ['request_id','raw_path','raw_sha256','compressed_bytes','uncompressed_bytes','ticks','status']} for r in records])+b'\n'}
    files['SCHEDULE_PREFLIGHT.json']=canonical(schedule_report or {})+b'\n'
    # All real price-bearing gzip chunks remain DEVICE_LOCAL_ONLY. No raw audit.
    # Scan full plaintext including compressed audit chunks for known secrets.
    for name,data in files.items():
        plain=gzip.decompress(data) if name.endswith('.gz') else data
        reject_sensitive_keys(json.loads(plain));reject_quote_export(json.loads(plain));secrets.scan(plain)
    files['CHECKSUMS.sha256']=''.join(f'{sha(b)}  {n}\n' for n,b in sorted(files.items())).encode()
    target=root/'RETURN_TO_CHATGPT'/RETURN_NAME;target.parent.mkdir(exist_ok=True);tmp=target.with_suffix('.partial')
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for name,data in sorted(files.items()):
                info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
        with zipfile.ZipFile(tmp) as z:
            if z.testzip() is not None or set(z.namelist())!=set(files):raise PermissionError('return ZIP integrity')
            for name,data in files.items():
                if z.read(name)!=data:raise PermissionError('return ZIP bytes')
                secrets.scan(gzip.decompress(data) if name.endswith('.gz') else data)
        os.replace(tmp,target)
    finally:tmp.unlink(missing_ok=True)
    return target

def run_device(root,*,oauth=None,transport_factory=None,progress=print,private_registry_root=None):
    root=Path(root);package,plan=verify(root)
    if oauth is None:
        verify_runtime(root)
        for name in ['research_core_v4.quote_probe_plan_v1','research_core_v4.quote_probe_transport_v1','research_core_v4.quote_probe_support_v1','research_core_v4.quote_probe_schedule_preflight_v1','research_core_v4.pydroid_quote_probe_v1']:
            if Path(importlib.import_module(name).__file__).resolve()!=root/(name.replace('.','/')+'.py'):raise PermissionError('wrong loaded probe source origin')
        from m6 import pydroid_oauth as oauth
    if transport_factory is None:
        from m6.ctrader_transport import StdlibCTraderTransport
        transport_factory=StdlibCTraderTransport
    private_root=Path(private_registry_root) if private_registry_root is not None else Path(oauth.APP_CONFIG_PATH).parent
    progress('[LOCAL] Verificare lock POSIX privat; proba nu a contactat brokerul.')
    lock=acquire_device_lock(private_root)
    try:
        workdir=root/'DEVICE_LOCAL_PROBE_RAW'/PLAN_SHA;workdir.mkdir(parents=True,exist_ok=True)
        recovery=recovery_gate(root,workdir,private_root,plan) if (root/'research_core_v4/state/DECODER_RECOVERY_AUTHORITY_V1.json').exists() else None
        claim_device_execution(private_root,root,plan,held_lock=lock)
        secrets=Secrets();secrets.capture(oauth);token_request=oauth._token_request
    except BaseException:release_device_lock(lock);raise
    def token(params):
        for k in ['client_id','client_secret','refresh_token','code']:secrets.add(params.get(k))
        value=token_request(params)
        for k in ['accessToken','refreshToken']:secrets.add(value.get(k))
        return value
    oauth._token_request=token;meta=None;start=time.monotonic();records=[]
    elapsed_path=workdir/'active_seconds.json'
    try:
        previous=unseal(json.loads(elapsed_path.read_bytes()))['active_seconds'] if elapsed_path.exists() else 0
        if type(previous) not in (int,float) or not math.isfinite(previous) or not 0<=previous<=7200:raise PermissionError('active budget checkpoint')
        if recovery is not None and previous+120>7200:raise PermissionError('active reserve exhausted before OAuth')
    except Exception:
        oauth._token_request=token_request;release_device_lock(lock);raise
    heart=Heartbeat(plan['base_request_count'],0,progress);heart.__enter__()
    try:
        app,access,mode=oauth.ensure_v2_authorization();secrets.capture(oauth)
        for k in ['client_id','client_secret']:secrets.add(app[k])
        secrets.add(access)
        if app.get('scope','').lower()!='accounts':raise PermissionError('SCOPE_VIEW OAuth required')
        for attempt in range(2):
            meta=MetadataTransport(transport_factory(),oauth,secrets,progress=progress)
            try:aid=authenticate(meta,app,access,plan);break
            except Exception:
                meta.close()
                if attempt==0 and mode!='FRESH_ANDROID_SAFE_BROWSER_AUTHORIZATION' and meta.authorization_needs_refresh:
                    app,access,mode=oauth.force_fresh_v2_authorization();secrets.capture(oauth)
                    for k in ['client_id','client_secret']:secrets.add(app[k])
                    secrets.add(access)
                    if app.get('scope','').lower()!='accounts':raise PermissionError('SCOPE_VIEW OAuth required')
                else:raise
        schedule_report=preflight(meta,aid,plan)
        schedule_bytes=canonical(seal(schedule_report))
        if recovery is not None:
            recovery['authorized_current_schedule_sha256']=sha(schedule_bytes)
            atomic(workdir/'decoder_recovery_binding.json',canonical(seal(recovery)))
        atomic(workdir/'current_schedule_preflight.json',schedule_bytes)
        if schedule_report['status']!='EXACT_FROZEN_WINDOWS_MATCH':
            return schedule_mismatch_return(root,schedule_report,secrets)
        tr=ProbeTransport(meta,plan['slots'],aid,workdir,recovery=recovery)
        def cumulative_budget():
            current=previous+(time.monotonic()-start)
            if current+120>7200:raise PermissionError('cumulative active time reserve exhausted')
            # Prepay up to120sec request plus bounded reconnect; abrupt interruption cannot
            # reset the durable active budget. Normal exit records actual time.
            old_size=elapsed_path.stat().st_size if elapsed_path.exists() else 0
            encoded=canonical(seal({'active_seconds':current+120}))
            if tr.local_bytes+len(encoded)-old_size>2000000000:raise PermissionError('active checkpoint storage cap')
            atomic(elapsed_path,encoded);tr.local_bytes+=len(encoded)-old_size
        tr.budget_check=cumulative_budget

        verified_cache={}
        for s in plan['slots']:
            if s['status']=='PLANNED' and (workdir/'completed'/f"{s['request_id']}.json").exists():
                cumulative_budget();verified_cache[s['request_id']]=logical_capture(tr,s,workdir);heart.done=len(verified_cache)
        done=len(verified_cache)
        heart.done=done;heart.initial=done;heart.start=time.monotonic()
        for slot in plan['slots']:
            if slot['status']!='PLANNED':continue
            was_done=(workdir/'completed'/f"{slot['request_id']}.json").exists()
            if previous+(time.monotonic()-start)>plan['maximum_run_wall_seconds']:raise PermissionError('cumulative active time budget')
            record=verified_cache.get(slot['request_id']) or logical_capture(tr,slot,workdir);records.append(record)
            if not was_done:heart.done+=1
            if tr.local_bytes>plan['maximum_local_compressed_bytes']:raise PermissionError('local storage budget')
        meta.close();meta=None
        return compact_return(root,workdir,plan,package,records,secrets,previous+(time.monotonic()-start),tr.attempts,progress,schedule_report,cumulative_budget)
    finally:
        try:
            heart.__exit__()
            atomic(elapsed_path,canonical(seal({'active_seconds':previous+(time.monotonic()-start)})))
        finally:
            try:
                if meta is not None:meta.close()
            finally:
                oauth._token_request=token_request;release_device_lock(lock)

def main(root):
    try:
        p=run_device(root)
        with zipfile.ZipFile(p) as z:status=json.loads(z.read('PROBE_EXECUTION_MANIFEST.json'))['status']
        if status=='STOP_BEFORE_HISTORICAL_SCHEDULE_MISMATCH':print('[OPRIT ÎNAINTE DE ISTORICE] Calendarul curent nu coincide exact cu planul; trimite raportul pentru revizuire.')
        else:print('[FINALIZAT] Numai transport și suport; fără valori de răspuns. Toate prețurile brute rămân pe telefon.')
        print('TRIMITE DOAR ACEST ZIP:');print(p.resolve());return 0 if status=='PROBE_COMPLETED_SUPPORT_TRANSPORT_ONLY' else 2
    except KeyboardInterrupt:
        print('[OPRIT] Checkpoint păstrat. Ulterior rulează același fișier din același folder pentru resume.');return 130
    except Exception as exc:
        tb=exc.__traceback__
        while tb is not None and tb.tb_next is not None:tb=tb.tb_next
        location=(Path(tb.tb_frame.f_code.co_filename).name+':'+str(tb.tb_lineno)) if tb is not None else 'UNKNOWN'
        print('[DIAGNOSTIC SIGUR] tip='+type(exc).__name__+'; errno='+str(getattr(exc,'errno',None))+'; sursa='+location)
        print('[BLOCAT ÎN SIGURANȚĂ] Checkpoint păstrat; nu trimite un ZIP vechi. Nu trimite credențiale.');return 1
