"""One current-financing screen; reuse VIEW transport, original wire and custody."""
import base64,gzip,json,os,subprocess,sys,tempfile,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .common import need,encoded,bytes_digest
from .spot_observation_reception import AUTH,BROKER,CHECKOUT,UPLOAD,DOWNLOAD,NATIVE,BOUNDARY_SHA,fingerprint,utc_millis
ROOT=Path(__file__).resolve().parents[2]
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
MODULE='research_core_v4.laboratory.financing_carry_development';PATH='.github/workflows/mxm-financing-carry-development.yml'
SPEC='research_programs/admissions/FINANCING_CARRY_20261027.json';PART='research_programs/partitions/FINANCING_CARRY_20261027.json'
PROJECT='research_core_v4/laboratory/csharp/financing_carry/MxmFinancingCarry.csproj';OUT='verification/financing-carry'
ROSTER='research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json'
ROSTER_SHA='5e85a9f21229c6ccd65875ef25815468ea500e315851bc18692d99d1ae102860'
FILES=['research_core_v4/laboratory/financing_carry_development.py','research_core_v4/laboratory/spot_observation_reception.py','research_core_v4/laboratory/spot_observation_profile.py',SPEC,PART,ROSTER]
CAPS={'ProtoOATraderReq':1,'ProtoOAAssetListReq':1,'ProtoOASymbolsListReq':1,'ProtoOASymbolByIdReq':526}
POLICY={'model_id':'MXM_SAME_SYMBOL_EQUAL_VOLUME_FINANCING_CARRY_20261027_V1',
 'universe_count':1576,'roster_sha256':ROSTER_SHA,'batch_size':3,'minimum_request_spacing_seconds':0.5,
 'contact_seconds':900,'wire_bytes_cap':16000000,'private_bytes_cap':32000000,'frame_bytes_cap':500000,
 'native_attempts':1,'model_trials_max':1,'automatic_retry':False,'confirmation_eligible':False,
 'mechanism':'EQUAL_VOLUME_SIMULTANEOUS_LONG_SHORT_SAME_SYMBOL_DISPLAYED_FINANCING_RATE_SIGN',
 'no_default_optional_fields':True,'no_cash_amount_or_future_rate_inference':True,
 'orders':0,'cloud':False,'broker_fills':False,'capital_replay':False,
 'classification':'DEPENDENT_DEVELOPMENT_CURRENT_FINANCING_NECESSARY_CONDITION_ONLY'}
def roster():
 raw=(ROOT/ROSTER).read_bytes();need(bytes_digest(raw)==ROSTER_SHA,'FINANCING_FROZEN_ROSTER')
 v=json.loads(raw);need(len(v)==1576 and len({x['symbol_id'] for x in v})==1576 and v==sorted(v,key=lambda x:x['symbol_id']),'FINANCING_ROSTER')
 return v
def partition():return {'schema':'mxm.prospective-economic-source-partition.v1','model_id':POLICY['model_id'],'classification':'DEVELOPMENT',
 'contact_interval':'ENTIRE_ACTUAL_CONTACT_WINDOW_FROM_NATIVE_RECEIPT','confirmation_eligible':False,
 'exclude_intersecting_feature_response_windows_all_identities':True,'prior_diagnostic_or_protected_data_reclassified':False}
def spec(main):
 s=json.loads((main/SPEC).read_bytes());need(s['policy']==POLICY and json.loads((main/PART).read_bytes())==partition(),'FINANCING_FROZEN_POLICY_PARTITION')
 for p,h in s['implementation_sha256'].items():need(bytes_digest((main/p).read_bytes())==h,'FINANCING_EXACT_IMPLEMENTATION')
 return s
