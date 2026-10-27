"""One bounded VIEW-only receipt-clock source pilot. No history/model/order/writer."""
import base64,gzip,hashlib,json,os,subprocess,sys,tempfile,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .common import need,encoded,bytes_digest
from .spot_observation_profile import SpotProfile
ROOT=Path(__file__).resolve().parents[2]
REPO='mariancradulescu/mxm-quant-greenfield';BRANCH='mxm-remediation-p0-p4-20261015-v1'
NATIVE='d2fae5641b759b1c8c24161d83d62d39e104eafd'
PATH='.github/workflows/mxm-spot-observation-reception.yml'
MODULE='research_core_v4.laboratory.spot_observation_reception'
FILES=('spot_observation_reception.py','spot_observation_profile.py')
OUT='verification/spot-observation'
AUTH=('ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq')
CAPS={'ProtoOATraderReq':1,'ProtoOAAssetListReq':1,'ProtoOASymbolsListReq':1,
 'ProtoOASymbolByIdReq':1,'ProtoOAExpectedMarginReq':3,'ProtoOASubscribeSpotsReq':1,'ProtoOAUnsubscribeSpotsReq':1}
ALLOWED=frozenset((*AUTH,*CAPS,'ProtoHeartbeatEvent'))
BROKER=('R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_ACCESS_TOKEN')
POLICY={'schema':'mxm.spot-observation-source-policy.v1','symbols':{'1':'EURUSD','2':'GBPUSD','250':'SpotCrude'},
 'capture_seconds_after_subscription':360,'maximum_contact_seconds':480,'max_market_events':100000,
 'max_wire_bytes':16_000_000,'max_private_bytes':24_000_000,'max_received_envelopes':200000,
 'max_metadata_response_bytes':500000,'max_market_canonical_bytes':12000000,
 'max_side_age_ms':5000,'minimum_observed_span_ms':300000,
 'initial_snapshot_is_fresh_quote_proof':False,'new_response_testing_allowed':False,
 'classification':'DEVELOPMENT_SOURCE_QUALITY_ONLY','confirmation_eligible':False,
 'exclusion':'ALL_IDENTITIES_INTERSECTING_ACTUAL_CONTACT_INTERVAL_EXCLUDED_FROM_CONFIRMATION',
 'reconnections':0,'automatic_retry':False,'history_requests':0,'strategy_trials':0,'orders':0}
POLICY_SHA=bytes_digest(encoded(POLICY))
BOUNDARY_SHA='605829d363c92ff74b0d5027442dd581f2944fb56336d8b6c9b8a3c74a875c1e'
PARTITION='research_programs/partitions/NATIVE_SPOT_OBSERVATION_20261027.json'
CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'
UPLOAD='actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
DOWNLOAD='actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093'

def partition():
    return {'schema':'mxm.prospective-source-quality-partition.v1','policy_sha256':POLICY_SHA,'workflow':PATH,
      'classification':POLICY['classification'],'confirmation_eligible':False,'response_testing_allowed':False,
      'interval_rule':'ENTIRE_ACTUAL_CONTACT_INTERVAL_RECORDED_BY_NATIVE_COLD_RECEIPT',
      'exclusion_scope':'ALL_IDENTITIES_WITH_INTERSECTING_FEATURE_OR_RESPONSE_WINDOWS',
      'prior_evidence_reclassified':False,'new_strategy_trial':False,'raw_event_times_or_prices_public':False}

