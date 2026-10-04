"""Pure post-probe feasibility decision. No transport, OAuth or response imports.

This module is a later review tool, not part of the unchanged Android probe.
Only support counts/timestamp masks and verified transport facts are accepted.
A CONTINUE classification grants no acquisition/execution authority.
"""
import base64,hashlib,json,math,zlib
from pathlib import Path
HISTORICAL_LAW_PATH='research_core_v4/state/NEXT_QUOTE_SEQUENCE_POST_PROBE_DECISION_LAW_V1.json'
LAW_PATH='research_core_v4/state/NEXT_QUOTE_SEQUENCE_POST_PROBE_DECISION_LAW_V2.json'
THRESHOLDS={'weekly_timestamp_completable_attempts_min':15,'weekly_retention_numerator':4,'weekly_retention_denominator':5,'sampled_pair_common_weeks_min':8,'sampled_week_count':10,'decision_context_count':27}
CELLS=[f'L{l}_I{i}_H{h}_{d}' for l in [10,30] for i in [0.6,0.8] for h in [10,30,90] for d in ['CONTINUATION','REVERSION']]
def digest(raw):return hashlib.sha256(raw).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def load_bound(root):
    root=Path(root);law=json.loads((root/LAW_PATH).read_bytes())
    if law['thresholds']!=THRESHOLDS:raise ValueError('frozen decision thresholds mismatch')
    for key,b in law['bindings'].items():
        raw=(root/b['path']).read_bytes()
        if digest(raw)!=b['sha256']:raise ValueError('bound input changed: '+key)
        if key=='current_metadata_census':
            plain=zlib.decompress(base64.b64decode(raw))
            if digest(plain)!=b['decoded_sha256']:raise ValueError('census bytes changed')
            rows=json.loads(plain)['rows'];identities=sorted([{k:r[k] for k in ['symbol_id','symbol','asset_class']} for r in rows],key=lambda x:x['symbol_id'])
            if len(identities)!=1576 or len({i['symbol_id'] for i in identities})!=1576 or digest(canonical(identities))!=b['frontier_identity_sha256']:raise ValueError('census identities changed')
    plan=json.loads((root/law['bindings']['probe_plan']['path']).read_bytes())
    return law,plan

