"""One prospective quote-triad source admission and conditional economic screen.

Reuse existing VIEW transport, native decoder, C# cost/FX/book primitives and
existing encrypted result/cold-readback flow. No parallel account or controller.
"""
import base64,contextlib,gzip,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
from decimal import Decimal as D
from .common import need,encoded,bytes_digest
from . import spot_observation_reception as source
ROOT=Path(__file__).resolve().parents[2]
MODULE='research_core_v4.laboratory.quote_triangle_development'
PATH=source.PATH;REPO=source.REPO;BRANCH=source.BRANCH;NATIVE=source.NATIVE
OUT='verification/quote-triangle'
SPEC='research_programs/admissions/QUOTE_TRIANGLE_20261029.json'
PART='research_programs/partitions/QUOTE_TRIANGLE_20261029.json'
PROJECT='research_core_v4/laboratory/csharp/quote_triangle/MxmQuoteTriangle.csproj'
IDENTITY='V4-NATIVE-TRIAD-20261029-GBPUSD-ADJUSTMENT'
POLICY={**source.POLICY,'schema':'mxm.prospective-triad-source-policy.v1','symbols':{'1':'EURUSD','2':'GBPUSD','9':'EURGBP'},
 'capture_seconds_after_subscription':720,'maximum_contact_seconds':840,'max_market_events':20000,
 'classification':'PROSPECTIVE_DEPENDENT_DEVELOPMENT_TRIAD_SOURCE','new_response_testing_allowed':True,
 'mechanism':IDENTITY,'target':2,'minimum_potential_decisions':100,'minimum_price_blind_response_geometry_fraction':.8,
 'entry_delay_ms':250,'entry_deadline_ms':3000,'exit_delay_ms':1000,'exit_deadline_ms':4000,'holdoff_ms':8000,
 'hurdle':'TWO_TARGET_SPREADS_PLUS_TWO_CURRENT_COMMISSION_CEILINGS_IN_QUOTE_CURRENCY',
 'numerical_hurdle_guard_quote':'1e-20','maximum_new_identities_after_source_admission':1,'minimum_completed_episodes_for_screen':20,
 'zero_unpriced_or_censored_episodes_for_survivor':True,'current_terms_are_actual_total_costs':False,
 'locked_reference_and_risk_marks':'EXISTING_NATIVE_NONCROSSED_PREDICATE_NO_LOCKED_EXECUTION',
 'guard_before_incoming_refresh':True,'initial_capital_reference_eur':200,'margin_cap_eur':80,'free_margin_reserve_eur':120,'risk_reference_eur':2,
 'stop_reference_quote':.0012,'round_trip_fee_reserve_eur':.2,'funding_and_actual_slippage':'UNRESOLVED',
 'cost_scenarios':['OBSERVED_BIDASK_AND_CURRENT_COMMISSION_REFERENCE','ADVERSE_ONE_PIP_ROUNDTRIP_PLUS_COMMISSION'],
 'strategy_trials':0,'source_only_prior_intervals_reused':False}
FILES=['research_core_v4/laboratory/quote_triangle_development.py','research_core_v4/laboratory/quote_triangle_reference.py',
 'research_core_v4/laboratory/economic_journal.py','research_core_v4/laboratory/spot_observation_reception.py',
 'research_core_v4/laboratory/spot_observation_profile.py','research_core_v4/laboratory/universe_commission_checks.py',SPEC,PART]
IMPL=[*FILES[:6],'research_core_v4/laboratory/csharp/quote_triangle/Program.cs',PROJECT,
 'research_core_v4/native_tick_replay_v1/csharp/MxmBookShape.cs','research_core_v4/native_tick_replay_v1/csharp/MxmBookObservation.cs',
 'research_core_v4/native_tick_replay_v1/csharp/MxmObservedCostFx.cs','research_core_v4/native_tick_replay_v1/csharp/MxmInstrumentCommission.cs']
