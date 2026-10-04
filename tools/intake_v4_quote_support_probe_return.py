"""Compact support-only intake. No broker, quote prices or scientific responses.

A complete device return is not an independent reopening of private raw nodes.
The frozen law therefore keeps missing independent raw/checkpoint proof explicit.
"""
import argparse,collections,hashlib,json,math,zipfile
from pathlib import Path
from research_core_v4.quote_probe_decision_law_v1 import load_bound,decide,CELLS
from research_core_v4.pydroid_quote_probe_v1 import reject_quote_export
from research_core_v4.quote_metadata_android_v1 import reject_sensitive_keys
NAMES={'CHECKSUMS.sha256','LOCAL_RAW_CHUNK_SHA256_MANIFEST.json','PROBE_EXECUTION_MANIFEST.json','SCHEDULE_PREFLIGHT.json','SUPPORT_ONLY_MATRIX.json','TRANSPORT_METRICS.json'}
PREFIX='MXM_V4_QUOTE_SUPPORT_TRANSPORT_PROBE_RETURN_V1/'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,why):
    if not ok:raise ValueError(why)
def intake(root,path):
    root=Path(root);path=Path(path);law,plan=load_bound(root)
    with zipfile.ZipFile(path) as z:
        names=z.namelist();require(len(names)==len(set(names)) and z.testzip() is None,'ZIP integrity')
        require(set(names) in [NAMES,NAMES|{PREFIX}|{PREFIX+n for n in NAMES}],'unexpected ZIP member; no raw reading allowed')
        files={n:z.read(n) for n in NAMES}
        duplicate=PREFIX in names
        if duplicate:
            for n in NAMES:require(files[n]==z.read(PREFIX+n),'conflicting duplicate return member')
    checks={}
    for line in files['CHECKSUMS.sha256'].decode().splitlines():
        h,n=line.split('  ');require(n not in checks and n in NAMES-{'CHECKSUMS.sha256'},'checksum member');checks[n]=h
    require(set(checks)==NAMES-{'CHECKSUMS.sha256'},'complete checksums')
    for n,h in checks.items():require(sha(files[n])==h,'return file hash: '+n)
    values={n:json.loads(b) for n,b in files.items() if n.endswith('.json')}
    for v in values.values():reject_quote_export(v);reject_sensitive_keys(v)
    execution=values['PROBE_EXECUTION_MANIFEST.json'];matrix=values['SUPPORT_ONLY_MATRIX.json'];metrics=values['TRANSPORT_METRICS.json'];schedule=values['SCHEDULE_PREFLIGHT.json'];raw=values['LOCAL_RAW_CHUNK_SHA256_MANIFEST.json']
    authority=json.loads((root/'research_core_v4/state/USER_DEVICE_PROBE_EXECUTION_AUTHORITY_V1.json').read_bytes())
    deployment=root.parent/authority['android_package']['filename']
    require(sha(deployment.read_bytes())==authority['android_package']['sha256'],'accepted device source package outer hash')
    with zipfile.ZipFile(deployment) as z:
        manifest=json.loads(z.read('MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1/PACKAGE_MANIFEST.json'))
        for n,h in manifest['file_sha256'].items():require(sha(z.read('MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1/'+n))==h,'device package source binding')
    require(execution['source_file_sha256']==manifest['file_sha256'] and execution['source_head_binding']==manifest['source_head'] and execution['device_authority_scope_sha256']==manifest['device_authority_scope_sha256'],'returned source/package equality')
    slots={s['request_id']:s for s in plan['slots'] if s['status']=='PLANNED'}
    require(schedule['status']=='EXACT_FROZEN_WINDOWS_MATCH' and schedule['mismatches']==[] and schedule['identities_checked']==len(plan['identities']) and schedule['base_slot_count']==len(plan['slots']) and schedule['identity_week_windows_checked']==len({(s['symbol_id'],s['week_index']) for s in plan['slots']}),'schedule facts')
    records=metrics['logical_requests'];wires=metrics['wire_attempts'];require(len(records)==len(slots)==1120 and len(wires)==execution['historical_wire_attempts_including_retry']<=11200,'counts and wire cap')
    byid={r['request_id']:r for r in records};require(len(byid)==len(records) and set(byid)==set(slots),'exact logical manifest')
    for i,w in enumerate(wires):
        s=slots[w['request_id']];require(type(w['attempt_index']) is int and w['attempt_index']==i,'contiguous wire attempts')
        require(s['from_ms']<=w['from_ms']<=w['to_ms']<=s['to_ms'] and type(w['depth']) is int and w['depth']>=0 and type(w['retry_index']) is int and 0<=w['retry_index']<3,'wire scope')
    used=set();saturated=False
    for rid,r in byid.items():
        s=slots[rid];require(r['plan_sha256']==execution['plan_sha256'] and r['raw_path']=='raw/'+rid+'.json.gz' and len(r['raw_sha256'])==64 and int(r['raw_sha256'],16)>=0,'local chunk hash/path binding')
        traces=r['traces'];position=0
        def node(lo,hi,depth):
            nonlocal position,saturated
            require(position<len(traces),'missing split node');t=traces[position];position+=1
            require(t['request_id']==rid and t['from_ms']==lo and t['to_ms']==hi and t['depth']==depth and t['status']=='RECEIVED','exact split tree trace')
            index=t['attempt_index'];require(index not in used and 0<=index<len(wires) and wires[index]==t,'trace durable journal equality');used.add(index)
            require(type(t['returned_ticks']) is int and t['returned_ticks']>=0 and type(t['has_more']) is bool,'received shape')
            if not t['has_more']:return t['returned_ticks']
            if lo==hi:saturated=True;raise ValueError('saturated1ms')
            mid=(lo+hi)//2;return node(lo,mid,depth+1)+node(mid+1,hi,depth+1)
        ticks=node(s['from_ms'],s['to_ms'],0)
        require(position==len(traces) and ticks==r['ticks'] and r['status']==('EMPTY' if ticks==0 else 'COMPLETE'),'leaf/event completeness accounting')
        require(r['has_more_count']==sum(t['has_more'] for t in traces) and r['split_depth_max']==max(t['depth'] for t in traces),'pagination metrics')
        require(math.isclose(r['latency_seconds_received_pages'],sum(t['latency_seconds'] for t in traces),rel_tol=0,abs_tol=1e-8),'latency accounting')
    first=next(s for s in plan['slots'] if s['status']=='PLANNED')
    require(set(range(len(wires)))-used=={0},'only original received-but-unpersisted attempt may be unused')
    for w in wires[:2]:
        require(w['request_id']==first['request_id'] and w['from_ms']==first['from_ms'] and w['to_ms']==first['to_ms'] and w['depth']==0 and w['retry_index']==0 and w['status']=='RECEIVED' and w['returned_ticks']==66 and w['has_more'] is False,'exact one-page recovery trace')
    require(byid[first['request_id']]['traces']==[wires[1]],'replacement is first completed logical page')
    require(sum(w['request_id']==first['request_id'] for w in wires)==2,'no second replacement')
    raw_keys={'request_id','raw_path','raw_sha256','compressed_bytes','uncompressed_bytes','ticks','status'}
    expected_raw=[{k:v for k,v in r.items() if k in raw_keys} for r in records]
    require(raw==expected_raw,'all raw hash manifest bindings match completion records')
    totals=execution['local_totals']
    for k in ['compressed_bytes','uncompressed_bytes','ticks']:require(totals[k]==sum(r[k] for r in records),'transport total '+k)
    require(execution['empty_base_requests']==sum(r['status']=='EMPTY' for r in records) and execution['endpoint_unavailable_base_requests']==0,'empty count')
    require(0<execution['elapsed_active_seconds_all_resumes']<=7200 and totals['all_local_files_bytes']<=2000000000,'active/storage limits')
    identities={i['symbol_id']:i for i in plan['identities']};rows={}
    for row in matrix:
        key=(row['symbol_id'],row['week_index']);require(key not in rows,'duplicate matrix row');rows[key]=row
        require(row['asset_class']==identities[key[0]]['asset_class'],'matrix context')
        if row['status']=='SINGLETON_TRANSPORT_ONLY_NO_FEATURE_COUNTS':continue
        require(row['support']['economic_statistics_computed'] is False,'no economic statistics')
        for c in row['support']['cells']:
            n,k=c['nonoverlap_attempts'],c['timestamp_completable_attempts'];bits=int(c['attempt_seconds_mask_hex'],16);available=int(c['timestamp_completable_mask_hex'],16)
            require(bits>=0 and bits.bit_length()<=3600 and available>=0 and available & ~bits==0,'timestamp mask bounds/subset')
            require(bits.bit_count()==n and available.bit_count()==k and c['trigger_occurrences']>=n,'mask/count equality')
            indices=[i for i in range(3600) if bits>>i & 1];h=int(c['cell_id'].split('_')[2][1:])
            require(all(b-a>=h+1 for a,b in zip(indices,indices[1:])),'nonoverlap geometry')
            for field,v in [('attempts_three_subwindows',bits),('timestamp_completable_three_subwindows',available)]:
                require(c[field]==[((v>>(j*1200))&((1<<1200)-1)).bit_count() for j in range(3)],'subwindow masks')
            require(c['scientific_support_gate_evaluated'] is False,'no scientific certification')
    require(set(rows)=={(sid,w) for sid in identities for w in plan['week_indices']},'exact560 matrix rows')
    verification={'exact_manifest_complete':True,'package_checksums':True,'saturated_1ms':saturated,
       'scope_account_binding':True,'checkpoint_integrity':False,'lossless_reconstruction':False}
    # Scope/account is device-attested through exact bound authenticate source.
    # Private sealed checkpoints/raw nodes are intentionally not in compact ZIP.
    strict=decide(law,plan,execution,matrix,verification)
    conditional=decide(law,plan,execution,matrix,dict(verification,checkpoint_integrity=True,lossless_reconstruction=True))
    return {'schema':'mxm.v4.compact-probe-return-intake.v1','status':'COMPACT_RETURN_VERIFIED_INDEPENDENT_PRIVATE_CHECKPOINT_PROOF_NOT_INCLUDED','device_source_head':'524b1cf8db4e425d78887c605d1c7398287b0d8e','source_library_file_id':'libfile_ebab818a54a08191857c1fb1893e1c60','input_zip':{'filename':path.name,'sha256':sha(path.read_bytes()),'size_bytes':path.stat().st_size,'members':len(names),'identical_duplicate_wrapper_present':duplicate,'file_sha256':{n:sha(b) for n,b in files.items()}},'accepted_android_package':authority['android_package'],'verification':verification,'proof_provenance':{'independent_compact_checks':'ZIP/checksums, exact1120 frozen slots, all1155 journal indexes, complete split trees, received trace equality, original0/replacement1 first page, raw-hash manifest cross-bindings, totals and timestamp mask/count/subwindow/nonoverlap checks','producer_attestation':'Returned exact verified executable source manifest; fixed account authentication/calendar and local node/raw reconstruction were mandatory producer gates. This is not an independent reread of sealed private device checkpoints or raw chunks.','raw_checkpoint_independent_reverification':'NOT_PERFORMED; files intentionally not exported. No false Boolean proof substituted.','original_raw_payload_equality':'NOT_PROVEN; original66 prices unpersisted','original_active_seconds':'Exact original numeric/bytes not exported in return; cumulative716.7438408660091 supplied. No rounded5.56 substitution.'},'observed_transport':{'completed_base_requests':len(records),'historical_wire_attempts':len(wires),'original_attempt_permanently_counted':True,'exactly_one_replacement_observed':True,'active_seconds':execution['elapsed_active_seconds_all_resumes'],'ticks':totals['ticks'],'empty_base_requests':execution['empty_base_requests'],'endpoint_unavailable':0,'local_bytes':totals['all_local_files_bytes'],'compressed_chunk_bytes':totals['compressed_bytes'],'split_pages':sum(w.get('has_more',False) for w in wires),'wire_status_counts':dict(collections.Counter(w['status'] for w in wires))},'frozen_law_sha256':sha((root/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_POST_PROBE_DECISION_LAW_V2.json').read_bytes()),'strict_frozen_decision':strict,'conditional_support_only_decision_if_missing_private_proof_is_satisfied':conditional,'support_readout':{'paired_contexts':27,'contexts_meeting8_of10':len(conditional['plausible_contexts']),'max_common_qualified_weeks_by_context':{ctx:max(counts.values()) for ctx,counts in conditional['all27_context_same_cell_common_week_counts'].items()},'economic_null_claimed':False,'mechanism_closure_declared':False},'no_next_acquisition_authorized':True,'work_broker_contacts':0,'work_historical_requests':0,'real_raw_quotes_opened':0,'scientific_response_values_opened':0,'pnl_computed':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();result=intake(Path(__file__).resolve().parents[1],a.input);Path(a.output).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','observed_transport','support_readout','strict_frozen_decision']}))
