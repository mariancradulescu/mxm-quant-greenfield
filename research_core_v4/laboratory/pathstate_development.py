"""One finite delayed-target path-state DEVELOPMENT study. C# policy, independent array/Decimal checks.
No new broker data, EUR200 account, actual costs, formal V2 mutation or confirmation.
"""
import base64,collections,gzip,hashlib,json,os,subprocess,tempfile
from pathlib import Path
from decimal import Decimal as D
from .pathstate_reference import reference,reconcile
from .seasonality_development import decide
from .common import need,bytes_digest,encoded
from . import m5_authentic_envelope as env
from .m5_causal_gross_development import load_market_geometry,parse_rows
ROOT=env.ROOT
SPEC=ROOT/'research_core_v4/laboratory/PATHSTATE_DEVELOPMENT_V1.json'
SPEC_SHA='e9ff40a442915698daf4912baf43eb432dc9ee6313e102748f1c2fcb42f229a8'
PROJECT='research_core_v4/laboratory/csharp/pathstate/MxmPathStateDevelopment.csproj'
WORKFLOW='.github/workflows/mxm-pathstate-development.yml'
def validate_spec(active=False):
    raw=SPEC.read_bytes();need(bytes_digest(raw)==SPEC_SHA,'PATHSTATE_IMMUTABLE_PRECOMMIT')
    s=json.loads(raw)
    need(s['model_id']=='MXM_DELAYED_PATH_STATE_20261024_V1' and s['mechanisms']==1 and
         s['model_leaves']==1 and s['dependent_reference_friction_leaves']==4 and
         s['reference_roundtrip_bps']==[0,5,10,20] and s['cell_minimum_samples']==16 and
         s['forecast_threshold_bps']==10 and s['sample_rounding_bps_decimals']==8 and s['cells']==8 and s['cell_window']==32 and s['zero_prior_samples']==16 and
         s['evaluation_start']=='2026-08-27T00:00:00Z' and s['delay_bars']==2 and s['hold_bars']==12 and
         not s['confirmation_opened'] and not s['protected_opened'] and s['orders']==0 and
         s['partition']=='DEVELOPMENT_ALREADY_FULLY_EXPOSED','PATHSTATE_FINITE_SCOPE')
    if active:
        normalized=Path(__file__).read_bytes().replace(("SPEC_SHA='"+SPEC_SHA+"'").encode(),b"SPEC_SHA='SPEC_DIGEST_PLACEHOLDER'")
        need(bytes_digest(normalized)==s['runner_normalized_sha256'],'PATHSTATE_FROZEN_RUNNER')
        for path,digest in s['implementation_sha256'].items():
            need(bytes_digest((ROOT/path).read_bytes())==digest,'PATHSTATE_FROZEN_IMPLEMENTATION_'+path)
    return s

def context():
    validate_spec(active=True)
    need(os.environ.get('GITHUB_REPOSITORY')==env.REPO and
      os.environ.get('GITHUB_REF')=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
      os.environ.get('GITHUB_EVENT_NAME') in ('push','workflow_dispatch') and
      os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')=='pathstate-development' and
      os.environ.get('GITHUB_WORKFLOW_REF')==env.REPO+'/'+WORKFLOW+'@refs/heads/mxm-remediation-p0-p4-20261015-v1',
      'PATHSTATE_PROTECTED_CONTEXT')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'PATHSTATE_CLEAN_CODE')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN',
      'R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN')),'PATHSTATE_NO_WRITER_OR_BROKER')
    return sha

def first_native_run(commit):
    raw=subprocess.check_output(['gh','api',
        'repos/'+env.REPO+'/actions/workflows/mxm-pathstate-development.yml/runs?per_page=2'],text=True)
    history=json.loads(raw);runs=history.get('workflow_runs',[])
    need(history.get('total_count')==1 and len(runs)==1 and
         runs[0]['id']==int(os.environ['GITHUB_RUN_ID']) and runs[0]['head_sha']==commit and
         runs[0]['head_branch']=='mxm-remediation-p0-p4-20261015-v1' and runs[0]['run_attempt']==1,
         'PATHSTATE_ONE_REGISTERED_NATIVE_ATTEMPT')

