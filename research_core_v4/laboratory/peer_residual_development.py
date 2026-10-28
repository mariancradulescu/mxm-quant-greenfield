"""One finite dependent cross-sectional reference-price falsification. No broker."""
import gzip,json,os,subprocess,sys,tempfile,base64,hashlib,collections,shutil
from pathlib import Path
from decimal import Decimal
from .common import need,encoded,bytes_digest
from . import m5_authentic_envelope as env
from .m5_causal_gross_development import load_market_geometry,parse_rows
from .spot_observation_reception import BROKER,CHECKOUT,UPLOAD,BOUNDARY_SHA
ROOT=Path(__file__).resolve().parents[2];BRANCH='mxm-remediation-p0-p4-20261015-v1'
PATH='.github/workflows/mxm-peer-residual-development.yml';MODULE='research_core_v4.laboratory.peer_residual_development';JOB='peer-residual'
PROJECT='research_core_v4/laboratory/csharp/peer_residual/MxmPeerResidual.csproj';OUT='verification/peer-residual'
SPEC='research_programs/admissions/PEER_RESIDUAL_20261028.json'
POLICY={'model_id':'MXM_CROSS_SECTIONAL_PEER_RESIDUAL_REVERSION_20261028_V1','new_dependent_identity':1,'model_trials_max':1,'native_attempts':1,
 'universe':1576,'source_rows':3355389,'source_shards':100,'source_manifest_sha256':'cc28c61a7788fc9d18bd54a343bc0e2c7467b27f1dbb111bf54185f9f0f16cb4',
 'feature':'TWELVE_CONTIGUOUS_PRIOR_COMPLETED_M5_OPEN_TO_CLOSE_MOVE_ROUNDED_8_BPS',
 'peer':'SAME_FROZEN_ASSET_CLASS_LEAVE_ONE_OUT_MEDIAN_AT_LEAST_TEN_OTHER_OBSERVED_FEATURES',
 'selection':'ONE_GLOBAL_LARGEST_ABSOLUTE_PEER_RESIDUAL_PER_UTC_HOUR_ORDINAL_TIEBREAK',
 'target_eligibility':'OCT03_CURRENT_REFERENCE_STRUCTURALLY_ELIGIBLE_BOTH_MIN_MARGINS_LE80_NOT_HISTORICAL_PROOF',
 'threshold_bps':20,'direction':'OPPOSITE_PEER_RESIDUAL','entry_minutes_after_decision':5,'exit_minutes_after_decision':55,
 'missing_future':'CENSOR_ORIGINAL_SELECTION_NO_REPLACEMENT_REQUIRE_ALL11_M5_OPEN_ROWS',
 'evaluation_start':'2026-08-27T00:00:00Z','end_exclusive':'2026-09-17T00:00:00Z','feature_rounding':'EXACT_RATIONAL_NEAREST_8_BPS_AWAY_FROM_ZERO',
 'reference_roundtrip_bps':[5,10,20,40],'support_min':100,'censor_max_percent':5,'mean_hurdle_bps':5,'each_source_block_hurdle_bps':5,'top5_absolute_symbol_contribution_max_percent':50,
 'prices':'INDICATIVE_M5_OPEN_NOT_EXECUTABLE_BID_ASK','historical_costs_proven':False,'capital_replay':False,'actual_fills':False,
 'partition':'DEVELOPMENT_ALREADY_FULLY_EXPOSED','independent_confirmation':False,'protected_opened':False,'formal_V2_C033_changed':False,
 'new_broker_requests':0,'orders':0,'cloud':False,'automatic_retry':False,'automatic_followup':False}

