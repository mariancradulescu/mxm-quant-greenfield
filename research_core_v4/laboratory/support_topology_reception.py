"""One original-source TIME-ONLY observability reception, not an economic trial."""
import base64,collections,gzip,hashlib,json,os,subprocess,sys,tempfile,zipfile
from datetime import datetime,timezone
from pathlib import Path
from .common import need,encoded,bytes_digest
from . import m5_authentic_envelope as env
from .m5_causal_gross_development import load_market_geometry
from .spot_observation_reception import BROKER,CHECKOUT,UPLOAD,BOUNDARY_SHA
ROOT=Path(__file__).resolve().parents[2];BRANCH='mxm-remediation-p0-p4-20261015-v1'
PATH='.github/workflows/mxm-support-topology-reception.yml';MODULE='research_core_v4.laboratory.support_topology_reception';JOB='support-topology'
PROJECT='research_core_v4/laboratory/csharp/support_topology/MxmSupportTopology.csproj';OUT='verification/support-topology'
SPEC='research_programs/reconciliation/SUPPORT_TOPOLOGY_20261028.json'
POLICY={'schema':'mxm.time-only-support-topology-policy.v1','source_rows':3355389,'source_shards':100,'source_identities':1576,
 'source_manifest_sha256':'cc28c61a7788fc9d18bd54a343bc0e2c7467b27f1dbb111bf54185f9f0f16cb4',
 'source_start':'2026-08-20T00:00:00Z','source_end_exclusive':'2026-09-17T00:00:00Z','source_blocks':4,'slots_per_block':2016,
 'profiles':[{'lookback':h,'hold':h} for h in (1,12,288)],'decision_grid':'EVERY_M5_SLOT_NO_SIGNAL_OR_PRICE_FILTER',
 'feature':'ALL_PRIOR_LOOKBACK_M5_TIMESTAMPS_PRESENT','response':'DELAY_ONE_SLOT_THEN_HOLD_PLUS_ONE_TIMESTAMPS_ALL_PRESENT',
 'right_boundary':'RETAIN_CAUSAL_DECISION_SEPARATE_OUTSIDE_ARCHIVE_FROM_INTERNAL_MISSINGNESS',
 'missing_components':'ENTRY_EXIT_INTERIOR_NONEXCLUSIVE_COUNTS_NO_IMPUTATION',
 'segment_boundary':'CONTEXT_AND_RESPONSE_MAY_CROSS_CONTIGUOUS_SOURCE_BLOCKS_NOT_FINAL_ARCHIVE_BOUNDARY',
 'interpretation':'UNSELECTED_OBSERVATION_GRID_NOT_SIGNAL_CONDITIONED_CENSORING_OR_RETURN_STABILITY',
 'prices_exported':False,'new_strategy_identities':0,'model_trials':0,'native_attempts':1,'new_broker_requests':0,
 'orders':0,'cloud':False,'capital_replay':False,'independent_confirmation':False,'protected_opened':False,
 'automatic_retry':False,'automatic_followup':False,'closed_identities_reexecuted':False}

def workflow():
 return {'name':'MXM original M5 time-only support topology reception','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{JOB:{'if':f"github.repository == '{env.REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",'runs-on':'ubuntu-24.04','timeout-minutes':30,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[
 {'uses':CHECKOUT,'with':{'persist-credentials':False}},
 {'name':'Admit exact finite time-only source reception before custody','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
 {'name':'Compile independent support geometry and synthetic gap negatives before source access','run':'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\ndotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_support_topology -v'},
 {'name':'Authenticate all original shards in existing custody and export timestamps only','env':{'GH_TOKEN':'${{ github.token }}','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\npython3 -m '+MODULE+' export'},
 {'name':'Compute actual CSharp support and reconcile every cell with independent run-interval reference','env':{'GH_TOKEN':'${{ github.token }}'},'run':'umask 077\npython3 -m '+MODULE+' evaluate'},
 {'name':'Read back exact original encrypted topology in a separate custody process without recomputation','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\npython3 -m '+MODULE+' cold'},
 {'name':'Emit only original ciphertext DLL and receipts as a bounded restorable bundle','run':'python3 -m '+MODULE+' preserve'},
 {'uses':UPLOAD,'if':'always()','with':{'name':'support-topology-${{ github.run_id }}','path':OUT+'/receipt.json\n'+OUT+'/result.mxmenc\n'+OUT+'/evaluator.dll\n'+OUT+'/cold.json\n'+OUT+'/runtime-original.zip','if-no-files-found':'error','retention-days':90}}
 ]}}}
