"""Read existing authenticated raw quote checkpoints, not historical economics."""
import gzip,json,os,re,tempfile
from collections import Counter,defaultdict
from . import frontier_pregate as b
from .frontier_cached_support import quote_reason
from .common import need,encoded,digest,bytes_digest
from .runtime import file_at
from .custody import atomic_publish,chunk_ciphertext,restore_ciphertext
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
PARENT='1f5cd4e6df827d61d3231edd48440c66aa14c0a5'
PREFIX='diagnostics/preserved-native-quote-reuse'
OUT=b.ROOT/'verification/native-quote-reuse'
PLAN='research_programs/reconciliation/PRESERVED_NATIVE_QUOTE_REUSE.json'
WF='.github/workflows/mxm-native-quote-reuse.yml'

def projection(quotes,sample,start,end,cut):
    selected={x['symbol_id']:x for x in sample};seen={};conflicts=set();outside=Counter()
    for q in quotes:
        sid,t=q['symbol_id'],q['boundary_ms']
        need(type(sid) is int and type(t) is int and t<cut,'REUSE_QUOTE_BINDING')
        if sid not in selected:continue
        k=(sid,t)
        if k in seen and seen[k]!=q:conflicts.add(k)
        else:seen[k]=q
    rows=[]
    for sid,m in selected.items():
        counts=Counter();inside=Counter();times=[]
        for (s,t),q in seen.items():
            if s!=sid:continue
            reason='CONFLICTING_RECEIPT_BOUNDARY' if (s,t) in conflicts else quote_reason(q)
            counts[reason]+=1
            if start<=t<end:inside[reason]+=1;times.append(t)
        key='AUTHENTIC_CAUSAL_BILATERAL_SUPPORT_NOT_FILL'
        rows.append({'symbol_id':sid,'symbol':m['symbol'],'class':m['broker_native_context'],'all_boundary_status_counts':dict(counts),
          'B_period_status_counts':dict(inside),'B_period_boundaries':len(times),'B_period_valid_strict_bilateral':inside[key],
          'B_period_boundary_times_ms':sorted(times),'fees_or_margin_certified':False,'is_trade_or_fill':False})
    return {'instruments':rows,'selected_identities':len(rows),'selected_unique_boundaries':sum(sum(x['all_boundary_status_counts'].values()) for x in rows),
      'B_period_boundaries':sum(x['B_period_boundaries'] for x in rows),'B_period_valid_strict_bilateral':sum(x['B_period_valid_strict_bilateral'] for x in rows),
      'B_period_identities_with_valid_strict_bilateral':sum(x['B_period_valid_strict_bilateral']>0 for x in rows),'conflicts':len(conflicts),
      'source_native_raw_boundaries':len(quotes),'matched_sample_not_return_ranked':True,'event_coverage_certified':False,'economic_outcomes_opened':0}

def worker():
    need(os.environ['GITHUB_JOB']=='reader' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_REPOSITORY']==b.old.REPO and os.environ['GITHUB_REF_NAME']==b.old.BRANCH,'REUSE_WORKLOAD')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY') and not any(os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),'REUSE_NO_BROKER_CREDENTIALS')
    route=GetOnly();b.anchors(route);plan=strict_json((b.ROOT/PLAN).read_bytes())
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'REUSE_PARENT_MOVED')
    runs=route.json('actions/runs?per_page=100')['workflow_runs'];own=[r for r in runs if r['path']==WF]
    need(len(own)==1 and own[0]['id']==int(os.environ['GITHUB_RUN_ID']),'REUSE_FINITE_SINGLE_INVOCATION')
    need(not any(r['id']!=int(os.environ['GITHUB_RUN_ID']) and r['status'] in ('queued','waiting','in_progress') and r['path'] in (WF,b.WF,'.github/workflows/mxm-integrated-laboratory.yml') for r in runs),'REUSE_CONCURRENT_WORK')
    prior=route.json('actions/runs/38540231625');need(prior['conclusion']=='success' and prior['head_sha']==plan['historical_source_sha'],'REUSE_HISTORICAL_SOURCE')
    native=route.json('releases/'+str(plan['release_id']));assets={a['id']:a for a in native['assets']}
    sample=strict_json(file_at(route,'research_programs/reconciliation/FRONTIER_SUPPORT_PREGATE_B.json','ac4c24e11c04e77be5c94fc176d02a23e9d1207a'))['sample']
    original=file_at(route,'program-state.json',PARENT);state=strict_json(original);need(state['sequence']==16 and state['pending'] is None and state['safe_stop'] is True,'REUSE_ORIGINAL_STATE')
    frozen=plan['assets'];need(len(frozen)==39 and sum(x['size'] for x in frozen)==369925 and len(sample)==29,'REUSE_RESOURCE_BINDING')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    OUT.mkdir(parents=True,exist_ok=True);os.umask(0o077);quotes=[];proof=[]
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        tmp=b.Path(td);key,fp=_private_key_from_secret(tmp);need(fp==b.old.FP,'REUSE_OWNER_KEY')
        for frozen_asset in frozen:
            a=assets[frozen_asset['id']];need(a['name']==frozen_asset['name'] and a['size']==frozen_asset['size'] and a['digest']=='sha256:'+frozen_asset['ciphertext_sha256'],'REUSE_NATIVE_ASSET')
            with route.open(a['browser_download_url'],timeout=60) as response:blob=response.read(a['size']+1)
            need(len(blob)==a['size'] and bytes_digest(blob)==frozen_asset['ciphertext_sha256'],'REUSE_CIPHER_DIGEST')
            raw=unpack(owner.bounded_decrypt(blob,key,tmp));need(len(raw)<=4*1024*1024,'REUSE_PLAINTEXT_BOUND')
            packet=strict_json(raw,max_elements=1000000);need(packet['schema']=='mxm.native.coverage.quote.checkpoint.v1' and packet['head']==plan['historical_source_sha'] and packet['raw_receipts_authenticated_by_existing_transport'] is True,'REUSE_RAW_SOURCE')
            need(len(packet['quotes'])<=64,'REUSE_PACKET_BOUND');quotes.extend(packet['quotes']);proof.append({'asset_id':a['id'],'ciphertext_sha256':bytes_digest(blob),'plaintext_sha256':bytes_digest(raw),'quote_count':len(packet['quotes'])})
        need(len(quotes)==2462,'REUSE_SOURCE_BOUNDARY_COUNT')
        result=projection(quotes,sample,1787184000000,1787788800000,1789646578000)
        receipt={'schema':'mxm.preserved-native-quote-reuse-public.v1','source_sha':os.environ['PREGATE_SOURCE_SHA'],'trigger_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
          'parent_evidence':PARENT,'original_state_sha256':bytes_digest(original),'source_release':plan['release_id'],'historical_source_run':38540231625,
          'old_cipher_assets_reused':39,'old_cipher_bytes_reused':369925,'result':result,'new_reservations':0,'new_outcomes':0,'broker_requests':0,'orders':0,
          'confirmation_opened':False,'safe_stop':True,'B_budget_reset':False,'historical_cost_authority_promoted':False,'independent_confirmation':False}
        raw=encoded({'receipt':receipt,'asset_provenance':proof,'no_old_economics_function_called':True});pub=b.ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(pub)==b.old.FP,'REUSE_RECIPIENT')
        target=OUT/'result.mxmenc';encrypt_shard(gzip.compress(raw,mtime=0),public_key=pub,output=target);need(unpack(owner.bounded_decrypt(target.read_bytes(),key,tmp))==raw,'REUSE_ENCRYPTED_READBACK')
    b.anchors(route);receipt['ciphertext_sha256']=bytes_digest(target.read_bytes());(OUT/'receipt.json').write_bytes(encoded(receipt));print(json.dumps(receipt,sort_keys=True))

