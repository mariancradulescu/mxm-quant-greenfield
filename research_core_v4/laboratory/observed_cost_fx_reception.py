"""One integrated original-source cost-FX reception; no new source or economic trial."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
from .common import need,encoded,bytes_digest
from .observed_cost_fx import PROJECT,reconcile_source,run
from .durable_spot_observation import MANIFEST_SHA
ROOT=Path(__file__).resolve().parents[2]
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd';ORIGINAL_HEAD='d16db0a9e40ca2f48f8b9f0d483ca3b131d173e1'
FOLDER='docs/economic-development/20261027/native-spot-40455704891'
PATH='.github/workflows/mxm-observed-cost-fx-reception.yml';MODULE='research_core_v4.laboratory.observed_cost_fx_reception';JOB='observed-cost-fx'
FILES=('observed_cost_fx_reception.py','observed_cost_fx.py','current_margin_evidence.py','universe_commission_checks.py','durable_spot_observation.py','spot_observation_reception.py','spot_observation_profile.py')
OUT='verification/observed-cost-fx/receipt.json'
POLICY={'schema':'mxm.observed-cost-fx-integration-policy.v1','original_run':40455704891,'original_manifest_sha256':MANIFEST_SHA,
 'symbol_ids':[1,2,250],'all_original_events':1140,'new_broker_requests':0,'orders':0,'response_tests':0,'economic_model_runs':0,
 'maximum_local_side_age_ms':5000,'maximum_metadata_path_legs':3,'route_rule':'UNIQUE_SHORTEST_METADATA_PATH_BEFORE_PRICE_HEALTH_NO_STALE_FALLBACK',
 'cost_side':'ASK_OR_INVERSE_BID_UPWARD_ROUNDED_18_DECIMALS',
 'scope':'DECLARED_MINIMUM_VOLUME_COMMISSION_COMPONENTS_ONLY_NOT_FULL_COSTS_OR_ENTRY_ADMISSION',
 'source_clock_certified':False,'original_quality_policy_changed':False,'directional_response_testing_allowed':False,
 'private_result':'ENCRYPT_TO_EXISTING_RECIPIENT_AND_SEPARATE_CUSTODY_PROCESS_READBACK',
 'automatic_retry':False}
POLICY_SHA=bytes_digest(encoded(POLICY))
def workflow():
    return {'name':'MXM observed cost FX integrated original-source reception',
     'on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
     'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{JOB:{
      'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",
      'runs-on':'ubuntu-24.04','timeout-minutes':12,'environment':'mxm-r3-custody-v1',
      'permissions':{'contents':'read','actions':'read'},'steps':[
       {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','with':{'persist-credentials':False}},
       {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','with':{'ref':NATIVE,'path':'.cost-fx-native','persist-credentials':False}},
       {'name':'Admit exact one-shot existing evidence scope before custody','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
       {'name':'Compile actual observed cost FX and validate independent artificial paths without keys','run':
        'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
        'dotnet build '+PROJECT+' -c Release\n'
        'python3 -m unittest research_core_v4.laboratory.test_observed_cost_fx research_core_v4.laboratory.test_observed_cost_fx_reception -v\n'
        'python3 -m research_core_v4.laboratory.durable_spot_observation --out "${RUNNER_TEMP}/mxm-observed-cost-fx/original"\n'
        'cp '+' '.join('research_core_v4/laboratory/'+f for f in FILES)+' .cost-fx-native/research_core_v4/laboratory/'},
       {'name':'Authenticate original source and export complete existing event and metadata input only in custody',
        'env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},
        'run':'umask 077\ncd .cost-fx-native\npython3 -m '+MODULE+' export "${RUNNER_TEMP}/mxm-observed-cost-fx/original/capture.mxmenc" "${RUNNER_TEMP}/mxm-observed-cost-fx/input.json"'},
       {'name':'Reconcile every source cost component CSharp Decimal and encrypt the private ledger without keys',
        'env':{'GH_TOKEN':'${{ github.token }}'},'run':'umask 077\npython3 -m '+MODULE+' finalize "${RUNNER_TEMP}/mxm-observed-cost-fx"'},
       {'name':'Read back encrypted result in a separate native custody process',
        'env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},
        'run':'umask 077\ncd .cost-fx-native\npython3 -m '+MODULE+' cold'},
       {'uses':'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02','with':{
        'name':'observed-cost-fx-${{ github.run_id }}','path':OUT+'\nverification/observed-cost-fx/ledger.mxmenc\nverification/observed-cost-fx/cold.json','if-no-files-found':'error','retention-days':90}}
      ]}}}
def context():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')==JOB and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'OBSERVED_COST_FX_NATIVE_CONTEXT')
def no_keys(custody=False):
    names=['SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM']
    if not custody:names.append('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')
    need(not any(os.environ.get(k) for k in names),'OBSERVED_COST_FX_SECRET_ROLE_SEPARATION')
def one_shot(v,run_id):
    need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==run_id and v['workflow_runs'][0]['run_attempt']==1,'OBSERVED_COST_FX_ONE_ATTEMPT')
def admit():
    context();no_keys()
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      subprocess.check_output(['git','-C','.cost-fx-native','rev-parse','HEAD'],text=True).strip()==NATIVE and
      json.loads((ROOT/PATH).read_bytes())==workflow(),'OBSERVED_COST_FX_EXACT_SOURCE_AND_WORKFLOW')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'OBSERVED_COST_FX_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'OBSERVED_COST_FX_AUTHORITY_UNCHANGED')
    one_shot(route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100'),int(os.environ['GITHUB_RUN_ID']))
    source=route.json('actions/runs/40455704891')
    need(source['head_sha']==ORIGINAL_HEAD and source['run_attempt']==1 and source['status']=='completed' and source['conclusion']=='success','OBSERVED_COST_FX_ORIGINAL_NATIVE_RUN')
    print('MXM_OBSERVED_COST_FX_ADMITTED_EXISTING_SOURCE_NO_BROKER_NO_MODEL',flush=True);return head

def native_export_context():
    context();no_keys(custody=True);main=ROOT.parent
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and
      subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and
      subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0 and
      json.loads((main/PATH).read_bytes())==workflow(),'OBSERVED_COST_FX_PINNED_EXPORT_SOURCE')
    for f in FILES:need((ROOT/'research_core_v4/laboratory'/f).read_bytes()==(main/'research_core_v4/laboratory'/f).read_bytes(),'OBSERVED_COST_FX_EXACT_NATIVE_EXTENSION')
    return main

def export(cipher_path,output):
    main=native_export_context()
    raw_manifest=(main/FOLDER/'MANIFEST.json').read_bytes();need(bytes_digest(raw_manifest)==MANIFEST_SHA,'OBSERVED_COST_FX_ORIGINAL_MANIFEST')
    manifest=json.loads(raw_manifest);cipher=Path(cipher_path).read_bytes()
    need(bytes_digest(cipher)==manifest['members']['capture.mxmenc']['sha256'],'OBSERVED_COST_FX_ORIGINAL_CIPHER')
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    from .spot_observation_reception import verify_private,market_event
    from .current_margin_evidence import extract
    from m6.ctrader_transport import decode_envelope,extract_payload
    import base64
    with tempfile.TemporaryDirectory() as tmp:
        key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'OBSERVED_COST_FX_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)),max_bytes=24000000)
        need(bytes_digest(raw)==manifest['private_sha256'],'OBSERVED_COST_FX_ORIGINAL_PRIVATE')
        p=strict_json(raw,max_elements=3000000)
        need(p['identity']['source_sha']==ORIGINAL_HEAD and p['identity']['run_id']==40455704891 and p['identity']['attempt']==1,'OBSERVED_COST_FX_ORIGINAL_IDENTITY')
        need(verify_private(p)==manifest['profile'] and len(p['market'])==1140,'OBSERVED_COST_FX_ORIGINAL_QUALITY_UNCHANGED')
        items=extract(p);responses={}
        for row in p['receipts']:
            if row['request_type'] in ('ProtoOAAssetListReq','ProtoOASymbolsListReq'):
                responses[row['request_type']]=extract_payload(decode_envelope(base64.b64decode(row['response_wire'],validate=True)))
        assets={int(a.assetId):a.name for a in responses['ProtoOAAssetListReq'].asset};instruments=[]
        for light in responses['ProtoOASymbolsListReq'].symbol:
            if int(light.symbolId) not in (1,2,250):continue
            base=assets.get(int(light.baseAssetId)) if light.HasField('baseAssetId') else None
            quote=assets.get(int(light.quoteAssetId)) if light.HasField('quoteAssetId') else None
            if base and quote and base!=quote:instruments.append(dict(Source=str(light.symbolId),BaseAsset=base,QuoteAsset=quote))
        data={'instruments':sorted(instruments,key=lambda i:i['Source']),'sources':['1','2','250'],'terms':items,
          'events':[market_event(row,p['account']) for row in p['market']]}
        out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('xb') as stream:stream.write(encoded(data)+b'\n')
        bridge={'schema':'mxm.observed-cost-fx-native-export.v1','original_run':40455704891,'original_head':ORIGINAL_HEAD,
          'cipher_sha256':bytes_digest(cipher),'private_sha256':manifest['private_sha256'],'derived_sha256':bytes_digest(out.read_bytes()),
          'rows':1140,'policy_sha256':POLICY_SHA,'original_quality_profile_unchanged':True,'new_broker_requests':0,'orders':0,'response_tests':0}
        Path(str(out)+'.receipt.json').write_bytes(encoded(bridge)+b'\n')
    print('MXM_OBSERVED_COST_FX_ORIGINAL_SOURCE_EXPORTED_ONLY_IN_CUSTODY',flush=True)

def finalize(folder):
    import gzip
    head=admit();folder=Path(folder);path=folder/'input.json';raw=path.read_bytes()
    bridge=json.loads(Path(str(path)+'.receipt.json').read_bytes());data=json.loads(raw)
    manifest=json.loads((ROOT/FOLDER/'MANIFEST.json').read_bytes())
    need(bridge['original_run']==40455704891 and bridge['original_head']==ORIGINAL_HEAD and bridge['rows']==len(data['events'])==1140 and
      [i['symbol_id'] for i in data['terms']]==[1,2,250] and bridge['policy_sha256']==POLICY_SHA and bridge['derived_sha256']==bytes_digest(raw) and
      bridge['private_sha256']==manifest['private_sha256'] and bridge['cipher_sha256']==manifest['members']['capture.mxmenc']['sha256'],'OBSERVED_COST_FX_NATIVE_BRIDGE')
    actual=run(data,'--source');counts=reconcile_source(data,actual)
    need(sum(sum(c.values()) for c in counts.values())==1140,'OBSERVED_COST_FX_ALL_SOURCE_EVENTS_RECONCILED')
    identity={'run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':head,'policy_sha256':POLICY_SHA,'original_source_run':40455704891,
      'original_source_head':ORIGINAL_HEAD,'original_manifest_sha256':MANIFEST_SHA,'original_private_sha256':bridge['private_sha256'],
      'derived_input_sha256':bytes_digest(raw)}
    private=encoded({'schema':'mxm.observed-cost-fx-private-ledger.v1',**identity,'ledger':actual})
    need(len(private)<1000000,'OBSERVED_COST_FX_PRIVATE_LEDGER_CAP')
    dest=ROOT/OUT;dest.parent.mkdir(parents=True,exist_ok=True)
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    from research_core_v4.successor_c_20261018.readback import FP
    public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public)==FP,'OBSERVED_COST_FX_EXISTING_RECIPIENT')
    cipher=dest.parent/'ledger.mxmenc';encrypt_shard(gzip.compress(private,mtime=0),public_key=public,output=cipher)
    dll=ROOT/'research_core_v4/laboratory/csharp/observed_cost_fx/bin/Release/net8.0/MxmObservedCostFx.dll'
    result={'schema':'mxm.observed-cost-fx-native-reception.v1',**identity,'csharp_assembly_sha256':bytes_digest(dll.read_bytes()),
      'encrypted_ledger_sha256':bytes_digest(cipher.read_bytes()),'private_ledger_sha256':bytes_digest(private),'events':1140,'counts':counts,
      'every_event_independently_reconciled':True,'original_quality_profile_unchanged':True,'original_diagnostic_exclusion_unchanged':True,
      'source_timestamp_certified':False,'executable_fx_or_actual_charges_proven':False,'all_in_costs_proven':False,'stop_risk_proven':False,
      'full_entry_admission':False,'economic_edge_proven':False,'hard21_proven':False,'native_robot_operational_reception_proven':False,
      'market_prices_or_cost_values_public':False,'new_broker_requests':0,'economic_model_runs':0,'response_tests':0,'orders':0,'cloud_activated':False}
    dest.write_bytes(encoded(result)+b'\n');print('MXM_OBSERVED_COST_FX_NATIVE '+encoded(result).decode(),flush=True)

def cold():
    main=native_export_context();folder=main/'verification/observed-cost-fx'
    result=json.loads((folder/'receipt.json').read_bytes());cipher=(folder/'ledger.mxmenc').read_bytes()
    need(result['run_id']==int(os.environ['GITHUB_RUN_ID']) and result['source_sha']==os.environ['GITHUB_SHA'] and result['policy_sha256']==POLICY_SHA and
      result['encrypted_ledger_sha256']==bytes_digest(cipher),'OBSERVED_COST_FX_RESULT_CIPHER_IDENTITY')
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    with tempfile.TemporaryDirectory() as tmp:
        key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'OBSERVED_COST_FX_COLD_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)),max_bytes=1000000)
        need(bytes_digest(raw)==result['private_ledger_sha256'],'OBSERVED_COST_FX_COLD_ORIGINAL_PRIVATE_LEDGER')
        private=strict_json(raw,max_elements=100000)
        for k in ('run_id','source_sha','policy_sha256','original_source_run','original_source_head','original_manifest_sha256','original_private_sha256','derived_input_sha256'):
            need(private[k]==result[k],'OBSERVED_COST_FX_COLD_PRIVATE_PROVENANCE')
        need(private['schema']=='mxm.observed-cost-fx-private-ledger.v1' and len(private['ledger'])==result['events']==1140,'OBSERVED_COST_FX_COLD_ALL_LEDGER_ROWS')
        from collections import Counter
        counts={str(s):dict(sorted(Counter(r['status'] for r in private['ledger'] if r['symbol']==s).items())) for s in (1,2,250)}
        need(counts==result['counts'],'OBSERVED_COST_FX_COLD_LEDGER_COUNTS')
    receipt={'schema':'mxm.observed-cost-fx-native-cold.v1','run_id':result['run_id'],'source_sha':result['source_sha'],
      'encrypted_ledger_sha256':bytes_digest(cipher),'private_ledger_sha256':bytes_digest(raw),'events':1140,
      'separate_custody_process_readback_verified':True,'independent_algorithm_is_csharp_python_not_this_readback':True,
      'new_broker_requests':0,'orders':0,'economic_edge_proven':False,'native_robot_operational_reception_proven':False}
    (folder/'cold.json').write_bytes(encoded(receipt)+b'\n');print('MXM_OBSERVED_COST_FX_COLD '+encoded(receipt).decode(),flush=True)
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==4 and sys.argv[1]=='export':export(*sys.argv[2:])
    elif len(sys.argv)==3 and sys.argv[1]=='finalize':finalize(sys.argv[2])
    elif sys.argv[1:]==['cold']:cold()
    else:raise ValueError('OBSERVED_COST_FX_EXACT_PHASE')