def decide(law,plan,execution,matrix,verification):
    """verification is an independent intake proof, never inferred from success.

Missing/incomplete/corrupt transport evidence STOPs before support classification.
Verification keys attest exact manifest/checkpoint/account/lossless/package integrity
and explicitly report saturated1ms. No probe or broker operation occurs here.
"""
    if law['thresholds']!=THRESHOLDS:raise ValueError('unfrozen thresholds')
    def result(kind,reasons,counts=None,plausible=None):
        return {'classification':kind,'action':'STOP_ACQUISITION_RETURN_TO_PROJECT_WIDE_SELECTION' if kind=='DATA_LIMITED_ACQUISITION_NOT_JUSTIFIED' else 'SEPARATELY_REVIEW_SECOND_STAGE_OUTCOME_BLIND_BREADTH_SUPPORT_CENSUS_DESIGN_ONLY' if kind=='SUPPORT_PLAUSIBLE_SECOND_STAGE_REVIEW_ONLY' else 'STOP_FAIL_CLOSED',
          'reasons':reasons,'plausible_contexts':plausible or [],'all27_context_same_cell_common_week_counts':counts or {},'full1576_capture_authorized':False,'scientific_response_authorized':False,'candidate_promotion_authorized':False,'economic_null_claimed':False,'mechanism_closure_declared':False,'next_information_source_selected':False,'second_stage_acquisition_authorized':False,'second_stage_design_review_eligible':kind=='SUPPORT_PLAUSIBLE_SECOND_STAGE_REVIEW_ONLY'}
    bad=[]
    try:
        if digest(canonical(plan)+b'\n')!=law['bindings']['probe_plan']['sha256']:bad.append('INPUT_PLAN_BYTES_CHANGED')
        if execution.get('status')!='PROBE_COMPLETED_SUPPORT_TRANSPORT_ONLY':bad.append('EXACT_PROBE_NOT_COMPLETED')
        for key in ['exact_manifest_complete','checkpoint_integrity','scope_account_binding','lossless_reconstruction','package_checksums']:
            if verification.get(key) is not True:bad.append(key.upper()+'_NOT_PROVED')
        if verification.get('saturated_1ms') is not False:bad.append('SATURATED_1MS_OR_UNKNOWN')
        if execution.get('plan_sha256')!=law['bindings']['probe_plan']['sha256']:bad.append('PLAN_BINDING')
        files=execution.get('source_file_sha256',{})
        if files.get(law['bindings']['probe_contract']['path'])!=law['bindings']['probe_contract']['sha256']:bad.append('CONTRACT_BINDING')
        if execution.get('frontier_identity_sha256')!=law['bindings']['current_metadata_census']['frontier_identity_sha256']:bad.append('CENSUS_BINDING')
        if execution.get('scope_view_verified') is not True:bad.append('SCOPE_VIEW')
        if execution.get('base_requests_completed')!=plan['base_request_count'] or execution.get('base_request_total')!=plan['base_request_count']:bad.append('BASE_MANIFEST_INCOMPLETE')
        if execution.get('no_window_side_slots')!=plan['no_window_side_slots']:bad.append('NO_WINDOW_MANIFEST_MISMATCH')
        for value,cap,label in [(execution.get('local_totals',{}).get('all_local_files_bytes'),2000000000,'LOCAL_BYTES'),(execution.get('elapsed_active_seconds_all_resumes'),7200,'ACTIVE_SECONDS'),(execution.get('historical_wire_attempts_including_retry'),11200,'WIRE_ATTEMPTS')]:
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=cap:bad.append(label+'_BUDGET_OR_MISSING')
        if execution.get('response_values_computed') is not False or execution.get('pnl_computed') is not False or execution.get('orders_sent')!=0 or execution.get('full_capture_started') is not False:bad.append('FORBIDDEN_ACTIVITY')
    except (TypeError,ValueError,KeyError):bad.append('MALFORMED_TRANSPORT_EVIDENCE')
    if bad:return result('TRANSPORT_ARCHITECTURE_NOT_FEASIBLE_AS_CURRENTLY_CONFIGURED',bad)
    try:
        identities={i['symbol_id']:i for i in plan['identities']};weeks=plan['week_indices'];expected={(sid,w) for sid in identities for w in weeks}
        rows={}
        for r in matrix:
            key=(r['symbol_id'],r['week_index'])
            if key not in expected or key in rows or r['asset_class']!=identities[key[0]]['asset_class']:raise ValueError('matrix identity/week mismatch')
            cells=r['support']['cells'];mapping={c['cell_id']:c for c in cells}
            if len(cells)!=24 or set(mapping)!=set(CELLS):raise ValueError('matrix must report all24 fixed siblings')
            if r['support'].get('response_values_read') is not False:raise ValueError('non-support input')
            if identities[key[0]]['transport_only_singleton'] and r['status']!='SINGLETON_TRANSPORT_ONLY_NO_FEATURE_COUNTS':raise ValueError('singleton diagnostic role')
            rows[key]=(r,mapping)
        if set(rows)!=expected:raise ValueError('complete560 identity-week matrix required')
        groups={}
        for i in identities.values():
            if not i['transport_only_singleton']:groups.setdefault(i['asset_class'],[]).append(i['symbol_id'])
        if len(groups)!=27 or any(len(ids)!=2 for ids in groups.values()):raise ValueError('exact27 paired contexts required')
        def qualified(sid,week,cell):
            row,cs=rows[sid,week]
            if row['status'] in ['NO_WINDOW','ENDPOINT_UNAVAILABLE']:return False
            if row['status']!='SUPPORT_COUNTS_ONLY':raise ValueError('unexpected support status')
            c=cs[cell];n=c['nonoverlap_attempts'];k=c['timestamp_completable_attempts'];ret=c['retention_fraction_timestamp_only']
            if type(n) is not int or type(k) is not int or not 0<=k<=n:raise ValueError('invalid support counts')
            if n==0:
                if ret is not None:raise ValueError('empty retention must be null')
            elif type(ret) not in (int,float) or not math.isfinite(ret) or abs(ret-k/n)>1e-12:raise ValueError('retention inconsistent with counts')
            return k>=15 and 5*k>=4*n # exact >=0.80; no floating threshold ambiguity
        q={(sid,w,c):qualified(sid,w,c) for ids in groups.values() for sid in ids for w in weeks for c in CELLS}
        counts={};plausible=[]
        for ctx,ids in sorted(groups.items()):
            counts[ctx]={c:sum(q[ids[0],w,c] and q[ids[1],w,c] for w in weeks) for c in CELLS}
            if any(n>=8 for n in counts[ctx].values()):plausible.append(ctx)
        if not plausible:return result('DATA_LIMITED_ACQUISITION_NOT_JUSTIFIED',['ZERO_OF27_CONTEXTS_PLAUSIBLE'],counts)
        return result('SUPPORT_PLAUSIBLE_SECOND_STAGE_REVIEW_ONLY',['AT_LEAST_ONE_PAIRED_CONTEXT_HAS_SAME_CELL_SUPPORT_IN8_OF10_WEEKS'],counts,plausible)
    except (TypeError,ValueError,KeyError):
        return result('TRANSPORT_ARCHITECTURE_NOT_FEASIBLE_AS_CURRENTLY_CONFIGURED',['SUPPORT_MATRIX_INTEGRITY_NOT_PROVED'])