def workflow():
 return {'name':'MXM one cross-sectional peer-residual economic falsification','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{JOB:{'if':f"github.repository == '{env.REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",'runs-on':'ubuntu-24.04','timeout-minutes':35,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[
 {'uses':CHECKOUT,'with':{'persist-credentials':False}},
 {'name':'Admit exact finite dependent hypothesis before source access','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
 {'name':'Compile CSharp and independently check artificial causal selection before custody','run':'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\ndotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_peer_residual -v'},
 {'name':'Authenticate original100 shards and export only original reference input in custody','env':{'GH_TOKEN':'${{ github.token }}','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\npython3 -m '+MODULE+' export'},
 {'name':'Execute exactly one CSharp policy; reconcile complete causal decision and episode audit with Python','env':{'GH_TOKEN':'${{ github.token }}'},'run':'umask 077\npython3 -m '+MODULE+' evaluate'},
 {'name':'Separate custody readback of original encrypted result without policy replay','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\npython3 -m '+MODULE+' cold'},
 {'uses':UPLOAD,'if':'always()','with':{'name':'peer-residual-${{ github.run_id }}','path':OUT+'/receipt.json\n'+OUT+'/result.mxmenc\n'+OUT+'/evaluator.dll\n'+OUT+'/cold.json','if-no-files-found':'error','retention-days':90}}
 ]}}}
def validate():
 spec=json.loads((ROOT/SPEC).read_bytes());need(spec['policy']==POLICY,'PEER_FROZEN_POLICY')
 for p,h in spec['implementation_sha256'].items():need(bytes_digest((ROOT/p).read_bytes())==h,'PEER_FROZEN_IMPLEMENTATION')
 need(json.loads((ROOT/PATH).read_bytes())==workflow() and bytes_digest(env.MANIFEST.read_bytes())==POLICY['source_manifest_sha256'],'PEER_FROZEN_SOURCE_WORKFLOW');return spec

def context(custody=False):
 need(os.environ.get('GITHUB_REPOSITORY')==env.REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')==JOB and os.environ.get('GITHUB_WORKFLOW_REF')==env.REPO+'/'+PATH+'@refs/heads/'+BRANCH,'PEER_NATIVE_CONTEXT')
 forbidden=list(BROKER)+['R3_CTRADER_REFRESH_TOKEN','SUCCESSOR_APP_PRIVATE_KEY','R3_CUSTODY_PRIVATE_KEY_PEM']
 if not custody:forbidden+=['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']
 need(not any(os.environ.get(k) for k in forbidden),'PEER_KEY_ROLE')
 head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'PEER_EXACT_CODE');validate()
 need(bytes_digest((ROOT/'V2_PROTECTED_FORWARD_START.json').read_bytes())==BOUNDARY_SHA,'PEER_PROTECTED_BOUNDARY');return head

def admit():
 head=context();from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'PEER_OFFICIAL_HEAD')
 for ref,h in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==h,'PEER_AUTHORITY')
 runs=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100');need(runs['total_count']==len(runs['workflow_runs'])==1 and runs['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and runs['workflow_runs'][0]['run_attempt']==1,'PEER_ONE_ATTEMPT')
 return {'run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':head,'spec_sha256':bytes_digest((ROOT/SPEC).read_bytes())}