def partition():return {'schema':'mxm.prospective-economic-source-partition.v1','mechanism':IDENTITY,'classification':'DEVELOPMENT',
 'entire_actual_contact_interval_excluded_from_confirmation':True,'confirmation_eligible':False,'prior_evidence_reclassified':False,
 'new_response_testing_allowed_only_for_this_frozen_procedure':True,'protected_opened':False,'orders':0}
@contextlib.contextmanager
def configured():
 old={k:getattr(source,k) for k in ('POLICY','POLICY_SHA','OUT','partition')}
 source.POLICY=POLICY;source.POLICY_SHA=bytes_digest(encoded(POLICY));source.OUT=OUT;source.partition=partition
 try:yield
 finally:
  for k,v in old.items():setattr(source,k,v)
def validate(main=ROOT):
 s=json.loads((main/SPEC).read_bytes());need(s['policy']==POLICY and json.loads((main/PART).read_bytes())==partition(),'TRIAD_FROZEN_SCOPE')
 need(set(s['implementation_sha256'])==set(IMPL),'TRIAD_IMPLEMENTATION_CLOSURE')
 for p,h in s['implementation_sha256'].items():need(bytes_digest((main/p).read_bytes())==h,'TRIAD_EXACT_IMPLEMENTATION')
 return bytes_digest((main/SPEC).read_bytes())
def workflow():
 w=source.workflow();w['name']='MXM prospective triad source admission and complete private economic journal'
 for role,j in w['jobs'].items():
  j['timeout-minutes']=20
  for st in j['steps']:
   if 'run' in st:
    st['run']=st['run'].replace('research_core_v4.laboratory.spot_observation_reception',MODULE)
    if st.get('name','').startswith('Verify source-only'):
     st['run']='python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\ndotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_quote_triangle -v\npython3 -m '+MODULE+' install'
   if st.get('uses')==source.DOWNLOAD:st['with'].update(name='quote-triad-source-${{ github.run_id }}',path=OUT)
   if st.get('uses')==source.UPLOAD:st['with'].update(name=('quote-triad-source-' if role=='spot-collect' else 'quote-triad-result-')+'${{ github.run_id }}',
    path=OUT+('/capture.mxmenc\n'+OUT+'/producer.json' if role=='spot-collect' else '/receipt.json\n'+OUT+'/result.mxmenc\n'+OUT+'/evaluator.dll\n'+OUT+'/cold.json\n'+OUT+'/runtime-original.zip'))
  if role=='spot-cold':
   decrypt=j['steps'][-2];decrypt['run']='umask 077\ncd .spot-native\npython3 -m '+MODULE+' export'
   j['steps'].insert(-1,{'name':'Source admission before identity; evaluate once in CSharp and preserve individual ledger encrypted',
    'env':{'GH_TOKEN':'${{ github.token }}'},'run':'umask 077\npython3 -m '+MODULE+' evaluate'})
   j['steps'].insert(-1,{'name':'Read original complete encrypted result in a separate custody process without model replay',
    'env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}','GH_TOKEN':'${{ github.token }}'},
    'run':'umask 077\ncd .spot-native\npython3 -m '+MODULE+' cold'})
   j['steps'].insert(-1,{'name':'Retain original result bytes without decryption or repeated economics','run':'python3 -m '+MODULE+' preserve'})
 return w

