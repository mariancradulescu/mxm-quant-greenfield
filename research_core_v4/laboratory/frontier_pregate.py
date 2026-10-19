"""Finite, outcome-blind reuse of preserved M5 shards. No broker or PnL path."""
import gzip,json,os,re,subprocess,tempfile,time
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from .common import need,encoded,digest,bytes_digest
from .runtime import file_at
from .custody import chunk_ciphertext,restore_ciphertext,atomic_publish
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
from research_core_v4.laboratory_completion_20261019_v2.runtime import source_admission
from research_core_v4.successor_c_20261018 import readback as old
ROOT=Path(__file__).resolve().parents[2]
PARENT='d22b6ff51888ba910524a7ad755eb34135860ee6'
PREFIX='diagnostics/frontier-support-pregate-B'
OUT=ROOT/'verification/frontier-pregate-B'
PLAN='research_programs/reconciliation/FRONTIER_SUPPORT_PREGATE_B_EXECUTION.json'
SOURCE_BRANCH='mxm-o04-successor-code-B-publisher-proof-r1'
WF='.github/workflows/mxm-frontier-pregate-b.yml'

def anchors(route):
    old.owner_unchanged(route)
    active='07d1ddbe0b83753bbf189770af1911623fef8d6f'
    need(route.json('git/ref/heads/mxm-o04-active-v1')['object']['sha']==active,'PREGATE_AUTHORITY_DRIFT')
    a=strict_json(file_at(route,'state.json',active));need(a['revoked'] is False and a['pending'] is None,'PREGATE_AUTHORITY_STOP')
    source_admission(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),os.environ['PREGATE_SOURCE_SHA'],route.json('git/ref/heads/'+SOURCE_BRANCH)['object']['sha'],route.json('rulesets/25222248'))
    need(route.json('git/ref/heads/mxm-o04-successor-code-laboratory-r3')['object']['sha']=='f9bfc29c2cec87a87f9bd62bd5f38f1654c5b522','PREGATE_RECEPTION_DRIFT')
    need(route.json('git/ref/heads/mxm-o04-successor-code-laboratory-research-r4')['object']['sha']=='b430a303dc76bd1ea07fbd7dd9e91dcc7c7e9ee5','PREGATE_C033_DRIFT')