def run(dest):
    commit=context();spec=validate_spec(active=True);first_native_run(commit)
    need(bytes_digest(env.MANIFEST.read_bytes())==spec['source_manifest_sha256'] and env.RELEASE_IDENTITY==spec['source_release'],
         'PATHSTATE_EXACT_SOURCE_MANIFEST')
    entries,manifest_sha=load_market_geometry()
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package,encrypt_shard,public_spki_sha256
    rows_verified=shards_verified=0;expected={};packet_hashes={}
    with tempfile.TemporaryDirectory(prefix='mxm-pathstate-') as rawdir:
        root=Path(rawdir);key,fp=_private_key_from_secret(root)
        need(fp=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11','PATHSTATE_EXISTING_RECIPIENT')
        assets=root/'cipher';assets.mkdir(mode=0o700)
        subprocess.run(['gh','release','download',env.RELEASE_IDENTITY,'--repo',env.REPO,'--dir',str(assets)],
          check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        need(len(list(assets.iterdir()))==100,'PATHSTATE_ALL_SHARDS')
        clean_env=os.environ.copy()
        for k in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','GH_TOKEN','GITHUB_TOKEN'):clean_env.pop(k,None)
        with (root/'csharp.json').open('wb') as csharp_out:
            child=subprocess.Popen(['dotnet','run','--project',PROJECT,'-c','Release','--no-build','--','--development-stream'],
              stdin=subprocess.PIPE,stdout=csharp_out,stderr=subprocess.PIPE,env=clean_env)
            try:
                for shard_index in range(25):
                    by_ordinal=collections.defaultdict(list)
                    for segment in range(1,5):
                        e=entries[(segment,shard_index)];cipher=(assets/e['ENCRYPTED_ASSET_NAME']).read_bytes()
                        need(bytes_digest(cipher)==e['ENCRYPTED_ASSET_SHA256'],'PATHSTATE_SOURCE_CIPHER')
                        plain=decrypt_synthetic_package(cipher,private_key=key)
                        need(bytes_digest(plain)==e['PLAINTEXT_CANONICAL_SHA256'],'PATHSTATE_SOURCE_PLAINTEXT')
                        data=json.loads(plain)
                        need(data['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1' and data['segment_index']==segment and
                          data['shard_index']==shard_index and data['identity_range']==e['IDENTITY_RANGE'] and
                          [x['ordinal'] for x in data['items']]==list(range(e['IDENTITY_RANGE'][0],e['IDENTITY_RANGE'][1]+1)),
                          'PATHSTATE_SHARD_IDENTITY')
                        count=0
                        for item in data['items']:
                            need(item['classification'] in ('NO_HISTORICAL_SUPPORT','SHALLOW_SUPPORT_COMPLETE','SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED')
                              and isinstance(item['rows'],list),'PATHSTATE_SUPPORT_CLASS')
                            for row in item['rows']:need(set(row)=={'time_utc','open','high','low','close','tick_volume'},'PATHSTATE_ROW_SCHEMA')
                            by_ordinal[item['ordinal']].extend(item['rows']);count+=len(item['rows'])
                        need(count==e['ROW_COUNT'],'PATHSTATE_SHARD_ROWS');rows_verified+=count;shards_verified+=1
                    for ordinal,rows in sorted(by_ordinal.items()):
                        parse_rows(rows) if rows else None
                        expected[ordinal]=reference(rows)
                        packet=encoded({'ordinal':ordinal,'rows':rows});packet_hashes[ordinal]=bytes_digest(packet)
                        child.stdin.write(packet+b'\n')
                child.stdin.close();need(child.wait(timeout=120)==0,'PATHSTATE_CSHARP_EXECUTION')
            finally:
                if child.poll() is None:child.kill();child.wait()
        need(rows_verified==3355389 and shards_verified==100 and len(expected)==1576,'PATHSTATE_COMPLETE_EXPOSURE')
        outputbytes=(root/'csharp.json').read_bytes();outputs=json.loads(outputbytes,parse_float=D)
        need([x['Ordinal'] for x in outputs]==list(range(1,1577)),'PATHSTATE_OUTPUT_ALL_ORDINALS')
        for actual in outputs:reconcile(actual,expected[actual['Ordinal']])
        need(all(x['BySegment']['1']['Complete']==0 and D(str(x['BySegment']['1']['SumGrossBps']))==0 for x in outputs),
             'PATHSTATE_FIRST_SEGMENT_TRAINING_ONLY')
        verdict,metrics=decide(outputs)
        # Decimal values are retained as exact text; original C# JSON is preserved byte-for-byte.
        details={'schema':'mxm.pathstate-development-private.v1','source_commit':commit,'spec_sha256':SPEC_SHA,
          'manifest_sha256':manifest_sha,'packet_sha256':packet_hashes,'original_csharp_json_b64':base64.b64encode(outputbytes).decode(),
          'independent_all_ordinals_reconciled':True,'metrics':metrics,'disposition':verdict,
          'rows_verified':rows_verified,'shards_verified':shards_verified,'hypothesis_count':1,'matured_training_labels':sum(x['TrainingLabels'] for x in outputs),
          'ready_forecasts':sum(x['ReadyForecasts'] for x in outputs),
          'eur200_account':False,'historical_costs':False,'native_fills':False,'hard21':False}
        out=Path(dest);out.mkdir(parents=True,exist_ok=True)
        public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==fp,'PATHSTATE_RECIPIENT')
        raw=encoded(details);encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=out/'full-result.mxmenc')
        receipt={'schema':'mxm.pathstate-development-public.v1','run_id':int(os.environ['GITHUB_RUN_ID']),
          'source_commit':commit,'spec_sha256':SPEC_SHA,'manifest_sha256':manifest_sha,'rows_verified':rows_verified,
          'shards_verified':shards_verified,'ordinals_verified':1576,'independent_episode_ledgers_reconciled':1576,'independent_signal_ledgers_reconciled':1576,'independent_forecast_ledgers_reconciled':1576,'independent_training_ledgers_reconciled':1576,
          'evaluation_start':spec['evaluation_start'],'warmup_only_source_segment':1,'friction_references_hypothetical':True,
          'mechanisms':1,'model_leaves':1,'dependent_reference_friction_leaves':4,'disposition':verdict,
          'all_gates_passed':all(metrics['gates'].values()),'partition':'DEVELOPMENT_ALREADY_FULLY_EXPOSED',
          'full_private_sha256':bytes_digest(raw),'ciphertext_sha256':bytes_digest((out/'full-result.mxmenc').read_bytes()),
          'historical_costs_proven':False,'native_fills_proven':False,'eur200_account_simulated':False,'hard21_proven':False,
          'independent_confirmation':False,'edge_confirmed':False,'canonical_V2_changed':False,'C033_preserved':True,
          'new_broker_requests':0,'orders':0,'cloud_activated':False}
        (out/'receipt.json').write_bytes(encoded(receipt))
        print('MXM_PATHSTATE_DEVELOPMENT '+json.dumps(receipt,sort_keys=True),flush=True)
        return receipt
if __name__=='__main__':
    import sys
    os.umask(0o077)
    if sys.argv[1:]==['admit']:context();print('MXM_PATHSTATE_PRECOMMIT_ADMITTED')
    else:need(len(sys.argv)==2,'PATHSTATE_ARGUMENTS');run(sys.argv[1])
