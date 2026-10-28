"""Existing authentic term units -> shared C# component -> encrypted ledger. No broker."""
import base64,gzip,json,os,subprocess,sys,tempfile,shutil
from pathlib import Path
from .common import need,encoded,bytes_digest
from .spot_observation_reception import NATIVE,BROKER,CHECKOUT,UPLOAD,BOUNDARY_SHA
MANIFEST_SHA='2986157382d938688e9770b92479833ff5743cddd8d8ca32a2bdac9e1386f7be'
ROOT=Path(__file__).resolve().parents[2]
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
PATH='.github/workflows/mxm-displayed-financing-reception.yml';MODULE='research_core_v4.laboratory.displayed_financing_reception';JOB='financing-units'
FOLDER='docs/economic-development/20261027/financing-carry-40587457654';ORIGINAL='c681974caa97f96cab036a05fd8322304e344a54'
PROJECT='research_core_v4/laboratory/csharp/displayed_financing/MxmDisplayedFinancing.csproj';OUT='verification/displayed-financing'
FILES=['research_core_v4/laboratory/displayed_financing_reception.py','research_core_v4/laboratory/financing_carry_development.py','research_core_v4/laboratory/spot_observation_reception.py','research_core_v4/laboratory/spot_observation_profile.py','research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json']
POLICY={'schema':'mxm.displayed-financing-unit-policy.v1','original_run':40587457654,'original_manifest_sha256':MANIFEST_SHA,
 'source_rows':1576,'directions':[1,-1],'volume':'EXPLICIT_NATIVE_MIN_VOLUME_CENTS_AND_LATTICE',
 'supported_types':[0,2],'percentage':'UNRESOLVED_NO_PRICE_OR_CASH_BASIS_INFERENCE','unit':'QUOTE_ASSET',
 'multiplier':1,'rounding':'EXACT_RATIONAL_FLOOR_SIGNED_18_DECIMALS_CREDITS_DOWN_DEBITS_AWAY_FROM_ZERO',
 'calendar_inferred':False,'broker_charge_proven':False,'historical_applicability':False,'new_broker_requests':0,
 'new_directional_trials':0,'closed_screen_reexecuted':False,'orders':0,'automatic_retry':False}
POLICY_SHA=bytes_digest(encoded(POLICY))
def workflow():
 return {'name':'MXM authentic displayed financing components in shared CSharp account','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':{JOB:{
 'if':f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1",'runs-on':'ubuntu-24.04','timeout-minutes':15,'environment':'mxm-r3-custody-v1','permissions':{'contents':'read','actions':'read'},'steps':[
 {'uses':CHECKOUT,'with':{'persist-credentials':False}}, {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.financing-unit-native','persist-credentials':False}},
 {'name':'Admit original source and one no-broker component reception before custody','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
 {'name':'Compile exact funding components and continuous-account/cold-process checks without keys','run':'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\ndotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_displayed_financing -v\npython3 -m '+MODULE+' prepare'},
 {'name':'Authenticate original raw wire and export terms only under existing custody','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\ncd .financing-unit-native\npython3 -m '+MODULE+' export'},
 {'name':'Calculate all native minimum-volume signed components CSharp and reconcile exact rational Python','env':{'GH_TOKEN':'${{ github.token }}'},'run':'umask 077\npython3 -m '+MODULE+' evaluate'},
 {'name':'Separate custody readback of exact original encrypted component ledger without calculation replay','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'},'run':'umask 077\ncd .financing-unit-native\npython3 -m '+MODULE+' cold'},
 {'uses':UPLOAD,'if':'always()','with':{'name':'displayed-financing-${{ github.run_id }}','path':OUT+'/receipt.json\n'+OUT+'/ledger.mxmenc\n'+OUT+'/evaluator.dll\n'+OUT+'/cold.json','if-no-files-found':'error','retention-days':90}}
 ]}}}
def context(custody=False,native=False):
 need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')==JOB and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'FINANCING_UNIT_NATIVE_CONTEXT')
 forbidden=list(BROKER)+['SUCCESSOR_APP_PRIVATE_KEY','R3_CUSTODY_PRIVATE_KEY_PEM','R3_CTRADER_REFRESH_TOKEN']
 if not custody:forbidden+=['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']
 need(not any(os.environ.get(k) for k in forbidden),'FINANCING_UNIT_KEY_ROLES')
 main=ROOT.parent if native else ROOT
 need(subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0,'FINANCING_UNIT_EXACT_MAIN')
 need(json.loads((main/PATH).read_bytes())==workflow() and bytes_digest((main/'V2_PROTECTED_FORWARD_START.json').read_bytes())==BOUNDARY_SHA,'FINANCING_UNIT_SCOPE')
 if native:
  need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'FINANCING_UNIT_PINNED_DECODER')
  for p in FILES:need((ROOT/p).read_bytes()==(main/p).read_bytes(),'FINANCING_UNIT_EXACT_EXTENSION')
 return main
