"""One finite gross-only DEVELOPMENT study. C# policy, independent Decimal episode checks.
No new broker data, EUR200 account, actual costs, formal V2 mutation or confirmation.
"""
import base64,collections,gzip,hashlib,json,os,subprocess,tempfile
from pathlib import Path
from decimal import Decimal as D
from .compression_reference import reference,reconcile
from .common import need,bytes_digest,encoded
from . import m5_authentic_envelope as env
from .m5_causal_gross_development import load_market_geometry,parse_rows
ROOT=env.ROOT
SPEC=ROOT/'research_core_v4/laboratory/COMPRESSION_DEVELOPMENT_V1.json'
SPEC_SHA='319299c9b20da772776688e92a9d621d03d0981ac588380a655fcb4c9221f363'
PROJECT='research_core_v4/native_tick_replay_v1/csharp/MxmCompressionDevelopment.csproj'
WORKFLOW='.github/workflows/mxm-compression-development.yml'
def validate_spec(active=False):
    raw=SPEC.read_bytes();need(bytes_digest(raw)==SPEC_SHA,'COMPRESSION_IMMUTABLE_PRECOMMIT')
    s=json.loads(raw)
    need(s['model_id']=='MXM_COMPRESSION_RELEASE_20261023_V1' and s['mechanisms']==1 and
         s['model_leaves']==1 and s['dependent_reference_friction_leaves']==4 and
         s['reference_roundtrip_bps']==[0,5,10,20] and s['lookbacks']=={'baseline':48,'fast':6,'channel':12} and
         s['compression_ratio']==.6 and s['delay_bars']==2 and s['hold_bars']==12 and
         not s['confirmation_opened'] and not s['protected_opened'] and s['orders']==0 and
         s['partition']=='DEVELOPMENT_ALREADY_FULLY_EXPOSED','COMPRESSION_FINITE_SCOPE')
    if active:
        for path,digest in s['implementation_sha256'].items():
            need(bytes_digest((ROOT/path).read_bytes())==digest,'COMPRESSION_FROZEN_IMPLEMENTATION_'+path)
    return s

def decide(outputs):
    n=sum(x['Complete'] for x in outputs);censored=sum(x['Censored'] for x in outputs)
    gross=sum((D(str(x['SumGrossBps'])) for x in outputs),D(0))
    blocks={k:{'episodes':sum(x['BySegment'][k]['Complete'] for x in outputs),
       'gross':sum((D(str(x['BySegment'][k]['SumGrossBps'])) for x in outputs),D(0))} for k in ('1','2','3','4')}
    contributions=sorted((abs(D(str(x['SumGrossBps']))) for x in outputs),reverse=True)
    concentration=sum(contributions[:5],D(0))/sum(contributions,D(0)) if sum(contributions,D(0)) else D(1)
    gates={'support':n>=1000,'gross':gross>0,'reference_5bps':n>0 and gross>D(5)*n,
       'all_four_source_segments_at_5bps':all(b['episodes']>0 and b['gross']>D(5)*b['episodes'] for b in blocks.values()),
       'censoring_at_most_20pct':n+censored>0 and D(censored)/D(n+censored)<=D('.2'),
       'top5_absolute_symbol_contribution_at_most_50pct':concentration<=D('.5')}
    label=('NO_COMPLETED_EPISODES' if n==0 else 'REFERENCE_SUPPORT_FAIL' if not gates['support'] else
      'GROSS_FAIL' if not gates['gross'] else 'REFERENCE_FRICTION_FAIL' if not gates['reference_5bps'] else
      'REFERENCE_TEMPORAL_FAIL' if not gates['all_four_source_segments_at_5bps'] else
      'REFERENCE_CENSORING_FAIL' if not gates['censoring_at_most_20pct'] else
      'REFERENCE_CONCENTRATION_FAIL' if not gates['top5_absolute_symbol_contribution_at_most_50pct'] else
      'REFERENCE_SCREEN_SURVIVOR_UNCONFIRMED')
    return label,{'complete':n,'censored':censored,'sum_gross_bps':str(gross),
      'mean_gross_bps':str(gross/n) if n else None,'gates':gates,'top5_abs_symbol_concentration':str(concentration),
      'reference_means_bps':{str(k):str(gross/n-D(k)) if n else None for k in (0,5,10,20)},
      'by_entry_segment':{k:{'episodes':v['episodes'],'sum_gross_bps':str(v['gross'])} for k,v in blocks.items()}}

def context():
    validate_spec(active=True)
    need(os.environ.get('GITHUB_REPOSITORY')==env.REPO and
      os.environ.get('GITHUB_REF')=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
      os.environ.get('GITHUB_EVENT_NAME') in ('push','workflow_dispatch') and
      os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')=='compression-development' and
      os.environ.get('GITHUB_WORKFLOW_REF')==env.REPO+'/'+WORKFLOW+'@refs/heads/mxm-remediation-p0-p4-20261015-v1',
      'COMPRESSION_PROTECTED_CONTEXT')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'COMPRESSION_CLEAN_CODE')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN',
      'R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN')),'COMPRESSION_NO_WRITER_OR_BROKER')
    return sha

