"""One frozen dependent DEVELOPMENT headroom trial; no cost defaults or account funding."""
import base64,gzip,json,os,subprocess,sys
from decimal import Decimal as D
from pathlib import Path
from .common import need,encoded,bytes_digest
from .spread_reversion_reference import source_rows,reference,reconcile,decide,PROJECT
from .usd_pair_native_reception import REPO,BRANCH,NATIVE,SOURCES,CHECKOUT,UPLOAD,one_shot
from .gbpusd_source_exposure import source_receipt
from .durable_gbpusd_week37_chronology import ROOT as ARCHIVE
ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/'research_core_v4/laboratory/SPREAD_REVERSION_DEVELOPMENT_V1.json'
SPEC_SHA='169a1dce04bc7fa1fe3f0fc37aa7378566d08da9ec4d6817cc6d4d66df3e7eed'
PATH='.github/workflows/mxm-spread-reversion-development.yml';JOB='spread-reversion-development'
MODULE='research_core_v4.laboratory.spread_reversion_development';OUT='verification/spread-reversion-development'
SECRET_NAMES=('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM')
def spec():
    need(bytes_digest(SPEC.read_bytes())==SPEC_SHA,'SPREAD_FROZEN_SPEC');s=json.loads(SPEC.read_bytes())
    for p,h in s['implementation_sha256'].items():need(bytes_digest((ROOT/p).read_bytes())==h,'SPREAD_FROZEN_IMPLEMENTATION')
    return s

def workflow():
    return {'name':'MXM one prospective unilateral spread reversion headroom trial',
      'on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
      'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{JOB:{
      'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",
      'runs-on':'ubuntu-24.04','timeout-minutes':25,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[
       {'uses':CHECKOUT,'with':{'persist-credentials':False}},
       {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.sealed-chronology-source','persist-credentials':False}},
       {'name':'Admit one frozen hypothesis and full existing week before custody','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
       {'name':'Compile actual CSharp and verify independent artificial causal cases before market data','run':
        'dotnet build '+PROJECT+' -c Release\n'
        'python3 -m unittest research_core_v4.laboratory.test_spread_reversion research_core_v4.laboratory.test_spread_reversion_development -v\n'
        'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
        'python3 -m research_core_v4.laboratory.durable_gbpusd_week37_chronology --out "${RUNNER_TEMP}/mxm-spread/original"\n'
        'cp research_core_v4/laboratory/week_chronology_reception.py research_core_v4/laboratory/usd_pair_native_reception.py research_core_v4/laboratory/usd_pair_alignment.py research_core_v4/laboratory/spread_reversion_cold.py .sealed-chronology-source/research_core_v4/laboratory/'},
       {'name':'Authenticate existing complete GBPUSD history only in pinned native custody','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},
        'run':'umask 077\ncd .sealed-chronology-source\npython3 -m research_core_v4.laboratory.usd_pair_native_reception export GBPUSD "${RUNNER_TEMP}/mxm-spread/original/capture.mxmenc" "${RUNNER_TEMP}/mxm-spread/gbp.ndjson"'},
       {'name':'Run one model without key and reconcile every decision episode and unresolved case; encrypt all economics',
        'env':{'GH_TOKEN':'${{ github.token }}'},'run':
        'umask 077\ndotnet run --project '+PROJECT+' -c Release --no-build -- "${RUNNER_TEMP}/mxm-spread/gbp.ndjson" "${RUNNER_TEMP}/mxm-spread/csharp.json"\n'
        'python3 -m '+MODULE+' result "${RUNNER_TEMP}/mxm-spread"'},
       {'name':'Separate custody process reads back exact encrypted economic result without running a model',
        'env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':
        'umask 077\ncd .sealed-chronology-source\npython3 -m research_core_v4.laboratory.spread_reversion_cold'},
       {'uses':UPLOAD,'with':{'name':'spread-reversion-development-${{ github.run_id }}','path':OUT+'/receipt.json\n'+OUT+'/full-result.mxmenc\n'+OUT+'/evaluator.dll\n'+OUT+'/cold.json','if-no-files-found':'error','retention-days':90}}
      ]}}}