def workflow():
    jobs={}
    for role,env in [('spot-collect','mxm-r3-pepperstone-v1'),('spot-cold','mxm-r3-custody-v1')]:
        steps=[{'uses':CHECKOUT,'with':{'persist-credentials':False}},
          {'uses':CHECKOUT,'with':{'ref':NATIVE,'path':'.spot-native','persist-credentials':False}},
          {'name':'Admit exact finite source scope before any secret access','env':{'GH_TOKEN':'${{ github.token }}'},'run':'python3 -m '+MODULE+' admit'},
          {'name':'Verify source-only contract and install exact extension into existing decoder','run':
           'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\n'
           'python3 -m unittest research_core_v4.laboratory.test_spot_observation_profile research_core_v4.laboratory.test_spot_observation_reception -v\n'
           'cp '+' '.join('research_core_v4/laboratory/'+f for f in FILES)+' .spot-native/research_core_v4/laboratory/'}]
        if role=='spot-cold':steps.append({'uses':DOWNLOAD,'with':{'name':'spot-observation-producer-${{ github.run_id }}','path':OUT}})
        secrets={'GH_TOKEN':'${{ github.token }}'}
        if role=='spot-collect':secrets.update({k:'${{ secrets.'+k+' }}' for k in BROKER})
        else:secrets['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']='${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'
        steps.append({'name':'Finite VIEW source collection' if role=='spot-collect' else 'Independent native ciphertext and wire readback',
          'env':secrets,'run':'umask 077\ncd .spot-native\npython3 -m '+MODULE+' '+role})
        paths=OUT+'/capture.mxmenc\n'+OUT+'/producer.json' if role=='spot-collect' else OUT+'/cold.json'
        steps.append({'uses':UPLOAD,'if':'always()','with':{'name':('spot-observation-producer-' if role=='spot-collect' else 'spot-observation-cold-')+'${{ github.run_id }}',
          'path':paths,'if-no-files-found':'error','retention-days':90}})
        job={'runs-on':'ubuntu-24.04','timeout-minutes':12 if role=='spot-collect' else 8,'environment':env,
          'permissions':{'contents':'read','actions':'read'},'steps':steps}
        if role=='spot-cold':job.update(needs='spot-collect',**{'if':'always()'})
        else:job['if']=f"github.repository == '{REPO}' && github.ref == 'refs/heads/{BRANCH}' && github.run_attempt == 1"
        jobs[role]=job
    return {'name':'MXM finite native spot receipt-clock source pilot',
      'on':{'push':{'branches':[BRANCH],'paths':[PATH]}},'permissions':{},
      'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},'jobs':jobs}

def admission(main,native=False):
    main=Path(main);job=os.environ.get('GITHUB_JOB')
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      job in ('spot-collect','spot-cold') and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'SPOT_NATIVE_CONTEXT')
    forbidden=['SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_REFRESH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM']
    forbidden+=list(BROKER) if not native or job=='spot-cold' else []
    if not native or job=='spot-collect':forbidden+=['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']
    need(not any(os.environ.get(k) for k in forbidden),'SPOT_SECRET_ROLE_SEPARATION')
    head=subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()
    need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0 and
      json.loads((main/PATH).read_bytes())==workflow(),'SPOT_EXACT_MAIN_SOURCE_AND_WORKFLOW')
    need(bytes_digest((main/'V2_PROTECTED_FORWARD_START.json').read_bytes())==BOUNDARY_SHA,
      'SPOT_PROTECTED_BOUNDARY_UNCHANGED')
    need(json.loads((main/PARTITION).read_bytes())==partition(),'SPOT_PROSPECTIVE_PARTITION')
    if native:
        need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and
          subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'SPOT_FIXED_NATIVE_SOURCE')
        for f in FILES:need((ROOT/'research_core_v4/laboratory'/f).read_bytes()==(main/'research_core_v4/laboratory'/f).read_bytes(),'SPOT_EXACT_EXTENSION')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'SPOT_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'SPOT_AUTHORITY_UNCHANGED')
    runs=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
    need(runs['total_count']==len(runs['workflow_runs'])==1 and runs['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and
      runs['workflow_runs'][0]['run_attempt']==1,'SPOT_SINGLE_ATTEMPT')
    return {'run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':head,'native_source':NATIVE,'policy_sha256':POLICY_SHA,
      'partition_sha256':bytes_digest(encoded(partition())),'attempt':1}

def fingerprint(account):return hashlib.sha256(('ctrader-account:'+str(account)).encode('ascii')).hexdigest()

def outbound_guard(name,active):
    need(name in ALLOWED,'SPOT_NARROW_FRAME_ALLOWLIST')
    if name!='ProtoHeartbeatEvent':
        need(active is not None and active.get('request_type')==name and 'client_msg_id' not in active,
          'SPOT_NO_UNTRACKED_OR_REPEATED_BUSINESS_FRAME')

def utc_millis(text):
    stamp=datetime.fromisoformat(text)
    need(stamp.tzinfo is not None,'SPOT_RECEIPT_UTC_REQUIRED')
    elapsed=stamp.astimezone(timezone.utc)-datetime(1970,1,1,tzinfo=timezone.utc)
    return elapsed.days*86400000+elapsed.seconds*1000+elapsed.microseconds//1000

def market_event(row,account):
    from m6.ctrader_transport import decode_envelope,extract_payload
    raw=base64.b64decode(row['wire'],validate=True)
    need(bytes_digest(raw)==row['sha256'],'SPOT_NATIVE_MARKET_WIRE_HASH')
    env=decode_envelope(raw);msg=extract_payload(env)
    need(env.IsInitialized() and type(msg).__name__=='ProtoOASpotEvent' and msg.IsInitialized() and
      int(msg.ctidTraderAccountId)==account and str(msg.symbolId) in POLICY['symbols'],'SPOT_NATIVE_EVENT_ACCOUNT_SYMBOL')
    return dict(symbol=int(msg.symbolId),sequence=row['sequence'],arrival_ns=row['receive_monotonic_ns'],
      received_ms=utc_millis(row['receive_utc']),
      server_ms=int(msg.timestamp) if msg.HasField('timestamp') else None,
      bid=int(msg.bid) if msg.HasField('bid') else None,ask=int(msg.ask) if msg.HasField('ask') else None)

def verify_private(p):
    from m6.ctrader_transport import decode_envelope,extract_payload
    from m6.ctrader_proto import OpenApiModelMessages_pb2 as enums
    from research_core_v4.shallow_m5_support_v2_production import ACCOUNT_FINGERPRINT_SHA256
    need(p['policy']==POLICY and p['identity']['policy_sha256']==POLICY_SHA and p['identity']['native_source']==NATIVE and
      p['identity']['partition_sha256']==bytes_digest(encoded(partition())),'SPOT_PRIVATE_POLICY')
    if not p['complete']:return None
    account=p['account'];need(fingerprint(account)==ACCOUNT_FINGERPRINT_SHA256,'SPOT_ACCOUNT_FINGERPRINT')
    expected=list(AUTH)+['ProtoOATraderReq','ProtoOAAssetListReq','ProtoOASymbolsListReq','ProtoOASymbolByIdReq']+['ProtoOAExpectedMarginReq']*3+['ProtoOASubscribeSpotsReq','ProtoOAUnsubscribeSpotsReq']
    if p['cleanup_state']=='CONNECTION_CLOSED_AT_DEADLINE_UNSUBSCRIBE_NOT_ACKNOWLEDGED':
        need(p['stream_end']=='CAPTURE_DEADLINE_TIMEOUT_CONNECTION_CLOSED','SPOT_CLOSED_DEADLINE_PROVENANCE')
        expected=expected[:-1]
    else:need(p['cleanup_state']=='UNSUBSCRIBE_ACKNOWLEDGED','SPOT_CLEANUP_STATE')
    need([r['request_type'] for r in p['receipts']]==expected,'SPOT_EXACT_NATIVE_REQUEST_SEQUENCE')
    responses=[];ids=set();margin_ids=set()
    for r in p['receipts']:
        need(r.get('client_msg_id') not in ids,'SPOT_UNIQUE_CORRELATION');ids.add(r.get('client_msg_id'))
        env=decode_envelope(base64.b64decode(r['response_wire'],validate=True))
        res=extract_payload(env);name=r['request_type'];responses.append(res)
        need(env.IsInitialized() and res.IsInitialized() and env.clientMsgId==r['client_msg_id'] and
          type(res).__name__==name[:-3]+'Res','SPOT_NATIVE_RESPONSE_CORRELATION')
        if hasattr(res,'ctidTraderAccountId'):need(int(res.ctidTraderAccountId)==account,'SPOT_NATIVE_RESPONSE_ACCOUNT')
        if name not in AUTH:
            reqenv=decode_envelope(base64.b64decode(r['request_wire'],validate=True));req=extract_payload(reqenv)
            need(reqenv.IsInitialized() and req.IsInitialized() and reqenv.clientMsgId==env.clientMsgId and
              type(req).__name__==name and int(req.ctidTraderAccountId)==account,'SPOT_NATIVE_REQUEST_ACCOUNT')
            if name in ('ProtoOASymbolByIdReq','ProtoOASubscribeSpotsReq','ProtoOAUnsubscribeSpotsReq'):
                need(list(req.symbolId)==[1,2,250],'SPOT_EXACT_REQUEST_PANEL')
            if name=='ProtoOASubscribeSpotsReq':need(req.HasField('subscribeToSpotTimestamp') and req.subscribeToSpotTimestamp,'SPOT_TIMESTAMP_REQUEST')
            if name=='ProtoOAExpectedMarginReq':
                need(req.symbolId not in margin_ids,'SPOT_MARGIN_UNIQUE_SYMBOL');margin_ids.add(req.symbolId)
                full={int(s.symbolId):s for s in responses[6].symbol}
                need(req.symbolId in full and list(req.volume)==[int(full[req.symbolId].minVolume)],'SPOT_MARGIN_NATIVE_MINIMUM_VOLUME')
    accounts=responses[1];matches=[a for a in accounts.ctidTraderAccount if int(a.ctidTraderAccountId)==account]
    need(accounts.HasField('permissionScope') and accounts.permissionScope==enums.SCOPE_VIEW and len(matches)==1 and
      matches[0].HasField('isLive') and matches[0].isLive,'SPOT_INDEPENDENT_NATIVE_VIEW_AUTH')
    assets={int(a.assetId):a.name for a in responses[4].asset};trader=responses[3].trader
    need('pepperstone' in trader.brokerName.casefold() and assets.get(int(trader.depositAssetId))=='EUR','SPOT_NATIVE_PEPPERSTONE_EUR')
    lights={int(s.symbolId):s for s in responses[5].symbol};fulls={int(s.symbolId):s for s in responses[6].symbol}
    need(set(fulls)=={1,2,250} and margin_ids=={1,2,250},'SPOT_FULL_PANEL_METADATA')
    for key,name in POLICY['symbols'].items():
        sid=int(key);need(sid in lights and lights[sid].symbolName==name and lights[sid].enabled and
          fulls[sid].HasField('minVolume') and fulls[sid].minVolume>0,'SPOT_EXACT_ENABLED_PANEL')
    start=datetime.fromisoformat(p['contact_start_utc']);end=datetime.fromisoformat(p['contact_end_utc'])
    need(start.tzinfo is not None and end.tzinfo is not None and start<=end and
      0<=p['contact_end_ns']-p['contact_start_ns']<=POLICY['maximum_contact_seconds']*1_000_000_000+20_000_000_000,
      'SPOT_FINITE_CONTACT_CLOCK')
    need(p['contact_start_ns']<=p['subscription_start_ns']<=p['stream_end_ns']<=p['contact_end_ns'] and
      (POLICY['capture_seconds_after_subscription']-1)*1_000_000_000<=p['stream_end_ns']-p['subscription_start_ns'] and
      p['connection_epochs']==1 and p['wire_bytes']<=POLICY['max_wire_bytes'] and
      p['received_envelopes']<=POLICY['max_received_envelopes'],'SPOT_NATIVE_DURATION_AND_RESOURCE_READBACK')
    need(len(p['market'])<=POLICY['max_market_events'],'SPOT_EVENT_CAP')
    profiler=SpotProfile([1,2,250])
    for row in p['market']:
        stamp=datetime.fromisoformat(row['receive_utc'])
        need(start<=stamp<=end and p['contact_start_ns']<=row['receive_monotonic_ns']<=p['contact_end_ns'],'SPOT_RECEIPT_WINDOW')
        profiler.observe(**market_event(row,account))
    result=profiler.result();need(result==p['producer_profile'],'SPOT_COLD_ALL_EVENTS_PROFILE_PARITY')
    return result

def collect(identity):
    from collections import Counter
    from m6.ctrader_transport import decode_envelope,extract_payload
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    from research_core_v4.dom_information_20261014_v1.live_adapter_v1 import InformationTransport
    from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,ACCOUNT_FINGERPRINT_SHA256,encrypt_shard,public_spki_sha256
    from research_core_v4.successor_c_20261018.readback import FP
    p={'schema':'mxm.native-spot-observation-private.v1','identity':identity,'policy':POLICY,'complete':False,
      'receipts':[],'market':[],'failure_class':None,'account':None}
    start=datetime.now(timezone.utc);end=start+timedelta(seconds=POLICY['maximum_contact_seconds'])
    profiler=SpotProfile([1,2,250]);wire_bytes=0;received_count=0;market_canonical_bytes=0;counts=Counter()
    def handle(msg,stamp,env):
        nonlocal market_canonical_bytes
        need(len(p['market'])<POLICY['max_market_events'],'SPOT_MARKET_CAP')
        wire=env.SerializeToString();row={**stamp,'wire':base64.b64encode(wire).decode(),'sha256':bytes_digest(wire)}
        market_canonical_bytes+=len(encoded(row))
        need(market_canonical_bytes<=POLICY['max_market_canonical_bytes'],'SPOT_MARKET_CANONICAL_CAP')
        p['market'].append(row);profiler.observe(**market_event(row,int(msg.ctidTraderAccountId)))
    class Wire(InformationTransport):
        active=None
        def _send_bytes(self,frame):
            nonlocal wire_bytes
            env=decode_envelope(frame[4:]);msg=extract_payload(env);name=type(msg).__name__
            outbound_guard(name,self.active)
            wire_bytes+=len(frame);need(wire_bytes<=POLICY['max_wire_bytes'],'SPOT_WIRE_CAP')
            if self.active is not None and name==self.active['request_type']:
                need('client_msg_id' not in self.active,'SPOT_NO_SECOND_SEND')
                self.active['client_msg_id']=env.clientMsgId
                if name not in AUTH:self.active['request_wire']=base64.b64encode(env.SerializeToString()).decode()
            return super()._send_bytes(frame)
        def _recv_exact(self,count,*,deadline):
            nonlocal wire_bytes
            need(0<count<=POLICY['max_metadata_response_bytes'] and
              wire_bytes+count<=POLICY['max_wire_bytes'],'SPOT_NATIVE_FRAME_AND_WIRE_RESOURCE_CAP')
            try:data=super()._recv_exact(count,deadline=deadline)
            except Exception:
                wire_bytes+=self.partial_frame_received
                raise
            wire_bytes+=len(data);return data
        def receive_envelope(self,*,deadline):
            nonlocal received_count
            env=super().receive_envelope(deadline=deadline);received_count+=1
            need(wire_bytes<=POLICY['max_wire_bytes'] and received_count<=POLICY['max_received_envelopes'],'SPOT_RECEIVE_CAP')
            if self.active is not None and env.clientMsgId==self.active.get('client_msg_id'):
                need('response_wire' not in self.active,'SPOT_DUPLICATE_RESPONSE')
                need(len(env.SerializeToString())<=POLICY['max_metadata_response_bytes'],'SPOT_METADATA_RESPONSE_CAP')
                self.active['response_wire']=base64.b64encode(env.SerializeToString()).decode()
            return env
        def request(self,request,**kw):
            name=type(request).__name__;need(name in ALLOWED and name!='ProtoHeartbeatEvent','SPOT_REQUEST_ALLOWLIST')
            if name in AUTH:need(len(p['receipts'])<3 and name==AUTH[len(p['receipts'])],'SPOT_AUTH_SEQUENCE')
            else:need(len(p['receipts'])>=3 and counts[name]<CAPS[name],'SPOT_BUSINESS_CAP')
            counts[name]+=1;row={'request_type':name};p['receipts'].append(row);self.active=row
            try:
                response=super().request(request,**kw)
                need('response_wire' in row,'SPOT_NATIVE_RESPONSE_REQUIRED')
                return response
            finally:self.active=None
    tr=Wire(start_utc=start,end_utc=end,account_fingerprint=ACCOUNT_FINGERPRINT_SHA256,
      event_handler=handle,maximum_connection_seconds=POLICY['maximum_contact_seconds'],connect_timeout=15,response_timeout=20)
    p['contact_start_utc']=start.isoformat();p['contact_start_ns']=time.monotonic_ns();account=None
    try:
        need(all(os.environ.get(k) for k in BROKER),'SPOT_EXISTING_VIEW_CREDENTIALS')
        values=tuple(os.environ.pop(k) for k in BROKER);tr.connect();account=authenticate_segment(tr,*values);values=None;p['account']=account
        def req(message):
            response=tr.request(message,timeout=20)
            need(type(response).__name__==type(message).__name__[:-3]+'Res','SPOT_METADATA_RESPONSE_TYPE')
            if hasattr(response,'ctidTraderAccountId'):need(int(response.ctidTraderAccountId)==account,'SPOT_RESPONSE_ACCOUNT')
            return response
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account)).trader
        assets={int(a.assetId):a.name for a in req(m.ProtoOAAssetListReq(ctidTraderAccountId=account)).asset}
        need('pepperstone' in trader.brokerName.casefold() and assets.get(int(trader.depositAssetId))=='EUR','SPOT_PEPPERSTONE_EUR')
        lights={int(s.symbolId):s for s in req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False)).symbol}
        for key,name in POLICY['symbols'].items():
            sid=int(key);need(sid in lights and lights[sid].symbolName==name and lights[sid].enabled,'SPOT_EXACT_PANEL_BEFORE_SYMBOL_REQUEST')
        tr.selected={1,2,250}
        full={int(s.symbolId):s for s in req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[1,2,250])).symbol}
        need(set(full)=={1,2,250},'SPOT_FULL_PANEL')
        for sid in (1,2,250):
            need(full[sid].HasField('minVolume') and full[sid].minVolume>0,'SPOT_OBSERVED_MINIMUM_VOLUME')
            req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,volume=[full[sid].minVolume]))
        req(m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=account,symbolId=[1,2,250],subscribeToSpotTimestamp=True))
        deadline=min(tr.contact_deadline-20,tr._clock()+POLICY['capture_seconds_after_subscription'])
        need(deadline-tr._clock()>=POLICY['capture_seconds_after_subscription']-1,'SPOT_FULL_PROSPECTIVE_WINDOW_AVAILABLE')
        p['subscription_start_ns']=time.monotonic_ns();print('MXM_NATIVE_SPOT_SOURCE_ACTIVE_NO_MODEL_NO_ORDERS',flush=True)
        p['stream_end']=tr.stream_until(deadline)
        p['stream_end_ns']=time.monotonic_ns()
        need(p['stream_end'] in ('CAPTURE_DEADLINE','CAPTURE_DEADLINE_TIMEOUT_CONNECTION_CLOSED'),'SPOT_STREAM_TERMINATION')
        need(time.monotonic_ns()-p['subscription_start_ns']>=POLICY['capture_seconds_after_subscription']*1_000_000_000-1_000_000_000,'SPOT_CAPTURE_DURATION')
        # A receive deadline may leave a partial frame and closes transport.
        # Never reconnect or invent successful unsubscription in that case.
        if tr.connected:
            tr.market_capture_enabled=False;tr.cleanup=True;tr.cleanup_end=tr._clock()+15
            req(m.ProtoOAUnsubscribeSpotsReq(ctidTraderAccountId=account,symbolId=[1,2,250]))
            p['cleanup_state']='UNSUBSCRIBE_ACKNOWLEDGED'
        else:
            p['cleanup_state']='CONNECTION_CLOSED_AT_DEADLINE_UNSUBSCRIBE_NOT_ACKNOWLEDGED'
        p['complete']=True
    except Exception as exc:
        p['failure_class']=type(exc).__name__
        code=str(exc)
        if type(exc).__name__=='LabError' and code.startswith('LAB_SPOT_') and len(code)<=120 and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in code):
            p['failure_code']=code
    finally:
        tr.close()
        for k in BROKER:os.environ.pop(k,None)
        p['contact_end_utc']=datetime.now(timezone.utc).isoformat();p['contact_end_ns']=time.monotonic_ns()
        p['producer_profile']=profiler.result();p['wire_bytes']=wire_bytes;p['received_envelopes']=received_count
        p['wire_counts']=dict(tr.wire_counts);p['heartbeat_count']=len(tr.heartbeat_stamps);p['connection_epochs']=tr.connection_epochs
        # Encrypted evidence, including incomplete source, remains in native custody.
        raw=encoded(p);need(len(raw)<=POLICY['max_private_bytes'],'SPOT_PRIVATE_CAP')
        output=ROOT.parent/OUT;output.mkdir(parents=True,exist_ok=True)
        public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
        need(public_spki_sha256(public)==FP,'SPOT_EXISTING_RECIPIENT')
        encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=output/'capture.mxmenc')
    verified=verify_private(p)
    result={'schema':'mxm.native-spot-observation-public.v1',**identity,'role':'spot-collect','accepted':p['complete'],
      'cipher_sha256':bytes_digest((output/'capture.mxmenc').read_bytes()),'private_sha256':bytes_digest(raw),
      'profile':verified if verified is not None else p['producer_profile'],'failure_class':p['failure_class'],
      'failure_code':p.get('failure_code','NONE' if p['complete'] else 'PRIVATE_OR_UNCLASSIFIED_TRANSPORT_FAILURE'),
      'cleanup_state':p.get('cleanup_state','NOT_REACHED'),
      'classification':POLICY['classification'],'new_broker_connections':p['connection_epochs'],
      'historical_costs_proven':False,'economic_edge_proven':False,'hard21_proven':False,'orders':0,'strategy_trials':0}
    (output/'producer.json').write_bytes(encoded(result)+b'\n');print('MXM_SPOT_PRODUCER '+encoded(result).decode(),flush=True)
    need(p['complete'],'SPOT_COLLECTION_INCOMPLETE_NO_RETRY')