def admit():
 main=context();from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();head=os.environ['GITHUB_SHA'];need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'FINANCING_UNIT_OFFICIAL_HEAD')
 for ref,sha in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==sha,'FINANCING_UNIT_AUTHORITY')
 runs=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100');need(runs['total_count']==len(runs['workflow_runs'])==1 and runs['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and runs['workflow_runs'][0]['run_attempt']==1,'FINANCING_UNIT_ONE_ATTEMPT')
 original=route.json('actions/runs/40587457654');need(original['head_sha']==ORIGINAL and original['run_attempt']==1 and original['status']=='completed' and original['conclusion']=='success','FINANCING_UNIT_ORIGINAL_NATIVE_RUN')
 return {'source_sha':head,'run_id':int(os.environ['GITHUB_RUN_ID']),'policy_sha256':POLICY_SHA}
def folder():return Path(os.environ['RUNNER_TEMP'])/'mxm-displayed-financing'
def prepare():
 from .verify_financing_carry_result import verify
 from .durable_native_chronology import decode_archive
 verify();m=json.loads((ROOT/FOLDER/'MANIFEST.json').read_bytes());_,files=decode_archive(ROOT/FOLDER/'source',m['artifacts']['source']['sha256'])
 temp=folder();temp.mkdir(mode=0o700,exist_ok=True);(temp/'capture.mxmenc').write_bytes(files['capture.mxmenc'])
 for p in FILES:
  target=ROOT/'.financing-unit-native'/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,target)
def decrypt(path):
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack,strict_json
 with tempfile.TemporaryDirectory() as tmp:
  key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'FINANCING_UNIT_EXISTING_CUSTODY');raw=unpack(owner.bounded_decrypt(path.read_bytes(),key,Path(tmp)),max_bytes=32000000)
  return strict_json(raw,max_elements=5000000),bytes_digest(raw)
def export():
 main=context(custody=True,native=True);raw=(main/FOLDER/'MANIFEST.json').read_bytes();need(bytes_digest(raw)==MANIFEST_SHA,'FINANCING_UNIT_ORIGINAL_MANIFEST');m=json.loads(raw)
 cipher=folder()/'capture.mxmenc';need(bytes_digest(cipher.read_bytes())==m['source_cipher_sha256'],'FINANCING_UNIT_ORIGINAL_CIPHER')
 p,h=decrypt(cipher);need(h==m['source_private_sha256'] and p['identity']['run_id']==40587457654 and p['identity']['source_sha']==ORIGINAL,'FINANCING_UNIT_ORIGINAL_PRIVATE')
 # Source authentication only: never call the closed screen's reference/verdict/evaluate.
 from .financing_carry_development import normalize
 from m6.ctrader_transport import decode_envelope,extract_payload
 source=normalize(p)
 responses=[extract_payload(decode_envelope(base64.b64decode(x['response'],validate=True))) for x in p['receipts']]
 assets={x.assetId:x.name for x in responses[4].asset};lights={x.symbolId:x for x in responses[5].symbol};rows=[]
 for r in source['rows']:
  light=lights.get(r['symbol_id']);asset=assets.get(light.quoteAssetId) if light is not None and light.HasField('quoteAssetId') and r['identity_available'] else None
  rows.append({'symbol_id':r['symbol_id'],'quote_asset':asset,'full':r['full'],'source_sha256':h})
 need(len(rows)==1576,'FINANCING_UNIT_ALL_IDENTITIES');(folder()/'input.json').write_bytes(encoded(rows))
 (folder()/'bridge.json').write_bytes(encoded({'original_source_run':40587457654,'original_source_sha':ORIGINAL,'original_private_sha256':h,'original_cipher_sha256':m['source_cipher_sha256'],'input_sha256':bytes_digest(encoded(rows)),'rows':1576,'policy_sha256':POLICY_SHA}))
 print('MXM_ORIGINAL_FINANCING_TERMS_AUTHENTICATED_NO_SCREEN_REPLAY',flush=True)
