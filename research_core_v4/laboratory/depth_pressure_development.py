"""One prospective VIEW depth-size study; existing transport, decoder and custody."""
import base64,gzip,json,os,subprocess,sys,tempfile,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .common import need,encoded,bytes_digest
from .spot_observation_reception import AUTH,BROKER,CHECKOUT,UPLOAD,DOWNLOAD,NATIVE,BOUNDARY_SHA,fingerprint,utc_millis
ROOT=Path(__file__).resolve().parents[2]
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
MODULE='research_core_v4.laboratory.depth_pressure_development';PATH='.github/workflows/mxm-depth-pressure-development.yml'
SPEC='research_programs/admissions/DEPTH_ANNOUNCEMENT_PRESSURE_20261027.json';PART='research_programs/partitions/DEPTH_ANNOUNCEMENT_PRESSURE_20261027.json'
PROJECT='research_core_v4/laboratory/csharp/depth_pressure/MxmDepthPressure.csproj';OUT='verification/depth-pressure'
FILES=['research_core_v4/laboratory/depth_pressure_development.py','research_core_v4/laboratory/spot_observation_reception.py','research_core_v4/laboratory/spot_observation_profile.py',SPEC,PART]
CAPS={'ProtoOATraderReq':1,'ProtoOAAssetListReq':1,'ProtoOASymbolsListReq':1,'ProtoOASymbolByIdReq':1,'ProtoOAExpectedMarginReq':1,
 'ProtoOASubscribeSpotsReq':1,'ProtoOASubscribeDepthQuotesReq':1,'ProtoOAUnsubscribeDepthQuotesReq':1,'ProtoOAUnsubscribeSpotsReq':1}
POLICY={'model_id':'MXM_DEPTH_ANNOUNCEMENT_PRESSURE_SPOTCRUDE_20261027_V1','symbol_id':250,'symbol':'SpotCrude',
 'capture_seconds':720,'contact_seconds':900,'events_cap':100000,'wire_bytes_cap':48000000,'private_bytes_cap':64000000,
 'frame_bytes_cap':500000,'feature_ms':1000,'feature_min_items':10,'depth_warmup_ms':5000,'first_depth_message_excluded':True,'dominance_ratio':3,'holdoff_ms':5000,
 'entry_delay_ms':250,'entry_deadline_ms':1000,'hold_ms':2000,'exit_deadline_ms':2500,'maximum_side_age_ms':5000,
 'complete_min':100,'censor_max_percent':5,'orders':0,'cloud':False,'broker_fills':False,'capital_replay':False,
 'native_attempts':1,'model_trials_max':1,'automatic_retry':False,'confirmation_eligible':False,
 'classification':'PROSPECTIVE_DEPENDENT_DEVELOPMENT_QUOTED_HEADROOM_COSTS_UNRESOLVED'}
def partition():return {'schema':'mxm.prospective-economic-source-partition.v1','model_id':POLICY['model_id'],'classification':'DEVELOPMENT',
 'contact_interval':'ENTIRE_ACTUAL_CONTACT_WINDOW_FROM_NATIVE_RECEIPT','confirmation_eligible':False,
 'exclude_intersecting_feature_response_windows_all_identities':True,'prior_diagnostic_or_protected_data_reclassified':False}
def spec(main):
 s=json.loads((main/SPEC).read_bytes());need(s['policy']==POLICY and json.loads((main/PART).read_bytes())==partition(),'PRESSURE_FROZEN_POLICY_PARTITION')
 for p,h in s['implementation_sha256'].items():need(bytes_digest((main/p).read_bytes())==h,'PRESSURE_EXACT_IMPLEMENTATION')
 return s