def publish():
    # needs.reader.result is supplied by the native workflow dependency graph,
    # not the eventually-consistent REST job listing. Artifact is same-run only.
    need(os.environ['GITHUB_JOB']=='durable-reuse' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ.get('NATIVE_READER_RESULT')=='success','REUSE_NATIVE_DEPENDENCY')
    need(not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'REUSE_KEYLESS_WRITER')
    route=GetOnly();b.anchors(route);d=b.ROOT/'verification/reuse-input';r=strict_json((d/'receipt.json').read_bytes());blob=(d/'result.mxmenc').read_bytes()
    need(r['schema']=='mxm.preserved-native-quote-reuse-public.v1' and r['source_sha']==os.environ['PREGATE_SOURCE_SHA'] and r['trigger_sha']==os.environ['GITHUB_SHA'] and r['run_id']==int(os.environ['GITHUB_RUN_ID']),'REUSE_ARTIFACT_RUNTIME_BINDING')
    need(all(r[k]==0 for k in ('new_reservations','new_outcomes','broker_requests','orders')) and r['confirmation_opened'] is False and r['B_budget_reset'] is False,'REUSE_PUBLIC_SCOPE')
    need(bytes_digest(blob)==r['ciphertext_sha256'] and blob.startswith(b'MXM_SHALLOW_M5_V2_ENC1\x00'),'REUSE_ARTIFACT_CIPHER')
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'REUSE_PUBLISH_STALE')
    original=file_at(route,'program-state.json',PARENT);need(bytes_digest(original)==r['original_state_sha256'],'REUSE_STATE_BINDING')
    files,manifest=chunk_ciphertext(blob,PREFIX);files[PREFIX+'/checkpoint.parts.json']=encoded(manifest);files[PREFIX+'/receipt.json']=encoded(r)
    oid=atomic_publish(route,PARENT,files,'Preserve existing native raw quote reuse on fixed29 sample; no new collection, outcomes or checkpoint16 mutation')
    need(file_at(route,'program-state.json',oid)==original,'REUSE_ORIGINAL_CHANGED')
    need(restore_ciphertext(strict_json(file_at(route,PREFIX+'/checkpoint.parts.json',oid)),lambda p:file_at(route,p,oid))==blob,'REUSE_REMOTE_READBACK');b.anchors(route)
    print(json.dumps({'state':'PRESERVED_NATIVE_QUOTE_REUSE_DURABLE','evidence_oid':oid,'new_outcomes':0,'ciphertext_sha256':r['ciphertext_sha256']}))
if __name__=='__main__':
    import sys
    try:
        need(len(sys.argv)==2 and sys.argv[1] in ('worker','publish'),'REUSE_MODE');worker() if sys.argv[1]=='worker' else publish()
    except Exception as e:
        print(json.dumps({'state':'PRESERVED_NATIVE_QUOTE_REUSE_SAFE_STOP','safe_code':str(e) if re.fullmatch(r'LAB_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
