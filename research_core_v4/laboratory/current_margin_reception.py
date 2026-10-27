"""One finite custody-only readback of already saved current metadata/margins."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
from .common import need,encoded,bytes_digest
from .current_margin_evidence import PROJECT,extract,reference,run_report
from .durable_spot_observation import MANIFEST_SHA
ROOT=Path(__file__).resolve().parents[2]
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd';ORIGINAL_HEAD='d16db0a9e40ca2f48f8b9f0d483ca3b131d173e1'
FOLDER='docs/economic-development/20261027/native-spot-40455704891'
PATH='.github/workflows/mxm-current-margin-reception.yml';MODULE='research_core_v4.laboratory.current_margin_reception';JOB='current-margin'
FILES=('current_margin_reception.py','current_margin_evidence.py','universe_commission_checks.py','durable_spot_observation.py','spot_observation_reception.py','spot_observation_profile.py')
OUT='verification/current-margin/receipt.json'
POLICY={'schema':'mxm.current-margin-evidence-policy.v1','original_run':40455704891,'original_manifest_sha256':MANIFEST_SHA,
 'symbol_ids':[1,2,250],'volume_rule':'EXACT_ORIGINAL_REQUESTED_SYMBOL_MINIMUM_ALL_THREE_BOTH_SIDES',
 'reference_capital_eur':'200','maximum_ticket_margin_eur':'80','minimum_free_margin_reference_eur':'120',
 'fee_zero_is_lower_bound_not_observed_fee':True,'missing_money_digits':'UNRESOLVED_NO_DEFAULT',
 'margin_applicability':'SOURCE_CONTACT_INTERVAL_ONLY_NOT_ORDER_OR_HISTORICAL_CERTIFICATION',
 'market_prices_exported':False,'response_tests':0,'economic_model_runs':0,'new_broker_requests':0,'orders':0,'automatic_retry':False}
POLICY_SHA=bytes_digest(encoded(POLICY))
def workflow():
    return {'name':'MXM existing contemporary minimum-volume margin evidence',
     'on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
     'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{JOB:{
      'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",
      'runs-on':'ubuntu-24.04','timeout-minutes':12,'environment':'mxm-r3-custody-v1',
      'permissions':{'contents':'read','actions':'read'},'steps':[
       {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','with':{'persist-credentials':False}},
       {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','with':{'ref':NATIVE,'path':'.margin-native','persist-credentials':False}},
       {'name':'Admit exact one-shot existing evidence scope before custody','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
       {'name':'Compile shared margin and cost decoders and verify artificial boundaries without keys','run':
        'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
        'dotnet build '+PROJECT+' -c Release\n'
        'python3 -m unittest research_core_v4.laboratory.test_current_margin_evidence research_core_v4.laboratory.test_current_margin_reception -v\n'
        'python3 -m research_core_v4.laboratory.durable_spot_observation --out "${RUNNER_TEMP}/mxm-current-margin/original"\n'
        'cp '+' '.join('research_core_v4/laboratory/'+f for f in FILES)+' .margin-native/research_core_v4/laboratory/'},
       {'name':'Authenticate original source and export only existing metadata and margin responses',
        'env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},
        'run':'umask 077\ncd .margin-native\npython3 -m '+MODULE+' export "${RUNNER_TEMP}/mxm-current-margin/original/capture.mxmenc" "${RUNNER_TEMP}/mxm-current-margin/input.json"'},
       {'name':'Reconcile every contemporary estimate CSharp Decimal and independent Python',
        'env':{'GH_TOKEN':'${{ github.token }}'},'run':'umask 077\npython3 -m '+MODULE+' finalize "${RUNNER_TEMP}/mxm-current-margin"'},
       {'uses':'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02','with':{
        'name':'current-margin-${{ github.run_id }}','path':OUT,'if-no-files-found':'error','retention-days':90}}
      ]}}}
def context():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')==JOB and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'MARGIN_NATIVE_CONTEXT')
def no_keys(custody=False):
    names=['SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM']
    if not custody:names.append('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')
    need(not any(os.environ.get(k) for k in names),'MARGIN_SECRET_ROLE_SEPARATION')
def one_shot(v,run_id):
    need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==run_id and v['workflow_runs'][0]['run_attempt']==1,'MARGIN_ONE_ATTEMPT')
def admit():
    context();no_keys()
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      subprocess.check_output(['git','-C','.margin-native','rev-parse','HEAD'],text=True).strip()==NATIVE and
      json.loads((ROOT/PATH).read_bytes())==workflow(),'MARGIN_EXACT_SOURCE_AND_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'MARGIN_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'MARGIN_AUTHORITY_UNCHANGED')
    one_shot(route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100'),int(os.environ['GITHUB_RUN_ID']))
    source=route.json('actions/runs/40455704891')
    need(source['head_sha']==ORIGINAL_HEAD and source['run_attempt']==1 and source['status']=='completed' and source['conclusion']=='success','MARGIN_ORIGINAL_NATIVE_RUN')
    print('MXM_CURRENT_MARGIN_ADMITTED_EXISTING_SOURCE_NO_BROKER_NO_MODEL',flush=True);return head

def export(cipher_path,output):
    context();no_keys(custody=True);main=ROOT.parent
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0 and
      json.loads((main/PATH).read_bytes())==workflow(),'MARGIN_PINNED_EXPORT_SOURCE')
    for f in FILES:need((ROOT/'research_core_v4/laboratory'/f).read_bytes()==(main/'research_core_v4/laboratory'/f).read_bytes(),'MARGIN_EXACT_NATIVE_EXTENSION')
    raw_manifest=(main/FOLDER/'MANIFEST.json').read_bytes();need(bytes_digest(raw_manifest)==MANIFEST_SHA,'MARGIN_ORIGINAL_MANIFEST')
    manifest=json.loads(raw_manifest);cipher=Path(cipher_path).read_bytes()
    need(bytes_digest(cipher)==manifest['members']['capture.mxmenc']['sha256'],'MARGIN_ORIGINAL_CIPHER')
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    from .spot_observation_reception import verify_private
    with tempfile.TemporaryDirectory() as tmp:
        key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'MARGIN_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)),max_bytes=24000000)
        need(bytes_digest(raw)==manifest['private_sha256'],'MARGIN_ORIGINAL_PRIVATE')
        p=strict_json(raw,max_elements=3000000)
        need(p['identity']['source_sha']==ORIGINAL_HEAD and p['identity']['run_id']==40455704891 and p['identity']['attempt']==1,'MARGIN_ORIGINAL_IDENTITY')
        # Recheck original source authentication, not another cause census or response study.
        need(verify_private(p)==manifest['profile'],'MARGIN_ORIGINAL_SOURCE_AUTHENTICATION')
        items=extract(p);out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('xb') as stream:stream.write(encoded(items)+b'\n')
        bridge={'schema':'mxm.current-margin-native-export.v1','original_run':40455704891,'original_head':ORIGINAL_HEAD,
          'cipher_sha256':bytes_digest(cipher),'private_sha256':manifest['private_sha256'],'derived_sha256':bytes_digest(out.read_bytes()),
          'rows':3,'policy_sha256':POLICY_SHA,'contact_start_utc':p['contact_start_utc'],'contact_end_utc':p['contact_end_utc'],
          'individual_metadata_response_timestamps_available':False,'new_broker_requests':0,'orders':0,'response_tests':0}
        Path(str(out)+'.receipt.json').write_bytes(encoded(bridge)+b'\n')
    print('MXM_CURRENT_MARGIN_METADATA_EXPORTED_NO_MARKET_PRICES_OR_ACCOUNT_IDENTITY',flush=True)
def finalize(folder):
    head=admit();folder=Path(folder);path=folder/'input.json';raw=path.read_bytes()
    bridge=json.loads(Path(str(path)+'.receipt.json').read_bytes());items=json.loads(raw)
    manifest=json.loads((ROOT/FOLDER/'MANIFEST.json').read_bytes())
    need(bridge['original_run']==40455704891 and bridge['original_head']==ORIGINAL_HEAD and bridge['rows']==len(items)==3 and
      [i['symbol_id'] for i in items]==[1,2,250] and bridge['policy_sha256']==POLICY_SHA and bridge['derived_sha256']==bytes_digest(raw) and
      bridge['private_sha256']==manifest['private_sha256'] and bridge['cipher_sha256']==manifest['members']['capture.mxmenc']['sha256'],'MARGIN_NATIVE_BRIDGE')
    expected=reference(items)
    executions={}
    for framework in ('net6.0','net8.0'):
        report=run_report(items,framework);need(report['rows']==expected,'MARGIN_EVERY_ESTIMATE_CSHARP_PYTHON')
        executions[framework]={'runtime_version':report['runtime_version'],'target_framework':report['target_framework']}

    # Values are public metadata/estimates only. Account balance/id, prices, source
    # response paths and FX quotes are deliberately absent from this artifact.
    safe=json.loads(json.dumps(expected,default=lambda v:format(v,'f')))
    dlls={f:bytes_digest((ROOT/'research_core_v4/laboratory/csharp/current_margin/bin/Release'/f/'MxmCurrentMargin.dll').read_bytes()) for f in ('net6.0','net8.0')}
    result={'schema':'mxm.current-margin-native-reception.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':head,
      'policy_sha256':POLICY_SHA,'original_source_run':40455704891,'original_source_head':ORIGINAL_HEAD,'original_manifest_sha256':MANIFEST_SHA,
      'original_private_sha256':bridge['private_sha256'],'derived_input_sha256':bytes_digest(raw),'csharp_assembly_sha256':dlls,'actual_execution_runtimes':executions,'runtime_roll_forward_allowed':True,
      'source_contact_start_utc':bridge['contact_start_utc'],'source_contact_end_utc':bridge['contact_end_utc'],
      'individual_metadata_response_timestamps_available':False,'reference_capital_eur':'200','reference_is_not_a_funded_account_or_reset':True,
      'panel':safe,'all_estimates_independently_reconciled':True,'market_prices_exported':False,'directional_response_tested':False,
      'full_entry_admission':False,'historical_applicability_proven':False,'actual_broker_charges_proven':False,
      'loss_side_fx_proven':False,'stop_risk_proven':False,'original_source_policy_changed':False,'economic_edge_proven':False,
      'hard21_proven':False,'native_robot_operational_reception_proven':False,'new_broker_requests':0,'economic_model_runs':0,'orders':0,'cloud_activated':False}
    dest=ROOT/OUT;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(encoded(result)+b'\n')
    print('MXM_CURRENT_MARGIN_NATIVE '+encoded(result).decode(),flush=True)
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==4 and sys.argv[1]=='export':export(*sys.argv[2:])
    elif len(sys.argv)==3 and sys.argv[1]=='finalize':finalize(sys.argv[2])
    else:raise ValueError('MARGIN_EXACT_PHASE')
