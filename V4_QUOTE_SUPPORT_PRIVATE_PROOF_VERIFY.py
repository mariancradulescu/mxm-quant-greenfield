"""Independent local private-evidence proof. No transport constructor or OAuth."""
import contextlib,fcntl,gzip,hashlib,io,json,math,os,re,sys,zipfile
from pathlib import Path
PLAN_SHA='e60b2dcb6cac33fd0f419daf0263d0003beaf1a0d77e7842a5ae690ff855bb16'
FIRST='6eed644c4506f73218ccf7df8e978b157447aeced6340935b7b9d67b696a477e'
OUTPUT='MXM_V4_QUOTE_SUPPORT_PRIVATE_PROOF_V1.zip'
CONTROL=('terminal_transport_stop.json','wire_attempts.jsonl','wire_outcomes.jsonl','current_schedule_preflight.json','active_seconds.json')
GUARD=None
HOOK_INSTALLED=False
class ProofError(Exception):pass
def check(ok,code):
    if not ok:raise ProofError(code)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def sealed(raw):
    v=json.loads(raw);check(isinstance(v,dict),'SEALED_OBJECT');body=dict(v);h=body.pop('checkpoint_sha256',None);check(h==sha(canonical(body)),'CHECKPOINT_SEAL');return body
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def guard_hook(event,args):
    g=GUARD
    if g is None:return
    if event.startswith('socket.') or event in {'urllib.Request','subprocess.Popen','os.system','os.posix_spawn','os.exec'}:
        g['denied']+=1;raise ProofError('NETWORK_OR_EXTERNAL_EXECUTION_DENIED')
    paths=[]
    if event=='open':
        path,mode,flags=args
        if isinstance(path,(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(path)).resolve()
            if p.name in {'app_credentials.json','oauth_state.json','account_selection.json'}:g['denied']+=1;raise ProofError('OAUTH_PRIVATE_CACHE_ACCESS_DENIED')
            write=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
            if write:paths=[p]
    elif event in {'os.remove','os.rmdir','os.mkdir','os.chmod','os.utime','os.truncate','os.link','os.symlink'}:paths=[Path(os.fsdecode(args[0])).resolve()]
    elif event=='os.rename':paths=[Path(os.fsdecode(x)).resolve() for x in args[:2]]
    for p in paths:
        if p!=g['out'] and g['out'] not in p.parents:g['denied']+=1;raise ProofError('WRITE_OUTSIDE_PROOF_OUTPUT_DENIED')
@contextlib.contextmanager
def denial(output):
    global GUARD,HOOK_INSTALLED
    check(GUARD is None,'VERIFIER_ALREADY_ACTIVE')
    if not HOOK_INSTALLED:sys.addaudithook(guard_hook);HOOK_INSTALLED=True
    old=sys.dont_write_bytecode;sys.dont_write_bytecode=True;g={'out':Path(output).resolve(),'denied':0};GUARD=g
    try:yield g
    finally:GUARD=None;sys.dont_write_bytecode=old

def snapshot(w,registry,request_ids):
    hashes={}
    for p in sorted(w.rglob('*')):
        check(not p.is_symlink(),'EVIDENCE_SYMLINK')
        if p.is_file():
            rel=p.relative_to(w).as_posix();parts=Path(rel).parts
            allowed=rel in set(CONTROL)|{'decoder_recovery_binding.json','.run.lock'} or rel in {'ORIGINAL_DECODER_STOP_EVIDENCE/'+n for n in CONTROL}
            if len(parts)==2 and parts[0] in {'raw','completed'}:allowed=parts[1] in {rid+('.json.gz' if parts[0]=='raw' else '.json') for rid in request_ids}
            if len(parts)==3 and parts[0]=='nodes':allowed=parts[1] in request_ids and re.fullmatch(r'[0-9]+_[0-9]+\.json\.gz',parts[2]) is not None
            check(allowed,'UNEXPECTED_EVIDENCE_FILE');hashes[rel]=sha(p.read_bytes())
    return {'files':hashes,'registry_sha256':sha(registry.read_bytes())}
def source_verify(root):
    own=json.loads((root/'PRIVATE_PROOF_PACKAGE_MANIFEST.json').read_bytes())
    for rel,h in own['file_sha256'].items():
        p=root/rel;check(not p.is_symlink() and sha(p.read_bytes())==h,'VERIFIER_SOURCE_BINDING')
    authority=json.loads((root/'PRIVATE_PROOF_AUTHORITY_V1.json').read_bytes())
    manifest_raw=(root/'PACKAGE_MANIFEST.json').read_bytes();check(sha(manifest_raw)==authority['accepted_probe_manifest_sha256'],'ORIGINAL_DEPLOYMENT_MANIFEST')
    manifest=json.loads(manifest_raw)
    for rel,h in manifest['file_sha256'].items():
        p=root/rel;check(not Path(rel).is_absolute() and '..' not in Path(rel).parts and not p.is_symlink() and sha(p.read_bytes())==h,'ORIGINAL_DEPLOYMENT_FILE_HASH')
    check(sha((root/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json').read_bytes())==PLAN_SHA,'FROZEN_PLAN_HASH')
    return authority,manifest

def verify_private(root,private,authority,progress):
    # Only pure frozen support is imported, after deployment hashes pass.
    from research_core_v4.quote_probe_support_v1 import count_support
    from research_core_v4.quote_probe_transport_v1 import EVENT_ORDER,validate_rows
    root=Path(root)
    for name in ['research_core_v4.quote_probe_support_v1','research_core_v4.quote_probe_transport_v1']:
        check(sha(Path(sys.modules[name].__file__).read_bytes())==sha((root/(name.replace('.','/')+'.py')).read_bytes()),'LOADED_PURE_MODULE_HASH')
    w=root/'DEVICE_LOCAL_PROBE_RAW'/PLAN_SHA;check(not w.is_symlink() and not (root/'DEVICE_LOCAL_PROBE_RAW').is_symlink(),'EVIDENCE_ROOT_SYMLINK')
    plan=json.loads((root/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json').read_bytes())
    slots=[s for s in plan['slots'] if s['status']=='PLANNED'];lookup={s['request_id']:s for s in slots}
    check(len(slots)==1120 and slots[0]['request_id']==FIRST,'EXACT1120_PLAN')
    registry=private/('v4_probe_'+PLAN_SHA+'.json');check(not registry.is_symlink(),'PRIVATE_REGISTRY_SYMLINK');registry_body=sealed(registry.read_bytes())
    check(registry_body=={'plan_sha256':PLAN_SHA,'folder_sha256':sha(str(root.resolve()).encode()),'logical_execution_count':1},'SAME_PRIVATE_FOLDER_REGISTRY')
    before=snapshot(w,registry,set(lookup))
    binding=sealed((w/'decoder_recovery_binding.json').read_bytes())
    recovery_raw=(root/'research_core_v4/state/DECODER_RECOVERY_AUTHORITY_V1.json').read_bytes();recovery=json.loads(recovery_raw)
    check(binding.get('schema')=='mxm.v4.exact-device-decoder-recovery-binding.v2' and binding.get('payload_equality_proven') is False and isinstance(binding.get('replacement_request_sha256'),str) and re.fullmatch('[0-9a-f]{64}',binding['replacement_request_sha256']) is not None,'RECOVERY_BINDING_SCHEMA')
    check(binding['authority_sha256']==sha(recovery_raw) and binding['folder_binding']==registry_body and binding['private_registry_sha256']==sha(registry.read_bytes()) and binding['replacement_consumed'] is True,'RECOVERY_AUTHORITY_BINDING')
    check(set(binding['original_file_sha256'])==set(CONTROL),'ORIGINAL_ARCHIVE_MEMBERS')
    originals={n:(w/'ORIGINAL_DECODER_STOP_EVIDENCE'/n).read_bytes() for n in CONTROL}
    for n,b in originals.items():
        check(sha(b)==binding['original_file_sha256'][n],'ORIGINAL_ARCHIVE_HASH')
        if not n.endswith('.jsonl'):sealed(b)
    stop=(w/'terminal_transport_stop.json').read_bytes()
    check(stop==originals['terminal_transport_stop.json'] and sha(stop)==recovery['original_stop_sha256'],'ORIGINAL_STOP_BYTES')
    sealed(stop);check(not (w/'terminal_recovery_stop.json').exists(),'LATER_TERMINAL_STOP')
    aa=[sealed(line) for line in (w/'wire_attempts.jsonl').read_bytes().splitlines()];oo=[sealed(line) for line in (w/'wire_outcomes.jsonl').read_bytes().splitlines()]
    for n in ['wire_attempts.jsonl','wire_outcomes.jsonl']:check((w/n).read_bytes().startswith(originals[n]),'ORIGINAL_JOURNAL_PREFIX')
    check(len(originals['wire_attempts.jsonl'].splitlines())==len(originals['wire_outcomes.jsonl'].splitlines())==1,'ONE_ORIGINAL_ATTEMPT')
    for n in ['wire_attempts.jsonl','wire_outcomes.jsonl']:sealed(originals[n].splitlines()[0])
    check(len(aa)==len(oo)==1155,'EXACT1155_JOURNALS')
    outcomes={o['attempt_index']:o for o in oo};check(set(outcomes)==set(range(1155)) and len(outcomes)==len(oo),'ALL_OUTCOMES_UNIQUE')
    wires=[]
    for i,q in enumerate(aa):
        check(type(q['attempt_index']) is int and q['attempt_index']==i and q['request_id'] in lookup and q['status']=='SENT_OR_ACK_UNKNOWN','JOURNAL_INDEX_SCOPE')
        slot=lookup[q['request_id']]
        check(all(type(q[k]) is int for k in ['from_ms','to_ms','depth','retry_index']) and slot['from_ms']<=q['from_ms']<=q['to_ms']<=slot['to_ms'] and q['depth']>=0 and 0<=q['retry_index']<3,'JOURNAL_NUMERIC_RANGE')
        o=outcomes[i]
        for k in ['request_id','from_ms','to_ms','depth','retry_index']:check(q[k]==o[k],'OUTCOME_SCOPE')
        check(o['status']=='RECEIVED' and type(o['has_more']) is bool and type(o['returned_ticks']) is int and o['returned_ticks']>=0,'RECEIVED_NO_BROKER_ERROR')
        combined=dict(q);combined.update(o);wires.append(combined)
    first=slots[0]
    for t in wires[:2]:
        check(t['request_id']==FIRST and t['from_ms']==first['from_ms'] and t['to_ms']==first['to_ms'] and t['depth']==0 and t['retry_index']==0 and t['returned_ticks']==66 and t['has_more'] is False,'ONE_EXACT_REPLACEMENT')
    check(sum(t['request_id']==FIRST for t in wires)==2 and binding['original_attempts_charged']==1,'NO_SECOND_REPLACEMENT')
    original_active=sealed(originals['active_seconds.json'])['active_seconds'];active=sealed((w/'active_seconds.json').read_bytes())['active_seconds']
    check(finite(original_active) and 0<original_active<=7200 and original_active==binding['original_active_seconds_charged'] and finite(active) and original_active<=active<=7200 and active>=authority['minimum_completion_active_seconds'],'EXACT_CUMULATIVE_ACTIVE_CAP')
    schedule_raw=(w/'current_schedule_preflight.json').read_bytes();schedule=sealed(schedule_raw)
    check(sha(schedule_raw)==binding['authorized_current_schedule_sha256'] and schedule['status']=='EXACT_FROZEN_WINDOWS_MATCH' and schedule['mismatches']==[] and schedule['identities_checked']==56 and schedule['identity_week_windows_checked']==560 and schedule['base_slot_count']==1120,'CURRENT_SCHEDULE_BINDING')
    check(sha(canonical(schedule)+b'\n')==authority['compact_file_sha256']['SCHEDULE_PREFLIGHT.json'],'SCHEDULE_RETURN_HASH')
    expected_records={s['request_id']+'.json' for s in slots};expected_raw={s['request_id']+'.json.gz' for s in slots}
    check({p.name for p in (w/'completed').iterdir()}==expected_records and {p.name for p in (w/'raw').iterdir()}==expected_raw,'EXACT_COMPLETED_RAW_FILE_SETS')
    raw_keys=['request_id','raw_path','raw_sha256','compressed_bytes','uncompressed_bytes','ticks','status']
    trusted_records=[sealed((w/'completed'/(s['request_id']+'.json')).read_bytes()) for s in slots]
    check(sha(canonical([{k:r[k] for k in raw_keys} for r in trusted_records])+b'\n')==authority['compact_file_sha256']['LOCAL_RAW_CHUNK_SHA256_MANIFEST.json'],'RAW_MANIFEST_BEFORE_RAW_DECODE')
    check(sha(canonical({'logical_requests':trusted_records,'wire_attempts':wires})+b'\n')==authority['compact_file_sha256']['TRANSPORT_METRICS.json'],'TRANSPORT_BEFORE_RAW_DECODE')
    def decompress(blob,limit):
        with gzip.GzipFile(fileobj=io.BytesIO(blob)) as g:data=g.read(limit+1)
        check(len(data)<=limit,'GZIP_EXPANSION_LIMIT');return data
    used=set();nodes_seen=set();records=[];raw_hashes=[];payloads={};current_limit=0
    def node(rid,lo,hi,depth):
        path=w/'nodes'/rid/f'{lo}_{hi}.json.gz';rel=path.relative_to(w).as_posix();check(rel not in nodes_seen,'NODE_REUSE');nodes_seen.add(rel)
        blob=path.read_bytes();r=sealed(decompress(blob,current_limit+4096))
        check(r['request_id']==rid and r['from_ms']==lo and r['to_ms']==hi and r['depth']==depth and r['event_order']==EVENT_ORDER,'NODE_BINDING')
        t=r['trace'];index=t['attempt_index'];check(index not in used and 0<=index<1155 and wires[index]==t,'NODE_JOURNAL_EQUALITY');used.add(index)
        check(t['request_id']==rid and t['from_ms']==lo and t['to_ms']==hi and t['depth']==depth,'NODE_TRACE_GEOMETRY')
        if rid==FIRST:check(sha(blob)==binding['replacement_node_sha256'] and sha(blob)==before['files'][rel],'REPLACEMENT_NODE_BINDING')
        if r['status']=='LEAF':
            rows=r['rows'];validate_rows(rows,lo,hi);check(t['has_more'] is False and t['returned_ticks']==len(rows),'LEAF_COMPLETENESS');return rows,[t]
        check(r['status']=='SPLIT' and t['has_more'] is True and 'rows' not in r and lo<hi,'DISJOINT_SPLIT_NO_SATURATED1MS')
        mid=(lo+hi)//2;left,lt=node(rid,lo,mid,depth+1);right,rt=node(rid,mid+1,hi,depth+1)
        check(not left or not right or left[-1][0]<right[0][0],'DISJOINT_EVENT_CHRONOLOGY');return left+right,[t]+lt+rt
    for index,s in enumerate(slots):
        rid=s['request_id'];rec_path=w/'completed'/(rid+'.json');record=trusted_records[index];rawpath=w/'raw'/(rid+'.json.gz');blob=rawpath.read_bytes();check(sha(blob)==record['raw_sha256'],'RAW_BLOB_SHA_BEFORE_DECODE');current_limit=record['uncompressed_bytes'];plain=decompress(blob,current_limit);payload=sealed(plain)
        check(record['request_id']==payload['request_id']==rid and record['plan_sha256']==payload['plan_sha256']==PLAN_SHA and record['raw_path']=='raw/'+rid+'.json.gz' and record['raw_sha256']==sha(blob),'RAW_HASH_PLAN_REQUEST_BINDING')
        check(record['compressed_bytes']==len(blob) and record['uncompressed_bytes']==len(plain) and record['ticks']==len(payload['rows']),'RAW_SIZE_TICK_COUNT')
        validate_rows(payload['rows'],s['from_ms'],s['to_ms']);check(payload['event_order']==EVENT_ORDER and payload['status']==record['status']==('EMPTY' if not payload['rows'] else 'COMPLETE'),'RAW_ORDER_EMPTY_STATUS')
        reconstructed,traces=node(rid,s['from_ms'],s['to_ms'],0)
        check(reconstructed==payload['rows'] and traces==payload['traces']==record['traces'],'LOSSLESS_NODE_RAW_TRACE_EQUALITY')
        check(record['has_more_count']==sum(t['has_more'] for t in traces) and record['split_depth_max']==max(t['depth'] for t in traces) and math.isclose(record['latency_seconds_received_pages'],sum(t['latency_seconds'] for t in traces),rel_tol=0,abs_tol=1e-8),'COMPLETED_TRANSPORT_SUMMARY')
        records.append(record);payloads[rid]=payload['rows'];raw_hashes.append({k:record[k] for k in ['request_id','raw_path','raw_sha256','compressed_bytes','uncompressed_bytes','ticks','status']})
        if index%50==0:progress(f'[OFFLINE] {index+1}/1120 checkpointuri verificate; rețea=0.')
    actual_nodes={p.relative_to(w).as_posix() for p in (w/'nodes').rglob('*') if p.is_file()};check(actual_nodes==nodes_seen,'EXACT_NODE_FILE_SET')
    check(set(range(1155))-used=={0} and records[0]['traces']==[wires[1]],'ALL_PAGES_EXCEPT_CHARGED_ORIGINAL_RECONSTRUCTED')
    allowed=nodes_seen|{'completed/'+n for n in expected_records}|{'raw/'+n for n in expected_raw}|set(CONTROL)|{'decoder_recovery_binding.json','.run.lock'}|{'ORIGINAL_DECODER_STOP_EVIDENCE/'+n for n in CONTROL}
    check(set(before['files'])<=allowed,'UNEXPECTED_EVIDENCE_FILE')
    check(sum(p.stat().st_size for p in w.rglob('*') if p.is_file())<=2000000000,'LOCAL_STORAGE_CAP')
    groups={}
    for s in plan['slots']:groups.setdefault((s['symbol_id'],s['week_index']),{})[s['side']]=s
    matrix=[]
    for index,((sid,wi),sides) in enumerate(sorted(groups.items())):
        bid,ask=sides['BID'],sides['ASK'];entry={'symbol_id':sid,'asset_class':bid['asset_class'],'week_index':wi,'singleton_transport_only':bid['transport_only_singleton']}
        if bid['transport_only_singleton']:entry['status']='SINGLETON_TRANSPORT_ONLY_NO_FEATURE_COUNTS'
        elif bid['status']=='NO_WINDOW':entry['status']='NO_WINDOW'
        else:entry['status']='SUPPORT_COUNTS_ONLY';entry['support']=count_support(payloads[bid['request_id']],payloads[ask['request_id']],bid['signal_from_ms'],bid['signal_to_ms'])
        if 'support' not in entry:entry['support']={'cells':[{'cell_id':f'L{l}_I{i}_H{h}_{d}','nonoverlap_attempts':None,'timestamp_completable_attempts':None,'status':'UNOBSERVED_'+entry['status']} for l in [10,30] for i in [0.6,0.8] for h in [10,30,90] for d in ['CONTINUATION','REVERSION']],'response_values_read':False}
        matrix.append(entry)
        if index%25==0:progress(f'[SUPORT OFFLINE] {index+1}/560; fără răspunsuri economice.')
    rebuilt={'LOCAL_RAW_CHUNK_SHA256_MANIFEST.json':canonical(raw_hashes)+b'\n','SUPPORT_ONLY_MATRIX.json':canonical(matrix)+b'\n','TRANSPORT_METRICS.json':canonical({'logical_requests':records,'wire_attempts':wires})+b'\n','SCHEDULE_PREFLIGHT.json':canonical(schedule)+b'\n'}
    for n,b in rebuilt.items():check(sha(b)==authority['compact_file_sha256'][n],'RECOMPUTED_'+n)
    # Compact return may be absent; committed five hashes still bind all rebuilds.
    compact=root/'RETURN_TO_CHATGPT'/'MXM_V4_QUOTE_SUPPORT_TRANSPORT_PROBE_RETURN_V1.zip'
    if compact.exists():
        check(not compact.is_symlink() and sha(compact.read_bytes())==authority['compact_zip_sha256'],'ACCEPTED_COMPACT_OUTER_SHA')
        with zipfile.ZipFile(compact) as z:
            check(z.testzip() is None and len(z.namelist())==len(set(z.namelist())),'COMPACT_ZIP_CRC')
            for n,h in authority['compact_file_sha256'].items():
                matches=[x for x in z.namelist() if x==n or x=='MXM_V4_QUOTE_SUPPORT_TRANSPORT_PROBE_RETURN_V1/'+n]
                check(matches and all(sha(z.read(x))==h for x in matches),'EXISTING_COMPACT_FILE_HASH')
    after=snapshot(w,registry,set(lookup));check(before==after,'EVIDENCE_TREE_UNCHANGED')
    tree_sha=sha(canonical(before));flags={'checkpoint_integrity':True,'lossless_reconstruction':True,'exact1120_complete':True,'exact1155_wire_attempts':True,'support_matrix_hash_match':True,'raw_manifest_hash_match':True,'response_values_computed':False,'pnl_computed':False,'network_calls':0}
    return {'PRIVATE_PROOF_MANIFEST.json':dict(schema='mxm.v4.quote-support-private-proof.v1',status='PASS_PRIVATE_EVIDENCE',plan_sha256=PLAN_SHA,verifier_package_manifest_sha256=sha((root/'PRIVATE_PROOF_PACKAGE_MANIFEST.json').read_bytes()),private_proof_authority_sha256=sha((root/'PRIVATE_PROOF_AUTHORITY_V1.json').read_bytes()),accepted_probe_manifest_sha256=authority['accepted_probe_manifest_sha256'],decoder_recovery_authority_sha256=sha(recovery_raw),accepted_compact_file_sha256=authority['compact_file_sha256'],evidence_tree_sha256_before=tree_sha,evidence_tree_sha256_after=tree_sha,evidence_unchanged=True,**flags),
      'CHECKPOINT_INTEGRITY_PROOF.json':{'sealed_completed_records':1120,'sealed_raw_payloads':1120,'sealed_node_records':len(nodes_seen),'journal_attempts':1155,'journal_outcomes':1155,'original_archive_hashes':binding['original_file_sha256'],'original_attempt_charged':True,'replacement_attempts':1,'replacement_request_sha256':binding['replacement_request_sha256'],'original_replacement_payload_equality_proven':False,'original_active_seconds_charged':original_active,'current_active_seconds':active,'later_terminal_stop_absent':True},
      'LOSSLESS_RECONSTRUCTION_PROOF.json':{'logical_requests_reconstructed':1120,'exact_ordered_event_equality':True,'exact_trace_equality':True,'disjoint_complete_split_geometry':True,'saturated_1ms':False,'empty_completed_responses':sum(r['status']=='EMPTY' for r in records),'ticks':sum(r['ticks'] for r in records)},
      'RAW_HASH_TREE.json':{'evidence_tree_sha256':tree_sha,'verified_raw_chunk_sha256':{r['request_id']:r['raw_sha256'] for r in records},'verified_node_sha256':{n:before['files'][n] for n in sorted(nodes_seen)},'private_registry_sha256':before['registry_sha256']},
      'SUPPORT_MATRIX_RECOMPUTATION_PROOF.json':{'sha256':sha(rebuilt['SUPPORT_ONLY_MATRIX.json']),'expected_sha256':authority['compact_file_sha256']['SUPPORT_ONLY_MATRIX.json'],'exact_match':True,'identity_week_rows':560,'response_values_read':False,'economic_statistics_computed':False},
      'TRANSPORT_RECOMPUTATION_PROOF.json':{'transport_metrics_sha256':sha(rebuilt['TRANSPORT_METRICS.json']),'raw_manifest_sha256':sha(rebuilt['LOCAL_RAW_CHUNK_SHA256_MANIFEST.json']),'exact_compact_matches':True,'logical_base_requests':1120,'wire_attempts':1155}}

def proof_sanitized(value):
    if isinstance(value,dict):
        forbidden={'rows','tick','price','bid','ask','bid_price','ask_price','future_price','response_price','account_id','ctidtraderaccountid','accountid','client_id','client_secret','access_token','refresh_token','clientid','clientsecret','accesstoken','refreshtoken','password','private_cache'}
        for key,child in value.items():check(str(key).lower() not in forbidden,'PRICE_OR_SECRET_FIELD_IN_PROOF');proof_sanitized(child)
    elif isinstance(value,list):
        for child in value:proof_sanitized(child)

def output_zip(root,proof):
    files={}
    for n,v in proof.items():proof_sanitized(v);files[n]=canonical(v)+b'\n'
    files['CHECKSUMS.sha256']=''.join(sha(b)+'  '+n+'\n' for n,b in sorted(files.items())).encode()
    out=Path(root)/'RETURN_PRIVATE_PROOF';out.mkdir(exist_ok=True);tmp=out/(OUTPUT+'.partial');target=out/OUTPUT
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,b in sorted(files.items()):
            info=zipfile.ZipInfo(n,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,b)
    os.replace(tmp,target);return target

def run(root,private=None,progress=print):
    root=Path(root).resolve();private=Path(private) if private is not None else Path.home()/'.mxm_quant'/'m6_ctrader_capture_clean_v3'
    output=root/'RETURN_PRIVATE_PROOF';evidence=root/'DEVICE_LOCAL_PROBE_RAW'/PLAN_SHA
    check(not output.is_symlink() and evidence.resolve() not in output.resolve().parents and output.resolve()!=evidence.resolve(),'OUTPUT_OUTSIDE_EVIDENCE')
    with denial(output) as g:
        authority,manifest=source_verify(root)
        # Existing app-private POSIX lock is acquired read-only; no registry write.
        lockpath=private/('v4_probe_'+PLAN_SHA+'.lock');check(not lockpath.is_symlink(),'PRIVATE_LOCK_SYMLINK')
        with open(lockpath,'rb') as lock:
            fcntl.lockf(lock,fcntl.LOCK_SH|fcntl.LOCK_NB,0,0,os.SEEK_SET)
            proof=verify_private(root,private,authority,progress)
            check(g['denied']==0,'DENIED_OPERATION_ATTEMPTED')
            result=output_zip(root,proof)
            check(g['denied']==0,'DENIED_OPERATION_ATTEMPTED')
            fcntl.lockf(lock,fcntl.LOCK_UN,0,0,os.SEEK_SET)
        return result

def main(root):
    try:
        path=run(root);print('[VERIFICAT OFFLINE] Dovezi private intacte; rețea=0; fără export de prețuri.');print('TRIMITE DOAR ACEST ZIP:');print(path);return 0
    except BaseException as exc:
        print('[OPRIT OFFLINE] Verificarea nu a trecut. Datele existente nu au fost modificate. Nu relansa proba.');print('Tip sigur: '+type(exc).__name__);return 1
