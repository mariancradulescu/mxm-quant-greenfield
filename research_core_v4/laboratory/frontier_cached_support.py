"""Second and final B pre-gate run: existing cached quote/term support only."""
import gzip,json,math,os,re,tempfile
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from . import frontier_pregate as b
from .common import need,encoded,bytes_digest,digest
from .custody import chunk_ciphertext,restore_ciphertext,atomic_publish
from .runtime import file_at
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
PARENT='ffaac1428220926509299d8cbca0f9d9fee35d3a'
PREFIX='diagnostics/frontier-support-pregate-B-cached'
OUT=b.ROOT/'verification/frontier-cached-support'
PLAN='research_programs/reconciliation/FRONTIER_SUPPORT_PREGATE_B_CACHED_EXECUTION.json'

def quote_reason(q):
    """Validate recorded causal bilateral support, never promote quotes to fills."""
    finite=lambda x:type(x) in (int,float) and math.isfinite(x)
    t=q.get('boundary_ms');s=q.get('sides',{})
    if type(t) is not int:return 'BOUNDARY_UNRESOLVED'
    for name in ('bid','ask'):
        p=s.get(name,{})
        if p.get('state')!='AUTHENTIC_CAUSAL_QUOTE':return 'SIDE_NOT_AUTHENTIC_CAUSAL'
        if p.get('source_has_more') is not False:return 'PAGINATION_UNRESOLVED'
        ts,age,price=p.get('timestamp_ms'),p.get('age_ms'),p.get('price')
        if type(ts) is not int or not finite(age) or not finite(price):return 'SIDE_FIELDS_UNRESOLVED'
        if ts>t or age<0:return 'FUTURE_OR_NEGATIVE_AGE'
        if age!=t-ts:return 'AGE_TIMESTAMP_MISMATCH'
        if age>5000:return 'STALE_QUOTE'
        if price<=0:return 'NONPOSITIVE_PRICE'
    if abs(s['bid']['timestamp_ms']-s['ask']['timestamp_ms'])>2000:return 'SIDE_TIME_SKEW'
    if s['bid']['price']>s['ask']['price']:return 'CROSSED_QUOTE'
    return 'AUTHENTIC_CAUSAL_BILATERAL_SUPPORT_NOT_FILL'

def project(corpus,sample,start,end,boundary):
    chosen={m['symbol_id']:m for m in sample};group=defaultdict(list);seen={};conflicts=set()
    for q in corpus['raw_quote_receipts']:
        sid=int(q['symbol_id']);t=q['boundary_ms']
        if sid not in chosen:continue
        need(type(t) is int and t<boundary,'CACHED_PROTECTED_QUOTE_BOUNDARY')
        key=(sid,t)
        if key in seen and seen[key]!=q:conflicts.add(key)
        else:seen[key]=q
    for (sid,t),q in seen.items():group[sid].append((t,q,None if (sid,t) not in conflicts else 'CONFLICTING_RECEIPT_BOUNDARY'))
    catalog=corpus['catalog']['full'];status={int(x['sid']):x for x in corpus['all_identity_status']};result=[]
    required=('commissionType','preciseTradingCommissionRate','preciseMinCommission','minCommissionType','pnlConversionFeeRate')
    for sid,m in chosen.items():
        f=catalog.get(str(sid),{});dates=[];reasons=Counter();within=Counter();good=0;good_window=0
        for t,q,conflict in group[sid]:
            dates.append(t);reason=conflict or quote_reason(q);reasons[reason]+=1
            supported=reason=='AUTHENTIC_CAUSAL_BILATERAL_SUPPORT_NOT_FILL';good+=int(supported)
            if start<=t<end:within[reason]+=1;good_window+=int(supported)
        size_fields=('minVolume','stepVolume','maxVolume','lotSize')
        schedule=[k for k in f if any(s in k.lower() for s in ('schedule','holiday','timezone','time_zone','session'))]
        fee_present=[k for k in required if k in f]
        row=status.get(sid,{})
        result.append({'symbol_id':sid,'symbol':m['symbol'],'class':m['broker_native_context'],
          'unique_quote_boundaries':len(group[sid]),'quote_validation_counts':dict(reasons),'valid_bilateral_boundaries':good,
          'quote_first_boundary_ms':min(dates) if dates else None,'quote_last_boundary_ms':max(dates) if dates else None,
          'within_M5_period_validation_counts':dict(within),'within_M5_period_valid_bilateral_boundaries':good_window,
          'catalogue_present':bool(f),'native_volume_field_names_present':[k for k in size_fields if k in f],
          'commission_field_names_present':fee_present,'commission_field_names_missing':[k for k in required if k not in f],
          'schedule_field_names_present':sorted(schedule),'current_margin_reference_present':row.get('margin_eur') is not None,
          'current_catalogue_reasons':row.get('reasons',[]),'historical_terms_certified':False,'historical_session_certified':False,
          'EUR200_historical_feasibility_certified':False,'quote_is_fill':False,
          'pre_gate':'QUOTE_SUPPORT_MISSING_IN_BOUND_CACHE_WINDOW' if not good_window else 'QUOTE_REFERENCE_PRESENT_COST_AND_EVENT_COVERAGE_NOT_CERTIFIED'})
    return {'instruments':result,'catalogue_temporal_authority':corpus['summary'].get('dated_contract_terms'),
      'cache_scope':'EXACT_PRESERVED_RECOVERY_CORPUS;NOT_ALL_AUTHORIZED_ARCHIVES',
      'selected_classes':len(sample),'classes_with_any_valid_bilateral_quotes':sum(x['valid_bilateral_boundaries']>0 for x in result),
      'classes_with_valid_bilateral_quotes_in_M5_period':sum(x['within_M5_period_valid_bilateral_boundaries']>0 for x in result),
      'selected_unique_quote_boundaries':sum(x['unique_quote_boundaries'] for x in result),
      'valid_bilateral_boundaries':sum(x['valid_bilateral_boundaries'] for x in result),
      'valid_bilateral_boundaries_in_M5_period':sum(x['within_M5_period_valid_bilateral_boundaries'] for x in result),
      'conflicting_boundaries':len(conflicts),'economic_admissions_qualified':0,'economic_outcomes':0,
      'limits':'Presence does not certify event coverage, time-valid costs, historical receipt time or fills. Missing within this cache is not global absence.'}