def workflow():
 jobs={}
 for role,env in [('capture','mxm-r3-pepperstone-v1'),('evaluate','mxm-r3-custody-v1')]:
  steps=[{'uses':CHECKOUT,'with':{'persist-credentials':False}},
   {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.pressure-native','persist-credentials':False}},
   {'name':'Admit one frozen finite model and partition before keys','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
   {'name':'Check independent artificial policy and exact native extension without keys','run':
    'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
    'dotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_depth_pressure -v\n'
    'python3 -m '+MODULE+' install'}]
  if role=='capture':
   steps.append({'name':'One bounded VIEW contact; no history or order capability','env':{**{'GH_TOKEN':'${{ github.token }}'},**{k:'${{ secrets.'+k+' }}' for k in BROKER}},'run':'umask 077\ncd .pressure-native\npython3 -m '+MODULE+' capture'})
  else:
   steps.append({'uses':DOWNLOAD,'with':{'name':'depth-pressure-source-${{ github.run_id }}','path':OUT}})
   steps.extend([
    {'name':'Authenticate every original wire event and export only in custody','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}','GH_TOKEN':'${{ github.token }}'},'run':'umask 077\ncd .pressure-native\npython3 -m '+MODULE+' export'},
    {'name':'Execute one actual CSharp model; reconcile independent array reference and encrypt','env':{'GH_TOKEN':'${{ github.token }}'},'run':'umask 077\npython3 -m '+MODULE+' evaluate'},
    {'name':'Read back original encrypted result in a separate custody process','env':{'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}','GH_TOKEN':'${{ github.token }}'},'run':'umask 077\ncd .pressure-native\npython3 -m '+MODULE+' cold'}])
  paths=OUT+'/capture.mxmenc\n'+OUT+'/producer.json' if role=='capture' else OUT+'/receipt.json\n'+OUT+'/result.mxmenc\n'+OUT+'/evaluator.dll\n'+OUT+'/cold.json'
  steps.append({'uses':UPLOAD,'if':'always()','with':{'name':('depth-pressure-source-' if role=='capture' else 'depth-pressure-result-')+'${{ github.run_id }}','path':paths,'if-no-files-found':'error','retention-days':90}})
  job={'runs-on':'ubuntu-24.04','timeout-minutes':20 if role=='capture' else 10,'environment':env,'permissions':{'contents':'read','actions':'read'},'steps':steps}
  if role=='capture':job['if']=f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1"
  else:job['needs']='capture'
  jobs[role]=job
 return {'name':'MXM one prospective depth-size economic headroom study','on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
  'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':jobs}
def admit(native=False,keyrole=None):
 main=ROOT.parent if native else ROOT
 need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
  os.environ.get('GITHUB_JOB') in ('capture','evaluate') and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'PRESSURE_NATIVE_CONTEXT')
 forbidden=['SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_REFRESH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM']
 if keyrole!='broker':forbidden+=list(BROKER)
 if keyrole!='custody':forbidden+=['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']
 need(not any(os.environ.get(k) for k in forbidden),'PRESSURE_KEY_ROLE')
 head=subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()
 need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0,'PRESSURE_EXACT_MAIN_HEAD')
 need(json.loads((main/PATH).read_bytes())==workflow() and bytes_digest((main/'V2_PROTECTED_FORWARD_START.json').read_bytes())==BOUNDARY_SHA,'PRESSURE_WORKFLOW_BOUNDARY')
 spec(main)
 if native:
  need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'PRESSURE_PINNED_DECODER')
  for p in FILES:need((ROOT/p).read_bytes()==(main/p).read_bytes(),'PRESSURE_EXACT_EXTENSION')
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'PRESSURE_OFFICIAL_HEAD')
 for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'PRESSURE_AUTHORITY')
 runs=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
 need(runs['total_count']==len(runs['workflow_runs'])==1 and runs['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and runs['workflow_runs'][0]['run_attempt']==1,'PRESSURE_ONE_ATTEMPT')
 return {'source_sha':head,'run_id':int(os.environ['GITHUB_RUN_ID']),'spec_sha256':bytes_digest((main/SPEC).read_bytes())}
def install():
 import shutil
 for p in FILES:
  dest=ROOT/'.pressure-native'/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,dest)
def normalize(p):
 from m6.ctrader_transport import decode_envelope,extract_payload
 from m6.ctrader_proto import OpenApiModelMessages_pb2 as e
 from research_core_v4.shallow_m5_support_v2_production import ACCOUNT_FINGERPRINT_SHA256
 need(p['complete'] and p['policy']==POLICY and p['partition']==partition() and fingerprint(p['account'])==ACCOUNT_FINGERPRINT_SHA256,'PRESSURE_COMPLETE_SOURCE_IDENTITY')
 expected=list(AUTH)+['ProtoOATraderReq','ProtoOAAssetListReq','ProtoOASymbolsListReq','ProtoOASymbolByIdReq','ProtoOAExpectedMarginReq','ProtoOASubscribeSpotsReq','ProtoOASubscribeDepthQuotesReq']
 if p['cleanup']=='ACKNOWLEDGED':expected+=['ProtoOAUnsubscribeDepthQuotesReq','ProtoOAUnsubscribeSpotsReq']
 else:need(p['cleanup']=='CLOSED_AT_DEADLINE','PRESSURE_EXPLICIT_TAIL')
 need([r['name'] for r in p['receipts']]==expected,'PRESSURE_REQUEST_SEQUENCE')
 responses=[];seen=set()
 for r in p['receipts']:
  env=decode_envelope(base64.b64decode(r['response'],validate=True));res=extract_payload(env);responses.append(res)
  need(env.IsInitialized() and res.IsInitialized() and env.clientMsgId==r['cid'] and r['cid'] not in seen and type(res).__name__==r['name'][:-3]+'Res','PRESSURE_RESPONSE_CORRELATION');seen.add(r['cid'])
  if hasattr(res,'ctidTraderAccountId'):need(res.ctidTraderAccountId==p['account'],'PRESSURE_RESPONSE_ACCOUNT')
  if r['name'] not in AUTH:
   reqenv=decode_envelope(base64.b64decode(r['request'],validate=True));req=extract_payload(reqenv)
   need(reqenv.IsInitialized() and req.IsInitialized() and reqenv.clientMsgId==r['cid'] and type(req).__name__==r['name'] and req.ctidTraderAccountId==p['account'],'PRESSURE_REQUEST_WIRE')
   if hasattr(req,'symbolId'):
    need((list(req.symbolId)==[250]) if r['name']!='ProtoOAExpectedMarginReq' else req.symbolId==250 and list(req.volume)==[responses[6].symbol[0].minVolume],'PRESSURE_SYMBOL_VOLUME')
   if r['name']=='ProtoOASubscribeSpotsReq':need(req.subscribeToSpotTimestamp,'PRESSURE_SERVER_CLOCK_REQUESTED')
 accounts=responses[1];matches=[a for a in accounts.ctidTraderAccount if a.ctidTraderAccountId==p['account']]
 need(accounts.HasField('permissionScope') and accounts.permissionScope==e.SCOPE_VIEW and len(matches)==1 and matches[0].isLive,'PRESSURE_VIEW_SCOPE')
 assets={a.assetId:a.name for a in responses[4].asset};trader=responses[3].trader
 need('pepperstone' in trader.brokerName.casefold() and assets.get(trader.depositAssetId)=='EUR','PRESSURE_PEPPERSTONE_EUR')
 lights={s.symbolId:s for s in responses[5].symbol};full=responses[6].symbol
 need(250 in lights and lights[250].symbolName=='SpotCrude' and lights[250].enabled and len(full)==1 and full[0].symbolId==250 and full[0].minVolume>0,'PRESSURE_NATIVE_SYMBOL')
 need(len(responses[7].margin)==1 and responses[7].margin[0].volume==full[0].minVolume,'PRESSURE_MARGIN_RESPONSE_VOLUME')
 need(p['epochs']==1 and 719000<=p['end_ms']-p['start_ms']<=POLICY['contact_seconds']*1000 and p['wire_bytes']<=POLICY['wire_bytes_cap'] and len(p['market'])<=POLICY['events_cap'],'PRESSURE_SOURCE_DURATION_BOUNDS')
 rows=[];lastseq=-1;lastt=-1
 for raw in p['market']:
  wire=base64.b64decode(raw['wire'],validate=True);need(bytes_digest(wire)==raw['sha256'],'PRESSURE_EVENT_WIRE_HASH');env=decode_envelope(wire);msg=extract_payload(env)
  need(utc_millis(p['contact_start_utc'])<=utc_millis(raw['receive_utc'])<=utc_millis(p['contact_end_utc']),'PRESSURE_EVENT_UTC_WINDOW')
  t=(raw['receive_monotonic_ns']-p['origin_ns'])//1000000;utc=utc_millis(raw['receive_utc']);seq=raw['sequence']
  need(env.IsInitialized() and msg.IsInitialized() and msg.ctidTraderAccountId==p['account'] and msg.symbolId==250 and t>=lastt and seq>lastseq and 0<=t<=p['end_ms'],'PRESSURE_EVENT_IDENTITY_CLOCK');lastseq=seq;lastt=t
  row=dict(t=t,utc=utc,seq=seq)
  if type(msg).__name__=='ProtoOASpotEvent':row.update(kind='spot',bid=int(msg.bid) if msg.HasField('bid') else None,ask=int(msg.ask) if msg.HasField('ask') else None,server=int(msg.timestamp) if msg.HasField('timestamp') else None)
  else:
   need(type(msg).__name__=='ProtoOADepthEvent','PRESSURE_EVENT_TYPE');quotes=[]
   for q in msg.newQuotes:
    side=1 if q.HasField('bid') and not q.HasField('ask') else -1 if q.HasField('ask') and not q.HasField('bid') else 0
    quotes.append(dict(id=int(q.id),side=side,price=int(q.bid if side==1 else q.ask),size=int(q.size)))
   row.update(kind='depth',quotes=quotes,deleted=[int(v) for v in msg.deletedQuotes])
  rows.append(row)
 return rows
def outbound_guard(name,active):
 need(name in (*AUTH,*CAPS,'ProtoHeartbeatEvent'),'PRESSURE_OUTBOUND_ALLOWLIST')
 if name!='ProtoHeartbeatEvent':need(active is not None and active['name']==name and 'cid' not in active,'PRESSURE_NO_DIRECT_OR_SECOND_SEND')
def collect():
 identity=admit(native=True,keyrole='broker')
 from collections import Counter
 from m6.ctrader_transport import decode_envelope,extract_payload
 from m6.ctrader_proto import OpenApiMessages_pb2 as m
 from research_core_v4.dom_information_20261014_v1.live_adapter_v1 import InformationTransport
 from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,ACCOUNT_FINGERPRINT_SHA256,encrypt_shard,public_spki_sha256
 from research_core_v4.successor_c_20261018.readback import FP
 main=ROOT.parent;out=main/OUT;out.mkdir(parents=True,exist_ok=True)
 p=dict(identity=identity,policy=POLICY,partition=partition(),complete=False,account=None,receipts=[],market=[],origin_ns=time.monotonic_ns(),contact_start_utc=datetime.now(timezone.utc).isoformat())
 counter=Counter();wire_bytes=0;canonical=0
 def handle(msg,stamp,env):
  nonlocal canonical
  raw=env.SerializeToString();row={**stamp,'wire':base64.b64encode(raw).decode(),'sha256':bytes_digest(raw)}
  canonical+=len(encoded(row));need(len(p['market'])<POLICY['events_cap'] and canonical<24000000,'PRESSURE_MARKET_CAP');p['market'].append(row)
 class Wire(InformationTransport):
  active=None
  def _send_bytes(self,frame):
   nonlocal wire_bytes
   env=decode_envelope(frame[4:]);name=type(extract_payload(env)).__name__
   outbound_guard(name,self.active)
   if name!='ProtoHeartbeatEvent':
    self.active['cid']=env.clientMsgId
    if name not in AUTH:self.active['request']=base64.b64encode(env.SerializeToString()).decode()
   wire_bytes+=len(frame);need(wire_bytes<=POLICY['wire_bytes_cap'],'PRESSURE_WIRE_CAP');return super()._send_bytes(frame)
  def _recv_exact(self,count,*,deadline):
   nonlocal wire_bytes
   need(0<count<=POLICY['frame_bytes_cap'] and wire_bytes+count<=POLICY['wire_bytes_cap'],'PRESSURE_FRAME_CAP')
   try:data=super()._recv_exact(count,deadline=deadline)
   except Exception:wire_bytes+=self.partial_frame_received;raise
   wire_bytes+=len(data);return data
  def receive_envelope(self,*,deadline):
   env=super().receive_envelope(deadline=deadline)
   need(self.receipt_sequence<=200000,'PRESSURE_ENVELOPE_CAP')
   if self.active is not None and env.clientMsgId==self.active.get('cid'):
    need('response' not in self.active,'PRESSURE_DUPLICATE_RESPONSE');self.active['response']=base64.b64encode(env.SerializeToString()).decode()
   return env
  def request(self,request,**kw):
   name=type(request).__name__
   need(name in (*AUTH,*CAPS) and counter[name]<(1 if name in AUTH else CAPS[name]),'PRESSURE_REQUEST_CAP')
   if name in AUTH:need(name==AUTH[len(p['receipts'])],'PRESSURE_AUTH_SEQUENCE')
   counter[name]+=1;row={'name':name};p['receipts'].append(row);self.active=row
   try:
    res=super().request(request,**kw);need(type(res).__name__==name[:-3]+'Res' and 'response' in row,'PRESSURE_REQUEST_RESPONSE');return res
   finally:self.active=None
 now=datetime.now(timezone.utc)
 tr=Wire(start_utc=now,end_utc=now+timedelta(seconds=POLICY['contact_seconds']),account_fingerprint=ACCOUNT_FINGERPRINT_SHA256,event_handler=handle,maximum_connection_seconds=POLICY['contact_seconds'],connect_timeout=15,response_timeout=20)
 try:
  need(all(os.environ.get(k) for k in BROKER),'PRESSURE_EXISTING_CREDENTIALS');values=[os.environ.pop(k) for k in BROKER]
  tr.connect();account=authenticate_segment(tr,*values);values=None;p['account']=account
  trader=tr.request(m.ProtoOATraderReq(ctidTraderAccountId=account)).trader
  assets={a.assetId:a.name for a in tr.request(m.ProtoOAAssetListReq(ctidTraderAccountId=account)).asset}
  need('pepperstone' in trader.brokerName.casefold() and assets.get(trader.depositAssetId)=='EUR','PRESSURE_NATIVE_ACCOUNT')
  lights={s.symbolId:s for s in tr.request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False)).symbol}
  need(250 in lights and lights[250].symbolName=='SpotCrude' and lights[250].enabled,'PRESSURE_CURRENT_IDENTITY');tr.selected={250}
  full=tr.request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[250])).symbol
  need(len(full)==1 and full[0].symbolId==250 and full[0].HasField('minVolume') and full[0].minVolume>0,'PRESSURE_CURRENT_TERMS')
  tr.request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=250,volume=[full[0].minVolume]))
  tr.request(m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=account,symbolId=[250],subscribeToSpotTimestamp=True))
  tr.request(m.ProtoOASubscribeDepthQuotesReq(ctidTraderAccountId=account,symbolId=[250]))
  p['start_ms']=(time.monotonic_ns()-p['origin_ns'])//1000000
  deadline=tr._clock()+POLICY['capture_seconds'];need(deadline<tr.contact_deadline-20,'PRESSURE_CAPTURE_BUDGET')
  print('MXM_DEPTH_PRESSURE_ONE_FROZEN_MODEL_SOURCE_ACTIVE_NO_ORDERS',flush=True)
  tail=tr.stream_until(deadline);need(tail in ('CAPTURE_DEADLINE','CAPTURE_DEADLINE_TIMEOUT_CONNECTION_CLOSED'),'PRESSURE_TAIL')
  if tr.connected:
   tr.market_capture_enabled=False;tr.cleanup=True;tr.cleanup_end=tr._clock()+15
   tr.request(m.ProtoOAUnsubscribeDepthQuotesReq(ctidTraderAccountId=account,symbolId=[250]))
   tr.request(m.ProtoOAUnsubscribeSpotsReq(ctidTraderAccountId=account,symbolId=[250]));p['cleanup']='ACKNOWLEDGED'
  else:p['cleanup']='CLOSED_AT_DEADLINE'
  p['complete']=True
 except Exception as ex:p['failure_class']=type(ex).__name__
 finally:
  tr.close();p['end_ms']=(time.monotonic_ns()-p['origin_ns'])//1000000;p['contact_end_utc']=datetime.now(timezone.utc).isoformat();p['wire_bytes']=wire_bytes;p['epochs']=tr.connection_epochs
  for k in BROKER:os.environ.pop(k,None)
  raw=encoded(p);need(len(raw)<POLICY['private_bytes_cap'],'PRESSURE_PRIVATE_CAP');public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'PRESSURE_EXISTING_RECIPIENT')
  encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=out/'capture.mxmenc')
  receipt={**identity,'accepted':p['complete'],'cipher_sha256':bytes_digest((out/'capture.mxmenc').read_bytes()),'private_sha256':bytes_digest(raw),'events':len(p['market']),'new_connections':p['epochs'],'orders':0,'new_economic_outcomes':0,'failure_class':p.get('failure_class'),'contact_start_utc':p['contact_start_utc'],'contact_end_utc':p['contact_end_utc']}
  (out/'producer.json').write_bytes(encoded(receipt)+b'\n');print('MXM_PRESSURE_SOURCE '+encoded(receipt).decode(),flush=True)
 need(p['complete'],'PRESSURE_CAPTURE_INCOMPLETE_NO_RETRY')
