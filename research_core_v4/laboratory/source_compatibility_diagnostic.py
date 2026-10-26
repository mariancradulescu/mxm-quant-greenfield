"""Finite read-only source admission and original-fault readback. NO model execution."""
import base64,io,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
from .intrinsic_original_readback import read_bundle,sha,SCIENCE,RUN,SOURCE,ARCHIVES
ROOT=Path(__file__).resolve().parents[2]
from .account_source_preflight import scan,consecutive
from .three_week_source_recovery import FOLDERS,RUNS,ROWS,NATIVE
from .common import need,encoded
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
PATH='.github/workflows/mxm-source-compatibility-diagnostic.yml'
CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'
def workflow():
    prep='python3 -m unittest research_core_v4.laboratory.test_account_source_preflight research_core_v4.laboratory.test_source_compatibility_diagnostic -v\npython3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
    for w,mod in [('W35','durable_week35_chronology'),('W36','durable_week36_chronology'),('W37','durable_week_chronology')]:prep+='python3 -m research_core_v4.laboratory.'+mod+' --out "${RUNNER_TEMP}/mxm-source-admission/'+w+'"\n'
    prep+='cp research_core_v4/laboratory/week_chronology_reception.py research_core_v4/laboratory/three_week_source_recovery.py .sealed-chronology-source/research_core_v4/laboratory/\n'
    export='umask 077\ncd .sealed-chronology-source\n'
    for w in FOLDERS:export+='python3 -m research_core_v4.laboratory.three_week_source_recovery '+w+' "${RUNNER_TEMP}/mxm-source-admission/'+w+'/capture.mxmenc" "${RUNNER_TEMP}/mxm-source-admission/'+w+'.ndjson"\n'
    return {'name':'MXM finite source compatibility and original fault diagnostic','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{'source-compatibility':{'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",'runs-on':'ubuntu-24.04','timeout-minutes':20,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[
      {'uses':CHECKOUT,'with':{'persist-credentials':False}},
      {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.sealed-chronology-source','persist-credentials':False}},
      {'name':'Admit one diagnostic before custody access','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m research_core_v4.laboratory.source_compatibility_diagnostic admit'},
      {'name':'Verify original bytes and real schemas before any decryption','run':prep},
      {'name':'Reauthenticate existing sources without model or new broker request','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':export},
      {'name':'Source preflight and whitelist-only original fault readback without economic replay','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\npython3 -m research_core_v4.laboratory.source_compatibility_diagnostic diagnose "${RUNNER_TEMP}/mxm-source-admission"'}
    ]}}}