def admit(native=False,keyrole=None):
 main=ROOT.parent if native else ROOT;job=os.environ.get('GITHUB_JOB')
 need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and
  os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and job in ('spot-collect','spot-cold') and
  os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'TRIAD_NATIVE_CONTEXT')
 forbidden=['SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_REFRESH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM']
 if keyrole!='broker':forbidden+=list(source.BROKER)
 if keyrole!='custody':forbidden+=['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']
 need(not any(os.environ.get(k) for k in forbidden),'TRIAD_SEPARATED_SECRET_ROLES')
 head=subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()
 need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
  subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0 and
  json.loads((main/PATH).read_bytes())==workflow(),'TRIAD_EXACT_HEAD_WORKFLOW')
 need(bytes_digest((main/'V2_PROTECTED_FORWARD_START.json').read_bytes())==source.BOUNDARY_SHA,'TRIAD_UNCHANGED_PROTECTED_BOUNDARY')
 spec_sha=validate(main)
 if native:
  need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'TRIAD_SEALED_NATIVE')
  for p in FILES:need((ROOT/p).read_bytes()==(main/p).read_bytes(),'TRIAD_EXACT_EXTENSION')
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'TRIAD_OFFICIAL_HEAD')
 for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'TRIAD_UNCHANGED_AUTHORITY')
 v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100');current=int(os.environ['GITHUB_RUN_ID'])
 need(v['total_count']==len(v['workflow_runs'])==3 and {r['id'] for r in v['workflow_runs']}=={40455704891,40836352578,current} and
  all(r['run_attempt']==1 for r in v['workflow_runs']) and all(r['conclusion']=='success' for r in v['workflow_runs'] if r['id']!=current),'TRIAD_ONE_NEW_ATTEMPT_NO_W33_REPLAY')
 return dict(run_id=current,source_sha=head,native_source=NATIVE,policy_sha256=bytes_digest(encoded(POLICY)),
  partition_sha256=bytes_digest(encoded(partition())),spec_sha256=spec_sha,attempt=1)
def install():
 import shutil
 for p in FILES:
  out=ROOT/'.spot-native'/p;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,out)
def metadata(p):
 from m6.ctrader_transport import decode_envelope,extract_payload
 from google.protobuf.json_format import MessageToDict
 from .universe_commission_checks import terms
 res=[extract_payload(decode_envelope(base64.b64decode(r['response_wire'],validate=True))) for r in p['receipts'][:10]]
 need(len(res)==10,'TRIAD_COMPLETE_PRE_SUBSCRIPTION_METADATA')
 assets={int(a.assetId):a.name for a in res[4].asset};lights={int(x.symbolId):x for x in res[5].symbol};full={int(x.symbolId):x for x in res[6].symbol}
 for sid,(base,quote) in {1:('EUR','USD'),2:('GBP','USD'),9:('EUR','GBP')}.items():
  light=lights[sid];need(light.HasField('baseAssetId') and light.HasField('quoteAssetId') and
   (assets.get(light.baseAssetId),assets.get(light.quoteAssetId))==(base,quote),'TRIAD_NATIVE_CURRENCY_RELATION')
 raw=MessageToDict(full[2],preserving_proto_field_name=False,use_integers_for_enums=True)
 try:term=terms(dict(symbol_id=2,quote_asset='USD',full=raw))
 except (KeyError,ValueError,TypeError):need(False,'TRIAD_MISSING_EXPLICIT_COST_TERMS')
 need(term['MinimumAsset'] in ('EUR','USD'),'TRIAD_COST_FX_AVAILABLE')
 m=res[8];need(m.HasField('moneyDigits') and 0<=m.moneyDigits<=28 and len(m.margin)==1 and
  m.margin[0].volume==term['MinimumVolume'] and m.margin[0].HasField('buyMargin') and m.margin[0].HasField('sellMargin') and
  min(m.margin[0].buyMargin,m.margin[0].sellMargin)>0,'TRIAD_NATIVE_MARGIN')
 margin=D(max(m.margin[0].buyMargin,m.margin[0].sellMargin))/D(10)**m.moneyDigits
 need(margin<=80,'TRIAD_MINIMUM_MARGIN_EXCEEDS_EXISTING_EUR200_BOUND')
 return dict(target_terms=raw,margin_eur=str(margin),current_metadata_is_historical_cost=False,actual_total_cost_proven=False)
def collect():
 identity=admit(native=True,keyrole='broker')
 with configured():source.collect(identity,metadata_guard=metadata)