def decrypt(path):
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.successor_c_20261018.readback import FP
 from research_core_v4.remediation_p0_p4_20261015 import owner
 from research_core_v4.remediation_p0_p4_20261015.safety import unpack,strict_json
 with tempfile.TemporaryDirectory() as tmp:
  key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'PRESSURE_EXISTING_CUSTODY')
  raw=unpack(owner.bounded_decrypt(path.read_bytes(),key,Path(tmp)),max_bytes=POLICY['private_bytes_cap'])
  return strict_json(raw,max_elements=5000000),bytes_digest(raw)
def export():
 identity=admit(native=True,keyrole='custody');main=ROOT.parent;out=main/OUT
 from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
 jobs=GetOnly().json('actions/runs/'+str(identity['run_id'])+'/jobs?per_page=100')['jobs'];capture=[j for j in jobs if j['name']=='capture'];need(len(capture)==1 and capture[0]['conclusion']=='success','PRESSURE_ACTUAL_CAPTURE_JOB')
 receipt=json.loads((out/'producer.json').read_bytes());need(receipt['accepted'] and all(receipt[k]==v for k,v in identity.items()) and bytes_digest((out/'capture.mxmenc').read_bytes())==receipt['cipher_sha256'],'PRESSURE_SOURCE_HANDOFF')
 p,h=decrypt(out/'capture.mxmenc');need(h==receipt['private_sha256'] and p['identity']==identity,'PRESSURE_ORIGINAL_PRIVATE_SOURCE');rows=normalize(p)
 target=Path(os.environ['RUNNER_TEMP'])/'mxm-depth-pressure';target.mkdir(mode=0o700,exist_ok=True)
 (target/'rows.json').write_bytes(encoded(rows));(target/'source.json').write_bytes(encoded({'identity':identity,'rows':len(rows),'input_sha256':bytes_digest(encoded(rows)),'capture_job':capture[0]['id'],'source_cipher_sha256':receipt['cipher_sha256']}))
 print('MXM_PRESSURE_ORIGINAL_WIRE_AND_VIEW_AUTHENTICATED rows='+str(len(rows)),flush=True)