def cold(identity):
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    output=ROOT.parent/OUT;producer=json.loads((output/'producer.json').read_bytes())
    for k,v in identity.items():need(producer[k]==v,'SPOT_NATIVE_PRODUCER_IDENTITY')
    route=GetOnly();jobs=route.json('actions/runs/'+str(identity['run_id'])+'/jobs?per_page=100')['jobs']
    source=[j for j in jobs if j['name']=='spot-collect'];need(len(source)==1 and source[0]['conclusion']=='success','SPOT_ACTUAL_PRODUCER_JOB_SUCCESS')
    cipher=(output/'capture.mxmenc').read_bytes();need(bytes_digest(cipher)==producer['cipher_sha256'],'SPOT_ORIGINAL_NATIVE_CIPHER')
    with tempfile.TemporaryDirectory() as tmp:
        key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'SPOT_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)),max_bytes=POLICY['max_private_bytes'])
        need(bytes_digest(raw)==producer['private_sha256'],'SPOT_ORIGINAL_PRIVATE_DIGEST')
        p=strict_json(raw,max_elements=3000000);need(p['identity']==identity,'SPOT_PRIVATE_NATIVE_IDENTITY')
        profile=verify_private(p);need(profile is not None and producer['accepted'] is True and profile==producer['profile'],'SPOT_SEPARATE_NATIVE_PROFILE_READBACK')
    result={**producer,'role':'spot-cold','native_producer_job':source[0]['id'],'independently_redecoded_original_wire':True,
      'profile_algorithm_independent':False,'contact_start_utc':p['contact_start_utc'],'contact_end_utc':p['contact_end_utc'],
      'entire_contact_interval_excluded_from_confirmation':True,'current_metadata_observed_not_historical_terms':True}
    (output/'cold.json').write_bytes(encoded(result)+b'\n');print('MXM_SPOT_COLD '+encoded(result).decode(),flush=True)

if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admission(ROOT)
    elif sys.argv[1:] in (['spot-collect'],['spot-cold']):
        identity=admission(ROOT.parent,native=True)
        (collect if sys.argv[1]=='spot-collect' else cold)(identity)
    else:raise ValueError('SPOT_EXACT_PHASE')