def export():
 identity=admit(native=True,keyrole='custody');out=ROOT.parent/OUT
 producer=json.loads((out/'producer.json').read_bytes());cipher=(out/'capture.mxmenc').read_bytes()
 need(all(producer[k]==v for k,v in identity.items()) and bytes_digest(cipher)==producer['cipher_sha256'],'TRIAD_NATIVE_PRODUCER_IDENTITY')
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 jobs=GetOnly().json('actions/runs/'+str(identity['run_id'])+'/jobs?per_page=100')['jobs']
 need(any(j['name']=='spot-collect' and j['conclusion']=='success' for j in jobs),'TRIAD_PRODUCER_SUCCESS')
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
 from research_core_v4.successor_c_20261018.readback import FP
 with tempfile.TemporaryDirectory() as tmp:
  key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'TRIAD_EXISTING_CUSTODY')
  raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)),max_bytes=POLICY['max_private_bytes'])
  need(bytes_digest(raw)==producer['private_sha256'],'TRIAD_ORIGINAL_PRIVATE_SOURCE');p=strict_json(raw,max_elements=3000000)
  with configured():
   need(source.verify_private(p)==producer['profile'],'TRIAD_ALL_NATIVE_SOURCE_EVENTS')
   events=[source.market_event(row,p['account']) for row in p['market']]
  data={**metadata(p),'events':events,'identity':identity,'source_private_sha256':producer['private_sha256'],
   'contact_interval':[p['contact_start_utc'],p['contact_end_utc']]}
  (out/'input.json').write_bytes(encoded(data)+b'\n')
 print('MXM_TRIAD_NATIVE_SOURCE_REDECODED_NO_MODEL_YET')
def run_csharp(data,out):
 subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',str(data),str(out)],check=True,capture_output=True)
def evaluate():
 identity=admit();out=ROOT/OUT;path=out/'input.json';data=json.loads(path.read_bytes())
 need(data['identity']==identity,'TRIAD_EXPORTED_IDENTITY');actual_path=out/'actual.json';run_csharp(path,actual_path)
 actual=json.loads(actual_path.read_bytes(),parse_float=D)
 from .quote_triangle_reference import reconcile
 checked=reconcile(data,actual)
 from .economic_journal import validate as journal_validate
 audit=journal_validate(actual['journal'],target_events=actual['target_events'],source_sha256=data['source_private_sha256'],policy_sha256=identity['spec_sha256']) if actual['models'] else None
 complete=[e for e in actual['episodes'] if e['exit'] is not None];censored=len(actual['episodes'])-len(complete)
 gross=sum((e['gross_eur'] for e in complete),D(0));net=sum((e['net_scenario_eur'] for e in complete),D(0))
 stressed=net-sum((D('.0001')*D(str(data['target_terms']['minVolume']))/100/D(str(e['exit']['Fx']['Bid'])) for e in complete),D(0))
 disposition='SOURCE_ADMISSION_STOP_NO_ECONOMIC_IDENTITY' if not actual['models'] else 'DATA_LIMITED_CENSORED_EPISODES' if censored else 'NO_FRICTION_EXCEEDING_OPPORTUNITIES' if not actual['episodes'] else 'INSUFFICIENT_EPISODES' if len(complete)<20 else 'NET_FAIL_CURRENT_COST_REFERENCE_SCENARIO' if net<=0 else 'COST_STRESS_FAIL' if stressed<=0 else 'EXPLORATORY_POSITIVE_TOTAL_COSTS_UNRESOLVED'
 private=encoded(dict(schema='mxm.first-execution-triad-research-private.v1',identity=identity,
  source_private_sha256=data['source_private_sha256'],source_input_sha256=bytes_digest(path.read_bytes()),
  original_csharp_json_b64=base64.b64encode(actual_path.read_bytes()).decode(),audit=audit,
  arithmetic_reconciliation=checked,disposition=disposition,cashflow_population='COMPLETE_EPISODES_ONLY_UNKNOWN_CENSORS_RETAINED',gross_eur=str(gross),net_commission_reference_eur=str(net),
  net_adverse_one_pip_roundtrip_eur=str(stressed),funding_actual_slippage_and_fills='UNRESOLVED',full_capital_replay=False))
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
 from research_core_v4.successor_c_20261018.readback import FP
 public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'TRIAD_EXISTING_RECIPIENT')
 encrypt_shard(gzip.compress(private,mtime=0),public_key=public,output=out/'result.mxmenc')
 binary=ROOT/'research_core_v4/laboratory/csharp/quote_triangle/bin/Release/net8.0/MxmQuoteTriangle.dll';(out/'evaluator.dll').write_bytes(binary.read_bytes())
 r=dict(schema='mxm.prospective-triad-public.v1',**identity,source_events=actual['source_events'],target_events=actual['target_events'],
  source_admission=actual['admission'],new_economic_models=actual['models'],new_identity_reservations=actual['models'],
  disposition=disposition,individual_journal_retained=bool(audit),journal_rows=audit['rows'] if audit else 0,
  opportunities=len(actual['episodes']),complete_episodes=len(complete),censored_episodes=censored,
  actual_evaluator_sha256=bytes_digest(binary.read_bytes()),private_sha256=bytes_digest(private),ciphertext_sha256=bytes_digest((out/'result.mxmenc').read_bytes()),
  source_private_sha256=data['source_private_sha256'],source_input_sha256=bytes_digest(path.read_bytes()),
  contact_interval=data['contact_interval'],entire_interval_excluded_from_confirmation=True,
  gross_positive=(gross>0 if actual['models'] and not censored else None),net_reference_positive=(net>0 if actual['models'] and not censored else None),net_stress_positive=(stressed>0 if actual['models'] and not censored else None),
  initial_capital_reference_eur=200,capital_replay=False,historical_total_costs_proven=False,actual_fills_proven=False,
  economic_edge_proven=False,hard21_proven=False,independent_confirmation=False,orders=0,cloud_activated=False,
  prior_closed_models_reexecuted=False,formal_V2_C033_changed=False,terminal='STOP_FIXED_PROCEDURE_NO_RETUNE_NO_AUTOMATIC_RETRY')
 (out/'receipt.json').write_bytes(encoded(r)+b'\n');print('MXM_PROSPECTIVE_TRIAD_RESULT '+encoded(r).decode())