def temporary():return Path(os.environ['RUNNER_TEMP'])/'mxm-peer-residual'
def export():
 context(custody=True);entries,manifest_sha=load_market_geometry()
 from .universe_commission_checks import snapshot
 from research_core_v4.shallow_m5_support_v2 import load_master
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package
 source,_=snapshot();meta={x['symbol_id']:x for x in source['rows']};master=load_master(ROOT);groups={g:i for i,g in enumerate(sorted({x['asset_class'] for x in master}))}
 need(len(meta)==len(master)==1576,'PEER_REFERENCE_UNIVERSE')
 temp=temporary();temp.mkdir(mode=0o700,exist_ok=True);total=shards=packets=0
 with tempfile.TemporaryDirectory(prefix='mxm-peer-source-') as d:
  root=Path(d);key,fp=_private_key_from_secret(root);need(fp=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11','PEER_EXISTING_CUSTODY')
  assets=root/'cipher';assets.mkdir(mode=0o700);subprocess.run(['gh','release','download',env.RELEASE_IDENTITY,'--repo',env.REPO,'--dir',str(assets)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  need(len(list(assets.iterdir()))==100,'PEER_ALL_SHARDS')
  with (temp/'input.jsonl').open('xb') as stream:
   for shard in range(25):
    by_ordinal=collections.defaultdict(list)
    for segment in range(1,5):
     e=entries[(segment,shard)];cipher=(assets/e['ENCRYPTED_ASSET_NAME']).read_bytes();need(bytes_digest(cipher)==e['ENCRYPTED_ASSET_SHA256'],'PEER_CIPHER');plain=decrypt_synthetic_package(cipher,private_key=key);need(bytes_digest(plain)==e['PLAINTEXT_CANONICAL_SHA256'],'PEER_PLAINTEXT');data=json.loads(plain)
     need(data['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1' and data['segment_index']==segment and data['shard_index']==shard and data['identity_range']==e['IDENTITY_RANGE'] and [x['ordinal'] for x in data['items']]==list(range(e['IDENTITY_RANGE'][0],e['IDENTITY_RANGE'][1]+1)),'PEER_NATIVE_IDENTITIES')
     count=0
     for item in data['items']:
      need(item['classification'] in ('NO_HISTORICAL_SUPPORT','SHALLOW_SUPPORT_COMPLETE','SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED') and isinstance(item['rows'],list),'PEER_SOURCE_SUPPORT')
      for row in item['rows']:need(set(row)=={'time_utc','open','high','low','close','tick_volume'},'PEER_ROW_SCHEMA')
      by_ordinal[item['ordinal']].extend(item['rows']);count+=len(item['rows'])
     need(count==e['ROW_COUNT'],'PEER_ROW_COUNT');total+=count;shards+=1
    for ordinal,rows in sorted(by_ordinal.items()):
     if rows:parse_rows(rows)
     identity=master[ordinal-1];m=meta[identity['symbol_id']];need(m['symbol']==identity['symbol'] and m['asset_class']==identity['asset_class'],'PEER_EXACT_REFERENCE_MAPPING')
     eligible=m['status']=='STRUCTURALLY_ELIGIBLE' and Decimal(m['buy_min_margin_eur'])<=80 and Decimal(m['sell_min_margin_eur'])<=80
     stream.write(encoded({'ordinal':ordinal,'group':groups[identity['asset_class']],'eligible':eligible,'rows':rows})+b'\n');packets+=1
 need((total,shards,packets)==(3355389,100,1576),'PEER_COMPLETE_SOURCE')
 (temp/'bridge.json').write_bytes(encoded({'manifest_sha256':manifest_sha,'input_sha256':file_hash(temp/'input.jsonl'),'rows':total,'shards':shards,'packets':packets,'reference_metadata_capture':source['completed_utc']}))
 print('MXM_PEER_ORIGINAL_SOURCE_AUTHENTICATED rows=3355389 shards=100 identities=1576',flush=True)
def file_hash(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def evaluate():
 from .peer_residual_reference import reference,verdict
 identity=admit();temp=temporary();bridge=json.loads((temp/'bridge.json').read_bytes());need(bridge['input_sha256']==file_hash(temp/'input.jsonl') and bridge['manifest_sha256']==POLICY['source_manifest_sha256'],'PEER_EXACT_MODEL_INPUT')
 with (temp/'input.jsonl').open() as stream:expected=reference(json.loads(line) for line in stream)
 subprocess.run(['dotnet','run','--project',PROJECT,'-c','Release','--no-build','--',str(temp/'input.jsonl'),str(temp/'actual.json')],check=True,capture_output=True)
 actual=json.loads((temp/'actual.json').read_bytes());need(actual==expected and actual['Packets']==1576 and actual['Rows']==3355389,'PEER_ALL_FEATURE_SELECTION_EPISODE_PARITY')
 label,gates,metrics=verdict(expected);out=ROOT/OUT;out.mkdir(parents=True,exist_ok=True)
 private=encoded({'identity':identity,'bridge':bridge,'original_csharp_json_b64':base64.b64encode((temp/'actual.json').read_bytes()).decode(),'metrics':metrics,'gates':gates,'disposition':label})
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
 from research_core_v4.successor_c_20261018.readback import FP
 public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'PEER_RECIPIENT');encrypt_shard(gzip.compress(private,mtime=0),public_key=public,output=out/'result.mxmenc')
 binary=ROOT/'research_core_v4/laboratory/csharp/peer_residual/bin/Release/net8.0/MxmPeerResidual.dll';(out/'evaluator.dll').write_bytes(binary.read_bytes())
 r={**identity,'schema':'mxm.peer-residual-development-public.v1','source_rows':3355389,'source_shards':100,'source_identities':1576,'source_manifest_sha256':bridge['manifest_sha256'],'input_sha256':bridge['input_sha256'],'model_trials':1,'new_dependent_hypotheses':1,'disposition':label,'gates':gates,'all_causal_feature_selection_and_episode_records_reconciled':True,'private_sha256':bytes_digest(private),'cipher_sha256':bytes_digest((out/'result.mxmenc').read_bytes()),'actual_evaluator_sha256':bytes_digest(binary.read_bytes()),'historical_costs_proven':False,'actual_fills_proven':False,'net_edge_proven':False,'capital_replay':False,'hard21_proven':False,'native_robot_operational_reception_proven':False,'reference_friction_is_hypothetical':True,'new_broker_requests':0,'orders':0,'protected_opened':False,'independent_confirmation':False,'formal_V2_C033_changed':False,'next_action':'STOP_FIXED_IDENTITY_NO_RETUNE_NO_AUTOMATIC_FOLLOWUP'}
 (out/'receipt.json').write_bytes(encoded(r)+b'\n');print('MXM_PEER_RESIDUAL '+encoded(r).decode(),flush=True)
def cold():
 context(custody=True);out=ROOT/OUT;r=json.loads((out/'receipt.json').read_bytes());cipher=(out/'result.mxmenc').read_bytes()
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack,strict_json
 from research_core_v4.successor_c_20261018.readback import FP
 with tempfile.TemporaryDirectory() as d:
  key,fp=_private_key_from_secret(Path(d));need(fp==FP,'PEER_EXISTING_COLD_CUSTODY');raw=unpack(owner.bounded_decrypt(cipher,key,Path(d)),max_bytes=4000000);p=strict_json(raw,max_elements=1000000)
 need(bytes_digest(cipher)==r['cipher_sha256'] and bytes_digest(raw)==r['private_sha256'] and p['identity']=={k:r[k] for k in ('run_id','source_sha','spec_sha256')} and p['disposition']==r['disposition'] and p['gates']==r['gates'] and bytes_digest((out/'evaluator.dll').read_bytes())==r['actual_evaluator_sha256'],'PEER_ORIGINAL_COLD_READBACK')
 c={'schema':'mxm.peer-residual-cold.v1','run_id':r['run_id'],'source_sha':r['source_sha'],'cipher_sha256':r['cipher_sha256'],'disposition':r['disposition'],'separate_custody_process_readback':True,'algorithm_reexecuted':False,'orders':0};(out/'cold.json').write_bytes(encoded(c)+b'\n');print('MXM_PEER_RESIDUAL_COLD '+encoded(c).decode(),flush=True)
if __name__=='__main__':
 os.umask(0o077);command=sys.argv[1:]
 if command==['admit']:admit()
 elif command==['export']:export()
 elif command==['evaluate']:evaluate()
 elif command==['cold']:cold()
 else:raise ValueError('PEER_EXACT_PHASE')
