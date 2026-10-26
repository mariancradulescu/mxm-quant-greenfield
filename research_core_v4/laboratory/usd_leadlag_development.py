"""One precommitted dependent DEVELOPMENT mechanism; no broker, writer or account reset."""
import base64,gzip,hashlib,json,os,subprocess,sys
from decimal import Decimal as D
from pathlib import Path
from .common import need,encoded,bytes_digest
from .usd_leadlag_reference import read_routes,reference,reconcile,decide
from .usd_pair_native_reception import REPO,BRANCH,NATIVE,SOURCES,CHECKOUT,UPLOAD,one_shot
ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/'research_core_v4/laboratory/USD_LEADLAG_DEVELOPMENT_V1.json'
SPEC_SHA='0f6b3d903990213ebb5840f4ce0123f397ef329708490a09808f8cf785a40ce1'
WORKFLOW='.github/workflows/mxm-usd-leadlag-development.yml'
PROJECT='research_core_v4/laboratory/csharp/usd_leadlag/MxmUsdLeadLag.csproj'

def spec():
    need(bytes_digest(SPEC.read_bytes())==SPEC_SHA,'LEADLAG_FROZEN_SPEC')
    s=json.loads(SPEC.read_bytes())
    for p,h in s['implementation_sha256'].items():need(bytes_digest((ROOT/p).read_bytes())==h,'LEADLAG_FROZEN_IMPLEMENTATION')
    return s

def workflow():
    return {'name':'MXM finite USD leader follower DEVELOPMENT','on':{'push':{'branches':[BRANCH],'paths':[WORKFLOW]}},
      'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{'usd-leadlag-development':{
      'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",
      'runs-on':'ubuntu-24.04','timeout-minutes':30,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[
       {'uses':CHECKOUT,'with':{'persist-credentials':False}},
       {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.sealed-chronology-source','persist-credentials':False}},
       {'name':'Admit one exact prospective model before custody','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m research_core_v4.laboratory.usd_leadlag_development admit'},
       {'name':'Compile CSharp and verify causal synthetic cases before economic inputs','run':
        'dotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_usd_leadlag_development -v\n'
        'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
        'python3 -m research_core_v4.laboratory.durable_week_chronology --out "${RUNNER_TEMP}/mxm-leadlag/eur-source"\n'
        'python3 -m research_core_v4.laboratory.durable_gbpusd_week37_chronology --out "${RUNNER_TEMP}/mxm-leadlag/gbp-source"\n'
        'cp research_core_v4/laboratory/week_chronology_reception.py research_core_v4/laboratory/usd_pair_native_reception.py research_core_v4/laboratory/usd_pair_alignment.py .sealed-chronology-source/research_core_v4/laboratory/'},
       {'name':'Decode original sources inside unchanged existing custody','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':
        'umask 077\ncd .sealed-chronology-source\n'
        'python3 -m research_core_v4.laboratory.usd_pair_native_reception export EURUSD "${RUNNER_TEMP}/mxm-leadlag/eur-source/capture.mxmenc" "${RUNNER_TEMP}/mxm-leadlag/eur.ndjson"\n'
        'python3 -m research_core_v4.laboratory.usd_pair_native_reception export GBPUSD "${RUNNER_TEMP}/mxm-leadlag/gbp-source/capture.mxmenc" "${RUNNER_TEMP}/mxm-leadlag/gbp.ndjson"'},
       {'name':'Run one CSharp candidate and independent offline selection; encrypt every economic number','run':
        'umask 077\ndotnet run --project '+PROJECT+' -c Release --no-build -- "${RUNNER_TEMP}/mxm-leadlag/eur.ndjson" "${RUNNER_TEMP}/mxm-leadlag/gbp.ndjson" "${RUNNER_TEMP}/mxm-leadlag/csharp.json"\n'
        'python3 -m research_core_v4.laboratory.usd_leadlag_development result "${RUNNER_TEMP}/mxm-leadlag" verification/usd-leadlag-development'},
       {'uses':UPLOAD,'with':{'name':'usd-leadlag-development-${{ github.run_id }}','path':'verification/usd-leadlag-development/receipt.json\nverification/usd-leadlag-development/full-result.mxmenc','if-no-files-found':'error','retention-days':90}}
      ]}}}