def workflow():
 jobs={}
 for role,env in [('capture','mxm-r3-pepperstone-v1'),('evaluate','mxm-r3-custody-v1')]:
  steps=[{'uses':CHECKOUT,'with':{'persist-credentials':False}},
   {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.financing-native','persist-credentials':False}},
   {'name':'Admit one frozen finite model and partition before keys','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
   {'name':'Check independent artificial policy and exact native extension without keys','run':
    'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
    'dotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_financing_carry -v\n'
    'python3 -m '+MODULE+' install'}]
  if role=='capture':
   steps.append({'name':'One bounded VIEW metadata contact; no market subscriptions or orders','env':{**{'GH_TOKEN':'${{ github.token }}'},**{k:'${{ secrets.'+k+' }}' for k in BROKER}},'run':'umask 077\ncd .financing-native\npython3 -m '+MODULE+' capture'})
  else:
   steps.append({'uses':DOWNLOAD,'with':{'name':'financing-carry-source-${{ github.run_id }}','path':OUT}})
   steps.extend([
    {'name':'Authenticate every original wire event and export only in custody','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}','GH_TOKEN':'${{ github.token }}'},'run':'umask 077\ncd .financing-native\npython3 -m '+MODULE+' export'},
    {'name':'Execute one actual CSharp model; reconcile independent array reference and encrypt','env':{'GH_TOKEN':'${{ github.token }}'},'run':'umask 077\npython3 -m '+MODULE+' evaluate'},
    {'name':'Read back original encrypted result in a separate custody process','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}','GH_TOKEN':'${{ github.token }}'},'run':'umask 077\ncd .financing-native\npython3 -m '+MODULE+' cold'}])
  paths=OUT+'/capture.mxmenc\n'+OUT+'/producer.json' if role=='capture' else OUT+'/receipt.json\n'+OUT+'/result.mxmenc\n'+OUT+'/evaluator.dll\n'+OUT+'/cold.json'
  steps.append({'uses':UPLOAD,'if':'always()','with':{'name':('financing-carry-source-' if role=='capture' else 'financing-carry-result-')+'${{ github.run_id }}','path':paths,'if-no-files-found':'error','retention-days':90}})
  job={'runs-on':'ubuntu-24.04','timeout-minutes':20 if role=='capture' else 10,'environment':env,'permissions':{'contents':'read','actions':'read'},'steps':steps}
  if role=='capture':job['if']=f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1"
  else:job['needs']='capture'
  jobs[role]=job
 return {'name':'MXM one universe-wide current financing carry screen','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
  'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':jobs}