def evaluate():
 from .depth_pressure_reference import reference,verdict
 from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
 from research_core_v4.successor_c_20261018.readback import FP
 need(not any(os.environ.get(k) for k in (*BROKER,'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY')),'PRESSURE_KEYLESS_ECONOMICS')
 identity=admit();temp=Path(os.environ['RUNNER_TEMP'])/'mxm-depth-pressure';source=json.loads((temp/'source.json').read_bytes());rows=json.loads((temp/'rows.json').read_bytes())
 need(source['identity']==identity and bytes_digest((temp/'rows.json').read_bytes())==source['input_sha256'],'PRESSURE_EXACT_MODEL_INPUT')
 subprocess.run(['dotnet','run','--project',PROJECT,'-c','Release','--no-build','--',str(temp/'rows.json'),str(temp/'actual.json')],check=True,capture_output=True)
 actual=json.loads((temp/'actual.json').read_bytes());expected=reference(rows)
 need(all(actual[k]==v for k,v in expected.items()) and actual['input_sha256']==source['input_sha256'],'PRESSURE_EVERY_DECISION_EPISODE_CENSOR_PARITY')
 result,gates=verdict(expected);out=ROOT/OUT;out.mkdir(exist_ok=True,parents=True)
 binary=ROOT/'research_core_v4/laboratory/csharp/depth_pressure/bin/Release/net8.0/MxmDepthPressure.dll';need(bytes_digest(binary.read_bytes())==actual['evaluator_sha256'],'PRESSURE_ACTUAL_BINARY')
 private={'source':source,'actual_csharp':actual,'disposition':result,'gates':gates};raw=encoded(private)
 public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'PRESSURE_RECIPIENT')
 encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=out/'result.mxmenc');(out/'evaluator.dll').write_bytes(binary.read_bytes())
 receipt={'schema':'mxm.depth-pressure-development-public.v1',**source['identity'],'source_rows':len(rows),'capture_job':source['capture_job'],'disposition':result,'gates':gates,
 'model_trials':1,'new_hypotheses':1,'all_decisions_episodes_censors_independently_reconciled':True,'result_private_sha256':bytes_digest(raw),'result_cipher_sha256':bytes_digest((out/'result.mxmenc').read_bytes()),'evaluator_sha256':actual['evaluator_sha256'],
 'capital_replay':False,'net_edge_proven':False,'hard21_proven':False,'broker_fills_proven':False,'native_robot_operational_reception_proven':False,'costs_defaulted_to_zero':False,'orders':0,'new_broker_contacts_in_evaluation':0,'next_action':'STOP_FIXED_IDENTITY_NO_RETUNE_OR_AUTOMATIC_FOLLOWUP'}
 (out/'receipt.json').write_bytes(encoded(receipt)+b'\n');print('MXM_PRESSURE_ECONOMIC '+encoded(receipt).decode(),flush=True)