def validate():
 spec=json.loads((ROOT/SPEC).read_bytes());need(spec['policy']==POLICY,'TOPOLOGY_FROZEN_POLICY')
 for p,h in spec['implementation_sha256'].items():need(bytes_digest((ROOT/p).read_bytes())==h,'TOPOLOGY_FROZEN_IMPLEMENTATION')
 need(json.loads((ROOT/PATH).read_bytes())==workflow() and bytes_digest(env.MANIFEST.read_bytes())==POLICY['source_manifest_sha256'],'TOPOLOGY_SOURCE_WORKFLOW');return spec

def context(custody=False):
 need(os.environ.get('GITHUB_REPOSITORY')==env.REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')==JOB and os.environ.get('GITHUB_WORKFLOW_REF')==env.REPO+'/'+PATH+'@refs/heads/'+BRANCH,'TOPOLOGY_NATIVE_CONTEXT')
 forbidden=list(BROKER)+['R3_CTRADER_REFRESH_TOKEN','SUCCESSOR_APP_PRIVATE_KEY','R3_CUSTODY_PRIVATE_KEY_PEM']
 if not custody:forbidden+=['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']
 need(not any(os.environ.get(k) for k in forbidden),'TOPOLOGY_KEY_ROLE')
 head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'TOPOLOGY_EXACT_CODE');validate()
 need(bytes_digest((ROOT/'V2_PROTECTED_FORWARD_START.json').read_bytes())==BOUNDARY_SHA,'TOPOLOGY_PROTECTED_BOUNDARY');return head

def admit():
 head=context();from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'TOPOLOGY_OFFICIAL_HEAD')
 for ref,h in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==h,'TOPOLOGY_AUTHORITY')
 runs=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100');need(runs['total_count']==len(runs['workflow_runs'])==1 and runs['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and runs['workflow_runs'][0]['run_attempt']==1,'TOPOLOGY_ONE_ATTEMPT')
 return {'run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':head,'spec_sha256':bytes_digest((ROOT/SPEC).read_bytes())}