def admit(native=False,keyrole=None):
 main=ROOT.parent if native else ROOT
 need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
  os.environ.get('GITHUB_JOB') in ('capture','evaluate') and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'FINANCING_NATIVE_CONTEXT')
 forbidden=['SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_REFRESH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM']
 if keyrole!='broker':forbidden+=list(BROKER)
 if keyrole!='custody':forbidden+=['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']
 need(not any(os.environ.get(k) for k in forbidden),'FINANCING_KEY_ROLE')
 head=subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()
 need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0,'FINANCING_EXACT_MAIN_HEAD')
 need(json.loads((main/PATH).read_bytes())==workflow() and bytes_digest((main/'V2_PROTECTED_FORWARD_START.json').read_bytes())==BOUNDARY_SHA,'FINANCING_WORKFLOW_BOUNDARY')
 spec(main)
 if native:
  need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'FINANCING_PINNED_DECODER')
  for p in FILES:need((ROOT/p).read_bytes()==(main/p).read_bytes(),'FINANCING_EXACT_EXTENSION')
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'FINANCING_OFFICIAL_HEAD')
 for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'FINANCING_AUTHORITY')
 runs=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
 need(runs['total_count']==len(runs['workflow_runs'])==1 and runs['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and runs['workflow_runs'][0]['run_attempt']==1,'FINANCING_ONE_ATTEMPT')
 return {'source_sha':head,'run_id':int(os.environ['GITHUB_RUN_ID']),'spec_sha256':bytes_digest((main/SPEC).read_bytes())}
def install():
 import shutil
 for p in FILES:
  dest=ROOT/'.financing-native'/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,dest)
def normalize(p):
 from m6.ctrader_transport import decode_envelope,extract_payload
 from m6.ctrader_proto import OpenApiModelMessages_pb2 as e
 from google.protobuf.json_format import MessageToDict
 from research_core_v4.shallow_m5_support_v2_production import ACCOUNT_FINGERPRINT_SHA256
 need(p['complete'] and p['policy']==POLICY and p['partition']==partition() and fingerprint(p['account'])==ACCOUNT_FINGERPRINT_SHA256,'FINANCING_SOURCE_IDENTITY')
 res=[];seen=set();requested=[]
 expected=list(AUTH)+['ProtoOATraderReq','ProtoOAAssetListReq','ProtoOASymbolsListReq']
 need([x['name'] for x in p['receipts'][:6]]==expected and 6<=len(p['receipts'])<=532,'FINANCING_SEQUENCE')
 for index,row in enumerate(p['receipts']):
  env=decode_envelope(base64.b64decode(row['response'],validate=True));msg=extract_payload(env)
  need(env.IsInitialized() and msg.IsInitialized() and env.clientMsgId==row['cid'] and row['cid'] not in seen and type(msg).__name__==row['name'][:-3]+'Res','FINANCING_RESPONSE_CORRELATION');seen.add(row['cid']);res.append(msg)
  if hasattr(msg,'ctidTraderAccountId'):need(msg.ctidTraderAccountId==p['account'],'FINANCING_ACCOUNT')
  if row['name'] not in AUTH:
   reqenv=decode_envelope(base64.b64decode(row['request'],validate=True));req=extract_payload(reqenv)
   need(reqenv.IsInitialized() and req.IsInitialized() and reqenv.clientMsgId==row['cid'] and req.ctidTraderAccountId==p['account'] and type(req).__name__==row['name'],'FINANCING_REQUEST')
   if index>=6:
    need(row['name']=='ProtoOASymbolByIdReq' and 0<len(req.symbolId)<=3 and len(set(req.symbolId))==len(req.symbolId),'FINANCING_BATCH')
    need(len({x.symbolId for x in msg.symbol})==len(msg.symbol) and set(x.symbolId for x in msg.symbol)<=set(req.symbolId),'FINANCING_RETURNED_SUBSET')
    requested.extend(req.symbolId)
 accounts=res[1];matches=[a for a in accounts.ctidTraderAccount if a.ctidTraderAccountId==p['account']]
 need(accounts.HasField('permissionScope') and accounts.permissionScope==e.SCOPE_VIEW and len(matches)==1 and matches[0].isLive,'FINANCING_VIEW')
 trader=res[3].trader;assets={a.assetId:a.name for a in res[4].asset}
 need('pepperstone' in trader.brokerName.casefold() and assets.get(trader.depositAssetId)=='EUR','FINANCING_PEPPERSTONE_EUR')
 lights={x.symbolId:x for x in res[5].symbol};need(len(lights)==len(res[5].symbol),'FINANCING_UNIQUE_LIGHT')
 targets=roster();expected_ids=[x['symbol_id'] for x in targets if x['symbol_id'] in lights]
 need(requested==expected_ids and p['epochs']==1 and p['wire_bytes']<=POLICY['wire_bytes_cap'] and 0<=p['end_ms']<=900000,'FINANCING_FULL_UNIVERSE_BOUNDS')
 full={x.symbolId:x for msg in res[6:] for x in msg.symbol};rows=[]
 for ident in targets:
  sid=ident['symbol_id'];light=lights.get(sid);f=full.get(sid)
  item={'symbol_id':sid,'identity_available':light is not None and light.symbolName==ident['symbol'],'enabled':bool(light.enabled) if light and light.HasField('enabled') else None,'full':{}}
  if f is not None:
   item['full']=MessageToDict(f,preserving_proto_field_name=False,use_integers_for_enums=True)
   for name in ('swapLong','swapShort'):
    if f.HasField(name):item['full'][name]=format(getattr(f,name),'.17g')
  rows.append(item)
 return {'account_type':int(trader.accountType) if trader.HasField('accountType') else None,'swap_free':bool(trader.swapFree) if trader.HasField('swapFree') else None,'rows':rows}
def outbound_guard(name,active):
 need(name in (*AUTH,*CAPS,'ProtoHeartbeatEvent'),'FINANCING_OUTBOUND_ALLOWLIST')
 if name!='ProtoHeartbeatEvent':need(active is not None and active['name']==name and 'cid' not in active,'FINANCING_NO_DIRECT_OR_SECOND_SEND')
def collect():
 identity=admit(native=True,keyrole='broker')
 from collections import Counter
 from m6.ctrader_transport import decode_envelope,extract_payload
 from m6.ctrader_proto import OpenApiMessages_pb2 as m
 from research_core_v4.dom_information_20261014_v1.live_adapter_v1 import InformationTransport
 from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,ACCOUNT_FINGERPRINT_SHA256,encrypt_shard,public_spki_sha256
 from research_core_v4.successor_c_20261018.readback import FP
 main=ROOT.parent;out=main/OUT;out.mkdir(parents=True,exist_ok=True)
 p=dict(identity=identity,policy=POLICY,partition=partition(),complete=False,account=None,receipts=[],origin_ns=time.monotonic_ns(),contact_start_utc=datetime.now(timezone.utc).isoformat())
 counter=Counter();wire_bytes=0;canonical=0
 def handle(msg,stamp,env):raise ValueError('FINANCING_NO_MARKET_EVENTS_AUTHORIZED')
 class Wire(InformationTransport):
  active=None
  def _send_bytes(self,frame):
   nonlocal wire_bytes
   env=decode_envelope(frame[4:]);name=type(extract_payload(env)).__name__
   outbound_guard(name,self.active)
   if name!='ProtoHeartbeatEvent':
    self.active['cid']=env.clientMsgId
    if name not in AUTH:self.active['request']=base64.b64encode(env.SerializeToString()).decode()
   wire_bytes+=len(frame);need(wire_bytes<=POLICY['wire_bytes_cap'],'FINANCING_WIRE_CAP');return super()._send_bytes(frame)
  def _recv_exact(self,count,*,deadline):
   nonlocal wire_bytes
   need(0<count<=POLICY['frame_bytes_cap'] and wire_bytes+count<=POLICY['wire_bytes_cap'],'FINANCING_FRAME_CAP')
   try:data=super()._recv_exact(count,deadline=deadline)
   except Exception:wire_bytes+=self.partial_frame_received;raise
   wire_bytes+=len(data);return data
  def receive_envelope(self,*,deadline):
   env=super().receive_envelope(deadline=deadline)
   need(self.receipt_sequence<=200000,'FINANCING_ENVELOPE_CAP')
   if self.active is not None and env.clientMsgId==self.active.get('cid'):
    need('response' not in self.active,'FINANCING_DUPLICATE_RESPONSE');self.active['response']=base64.b64encode(env.SerializeToString()).decode()
   return env
  def request(self,request,**kw):
   name=type(request).__name__
   need(name in (*AUTH,*CAPS) and counter[name]<(1 if name in AUTH else CAPS[name]),'FINANCING_REQUEST_CAP')
   if name in AUTH:need(name==AUTH[len(p['receipts'])],'FINANCING_AUTH_SEQUENCE')
   counter[name]+=1;row={'name':name};p['receipts'].append(row);self.active=row
   try:
    res=super().request(request,**kw);need(type(res).__name__==name[:-3]+'Res' and 'response' in row,'FINANCING_REQUEST_RESPONSE');return res
   finally:self.active=None
 now=datetime.now(timezone.utc)
 tr=Wire(start_utc=now,end_utc=now+timedelta(seconds=POLICY['contact_seconds']),account_fingerprint=ACCOUNT_FINGERPRINT_SHA256,event_handler=handle,maximum_connection_seconds=POLICY['contact_seconds'],connect_timeout=15,response_timeout=20)
 try:
  need(all(os.environ.get(k) for k in BROKER),'FINANCING_EXISTING_CREDENTIALS');values=[os.environ.pop(k) for k in BROKER]
  tr.connect();account=authenticate_segment(tr,*values);values=None;p['account']=account
  trader=tr.request(m.ProtoOATraderReq(ctidTraderAccountId=account)).trader
  assets={a.assetId:a.name for a in tr.request(m.ProtoOAAssetListReq(ctidTraderAccountId=account)).asset}
  need('pepperstone' in trader.brokerName.casefold() and assets.get(trader.depositAssetId)=='EUR','FINANCING_NATIVE_ACCOUNT')
  lights={s.symbolId:s for s in tr.request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False)).symbol}
  targets=[x['symbol_id'] for x in roster() if x['symbol_id'] in lights];tr.selected=set(targets)
  for offset in range(0,len(targets),3):
   time.sleep(0.5)
   tr.request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=targets[offset:offset+3]))
  p['complete']=True
 except Exception as ex:p['failure_class']=type(ex).__name__
 finally:
  tr.close();p['end_ms']=(time.monotonic_ns()-p['origin_ns'])//1000000;p['contact_end_utc']=datetime.now(timezone.utc).isoformat();p['wire_bytes']=wire_bytes;p['epochs']=tr.connection_epochs
  for k in BROKER:os.environ.pop(k,None)
  raw=encoded(p);need(len(raw)<POLICY['private_bytes_cap'],'FINANCING_PRIVATE_CAP');public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'FINANCING_EXISTING_RECIPIENT')
  encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=out/'capture.mxmenc')
  receipt={**identity,'accepted':p['complete'],'cipher_sha256':bytes_digest((out/'capture.mxmenc').read_bytes()),'private_sha256':bytes_digest(raw),'metadata_responses':len(p['receipts']),'new_connections':p['epochs'],'orders':0,'new_economic_outcomes':0,'failure_class':p.get('failure_class'),'contact_start_utc':p['contact_start_utc'],'contact_end_utc':p['contact_end_utc']}
  (out/'producer.json').write_bytes(encoded(receipt)+b'\n');print('MXM_FINANCING_SOURCE '+encoded(receipt).decode(),flush=True)
 need(p['complete'],'FINANCING_CAPTURE_INCOMPLETE_NO_RETRY')