def admit():
    spec()
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')=='usd-leadlag-development' and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+WORKFLOW+'@refs/heads/'+BRANCH,'LEADLAG_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID',
      'R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM')),'LEADLAG_NO_KEYS')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'LEADLAG_EXACT_CHECKOUT')
    need(json.loads((ROOT/WORKFLOW).read_bytes())==workflow(),'LEADLAG_EXACT_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==sha,'LEADLAG_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'LEADLAG_UNCHANGED_AUTHORITY')
    one_shot(route.json('actions/workflows/'+WORKFLOW.split('/')[-1]+'/runs?per_page=100'),int(os.environ['GITHUB_RUN_ID']))
    print('LEADLAG_ONE_PROSPECTIVE_DEPENDENT_DEVELOPMENT_NO_BROKER_NO_WRITER')

def result(folder,destination):
    spec();folder=Path(folder);raw=(folder/'csharp.json').read_bytes();c=json.loads(raw,parse_float=D)
    need(c['schema']=='mxm.csharp.usd-leadlag-development.v1' and c['broker_orders']==0 and
      all(c[k] is False for k in ('capital_replay','hard21_proven','edge_confirmed','historical_costs_proven','native_fills_proven')),'LEADLAG_NO_PROMOTION')
    for symbol,name in [('EURUSD','eur'),('GBPUSD','gbp')]:
        r=json.loads((folder/(name+'.ndjson.receipt.json')).read_bytes());s=SOURCES[symbol]
        need(r['source_run']==s['run'] and r['source_code']==s['code'] and r['source_trigger']==s['trigger'] and
          r['cipher_sha256']==s['cipher'] and r['private_sha256']==s['private'] and
          r['derived_sha256']==c[name+'_sha256']==bytes_digest((folder/(name+'.ndjson')).read_bytes()),'LEADLAG_EXACT_ORIGINAL_SOURCE')
    source,rows=read_routes(folder/'eur.ndjson',folder/'gbp.ndjson');need(source==c['source'] and source['Rows']==1960588,'LEADLAG_FULL_SOURCE_PARITY')
    expected=reference(rows);reconcile(c['result'],expected);verdict,metrics=decide(expected)
    details={'schema':'mxm.usd-leadlag-private.v1','source_sha':os.environ['GITHUB_SHA'],'spec_sha256':SPEC_SHA,
      'original_csharp_json_b64':base64.b64encode(raw).decode(),'independent_metrics':metrics,'disposition':verdict,
      'independent_all_decisions_and_episodes_reconciled':True,'hypotheses':1,'model_leaves':1,'partition':'DEVELOPMENT_ALREADY_EXPOSED',
      'capital_replay':False,'hard21_proven':False,'historical_costs_proven':False,'native_fills_proven':False}
    out=Path(destination);out.mkdir(parents=True,exist_ok=True)
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public)=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11','LEADLAG_EXISTING_CUSTODY')
    private=encoded(details);encrypt_shard(gzip.compress(private,mtime=0),public_key=public,output=out/'full-result.mxmenc')
    receipt={'schema':'mxm.usd-leadlag-public.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['GITHUB_SHA'],
      'spec_sha256':SPEC_SHA,'source_rows':1960588,'source_runs':{s:v['run'] for s,v in SOURCES.items()},
      'independent_all_decisions_and_episodes_reconciled':True,'disposition':verdict,'hypotheses':1,'model_leaves':1,
      'dependent_fee_slippage_scenarios':1,'partition':'DEVELOPMENT_ALREADY_EXPOSED','private_sha256':bytes_digest(private),
      'ciphertext_sha256':bytes_digest((out/'full-result.mxmenc').read_bytes()),'csharp_sha256':bytes_digest(raw),
      'capital_replay':False,'hard21_proven':False,'edge_confirmed':False,'historical_costs_proven':False,
      'native_fills_proven':False,'canonical_V2_changed':False,'orders':0,'new_broker_requests':0,'cloud_activated':False,
      'next_action':'STOP_FIXED_MODEL_NO_RETUNE' if verdict!='DEVELOPMENT_SURVIVOR_UNCONFIRMED' else 'SEPARATE_ADMISSION_REQUIRED_FOR_CONTINUOUS_EUR200_AND_COST_VALIDATION'}
    (out/'receipt.json').write_bytes(encoded(receipt));print(json.dumps(receipt,sort_keys=True))
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==4 and sys.argv[1]=='result':result(*sys.argv[2:])
    else:raise ValueError('LEADLAG_EXACT_ARGUMENTS')