def temporary():return Path(os.environ['RUNNER_TEMP'])/'mxm-support-topology'
def file_hash(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def timestamp_slots(rows,segment):
 start=datetime(2026,8,20,tzinfo=timezone.utc);slots=[];previous=-1
 for row in rows:
  need(set(row)=={'time_utc','open','high','low','close','tick_volume'},'TOPOLOGY_ORIGINAL_ROW_SCHEMA')
  stamp=row['time_utc'];need(isinstance(stamp,str) and stamp.endswith('Z'),'TOPOLOGY_UTC')
  t=datetime.fromisoformat(stamp.replace('Z','+00:00'));delta=t-start
  need(t.microsecond==0 and delta.total_seconds()%300==0,'TOPOLOGY_EXACT_M5')
  slot=int(delta.total_seconds())//300
  need((segment-1)*2016<=slot<segment*2016 and slot>previous,'TOPOLOGY_ORIGINAL_BLOCK_ORDER')
  slots.append(slot);previous=slot
 return slots

def export():
 context(True);entries,manifest_sha=load_market_geometry()
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package
 temp=temporary();temp.mkdir(mode=0o700,exist_ok=False);total=shards=packets=0
 with tempfile.TemporaryDirectory(prefix='mxm-support-source-') as d:
  root=Path(d);key,fp=_private_key_from_secret(root);need(fp=='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11','TOPOLOGY_EXISTING_CUSTODY')
  assets=root/'cipher';assets.mkdir(mode=0o700);subprocess.run(['gh','release','download',env.RELEASE_IDENTITY,'--repo',env.REPO,'--dir',str(assets)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  need(len(list(assets.iterdir()))==100,'TOPOLOGY_ALL_SHARDS')
  with (temp/'input.jsonl').open('xb') as stream:
   for shard in range(25):
    by_ordinal=collections.defaultdict(list)
    for segment in range(1,5):
     e=entries[(segment,shard)];cipher=(assets/e['ENCRYPTED_ASSET_NAME']).read_bytes();need(bytes_digest(cipher)==e['ENCRYPTED_ASSET_SHA256'],'TOPOLOGY_CIPHER');plain=decrypt_synthetic_package(cipher,private_key=key);need(bytes_digest(plain)==e['PLAINTEXT_CANONICAL_SHA256'],'TOPOLOGY_PLAINTEXT');data=json.loads(plain)
     need(data['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1' and data['segment_index']==segment and data['shard_index']==shard and data['identity_range']==e['IDENTITY_RANGE'] and [x['ordinal'] for x in data['items']]==list(range(e['IDENTITY_RANGE'][0],e['IDENTITY_RANGE'][1]+1)),'TOPOLOGY_NATIVE_IDENTITIES')
     count=0
     for item in data['items']:
      need(item['classification'] in ('NO_HISTORICAL_SUPPORT','SHALLOW_SUPPORT_COMPLETE','SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED') and isinstance(item['rows'],list),'TOPOLOGY_SOURCE_SUPPORT')
      by_ordinal[item['ordinal']].extend(timestamp_slots(item['rows'],segment));count+=len(item['rows'])
     need(count==e['ROW_COUNT'],'TOPOLOGY_ROW_COUNT');total+=count;shards+=1
    for ordinal,slots in sorted(by_ordinal.items()):
     stream.write(encoded({'ordinal':ordinal,'slots':slots})+b'\n');packets+=1
 need((total,shards,packets)==(3355389,100,1576),'TOPOLOGY_COMPLETE_SOURCE')
 (temp/'bridge.json').write_bytes(encoded({'manifest_sha256':manifest_sha,'input_sha256':file_hash(temp/'input.jsonl'),'rows':total,'shards':shards,'packets':packets,'prices_exported':False}))
 print('MXM_TIME_ONLY_ORIGINAL_SOURCE_AUTHENTICATED rows=3355389 shards=100 identities=1576',flush=True)

def evaluate():
 from .support_topology_reference import reference,summarize
 identity=admit();temp=temporary();bridge=json.loads((temp/'bridge.json').read_bytes());need(bridge['input_sha256']==file_hash(temp/'input.jsonl') and bridge['manifest_sha256']==POLICY['source_manifest_sha256'],'TOPOLOGY_EXACT_INPUT')
 with (temp/'input.jsonl').open() as stream:expected=reference(json.loads(line) for line in stream)
 subprocess.run(['dotnet','run','--project',PROJECT,'-c','Release','--no-build','--',str(temp/'input.jsonl'),str(temp/'actual.json')],check=True,capture_output=True)
 actual=json.loads((temp/'actual.json').read_bytes());need(actual==expected and actual['Packets']==1576 and actual['Rows']==3355389 and len(actual['Cells'])==1576*4*3,'TOPOLOGY_ALL_CELLS_PARITY')
 summary=summarize(actual);out=ROOT/OUT;out.mkdir(parents=True,exist_ok=True)
 private=encoded({'identity':identity,'bridge':bridge,'original_csharp_json_b64':base64.b64encode((temp/'actual.json').read_bytes()).decode(),'summary':summary})
 need(len(private)<12000000,'TOPOLOGY_PRIVATE_BOUND')
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
 from research_core_v4.successor_c_20261018.readback import FP
 public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'TOPOLOGY_RECIPIENT');encrypt_shard(gzip.compress(private,mtime=0),public_key=public,output=out/'result.mxmenc')
 binary=ROOT/'research_core_v4/laboratory/csharp/support_topology/bin/Release/net8.0/MxmSupportTopology.dll';(out/'evaluator.dll').write_bytes(binary.read_bytes())
 # No identity rankings, timestamps, support counts per asset or economic values are made public.
 r={**identity,'schema':'mxm.time-only-support-public.v1','source_rows':3355389,'source_shards':100,'source_identities':1576,'cells_reconciled':18912,'source_manifest_sha256':bridge['manifest_sha256'],'input_sha256':bridge['input_sha256'],
 'all_time_only_cells_reconciled':True,'private_sha256':bytes_digest(private),'cipher_sha256':bytes_digest((out/'result.mxmenc').read_bytes()),'actual_evaluator_sha256':bytes_digest(binary.read_bytes()),'disposition':summary['disposition'],
 'each_profile_all_four_blocks_at_most_5pct_missing_unselected_grid':{str(p['hold']):all(b['at_most_5pct_missing_for_this_unselected_grid'] for b in p['blocks']) for p in summary['profiles']},
 'prices_exported':False,'new_strategy_identities':0,'model_trials':0,'closed_identities_reexecuted':False,'return_stability_measured':False,'signal_conditioned_censoring_identified':False,
 'historical_costs_proven':False,'actual_fills_proven':False,'net_edge_proven':False,'capital_replay':False,'hard21_proven':False,'native_robot_operational_reception_proven':False,
 'new_broker_requests':0,'orders':0,'protected_opened':False,'independent_confirmation':False,'formal_V2_C033_changed':False,'next_action':'DIRECTOR_SOURCE_SELECTION_REQUIRES_DISTINCT_PROSPECTIVE_MECHANISM_NO_AUTOMATIC_TRIAL'}
 (out/'receipt.json').write_bytes(encoded(r)+b'\n');print('MXM_SUPPORT_TOPOLOGY '+encoded(r).decode(),flush=True)
def cold():
 context(True);out=ROOT/OUT;r=json.loads((out/'receipt.json').read_bytes());cipher=(out/'result.mxmenc').read_bytes()
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack,strict_json
 from research_core_v4.successor_c_20261018.readback import FP
 with tempfile.TemporaryDirectory() as d:
  key,fp=_private_key_from_secret(Path(d));need(fp==FP,'TOPOLOGY_COLD_CUSTODY');raw=unpack(owner.bounded_decrypt(cipher,key,Path(d)),max_bytes=12000000);p=strict_json(raw,max_elements=1000000)
 need(bytes_digest(cipher)==r['cipher_sha256'] and bytes_digest(raw)==r['private_sha256'] and p['identity']=={k:r[k] for k in ('run_id','source_sha','spec_sha256')} and p['summary']['disposition']==r['disposition'] and bytes_digest((out/'evaluator.dll').read_bytes())==r['actual_evaluator_sha256'],'TOPOLOGY_ORIGINAL_COLD_READBACK')
 c={'schema':'mxm.time-only-support-cold.v1','run_id':r['run_id'],'source_sha':r['source_sha'],'cipher_sha256':r['cipher_sha256'],'disposition':r['disposition'],'separate_custody_process_readback':True,'algorithm_reexecuted':False,'orders':0};(out/'cold.json').write_bytes(encoded(c)+b'\n');print('MXM_SUPPORT_TOPOLOGY_COLD '+encoded(c).decode(),flush=True)
def preserve():
 context();out=ROOT/OUT;members=('receipt.json','cold.json','result.mxmenc','evaluator.dll')
 need(all((out/p).is_file() and not (out/p).is_symlink() for p in members),'TOPOLOGY_BUNDLE_MEMBERS')
 r=json.loads((out/'receipt.json').read_bytes());c=json.loads((out/'cold.json').read_bytes())
 need(r['cipher_sha256']==c['cipher_sha256']==bytes_digest((out/'result.mxmenc').read_bytes()) and r['actual_evaluator_sha256']==bytes_digest((out/'evaluator.dll').read_bytes()) and c['algorithm_reexecuted'] is False,'TOPOLOGY_ORIGINAL_BUNDLE_LINKS')
 with zipfile.ZipFile(out/'runtime-original.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in members:z.write(out/p,p)
 bundle=(out/'runtime-original.zip').read_bytes();need(len(bundle)<1500000,'TOPOLOGY_BUNDLE_BOUND')
 print('MXM_ORIGINAL_SUPPORT_BUNDLE '+encoded({'bytes':len(bundle),'sha256':bytes_digest(bundle),'run_id':r['run_id'],'kind':'RUNTIME_ORIGINAL_OUTPUT_BUNDLE_NOT_ACTIONS_TRANSPORT_ZIP','members':{p:{'bytes':(out/p).stat().st_size,'sha256':bytes_digest((out/p).read_bytes())} for p in members}}).decode(),flush=True)
 for i in range(0,len(bundle),16384):print('MXM_ORIGINAL_SUPPORT_PART '+str(i//16384)+' '+base64.b64encode(bundle[i:i+16384]).decode(),flush=True)
if __name__=='__main__':
 os.umask(0o077);command=sys.argv[1:]
 if command==['admit']:admit()
 elif command==['export']:export()
 elif command==['evaluate']:evaluate()
 elif command==['cold']:cold()
 elif command==['preserve']:preserve()
 else:raise ValueError('TOPOLOGY_EXACT_PHASE')