def decrypt(path):
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack,strict_json
 with tempfile.TemporaryDirectory() as tmp:
  key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'FINANCING_EXISTING_CUSTODY')
  raw=unpack(owner.bounded_decrypt(path.read_bytes(),key,Path(tmp)),max_bytes=POLICY['private_bytes_cap'])
  return strict_json(raw,max_elements=5000000),bytes_digest(raw)
def export():
 identity=admit(native=True,keyrole='custody');main=ROOT.parent;out=main/OUT
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 jobs=GetOnly().json('actions/runs/'+str(identity['run_id'])+'/jobs?per_page=100')['jobs'];capture=[j for j in jobs if j['name']=='capture'];need(len(capture)==1 and capture[0]['conclusion']=='success','FINANCING_ACTUAL_CAPTURE_JOB')
 receipt=json.loads((out/'producer.json').read_bytes());need(receipt['accepted'] and all(receipt[k]==v for k,v in identity.items()) and bytes_digest((out/'capture.mxmenc').read_bytes())==receipt['cipher_sha256'],'FINANCING_SOURCE_HANDOFF')
 p,h=decrypt(out/'capture.mxmenc');need(h==receipt['private_sha256'] and p['identity']==identity,'FINANCING_ORIGINAL_PRIVATE_SOURCE');rows=normalize(p)
 target=Path(os.environ['RUNNER_TEMP'])/'mxm-financing-carry';target.mkdir(mode=0o700,exist_ok=True)
 (target/'rows.json').write_bytes(encoded(rows));(target/'source.json').write_bytes(encoded({'identity':identity,'rows':len(rows['rows']),'input_sha256':bytes_digest(encoded(rows)),'capture_job':capture[0]['id'],'source_cipher_sha256':receipt['cipher_sha256'],'contact_start_utc':receipt['contact_start_utc'],'contact_end_utc':receipt['contact_end_utc']}))
 print('MXM_FINANCING_ORIGINAL_WIRE_AND_VIEW_AUTHENTICATED rows='+str(len(rows['rows'])),flush=True)