def worker():
    need(os.environ['GITHUB_JOB']=='pregate' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_REPOSITORY']==b.old.REPO and os.environ['GITHUB_REF_NAME']==b.old.BRANCH,'CACHED_WORKLOAD')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY') and not any(os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),'CACHED_NO_BROKER_CREDENTIALS')
    route=GetOnly();b.anchors(route)
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'CACHED_STALE_PARENT')
    runs=route.json('actions/runs?per_page=100')['workflow_runs'];own=[r for r in runs if r['path']==b.WF]
    need(len(own)==2 and len([r for r in own if r['head_sha']==os.environ['GITHUB_SHA']])==1,'CACHED_FINITE_RUN_BUDGET')
    need(not any(r['id']!=int(os.environ['GITHUB_RUN_ID']) and r['status'] in ('queued','in_progress','waiting','pending') and r['path'] in (b.WF,'.github/workflows/mxm-integrated-laboratory.yml') for r in runs),'CACHED_DUPLICATE_WORK')
    jobs=route.json('actions/runs/39269194595/jobs?per_page=100')['jobs'];need(all(any(j['name']==n and j['conclusion']=='success' for j in jobs) for n in ('pregate','durable-pregate')),'CACHED_PARENT_NATIVE_SUCCESS')
    prior=strict_json(file_at(route,'diagnostics/frontier-support-pregate-B/receipt.json',PARENT));need(prior['assets_verified']==8 and prior['new_outcomes']==0,'CACHED_PARENT_SCOPE')
    plan=strict_json((b.ROOT/PLAN).read_bytes());need(plan['additional_download_assets']==0 and plan['additional_broker_requests']==0,'CACHED_PLAN')
    programme=strict_json(file_at(route,'research_programs/reconciliation/FRONTIER_SUPPORT_PREGATE_B.json','ac4c24e11c04e77be5c94fc176d02a23e9d1207a'))
    original=file_at(route,'program-state.json',PARENT);state=strict_json(original);need(state['sequence']==16 and state['pending'] is None and state['safe_stop'] is True,'CACHED_CHECKPOINT')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    from research_core_v4.autonomous_laboratory_20261019_v6.runtime import corpus,registry
    os.umask(0o077);OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        tmp=Path(td);key,fp=_private_key_from_secret(tmp);need(fp==b.old.FP,'CACHED_OWNER_KEY')
        data=corpus(key,tmp,registry());result=project(data,programme['sample'],1787184000000,1787788800000,1789646578000)
        receipt={'schema':'mxm.frontier-cached-support-public.v1','source_sha':os.environ['PREGATE_SOURCE_SHA'],'trigger_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
          'parent_evidence':PARENT,'original_state_sha256':bytes_digest(original),'programme_workflow_runs_consumed':2,'programme_max_workflow_runs':2,
          'additional_download_assets':0,'additional_download_bytes':0,'new_reservations':0,'new_outcomes':0,'broker_requests':0,'orders':0,
          'confirmation_opened':False,'safe_stop':True,'budget_stop':'PROGRAMME_B_FINITE_RUN_BUDGET_EXHAUSTED;NO_RENAME_OR_RESET',
          'support':result,'next_action':'PROSPECTIVE_EXACT_DATA_GAP_ACQUISITION_OR_DISTINCT_SUPPORTED_PROGRAMME;NO_UNSUPPORTED_ECONOMIC_OUTCOMES'}
        detail={'receipt':receipt,'execution_plan':plan,'original_state_mutated':False,'cashflow_or_return_computed':False}
        raw=encoded(detail);pub=b.ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(pub)==b.old.FP,'CACHED_RECIPIENT')
        target=OUT/'result.mxmenc';encrypt_shard(gzip.compress(raw,mtime=0),public_key=pub,output=target)
        need(unpack(owner.bounded_decrypt(target.read_bytes(),key,tmp))==raw,'CACHED_ENCRYPTED_READBACK')
    b.anchors(route);receipt['ciphertext_sha256']=bytes_digest(target.read_bytes());(OUT/'receipt.json').write_bytes(encoded(receipt));print(json.dumps(receipt,sort_keys=True))

