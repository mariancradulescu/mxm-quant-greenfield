"""One custody-only original-source cause readback; no new feed/model/response."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
from .common import need,encoded,bytes_digest
from .spot_source_causes import PROJECT,reconcile
from .durable_spot_observation import MANIFEST_SHA
ROOT=Path(__file__).resolve().parents[2]
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd';ORIGINAL_HEAD='d16db0a9e40ca2f48f8b9f0d483ca3b131d173e1'
FOLDER='docs/economic-development/20261027/native-spot-40455704891'
PATH='.github/workflows/mxm-spot-source-cause-reception.yml'
MODULE='research_core_v4.laboratory.spot_source_cause_reception';JOB='spot-source-causes'
FILES=('spot_source_cause_reception.py','spot_source_causes.py','durable_spot_observation.py','spot_observation_reception.py','spot_observation_profile.py')
OUT='verification/spot-source-causes/receipt.json'
POLICY={'schema':'mxm.spot-source-cause-policy.v1','original_run':40455704891,'original_manifest_sha256':MANIFEST_SHA,
 'all_original_events':1140,'symbol_ids':[1,2,250],'max_side_age_ms':5000,'minimum_observed_span_ms':300000,
 'new_broker_requests':0,'new_response_tests':0,'economic_model_runs':0,'orders':0,'consumer_policy_changed':False,
 'scope':'LOCKED_CROSSED_FIELD_PRESENCE_SAME_PRICE_AND_RECEIPT_GAP_CAUSES_WITH_CSHARP_PARITY'}
POLICY_SHA=bytes_digest(encoded(POLICY))
def workflow():
    return {'name':'MXM original spot source causes and CSharp input parity',
     'on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
     'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{JOB:{
      'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",
      'runs-on':'ubuntu-24.04','timeout-minutes':12,'environment':'mxm-r3-custody-v1',
      'permissions':{'contents':'read','actions':'read'},'steps':[
       {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','with':{'persist-credentials':False}},
       {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','with':{'ref':NATIVE,'path':'.cause-native','persist-credentials':False}},
       {'name':'Admit one original-source readback before custody access','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
       {'name':'Compile actual shared CSharp geometry and restore original ciphertext without key','run':
        'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
        'dotnet build '+PROJECT+' -c Release\n'
        'python3 -m unittest research_core_v4.laboratory.test_spot_source_causes research_core_v4.laboratory.test_spot_source_cause_reception -v\n'
        'python3 -m research_core_v4.laboratory.durable_spot_observation --out "${RUNNER_TEMP}/mxm-source-causes/original"\n'
        'cp '+' '.join('research_core_v4/laboratory/'+f for f in FILES)+' .cause-native/research_core_v4/laboratory/'},
       {'name':'Authenticate original source and export all receipt events only in native custody',
        'env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},
        'run':'umask 077\ncd .cause-native\npython3 -m '+MODULE+' export "${RUNNER_TEMP}/mxm-source-causes/original/capture.mxmenc" "${RUNNER_TEMP}/mxm-source-causes/events.ndjson"'},
       {'name':'Classify actual source in CSharp and independently reconcile every original disposition',
        'env':{'GH_TOKEN':'${{ github.token }}'},'run':
        'umask 077\ndotnet run --project '+PROJECT+' -c Release --no-build -- "${RUNNER_TEMP}/mxm-source-causes/events.ndjson" "${RUNNER_TEMP}/mxm-source-causes/csharp.json"\n'
        'python3 -m '+MODULE+' finalize "${RUNNER_TEMP}/mxm-source-causes"'},
       {'uses':'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02','with':{
        'name':'spot-source-causes-${{ github.run_id }}','path':OUT,'if-no-files-found':'error','retention-days':90}}
      ]}}}
def one_shot(v,run):
    need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==run and v['workflow_runs'][0]['run_attempt']==1,'SPOT_CAUSE_ONE_ATTEMPT')
def context():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')==JOB and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'SPOT_CAUSE_NATIVE_CONTEXT')
def no_keys(custody=False):
    names=['SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM']
    if not custody:names.append('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')
    need(not any(os.environ.get(k) for k in names),'SPOT_CAUSE_SECRET_ROLE_SEPARATION')
def admit():
    context();no_keys()
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      subprocess.check_output(['git','-C','.cause-native','rev-parse','HEAD'],text=True).strip()==NATIVE and
      json.loads((ROOT/PATH).read_bytes())==workflow(),'SPOT_CAUSE_EXACT_SOURCE_AND_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'SPOT_CAUSE_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'SPOT_CAUSE_AUTHORITY')
    one_shot(route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100'),int(os.environ['GITHUB_RUN_ID']))
    original=route.json('actions/runs/40455704891')
    need(original['head_sha']==ORIGINAL_HEAD and original['run_attempt']==1 and original['status']=='completed' and original['conclusion']=='success','SPOT_CAUSE_ORIGINAL_NATIVE_RUN')
    print('MXM_ORIGINAL_CAUSE_ADMITTED_NO_MODEL_NO_NEW_BROKER_REQUEST',flush=True)
    return head

def export(cipher_path,output):
    context();no_keys(custody=True);main=ROOT.parent
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0 and
      json.loads((main/PATH).read_bytes())==workflow(),'SPOT_CAUSE_PINNED_EXPORT_SOURCE')
    for f in FILES:need((ROOT/'research_core_v4/laboratory'/f).read_bytes()==(main/'research_core_v4/laboratory'/f).read_bytes(),'SPOT_CAUSE_EXACT_NATIVE_EXTENSION')
    manifest_raw=(main/FOLDER/'MANIFEST.json').read_bytes();need(bytes_digest(manifest_raw)==MANIFEST_SHA,'SPOT_CAUSE_ORIGINAL_MANIFEST')
    manifest=json.loads(manifest_raw);cipher=Path(cipher_path).read_bytes()
    need(bytes_digest(cipher)==manifest['members']['capture.mxmenc']['sha256'],'SPOT_CAUSE_ORIGINAL_CIPHER')
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    from .spot_observation_reception import verify_private,market_event
    with tempfile.TemporaryDirectory() as tmp:
        key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'SPOT_CAUSE_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)),max_bytes=24000000)
        need(bytes_digest(raw)==manifest['private_sha256'],'SPOT_CAUSE_ORIGINAL_PRIVATE')
        p=strict_json(raw,max_elements=3000000)
        need(p['identity']['source_sha']==ORIGINAL_HEAD and p['identity']['run_id']==40455704891 and p['identity']['attempt']==1,'SPOT_CAUSE_ORIGINAL_IDENTITY')
        original_profile=verify_private(p);need(original_profile==manifest['profile'] and len(p['market'])==1140,'SPOT_CAUSE_ALL_ORIGINAL_EVENTS')
        out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('xb') as stream:
            for row in p['market']:stream.write(encoded(market_event(row,p['account']))+b'\n')
    bridge={'schema':'mxm.spot-source-cause-native-export.v1','original_run':40455704891,'original_head':ORIGINAL_HEAD,
      'cipher_sha256':bytes_digest(cipher),'private_sha256':manifest['private_sha256'],'derived_sha256':bytes_digest(out.read_bytes()),
      'rows':1140,'original_profile':original_profile,'policy_sha256':POLICY_SHA,'new_broker_requests':0,'orders':0,'new_response_tests':0}
    Path(str(out)+'.receipt.json').write_bytes(encoded(bridge)+b'\n')
    print('MXM_ORIGINAL_ALL_SPOT_EVENTS_EXPORTED_CUSTODY_ONLY_NO_MODEL',flush=True)
def finalize(folder):
    head=admit();folder=Path(folder);path=folder/'events.ndjson'
    bridge=json.loads(Path(str(path)+'.receipt.json').read_bytes());report=json.loads((folder/'csharp.json').read_bytes())
    manifest=json.loads((ROOT/FOLDER/'MANIFEST.json').read_bytes())
    need(bridge['original_run']==40455704891 and bridge['original_head']==ORIGINAL_HEAD and bridge['rows']==1140 and
      bridge['cipher_sha256']==manifest['members']['capture.mxmenc']['sha256'] and bridge['private_sha256']==manifest['private_sha256'] and
      bridge['derived_sha256']==report['input_sha256'] and bridge['original_profile']==manifest['profile'] and
      bridge['policy_sha256']==POLICY_SHA,'SPOT_CAUSE_ORIGINAL_NATIVE_BRIDGE')
    reconcile(path,report)
    result=report['result'];need(result['events']==1140 and result['profile']==manifest['profile'],'SPOT_CAUSE_ORIGINAL_PROFILE_UNCHANGED')
    dll=ROOT/'research_core_v4/laboratory/csharp/spot_source/bin/Release/net8.0/MxmSpotSource.dll'
    need(report['source_commit']==head and report['assembly_sha256']==bytes_digest(dll.read_bytes()),'SPOT_CAUSE_ACTUAL_CSHARP_BINARY')
    output={'schema':'mxm.native-spot-source-cause-reception.v1','run_id':int(os.environ['GITHUB_RUN_ID']),
      'source_sha':head,'policy_sha256':POLICY_SHA,'original_source_run':40455704891,'original_source_head':ORIGINAL_HEAD,
      'original_manifest_sha256':MANIFEST_SHA,'original_private_sha256':bridge['private_sha256'],
      'derived_input_sha256':bridge['derived_sha256'],'csharp_assembly_sha256':report['assembly_sha256'],
      'csharp_result':result,'every_event_disposition_independently_reconciled':True,'original_profile_unchanged':True,
      'original_capture_remains_development_excluded_from_confirmation':True,
      'native_product_geometry_predicate_changed':False,'new_broker_requests':0,'orders':0,'cloud_activated':False,
      'new_response_tests':0,'economic_model_runs':0,'economic_edge_proven':False,'hard21_proven':False,'native_robot_operational_reception_proven':False}
    dest=ROOT/OUT;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(encoded(output)+b'\n')
    print('MXM_NATIVE_SPOT_SOURCE_CAUSES '+encoded(output).decode(),flush=True)
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==4 and sys.argv[1]=='export':export(*sys.argv[2:])
    elif len(sys.argv)==3 and sys.argv[1]=='finalize':finalize(sys.argv[2])
    else:raise ValueError('SPOT_CAUSE_EXACT_PHASE')