def admit():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')=='source-compatibility' and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'SOURCE_DIAGNOSTIC_CONTEXT')
    need(not any(os.environ.get(k) for k in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN')),'SOURCE_DIAGNOSTIC_NO_KEYS_BEFORE_ADMISSION')
    code=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(code==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and json.loads((ROOT/PATH).read_bytes())==workflow(),'SOURCE_DIAGNOSTIC_EXACT_CODE')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==code,'SOURCE_DIAGNOSTIC_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'SOURCE_DIAGNOSTIC_AUTHORITY')
    v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
    need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and v['workflow_runs'][0]['run_attempt']==1,'SOURCE_DIAGNOSTIC_ONE_FINITE_ATTEMPT')
    original=route.json('actions/runs/'+str(RUN))
    need(original['head_sha']==SOURCE and original['run_attempt']==1 and original['status']=='completed' and original['conclusion']=='success','SOURCE_DIAGNOSTIC_ORIGINAL_RUN')
    ident=12633527925;kind,size,digest=ARCHIVES[ident];meta=route.json('actions/artifacts/'+str(ident))
    need(meta['id']==ident and meta['workflow_run']['id']==RUN and meta['workflow_run']['head_sha']==SOURCE and meta['size_in_bytes']==size and meta['digest']=='sha256:'+digest and not meta['expired'],'SOURCE_DIAGNOSTIC_ORIGINAL_ARTIFACT')
    raw=route.data('actions/artifacts/'+str(ident)+'/zip',limit=1000000);read_bundle(raw,kind,size,digest)
    folder=Path(os.environ['RUNNER_TEMP'])/'mxm-source-admission';folder.mkdir(exist_ok=True)
    (folder/'original-result.zip').write_bytes(raw)
    print('SOURCE_COMPATIBILITY_ONLY_NO_NEW_MODEL_NO_ECONOMIC_EXECUTION_NO_WRITER')
def original_fault(private):
    need(private['schema']=='mxm.intrinsic-account-private.v1' and private['source_sha']=='b5b14da063a40f93797b8bc8a15537fe79489215' and private['spec_sha256']==SCIENCE and private['disposition']=='DATA_LIMITED' and private['gates']=={'complete_three_week_account':False},'DIAGNOSTIC_ORIGINAL_PRIVATE_IDENTITY')
    segments=private['independent_reference']['segments'];actual=private['original_csharp_json_b64']
    need(len(segments)==len(actual)==1,'DIAGNOSTIC_ORIGINAL_SEGMENT_COUNT')
    r=json.loads(base64.b64decode(actual[0],validate=True));f=segments[0]['fault']
    allowed=('OPEN_EXPOSURE_INSTRUMENT_UNPRICEABLE','OPEN_EXPOSURE_FX_UNPRICEABLE')
    need(f in allowed and isinstance(r['fault'],str) and f in r['fault'] and r['account'] is None,'DIAGNOSTIC_EXACT_WHITELIST_FAULT')
    return f

def diagnose(folder):
    folder=Path(folder);diagnostics={};receipts=[]
    for w,p in FOLDERS.items():
        path=folder/(w+'.ndjson');r=json.loads(Path(str(path)+'.receipt.json').read_bytes());m=json.loads((ROOT/p/'MANIFEST.json').read_bytes())
        need(r['profile']==w and r['run']==RUNS[w] and r['rows']==ROWS[w],'DIAGNOSTIC_REGISTERED_SOURCES');receipts.append(r)
        v=scan(path,r,m)
        diagnostics[w]={'source_run':RUNS[w],'rows_verified':v['rows_verified'],'admission':v['admission'],'unavailable_categories':sorted(v['reasons']),'coverage_between_observations_proven':False}
    consecutive(receipts)
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    kind,size,digest=ARCHIVES[12633527925]
    original=read_bundle((folder/'original-result.zip').read_bytes(),kind,size,digest)
    need(sha(original['receipt.json'])=='bb7300fc9bff4a05edea572cffda4732c72558458209e7f826d82dd97bbf3d36','DIAGNOSTIC_ORIGINAL_PUBLIC_RECEIPT')
    cipher=original['full-result.mxmenc'];receipt=json.loads(original['receipt.json'])
    need(sha(cipher)==receipt['ciphertext_sha256'],'DIAGNOSTIC_ORIGINAL_CIPHER')
    with tempfile.TemporaryDirectory() as t:
        key,fp=_private_key_from_secret(Path(t));need(fp==FP,'DIAGNOSTIC_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(t)),max_bytes=2000000)
        need(sha(raw)==receipt['private_sha256'],'DIAGNOSTIC_ORIGINAL_PLAINTEXT_COMMITMENT')
        fault=original_fault(strict_json(raw,max_elements=200000))
    result={'schema':'mxm.source-compatibility-diagnostic-public.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['GITHUB_SHA'],'original_economic_run':40285218660,'original_fault_verified':fault,'sources':diagnostics,'no_fault_category_causation_claim':True,'scientific_parameters_changed':False,'new_models':0,'new_economic_outcomes':0,'economic_rerun':False,'new_broker_requests':0,'orders':0,'cloud_activated':False,'protected_opened':False,'next_action':'STOP_FIXED_POLICY;REQUIRE_SOURCE_EXPOSURE_CONTRACT_BEFORE_NEXT_DISTINCT_MODEL'}
    print('MXM_SOURCE_COMPATIBILITY_RESULT '+encoded(result).decode(),flush=True)
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==3 and sys.argv[1]=='diagnose':diagnose(sys.argv[2])
    else:raise ValueError('SOURCE_DIAGNOSTIC_EXACT_PHASE')