def analyze_rows(rows,start,end,boundary):
    """Only timestamps, valid OHLC envelope, volume and contiguous support; no return."""
    times=[];volumes=[];hours=Counter();days=Counter();run=0;windows=0
    for row in rows:
        stamp=row['time_utc'];t=int(datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()*1000)
        need(start<=t<=end and t<boundary and t%300000==0,'PREGATE_ROW_TIME')
        need(not times or t>times[-1],'PREGATE_ROW_ORDER')
        values={k:Decimal(row[k]) for k in ('open','high','low','close')}
        need(all(v.is_finite() and v>0 for v in values.values()),'PREGATE_ROW_PRICE')
        need(values['low']<=values['open']<=values['high'] and values['low']<=values['close']<=values['high'],'PREGATE_ROW_ENVELOPE')
        v=Decimal(row['tick_volume']);need(v.is_finite() and v>=0 and v==int(v),'PREGATE_ROW_VOLUME')
        run=run+1 if times and t-times[-1]==300000 else 1
        windows+=int(run>=13);times.append(t);volumes.append(int(v));hours[stamp[11:13]]+=1;days[stamp[:10]]+=1
    gaps=[(b-a)//300000-1 for a,b in zip(times,times[1:]) if b-a>300000]
    return {'rows':len(rows),'first_bar_open_ms':times[0] if times else None,'last_bar_open_ms':times[-1] if times else None,
      'observed_calendar_days':len(days),'observed_UTC_hour_counts':dict(sorted(hours.items())),
      'contiguous_13bar_windows':windows,'observed_gap_count':len(gaps),'missing_grid_slots_between_observed_rows':sum(gaps),
      'zero_tick_volume_rows':volumes.count(0),'unique_tick_volumes':len(set(volumes)),
      'volume_constant':len(set(volumes))==1 if volumes else None,'nonoutcome_support':bool(windows),
      'gap_is_broker_session_certificate':False,'historical_receipt_times_certified':False,'economic_qualification':False}

def worker():
    need(os.environ['GITHUB_JOB']=='pregate' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_REPOSITORY']==old.REPO and os.environ['GITHUB_REF_NAME']==old.BRANCH,'PREGATE_WORKLOAD')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY') and not any(os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_ACCESS_TOKEN','CTRADER_CLIENT_SECRET')),'PREGATE_NO_BROKER_CREDENTIALS')
    route=GetOnly();anchors(route);plan=strict_json((ROOT/PLAN).read_bytes())
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'PREGATE_PARENT_MOVED')
    runs=route.json('actions/runs?per_page=100')['workflow_runs'];own=[r for r in runs if r['path']==WF]
    need(len(own)<=2 and len([r for r in own if r['head_sha']==os.environ['GITHUB_SHA']])==1,'PREGATE_RUN_BUDGET_OR_DUPLICATE')
    need(not any(r['status'] in ('queued','in_progress','waiting','pending') and r['id']!=int(os.environ['GITHUB_RUN_ID']) and r['path'] in (WF,'.github/workflows/mxm-integrated-laboratory.yml') for r in runs),'PREGATE_CONCURRENT_WORK')
    jobs=route.json('actions/runs/39262196243/jobs?per_page=100')['jobs'];need(all(any(j['name']==n and j['conclusion']=='success' for j in jobs) for n in ('reconcile','durable-reconciliation')),'PREGATE_RECONCILIATION_NOT_VERIFIED')
    prior=strict_json(file_at(route,'diagnostics/reconciliation-20261019-r1/receipt.json',PARENT));need(prior['new_outcomes']==0 and prior['input_sequence']==16,'PREGATE_RECONCILIATION_SCOPE')
    original=file_at(route,'program-state.json',PARENT);state=strict_json(original);need(state['sequence']==16 and state['pending'] is None and state['safe_stop'] is True,'PREGATE_ORIGINAL_STATE')
    programme=strict_json(file_at(route,plan['programme_path'],plan['programme_commit']))
    need(programme['id']=='FRONTIER_SUPPORT_PREGATE_B' and programme['machine_budget']['cipher_assets_max']==8 and programme['machine_budget']['economic_outcomes']==0,'PREGATE_PROGRAMME')
    assets=plan['selected_assets'];need(len(assets)<=8 and sum(a['encrypted_bytes'] for a in assets)==plan['download_bytes']<=67108864,'PREGATE_DATA_BUDGET')
    release=route.json('releases/tags/'+plan['release_tag']);native={a['id']:a for a in release['assets']}
    sample={m['symbol_id']:m for m in programme['sample']};need(len(sample)==29,'PREGATE_SAMPLE')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    from research_core_v4.autonomous_laboratory_20261019_v6.runtime import corpus,registry
    start,end=[int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000) for s in plan['bar_window_utc']]
    boundary=int(datetime.fromisoformat(plan['protected_boundary_utc'].replace('Z','+00:00')).timestamp()*1000)
    os.umask(0o077);OUT.mkdir(parents=True,exist_ok=True);begin=time.monotonic();rows_by_id={};proof=[];downloaded=0
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        tmp=Path(td);key,fp=_private_key_from_secret(tmp);need(fp==old.FP,'PREGATE_OWNER_KEY')
        for frozen in assets:
            need(time.monotonic()-begin<900,'PREGATE_TIME_BUDGET')
            asset=native[frozen['release_asset_id']]
            need(asset['name']==frozen['ENCRYPTED_ASSET_NAME'] and asset['size']==frozen['encrypted_bytes'] and asset['digest']=='sha256:'+frozen['ENCRYPTED_ASSET_SHA256'],'PREGATE_RELEASE_ASSET')
            with route.open(asset['browser_download_url'],timeout=90) as response:blob=response.read(asset['size']+1)
            need(len(blob)==asset['size'] and bytes_digest(blob)==frozen['ENCRYPTED_ASSET_SHA256'],'PREGATE_CIPHER')
            downloaded+=len(blob);need(downloaded<=67108864,'PREGATE_DOWNLOAD_BUDGET')
            raw=owner.bounded_decrypt(blob,key,tmp);need(bytes_digest(raw)==frozen['PLAINTEXT_CANONICAL_SHA256'],'PREGATE_PLAINTEXT')
            shard=strict_json(raw,max_elements=8000000)
            need(shard['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1' and shard['segment_index']==1 and shard['shard_index']==frozen['SHARD_INDEX'] and shard['identity_range']==frozen['IDENTITY_RANGE'],'PREGATE_SHARD_BINDING')
            need(sum(len(x['rows']) for x in shard['items'])==frozen['ROW_COUNT'],'PREGATE_SHARD_ROW_COUNT')
            selected=[]
            for item in shard['items']:
                sid=item['symbol_id']
                if sid not in sample:continue
                need(sid not in rows_by_id and item['ordinal']==sample[sid]['master_ordinal'],'PREGATE_SELECTED_BINDING')
                rows_by_id[sid]={**analyze_rows(item['rows'],start,end,boundary),'source_classification':item['classification'],'raw_rows_sha256':digest(item['rows']),'asset_id':asset['id']};selected.append(sid)
            proof.append({'asset_id':asset['id'],'ciphertext_sha256':bytes_digest(blob),'plaintext_sha256':bytes_digest(raw),'stored_rows_verified':frozen['ROW_COUNT'],'selected_symbol_ids':selected})
        # Reuse only the already accepted cached corpus reader, never a V6 experiment.
        cached=corpus(key,tmp,registry());catalog={int(x['sid']):x for x in cached['all_identity_status']}
        result=[]
        for sid,m in sample.items():
            d=rows_by_id.get(sid)
            result.append({'symbol_id':sid,'symbol':m['symbol'],'class':m['broker_native_context'],
              'status':'M5_NONOUTCOME_SUPPORT_MEASURED' if d else 'UNVISITED_AT_FINITE_ASSET_LIMIT_NOT_NEGATIVE',
              'M5':d,'October_catalogue_reference':{'present':sid in catalog,'recorded_reasons':catalog.get(sid,{}).get('reasons',[])},
              'historical_cost_authority':'NOT_CERTIFIED_BY_M5_OR_CURRENT_CATALOGUE','EUR200_historical_feasibility':'NOT_CERTIFIED','quote_is_fill':False})
        receipt={'schema':'mxm.frontier-pregate-B-public.v1','source_sha':os.environ['PREGATE_SOURCE_SHA'],'trigger_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
          'parent_evidence':PARENT,'original_state_sha256':bytes_digest(original),'programme_commit':plan['programme_commit'],'execution_plan_sha256':bytes_digest((ROOT/PLAN).read_bytes()),
          'selected_classes':29,'measured_classes':len(rows_by_id),'unvisited_classes':29-len(rows_by_id),'selected_M5_rows':sum(x['rows'] for x in rows_by_id.values()),
          'downloaded_cipher_bytes':downloaded,'assets_verified':len(proof),'bar_window_utc':plan['bar_window_utc'],'instruments':result,
          'selection_and_adaptivity':programme['selection_exposure'],'full28day_coverage_claimed':False,'confirmation_opened':False,'new_reservations':0,'new_outcomes':0,'broker_requests':0,'orders':0,
          'safe_stop':True,'next_action':'CAUSAL_SESSION_QUOTE_AND_COST_SUPPORT_GAP_REGISTER_BEFORE_ECONOMIC_ADMISSION'}
        detail={'receipt':receipt,'asset_provenance':proof,'catalogue_reference':{str(sid):catalog.get(sid) for sid in sample},'original_state_mutated':False}
        raw=encoded(detail);public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==old.FP,'PREGATE_RECIPIENT')
        target=OUT/'result.mxmenc';encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=target)
        need(unpack(owner.bounded_decrypt(target.read_bytes(),key,tmp))==raw,'PREGATE_ENCRYPTED_READBACK')
    anchors(route);need(file_at(route,'program-state.json',PARENT)==original,'PREGATE_ORIGINAL_STATE_CHANGED')
    receipt['ciphertext_sha256']=bytes_digest(target.read_bytes());(OUT/'receipt.json').write_bytes(encoded(receipt));print(json.dumps(receipt,sort_keys=True))