def publish():
    need(os.environ['GITHUB_JOB']=='durable-pregate' and not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'CACHED_KEYLESS_PUBLISH')
    route=GetOnly();b.anchors(route);d=b.ROOT/'verification/pregate-input';r=strict_json((d/'receipt.json').read_bytes());blob=(d/'result.mxmenc').read_bytes()
    need(r['schema']=='mxm.frontier-cached-support-public.v1' and r['run_id']==int(os.environ['GITHUB_RUN_ID']) and r['source_sha']==os.environ['PREGATE_SOURCE_SHA'] and r['trigger_sha']==os.environ['GITHUB_SHA'],'CACHED_NATIVE_BINDING')
    need(all(r[k]==0 for k in ('additional_download_assets','additional_download_bytes','new_reservations','new_outcomes','broker_requests','orders')) and not r['confirmation_opened'] and r['programme_workflow_runs_consumed']==2,'CACHED_PUBLIC_SCOPE')
    need(r['parent_evidence']==PARENT and bytes_digest(blob)==r['ciphertext_sha256'] and blob.startswith(b'MXM_SHALLOW_M5_V2_ENC1\x00'),'CACHED_ENCRYPTED_ARTIFACT')
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'CACHED_PUBLISH_STALE')
    original=file_at(route,'program-state.json',PARENT);need(bytes_digest(original)==r['original_state_sha256'],'CACHED_ORIGINAL_STATE')
    jobs=route.json('actions/runs/'+os.environ['GITHUB_RUN_ID']+'/jobs?per_page=100')['jobs'];need(any(j['name']=='pregate' and j['conclusion']=='success' for j in jobs),'CACHED_NATIVE_SUCCESS')
    files,manifest=chunk_ciphertext(blob,PREFIX);files[PREFIX+'/checkpoint.parts.json']=encoded(manifest);files[PREFIX+'/receipt.json']=encoded(r)
    oid=atomic_publish(route,PARENT,files,'Preserve final B cached quote and term support readback without outcomes or checkpoint16 change')
    need(file_at(route,'program-state.json',oid)==original,'CACHED_ORIGINAL_CHANGED')
    need(restore_ciphertext(strict_json(file_at(route,PREFIX+'/checkpoint.parts.json',oid)),lambda p:file_at(route,p,oid))==blob,'CACHED_REMOTE_READBACK');b.anchors(route)
    print(json.dumps({'state':'FRONTIER_CACHED_SUPPORT_DURABLE','evidence_oid':oid,'ciphertext_sha256':r['ciphertext_sha256'],'new_outcomes':0}))
if __name__=='__main__':
    import sys
    try:
        need(len(sys.argv)==2 and sys.argv[1] in ('worker','publish'),'CACHED_MODE')
        worker() if sys.argv[1]=='worker' else publish()
    except Exception as e:
        print(json.dumps({'state':'FRONTIER_CACHED_SUPPORT_SAFE_STOP','safe_code':str(e) if re.fullmatch(r'LAB_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