def run(dest):
    commit=context();spec=validate_spec(active=True)
    need(bytes_digest(env.MANIFEST.read_bytes())==spec['source_manifest_sha256'] and env.RELEASE_IDENTITY==spec['source_release'],
         'COMPRESSION_EXACT_SOURCE_MANIFEST')
    entries,manifest_sha=load_market_geometry()
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package,encrypt_shard,public_spki_sha256
    rows_verified=shards_verified=0;expected={};packet_hashes={}
    with tempfile.TemporaryDirectory(prefix='mxm-compression-') as rawdir:
        root=Path(rawdir);key,fp=_private_key_from_secret(root)
        need(fp=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11','COMPRESSION_EXISTING_RECIPIENT')
        assets=root/'cipher';assets.mkdir(mode=0o700)
        subprocess.run(['gh','release','download',env.RELEASE_IDENTITY,'--repo',env.REPO,'--dir',str(assets)],
          check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        need(len(list(assets.iterdir()))==100,'COMPRESSION_ALL_SHARDS')
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
                        need(bytes_digest(cipher)==e['ENCRYPTED_ASSET_SHA256'],'COMPRESSION_SOURCE_CIPHER')
                        plain=decrypt_synthetic_package(cipher,private_key=key)
                        need(bytes_digest(plain)==e['PLAINTEXT_CANONICAL_SHA256'],'COMPRESSION_SOURCE_PLAINTEXT')
                        data=json.loads(plain)
                        need(data['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1' and data['segment_index']==segment and
                          data['shard_index']==shard_index and data['identity_range']==e['IDENTITY_RANGE'] and
                          [x['ordinal'] for x in data['items']]==list(range(e['IDENTITY_RANGE'][0],e['IDENTITY_RANGE'][1]+1)),
                          'COMPRESSION_SHARD_IDENTITY')
                        count=0
                        for item in data['items']:
                            need(item['classification'] in ('NO_HISTORICAL_SUPPORT','SHALLOW_SUPPORT_COMPLETE','SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED')
                              and isinstance(item['rows'],list),'COMPRESSION_SUPPORT_CLASS')
                            for row in item['rows']:need(set(row)=={'time_utc','open','high','low','close','tick_volume'},'COMPRESSION_ROW_SCHEMA')
                            by_ordinal[item['ordinal']].extend(item['rows']);count+=len(item['rows'])
                        need(count==e['ROW_COUNT'],'COMPRESSION_SHARD_ROWS');rows_verified+=count;shards_verified+=1
                    for ordinal,rows in sorted(by_ordinal.items()):
                        parse_rows(rows) if rows else None
                        expected[ordinal]=reference(rows)
                        packet=encoded({'ordinal':ordinal,'rows':rows});packet_hashes[ordinal]=bytes_digest(packet)
                        child.stdin.write(packet+b'\n')
                child.stdin.close();need(child.wait(timeout=120)==0,'COMPRESSION_CSHARP_EXECUTION')
            finally:
                if child.poll() is None:child.kill();child.wait()
        need(rows_verified==3355389 and shards_verified==100 and len(expected)==1576,'COMPRESSION_COMPLETE_EXPOSURE')
        outputbytes=(root/'csharp.json').read_bytes();outputs=json.loads(outputbytes,parse_float=D)
        need([x['Ordinal'] for x in outputs]==list(range(1,1577)),'COMPRESSION_OUTPUT_ALL_ORDINALS')
        for actual in outputs:reconcile(actual,expected[actual['Ordinal']])
        verdict,metrics=decide(outputs)
        # Decimal values are retained as exact text; original C# JSON is preserved byte-for-byte.
        details={'schema':'mxm.compression-development-private.v1','source_commit':commit,'spec_sha256':SPEC_SHA,
          'manifest_sha256':manifest_sha,'packet_sha256':packet_hashes,'original_csharp_json_b64':base64.b64encode(outputbytes).decode(),
          'independent_all_ordinals_reconciled':True,'metrics':metrics,'disposition':verdict,
          'rows_verified':rows_verified,'shards_verified':shards_verified,'hypothesis_count':1,
          'eur200_account':False,'historical_costs':False,'native_fills':False,'hard21':False}
        out=Path(dest);out.mkdir(parents=True,exist_ok=True)
        public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==fp,'COMPRESSION_RECIPIENT')
        raw=encoded(details);encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=out/'full-result.mxmenc')
        receipt={'schema':'mxm.compression-development-public.v1','run_id':int(os.environ['GITHUB_RUN_ID']),
          'source_commit':commit,'spec_sha256':SPEC_SHA,'manifest_sha256':manifest_sha,'rows_verified':rows_verified,
          'shards_verified':shards_verified,'ordinals_verified':1576,'independent_episode_ledgers_reconciled':1576,
          'mechanisms':1,'model_leaves':1,'dependent_reference_friction_leaves':4,'disposition':verdict,
          'all_gates_passed':all(metrics['gates'].values()),'partition':'DEVELOPMENT_ALREADY_FULLY_EXPOSED',
          'full_private_sha256':bytes_digest(raw),'ciphertext_sha256':bytes_digest((out/'full-result.mxmenc').read_bytes()),
          'historical_costs_proven':False,'native_fills_proven':False,'eur200_account_simulated':False,'hard21_proven':False,
          'independent_confirmation':False,'edge_confirmed':False,'canonical_V2_changed':False,'C033_preserved':True,
          'new_broker_requests':0,'orders':0,'cloud_activated':False}
        (out/'receipt.json').write_bytes(encoded(receipt))
        print('MXM_COMPRESSION_DEVELOPMENT '+json.dumps(receipt,sort_keys=True),flush=True)
        return receipt
if __name__=='__main__':
    import sys
    os.umask(0o077)
    if sys.argv[1:]==['admit']:context();print('MXM_COMPRESSION_PRECOMMIT_ADMITTED')
    else:need(len(sys.argv)==2,'COMPRESSION_ARGUMENTS');run(sys.argv[1])