def cold():
 identity=admit(native=True,keyrole='custody');out=ROOT.parent/OUT;r=json.loads((out/'receipt.json').read_bytes());cipher=(out/'result.mxmenc').read_bytes()
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
 from research_core_v4.successor_c_20261018.readback import FP
 with tempfile.TemporaryDirectory() as tmp:
  key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'TRIAD_COLD_EXISTING_RECIPIENT')
  raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)),max_bytes=32000000);p=strict_json(raw,max_elements=3000000)
 need(p['identity']==identity and r['ciphertext_sha256']==bytes_digest(cipher) and r['private_sha256']==bytes_digest(raw) and p['disposition']==r['disposition'],'TRIAD_COMPLETE_COLD_RESULT')
 actual=json.loads(base64.b64decode(p['original_csharp_json_b64']),parse_float=D)
 if actual['models']:
  from .economic_journal import validate as journal_validate
  audit=journal_validate(actual['journal'],target_events=actual['target_events'],source_sha256=p['source_private_sha256'],policy_sha256=identity['spec_sha256'])
  need(audit==p['audit'],'TRIAD_COLD_FULL_INDIVIDUAL_JOURNAL')
 c=dict(schema='mxm.prospective-triad-cold.v1',**identity,ciphertext_sha256=bytes_digest(cipher),
  full_individual_journal_read_back=bool(actual['models']),source_admission_stop_without_identity=not bool(actual['models']),
  model_reexecuted=False,disposition=p['disposition'],orders=0)
 (out/'cold.json').write_bytes(encoded(c)+b'\n');print('MXM_TRIAD_COLD '+encoded(c).decode())
def preserve():
 out=ROOT/OUT;names=('receipt.json','result.mxmenc','evaluator.dll','cold.json')
 with zipfile.ZipFile(out/'runtime-original.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
  for name in names:z.write(out/name,name)
if __name__=='__main__':
 os.umask(0o077);need(len(sys.argv)==2,'TRIAD_EXACT_PHASE')
 {'admit':admit,'install':install,'spot-collect':collect,'export':export,'evaluate':evaluate,'cold':cold,'preserve':preserve}[sys.argv[1]]()