def admit():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')==JOB and
      os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'SPREAD_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in SECRET_NAMES),'SPREAD_NO_KEYS_BEFORE_ADMISSION');spec()
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      subprocess.check_output(['git','-C','.sealed-chronology-source','rev-parse','HEAD'],text=True).strip()==NATIVE and
      json.loads((ROOT/PATH).read_bytes())==workflow(),'SPREAD_EXACT_CHECKOUT_AND_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==sha,'SPREAD_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'SPREAD_UNCHANGED_AUTHORITIES')
    one_shot(route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100'),int(os.environ['GITHUB_RUN_ID']))
    print('MXM_SPREAD_ONE_FROZEN_DEVELOPMENT_TRIAL_NO_BROKER_NO_NET_OR_ACCOUNT_CLAIM',flush=True)

def result(folder):
    admit();folder=Path(folder);raw=(folder/'csharp.json').read_bytes();c=json.loads(raw,parse_float=D)
    need(c['schema']=='mxm.csharp.spread-widening-reversion.v1' and c['broker_orders']==0 and
      all(c[k] is False for k in ('capital_replay','historical_arrival_order_proven','historical_costs_proven','costs_defaulted_to_zero','net_edge_proven','hard21_proven','native_robot_operational_reception_proven')),'SPREAD_NO_PROMOTION')
    bridge=json.loads((folder/'gbp.ndjson.receipt.json').read_bytes());manifest=json.loads((ROOT/ARCHIVE/'MANIFEST.json').read_bytes())
    original=source_receipt(bridge,manifest)
    need(bytes_digest((folder/'gbp.ndjson').read_bytes())==bridge['derived_sha256']==c['input_sha256'],'SPREAD_ORIGINAL_DERIVED_INPUT')
    source,rows=source_rows(folder/'gbp.ndjson')
    need(source==c['source'] and source['Rows']==1275114 and source['Groups']==812355 and source['SourceRows']['EURUSD']==0,'SPREAD_EVERY_ORIGINAL_SOURCE_GROUP')
    expected=reference(rows);reconcile(c['result'],expected);verdict,gates,metrics=decide(expected)
    binary=ROOT/'research_core_v4/laboratory/csharp/spread_reversion/bin/Release/net8.0/MxmSpreadReversion.dll'
    need(bytes_digest(binary.read_bytes())==c['assembly_sha256'],'SPREAD_ACTUAL_EVALUATOR_BINARY')
    private={'schema':'mxm.spread-reversion-development-private.v1','source_sha':os.environ['GITHUB_SHA'],'spec_sha256':SPEC_SHA,
      'original_source':original,'original_csharp_json_b64':base64.b64encode(raw).decode(),'private_metrics':metrics,
      'disposition':verdict,'gates':gates,'every_decision_episode_and_censor_reconciled':True,'new_hypotheses':1,'model_trials':1,
      'capital_replay':False,'net_edge_proven':False,'historical_costs_proven':False,'hard21_proven':False,'native_robot_operational_reception_proven':False}
    out=ROOT/OUT;out.mkdir(parents=True,exist_ok=True)
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public)=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11','SPREAD_EXISTING_CUSTODY')
    encoded_private=encoded(private);need(len(encoded_private)<30000000,'SPREAD_PRIVATE_RESULT_CAP')
    encrypt_shard(gzip.compress(encoded_private,mtime=0),public_key=public,output=out/'full-result.mxmenc');(out/'evaluator.dll').write_bytes(binary.read_bytes())
    receipt={'schema':'mxm.spread-reversion-development-public.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['GITHUB_SHA'],
      'spec_sha256':SPEC_SHA,'source_run':SOURCES['GBPUSD']['run'],'source_rows':1275114,'source_groups':812355,
      'every_decision_episode_and_censor_reconciled':True,'disposition':verdict,'gates':gates,'new_hypotheses':1,'model_trials':1,
      'partition':'DEVELOPMENT_ALREADY_EXPOSED','private_sha256':bytes_digest(encoded_private),'ciphertext_sha256':bytes_digest((out/'full-result.mxmenc').read_bytes()),
      'csharp_output_sha256':bytes_digest(raw),'evaluator_sha256':c['assembly_sha256'],'capital_replay':False,'net_edge_proven':False,
      'costs_defaulted_to_zero':False,'historical_costs_proven':False,'hard21_proven':False,'native_robot_operational_reception_proven':False,
      'formal_V2_or_C033_changed':False,'protected_or_confirmation_opened':False,'new_broker_requests':0,'orders':0,'cloud_activated':False,
      'next_action':'STOP_FIXED_IDENTITY_NO_RETUNE_OR_AUTOMATIC_FOLLOWUP'}
    (out/'receipt.json').write_bytes(encoded(receipt)+b'\n');print('MXM_SPREAD_DEVELOPMENT '+encoded(receipt).decode(),flush=True)
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==3 and sys.argv[1]=='result':result(sys.argv[2])
    else:raise ValueError('SPREAD_EXACT_PHASE')