def evaluate():
 from .displayed_financing_reference import reference
 from decimal import Decimal
 identity=admit();temp=folder();raw=(temp/'input.json').read_bytes();rows=json.loads(raw);bridge=json.loads((temp/'bridge.json').read_bytes());m=json.loads((ROOT/FOLDER/'MANIFEST.json').read_bytes())
 need(bridge['rows']==len(rows)==1576 and bridge['input_sha256']==bytes_digest(raw) and bridge['policy_sha256']==POLICY_SHA and bridge['original_private_sha256']==m['source_private_sha256'] and bridge['original_cipher_sha256']==m['source_cipher_sha256'],'FINANCING_UNIT_EXACT_INPUT')
 subprocess.run(['dotnet','run','--project',PROJECT,'-c','Release','--no-build','--',str(temp/'input.json'),str(temp/'actual.json')],check=True,capture_output=True)
 actual=json.loads((temp/'actual.json').read_bytes(),parse_float=Decimal);expected=reference(rows);need(actual==expected,'FINANCING_UNIT_ALL_COMPONENTS_EXACT_RATIONAL_PARITY')
 any_estimate=any(x['status']=='DISPLAYED_RATE_UNIT_COMPONENT_ONLY' for r in actual for x in r['estimates'])
 private=encoded({'identity':identity,'bridge':bridge,'ledger':json.loads((temp/'actual.json').read_bytes(),parse_float=str),'any_estimate':any_estimate})
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
 from research_core_v4.successor_c_20261018.readback import FP
 out=ROOT/OUT;out.mkdir(parents=True,exist_ok=True);public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'FINANCING_UNIT_RECIPIENT');encrypt_shard(gzip.compress(private,mtime=0),public_key=public,output=out/'ledger.mxmenc')
 binary=ROOT/'research_core_v4/laboratory/csharp/displayed_financing/bin/Release/net8.0/MxmDisplayedFinancing.dll';(out/'evaluator.dll').write_bytes(binary.read_bytes())
 result={**identity,**bridge,'schema':'mxm.displayed-financing-current-components.v1','all_components_independently_reconciled':True,'any_component_estimated':any_estimate,'disposition':'AUTHENTIC_CURRENT_UNIT_COMPONENTS_ONLY' if any_estimate else 'DATA_LIMITED','ledger_private_sha256':bytes_digest(private),'ledger_cipher_sha256':bytes_digest((out/'ledger.mxmenc').read_bytes()),'actual_evaluator_sha256':bytes_digest(binary.read_bytes()),'calendar_inferred':False,'actual_broker_charges_proven':False,'historical_applicability_proven':False,'market_account_replay':False,'new_strategy_trials':0,'closed_screen_reexecuted':False,'new_broker_requests':0,'orders':0,'native_robot_operational_reception_proven':False,'hard21_proven':False,'net_edge_proven':False}
 (out/'receipt.json').write_bytes(encoded(result)+b'\n');print('MXM_DISPLAYED_FINANCING '+encoded(result).decode(),flush=True)
def cold():
 main=context(custody=True,native=True);out=main/OUT;r=json.loads((out/'receipt.json').read_bytes());p,h=decrypt(out/'ledger.mxmenc')
 need(r['source_sha']==os.environ['GITHUB_SHA'] and r['run_id']==int(os.environ['GITHUB_RUN_ID']) and r['policy_sha256']==POLICY_SHA and bytes_digest((out/'ledger.mxmenc').read_bytes())==r['ledger_cipher_sha256'] and h==r['ledger_private_sha256'] and p['identity']=={k:r[k] for k in ('source_sha','run_id','policy_sha256')} and p['bridge']=={k:r[k] for k in p['bridge']} and len(p['ledger'])==1576 and p['any_estimate']==r['any_component_estimated'] and bytes_digest((out/'evaluator.dll').read_bytes())==r['actual_evaluator_sha256'],'FINANCING_UNIT_COLD_ORIGINAL_LEDGER')
 receipt={'schema':'mxm.displayed-financing-cold.v1','source_sha':r['source_sha'],'run_id':r['run_id'],'ledger_cipher_sha256':r['ledger_cipher_sha256'],'separate_custody_process_readback':True,'algorithm_reexecuted':False,'orders':0}
 (out/'cold.json').write_bytes(encoded(receipt)+b'\n');print('MXM_DISPLAYED_FINANCING_COLD '+encoded(receipt).decode(),flush=True)
if __name__=='__main__':
 os.umask(0o077);command=sys.argv[1:]
 if command==['admit']:admit()
 elif command==['prepare']:prepare()
 elif command==['export']:export()
 elif command==['evaluate']:evaluate()
 elif command==['cold']:cold()
 else:raise ValueError('FINANCING_UNIT_EXACT_PHASE')