def evaluate():
 from .financing_carry_reference import reference,verdict
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
 from research_core_v4.successor_c_20261018.readback import FP
 need(not any(os.environ.get(k) for k in (*BROKER,'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY')),'FINANCING_KEYLESS_ECONOMICS')
 identity=admit();temp=Path(os.environ['RUNNER_TEMP'])/'mxm-financing-carry';source=json.loads((temp/'source.json').read_bytes());rows=json.loads((temp/'rows.json').read_bytes())
 need(source['identity']==identity and bytes_digest((temp/'rows.json').read_bytes())==source['input_sha256'],'FINANCING_EXACT_MODEL_INPUT')
 subprocess.run(['dotnet','run','--project',PROJECT,'-c','Release','--no-build','--',str(temp/'rows.json'),str(temp/'actual.json')],check=True,capture_output=True)
 actual=json.loads((temp/'actual.json').read_bytes());expected=reference(rows)
 need(all(actual[k]==v for k,v in expected.items()) and actual['input_sha256']==source['input_sha256'],'FINANCING_EVERY_DECISION_EPISODE_CENSOR_PARITY')
 result,gates=verdict(expected);out=ROOT/OUT;out.mkdir(exist_ok=True,parents=True)
 binary=ROOT/'research_core_v4/laboratory/csharp/financing_carry/bin/Release/net8.0/MxmFinancingCarry.dll';need(bytes_digest(binary.read_bytes())==actual['evaluator_sha256'],'FINANCING_ACTUAL_BINARY')
 private={'source':source,'actual_csharp':actual,'disposition':result,'gates':gates};raw=encoded(private)
 public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'FINANCING_RECIPIENT')
 encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=out/'result.mxmenc');(out/'evaluator.dll').write_bytes(binary.read_bytes())
 receipt={'schema':'mxm.financing-carry-development-public.v1',**source['identity'],'source_rows':len(rows['rows']),'capture_job':source['capture_job'],'source_cipher_sha256':source['source_cipher_sha256'],'contact_start_utc':source['contact_start_utc'],'contact_end_utc':source['contact_end_utc'],'disposition':result,'gates':gates,
 'model_trials':1,'new_hypotheses':1,'all_universe_financing_rows_independently_reconciled':True,'result_private_sha256':bytes_digest(raw),'result_cipher_sha256':bytes_digest((out/'result.mxmenc').read_bytes()),'evaluator_sha256':actual['evaluator_sha256'],
 'capital_replay':False,'net_edge_proven':False,'hard21_proven':False,'broker_fills_proven':False,'native_robot_operational_reception_proven':False,'costs_defaulted_to_zero':False,'orders':0,'new_broker_contacts_in_evaluation':0,'next_action':'STOP_FIXED_IDENTITY_NO_RETUNE_OR_AUTOMATIC_FOLLOWUP'}
 (out/'receipt.json').write_bytes(encoded(receipt)+b'\n');print('MXM_FINANCING_ECONOMIC '+encoded(receipt).decode(),flush=True)