def publish():
    need(os.environ['GITHUB_JOB']=='durable-pregate' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'PREGATE_WRITER_SCOPE')
    route=GetOnly();anchors(route);d=ROOT/'verification/pregate-input';r=strict_json((d/'receipt.json').read_bytes());blob=(d/'result.mxmenc').read_bytes()
    need(r['schema']=='mxm.frontier-pregate-B-public.v1' and r['run_id']==int(os.environ['GITHUB_RUN_ID']) and r['source_sha']==os.environ['PREGATE_SOURCE_SHA'] and r['trigger_sha']==os.environ['GITHUB_SHA'],'PREGATE_NATIVE_BINDING')
    need(all(r[k]==0 for k in ('new_reservations','new_outcomes','broker_requests','orders')) and r['confirmation_opened'] is False and r['safe_stop'] is True,'PREGATE_SCOPE')
    need(r['parent_evidence']==PARENT and bytes_digest(blob)==r['ciphertext_sha256'] and blob.startswith(b'MXM_SHALLOW_M5_V2_ENC1\x00'),'PREGATE_ENCRYPTED_ARTIFACT')
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'PREGATE_PUBLISH_PARENT')
    original=file_at(route,'program-state.json',PARENT);need(bytes_digest(original)==r['original_state_sha256'],'PREGATE_STATE_HASH')
    jobs=route.json('actions/runs/'+os.environ['GITHUB_RUN_ID']+'/jobs?per_page=100')['jobs'];need(any(j['name']=='pregate' and j['conclusion']=='success' for j in jobs),'PREGATE_NATIVE_SUCCESS')
    files,manifest=chunk_ciphertext(blob,PREFIX);files[PREFIX+'/checkpoint.parts.json']=encoded(manifest);files[PREFIX+'/receipt.json']=encoded(r)
    oid=atomic_publish(route,PARENT,files,'Preserve finite frontier support pre-gate B; no outcomes, broker collection or checkpoint16 change')
    need(file_at(route,'program-state.json',oid)==original,'PREGATE_STATE_MUTATION')
    need(restore_ciphertext(strict_json(file_at(route,PREFIX+'/checkpoint.parts.json',oid)),lambda p:file_at(route,p,oid))==blob,'PREGATE_REMOTE_READBACK');anchors(route)
    print(json.dumps({'state':'FRONTIER_PREGATE_B_DURABLE','evidence_oid':oid,'ciphertext_sha256':r['ciphertext_sha256'],'new_outcomes':0}))

if __name__=='__main__':
    import sys
    try:
        need(len(sys.argv)==2 and sys.argv[1] in ('worker','publish'),'PREGATE_MODE')
        worker() if sys.argv[1]=='worker' else publish()
    except Exception as e:
        print(json.dumps({'state':'FRONTIER_PREGATE_B_SAFE_STOP','safe_code':str(e) if re.fullmatch(r'LAB_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