def cold():
 admit(native=True,keyrole='custody')
 main=ROOT.parent;out=main/OUT;r=json.loads((out/'receipt.json').read_bytes());p,h=decrypt(out/'result.mxmenc')
 need(h==r['result_private_sha256'] and bytes_digest((out/'result.mxmenc').read_bytes())==r['result_cipher_sha256'] and p['source']['identity']['source_sha']==os.environ['GITHUB_SHA'] and p['disposition']==r['disposition'] and p['gates']==r['gates'] and bytes_digest((out/'evaluator.dll').read_bytes())==r['evaluator_sha256'],'PRESSURE_SEPARATE_RESULT_READBACK')
 c={'schema':'mxm.depth-pressure-cold.v1','source_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),'result_cipher_sha256':r['result_cipher_sha256'],'disposition':r['disposition'],'separate_custody_process_readback':True,'algorithm_reexecuted':False,'orders':0}
 (out/'cold.json').write_bytes(encoded(c)+b'\n');print('MXM_PRESSURE_COLD '+encoded(c).decode(),flush=True)
if __name__=='__main__':
 os.umask(0o077)
 command=sys.argv[1:]
 if command==['admit']:admit()
 elif command==['install']:install()
 elif command==['capture']:collect()
 elif command==['export']:export()
 elif command==['evaluate']:evaluate()
 elif command==['cold']:cold()
 else:raise ValueError('PRESSURE_EXACT_PHASE')