def cold():
 admit(native=True,keyrole='custody')
 main=ROOT.parent;out=main/OUT;r=json.loads((out/'receipt.json').read_bytes());p,h=decrypt(out/'result.mxmenc')
 need(h==r['result_private_sha256'] and bytes_digest((out/'result.mxmenc').read_bytes())==r['result_cipher_sha256'] and p['source']['identity']['source_sha']==os.environ['GITHUB_SHA'] and p['disposition']==r['disposition'] and p['gates']==r['gates'] and bytes_digest((out/'evaluator.dll').read_bytes())==r['evaluator_sha256'],'FINANCING_SEPARATE_RESULT_READBACK')
 c={'schema':'mxm.financing-carry-cold.v1','source_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),'result_cipher_sha256':r['result_cipher_sha256'],'disposition':r['disposition'],'separate_custody_process_readback':True,'algorithm_reexecuted':False,'orders':0}
 (out/'cold.json').write_bytes(encoded(c)+b'\n');print('MXM_FINANCING_COLD '+encoded(c).decode(),flush=True)
if __name__=='__main__':
 os.umask(0o077)
 command=sys.argv[1:]
 if command==['admit']:admit()
 elif command==['install']:install()
 elif command==['capture']:collect()
 elif command==['export']:export()
 elif command==['evaluate']:evaluate()
 elif command==['cold']:cold()
 else:raise ValueError('FINANCING_EXACT_PHASE')
