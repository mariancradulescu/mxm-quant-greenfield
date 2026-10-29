"""One finite W33 historical source question; no model, fills or arrival-clock invention.

Reuses the sealed native tick splitter/decoder and existing VIEW/custody route.
The prior live spot pilot remains frozen; this operation supersedes its workflow only.
"""
import base64,gzip,json,os,re,subprocess,sys,tempfile,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from .common import need,encoded,bytes_digest,utc_ms
from . import spot_observation_reception as old
ROOT=Path(__file__).resolve().parents[2]
REPO=old.REPO;BRANCH=old.BRANCH;NATIVE=old.NATIVE;PATH=old.PATH;BROKER=old.BROKER;AUTH=old.AUTH
OUT='verification/panel-quote-support'
MODULE='research_core_v4.laboratory.panel_quote_support'
PARTITION='research_programs/partitions/PANEL_QUOTE_SUPPORT_20261029.json'
POLICY={'schema':'mxm.panel-quote-support-policy.v1','symbols':{'5':'AUDUSD','111':'Copper','250':'SpotCrude'},
 'from_ms':utc_ms('2026-08-11T10:00:00Z'),'to_ms':utc_ms('2026-08-11T10:10:00Z'),
 'history_request_cap':24,'maximum_contact_seconds':180,'max_wire_bytes':16_000_000,
 'max_response_bytes':4_000_000,'max_private_bytes':24_000_000,'orders':0,'strategy_trials':0,
 'automatic_retry':False,'confirmation_eligible':False,'classification':'EXPOSED_DEVELOPMENT_SOURCE_SUPPORT_ONLY',
 'question':'DO_ALL_THREE_FIXED_INSTRUMENTS_HAVE_COMPLETE_NONEMPTY_BID_AND_ASK_IN_W33',
 'selection_rule':'FULL_PANEL_NO_INSTRUMENT_WINDOW_OR_MODEL_SELECTION_AFTER_SOURCE',
 'window_reason':'TEN_MINUTES_ON_ORDINARY_W33_TUESDAY_DAYTIME_BEFORE_PROTECTED_FORWARD_NOT_OUTCOME_SELECTED',
 'quotes_are_historical_not_observed_arrival':True,'current_metadata_is_historical_terms':False}
POLICY_SHA=bytes_digest(encoded(POLICY))
CAPS={'ProtoOATraderReq':1,'ProtoOAAssetListReq':1,'ProtoOASymbolsListReq':1,'ProtoOASymbolByIdReq':1,
      'ProtoOAExpectedMarginReq':3,'ProtoOAGetTickDataReq':24}
ALLOWED=frozenset((*AUTH,*CAPS,'ProtoHeartbeatEvent'))

def partition():
    return {'schema':'mxm.prospective-source-quality-partition.v1','policy_sha256':POLICY_SHA,
      'classification':POLICY['classification'],'from_ms':POLICY['from_ms'],'to_ms':POLICY['to_ms'],
      'symbols':POLICY['symbols'],'confirmation_eligible':False,'response_testing_allowed':False,
      'prior_evidence_reclassified':False,'new_strategy_trial':False,'protected_opened':False}

def workflow():
    w=old.workflow();w['name']='MXM finite W33 panel quote support and USD registration'
    for role,j in w['jobs'].items():
        for s in j['steps']:
            if 'run' in s:
                s['run']=s['run'].replace('research_core_v4.laboratory.spot_observation_reception',MODULE)
                if s['name'].startswith('Verify source-only'):
                    s['run']='python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock\ncp research_core_v4/laboratory/panel_quote_support.py research_core_v4/laboratory/spot_observation_reception.py research_core_v4/laboratory/spot_observation_profile.py research_core_v4/laboratory/test_panel_quote_support.py .spot-native/research_core_v4/laboratory/\n(cd .spot-native && PANEL_TEST_MAIN_ROOT="$GITHUB_WORKSPACE" python3 -m unittest research_core_v4.laboratory.test_panel_quote_support -v)'
            if s.get('uses')==old.DOWNLOAD:s['with'].update(name='panel-support-producer-${{ github.run_id }}',path=OUT)
            if s.get('uses')==old.UPLOAD:
                s['with'].update(name=('panel-support-producer-' if role=='spot-collect' else 'panel-support-cold-')+'${{ github.run_id }}',
                  path=OUT+('/capture.mxmenc\n'+OUT+'/producer.json' if role=='spot-collect' else '/cold.json\n'+OUT+'/quote-assets.json\n'+OUT+'/registration.json'))
        if role=='spot-cold':
            j['steps'].insert(-1,{'name':'Admit independently decoded USD roster to existing C# account without market replay',
              'run':'dotnet run --project research_core_v4/laboratory/csharp/usd_account/MxmSharedUsdAccountFixture.csproj -c Release -- --register-usd-quotes '+OUT+'/quote-assets.json > '+OUT+'/registration.json\ncat '+OUT+'/registration.json'})
    return w

def admission(main,native=False):
    main=Path(main);job=os.environ.get('GITHUB_JOB')
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      job in ('spot-collect','spot-cold') and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'PANEL_NATIVE_CONTEXT')
    forbidden=['SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_REFRESH_TOKEN','R3_CUSTODY_PRIVATE_KEY_PEM']
    forbidden+=list(BROKER) if not native or job=='spot-cold' else []
    if not native or job=='spot-collect':forbidden+=['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']
    need(not any(os.environ.get(k) for k in forbidden),'PANEL_SECRET_ROLE_SEPARATION')
    head=subprocess.check_output(['git','-C',str(main),'rev-parse','HEAD'],text=True).strip()
    need(head==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
      subprocess.run(['git','-C',str(main),'diff','--quiet','HEAD','--']).returncode==0 and
      json.loads((main/PATH).read_bytes())==workflow(),'PANEL_EXACT_MAIN_SOURCE')
    need(bytes_digest((main/'V2_PROTECTED_FORWARD_START.json').read_bytes())==old.BOUNDARY_SHA and
      json.loads((main/PARTITION).read_bytes())==partition(),'PANEL_PARTITION_BOUNDARY')
    if native:
        need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE and
          subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'PANEL_SEALED_NATIVE')
        for f in ('panel_quote_support.py',*old.FILES):
            need((ROOT/'research_core_v4/laboratory'/f).read_bytes()==(main/'research_core_v4/laboratory'/f).read_bytes(),'PANEL_EXACT_EXTENSION')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==head,'PANEL_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:
        need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'PANEL_AUTHORITY_UNCHANGED')
    runs=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100')
    rows=runs['workflow_runs'];current=int(os.environ['GITHUB_RUN_ID'])
    need(runs['total_count']==len(rows)==2 and {r['id'] for r in rows}=={40455704891,current} and current!=40455704891 and
      all(r['run_attempt']==1 for r in rows) and
      next(r for r in rows if r['id']==40455704891)['conclusion']=='success','PANEL_ONE_NEW_ATTEMPT_AFTER_FROZEN_SPOT')
    return {'run_id':current,'source_sha':head,'native_source':NATIVE,'policy_sha256':POLICY_SHA,
      'partition_sha256':bytes_digest(encoded(partition())),'attempt':1}

def native_policy(sid):
    from . import chronology_reception as native
    native.POLICY={**native.POLICY,'symbol_id':sid,'from_ms':POLICY['from_ms'],'to_ms':POLICY['to_ms']}
    return native

def outbound_guard(name,row):
    need(name in ALLOWED,'PANEL_READ_ONLY_FRAME_ALLOWLIST')
    if name!='ProtoHeartbeatEvent':
        need(row is not None and row['request_type']==name and 'client_msg_id' not in row,'PANEL_NO_UNTRACKED_SECOND_SEND')

def decode_pair(row,account):
    from m6.ctrader_transport import decode_envelope,extract_payload
    env=decode_envelope(base64.b64decode(row['response_wire'],validate=True));res=extract_payload(env)
    name=row['request_type'];need(name in ALLOWED and name!='ProtoHeartbeatEvent','PANEL_RECEIPT_ALLOWLIST')
    need(env.IsInitialized() and res.IsInitialized() and re.fullmatch(r'mxm-[0-9]{12}',env.clientMsgId) and
      env.clientMsgId==row['client_msg_id'] and type(res).__name__==name[:-3]+'Res','PANEL_NATIVE_RESPONSE_CORRELATION')
    if hasattr(res,'ctidTraderAccountId'):need(int(res.ctidTraderAccountId)==account,'PANEL_RESPONSE_ACCOUNT')
    req=None
    if name not in AUTH:
        reqenv=decode_envelope(base64.b64decode(row['request_wire'],validate=True));req=extract_payload(reqenv)
        need(reqenv.IsInitialized() and req.IsInitialized() and reqenv.clientMsgId==env.clientMsgId and
          type(req).__name__==name and int(req.ctidTraderAccountId)==account,'PANEL_NATIVE_REQUEST_BINDING')
    return req,res

def verify_private(p):
    from m6.ctrader_proto import OpenApiModelMessages_pb2 as enums
    from research_core_v4.shallow_m5_support_v2_production import ACCOUNT_FINGERPRINT_SHA256
    need(p['policy']==POLICY and p['identity']['policy_sha256']==POLICY_SHA and p['identity']['native_source']==NATIVE and
      p['identity']['partition_sha256']==bytes_digest(encoded(partition())),'PANEL_PRIVATE_POLICY')
    need(p['complete'] is True and old.fingerprint(p['account'])==ACCOUNT_FINGERPRINT_SHA256,'PANEL_COMPLETE_ACCOUNT')
    receipts=p['receipts'];expected=list(AUTH)+list(CAPS)[:4]+['ProtoOAExpectedMarginReq']*3
    need(10<=len(receipts)<=34 and [r['request_type'] for r in receipts[:10]]==expected and
      all(r['request_type']=='ProtoOAGetTickDataReq' for r in receipts[10:]),'PANEL_EXACT_REQUEST_SEQUENCE')
    need(len({r['client_msg_id'] for r in receipts})==len(receipts),'PANEL_UNIQUE_CORRELATION')
    native_bytes=sum(len(base64.b64decode(r[k],validate=True)) for r in receipts for k in ('request_wire','response_wire') if k in r)
    need(native_bytes<=POLICY['max_wire_bytes'] and all(len(base64.b64decode(r['response_wire'],validate=True))<=POLICY['max_response_bytes'] for r in receipts),'PANEL_COLD_NATIVE_WIRE_CAP')
    pairs=[decode_pair(r,p['account']) for r in receipts];responses=[x[1] for x in pairs]
    accounts=responses[1];matches=[a for a in accounts.ctidTraderAccount if a.ctidTraderAccountId==p['account']]
    need(accounts.HasField('permissionScope') and accounts.permissionScope==enums.SCOPE_VIEW and len(matches)==1 and
      matches[0].HasField('isLive') and matches[0].isLive,'PANEL_NATIVE_VIEW_ONLY')
    assets={int(a.assetId):a.name for a in responses[4].asset};trader=responses[3].trader
    need('pepperstone' in trader.brokerName.casefold() and assets.get(int(trader.depositAssetId))=='EUR','PANEL_PEPPERSTONE_EUR')
    lights={int(s.symbolId):s for s in responses[5].symbol};full={int(s.symbolId):s for s in responses[6].symbol}
    ids=[int(x) for x in POLICY['symbols']]
    need(set(full)==set(ids) and list(pairs[6][0].symbolId)==ids and
      pairs[5][0].HasField('includeArchivedSymbols') and not pairs[5][0].includeArchivedSymbols,'PANEL_EXACT_FULL_SYMBOL_REQUEST')
    quote_assets=[];terms=[]
    for i,(key,name) in enumerate(POLICY['symbols'].items()):
        sid=int(key);s=full[sid];light=lights[sid];req,margin=pairs[7+i]
        need(light.symbolName==name and light.enabled and light.HasField('quoteAssetId') and
          assets.get(light.quoteAssetId)=='USD' and all(s.HasField(k) and getattr(s,k)>0 for k in ('minVolume','maxVolume','stepVolume')),
          'PANEL_EXPLICIT_USD_VOLUME_METADATA')
        need(req.symbolId==sid and list(req.volume)==[s.minVolume] and margin.HasField('moneyDigits') and
          len(margin.margin)==1 and margin.margin[0].volume==s.minVolume,'PANEL_CURRENT_NATIVE_MARGIN')
        quote_assets.append({'symbol':name,'symbol_id':sid,'quote_asset':'USD'})
        terms.append({'symbol':name,'volume_min_centunits':int(s.minVolume),'volume_step_centunits':int(s.stepVolume),
          'volume_max_centunits':int(s.maxVolume),'margin_money_digits':int(margin.moneyDigits),
          'minimum_buy_margin_raw':int(margin.margin[0].buyMargin),'minimum_sell_margin_raw':int(margin.margin[0].sellMargin)})
    # Adapt only receipt field names; retain the sealed splitter/decoder and every leaf.
    tick_receipts=[]
    for r,(req,res) in zip(receipts,pairs):
        tick_receipts.append({**r,'request_b64':base64.b64encode(req.SerializeToString()).decode() if req else None,
          'request_envelope_b64':r.get('request_wire'),'response_envelope_b64':r['response_wire']})
    cells=[];allused=[];need(set(p['trees'])==set(POLICY['symbols']),'PANEL_EXACT_TREE_PANEL')
    for key,name in POLICY['symbols'].items():
        native=native_policy(int(key));need(set(p['trees'][key])=={'BID','ASK'},'PANEL_BOTH_SIDES')
        for label,side in (('BID',1),('ASK',2)):
            rows,complete,used=native.verify_tree(p['trees'][key][label],tick_receipts,p['account'],side);allused+=used
            cells.append({'symbol':name,'side':label,'events':len(rows),'provider_window_complete':complete})
    need(len(allused)==len(set(allused)) and set(allused)==set(range(10,len(receipts))),'PANEL_EXACT_TICK_RECEIPT_INVENTORY')
    need(0<=p['contact_end_ns']-p['contact_start_ns']<=200_000_000_000 and p['connection_attempts']==1 and
      p['wire_bytes']<=POLICY['max_wire_bytes'],'PANEL_FINITE_CONTACT')
    result={'cells':cells,'history_requests':len(receipts)-10,'metadata_requests':7,'authentication_requests':3,
      'all_panel_sides_complete_nonempty':all(c['provider_window_complete'] and c['events']>0 for c in cells),
      'current_metadata_not_historical_terms':terms,'quote_assets':quote_assets}
    return result

def collect(identity):
    from m6.ctrader_transport import StdlibCTraderTransport,decode_envelope,extract_payload
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,encrypt_shard,public_spki_sha256
    from research_core_v4.successor_c_20261018.readback import FP
    p={'identity':identity,'policy':POLICY,'complete':False,'receipts':[],'trees':{},'failure_class':None,
       'contact_start_ns':time.monotonic_ns(),'contact_start_utc':datetime.now(timezone.utc).isoformat()}
    deadline=time.monotonic()+POLICY['maximum_contact_seconds'];counts=Counter();wire_bytes=0;last_history=0.
    class Wire(StdlibCTraderTransport):
        active=None;attempts=0
        def connect(self):
            need(self.attempts==0,'PANEL_NO_RECONNECT');self.attempts+=1;return super().connect()
        def _send_bytes(self,frame):
            nonlocal wire_bytes
            need(time.monotonic()<deadline,'PANEL_CONTACT_DEADLINE')
            env=decode_envelope(frame[4:]);msg=extract_payload(env);name=type(msg).__name__;outbound_guard(name,self.active)
            wire_bytes+=len(frame);need(wire_bytes<=POLICY['max_wire_bytes'],'PANEL_WIRE_CAP')
            if name!='ProtoHeartbeatEvent':
                self.active['client_msg_id']=env.clientMsgId
                if name not in AUTH:self.active['request_wire']=base64.b64encode(env.SerializeToString()).decode()
            return super()._send_bytes(frame)
        def _recv_exact(self,count,*,deadline):
            nonlocal wire_bytes
            need(0<count<=POLICY['max_response_bytes'] and wire_bytes+count<=POLICY['max_wire_bytes'],'PANEL_NATIVE_FRAME_CAP')
            data=super()._recv_exact(count,deadline=min(deadline,contact_deadline));wire_bytes+=len(data);return data
        def receive_envelope(self,*,deadline):
            env=super().receive_envelope(deadline=deadline)
            if self.active is not None and env.clientMsgId==self.active.get('client_msg_id'):
                need('response_wire' not in self.active,'PANEL_DUPLICATE_RESPONSE')
                self.active['response_wire']=base64.b64encode(env.SerializeToString()).decode()
            return env
        def request(self,request,**kw):
            nonlocal last_history
            name=type(request).__name__;need(name in ALLOWED and name!='ProtoHeartbeatEvent','PANEL_REQUEST_ALLOWLIST')
            if name in AUTH:need(len(p['receipts'])<3 and name==AUTH[len(p['receipts'])],'PANEL_AUTH_SEQUENCE')
            else:need(len(p['receipts'])>=3 and counts[name]<CAPS[name],'PANEL_BUSINESS_CAP')
            if name=='ProtoOAGetTickDataReq':
                time.sleep(max(0,.22-(time.monotonic()-last_history)));last_history=time.monotonic()
            counts[name]+=1;row={'request_type':name};p['receipts'].append(row);self.active=row
            try:return super().request(request,timeout=max(.001,min(20,contact_deadline-time.monotonic())))
            finally:self.active=None
    contact_deadline=deadline;tr=Wire(connect_timeout=10,response_timeout=20);values=None
    try:
        need(all(os.environ.get(k) for k in BROKER),'PANEL_EXISTING_VIEW_CREDENTIALS')
        values=tuple(os.environ.pop(k) for k in BROKER);tr.connect();account=authenticate_segment(tr,*values);values=None;p['account']=account
        def req(message):
            response=tr.request(message);need(type(response).__name__==type(message).__name__[:-3]+'Res','PANEL_RESPONSE_TYPE')
            return response
        req(m.ProtoOATraderReq(ctidTraderAccountId=account));req(m.ProtoOAAssetListReq(ctidTraderAccountId=account))
        lights={int(s.symbolId):s for s in req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False)).symbol}
        ids=[int(x) for x in POLICY['symbols']]
        need(all(sid in lights and lights[sid].symbolName==POLICY['symbols'][str(sid)] and lights[sid].enabled for sid in ids),'PANEL_SYMBOLS_BEFORE_HISTORY')
        full={int(s.symbolId):s for s in req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=ids)).symbol}
        need(set(full)==set(ids),'PANEL_FULL_METADATA')
        for sid in ids:req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,volume=[full[sid].minVolume]))
        def send(message):
            response=req(message);return len(p['receipts'])-1,response
        for sid in ids:
            native=native_policy(sid);p['trees'][str(sid)]={}
            for label,side in (('BID',1),('ASK',2)):
                p['trees'][str(sid)][label]=native.split_collect(send,account,side,POLICY['from_ms'],POLICY['to_ms']-1,
                  lambda:POLICY['history_request_cap']-counts['ProtoOAGetTickDataReq'])
        p['complete']=True
    except Exception as exc:
        p['failure_class']=type(exc).__name__
        code=str(exc)
        if re.fullmatch(r'LAB_PANEL_[A-Z0-9_]{1,100}',code):p['failure_code']=code
        p['failure_request_type']=p['receipts'][-1]['request_type'] if p['receipts'] else 'NONE'
        if p['receipts'] and 'response_wire' in p['receipts'][-1]:
            msg=extract_payload(decode_envelope(base64.b64decode(p['receipts'][-1]['response_wire'])))
            if type(msg).__name__=='ProtoOAErrorRes' and re.fullmatch(r'[A-Z0-9_]{1,100}',msg.errorCode):
                p['provider_error_code']=msg.errorCode
    finally:
        tr.close();values=None
        for k in BROKER:os.environ.pop(k,None)
        p.update(contact_end_ns=time.monotonic_ns(),contact_end_utc=datetime.now(timezone.utc).isoformat(),
          wire_bytes=wire_bytes,connection_attempts=tr.attempts)
        raw=encoded(p);need(len(raw)<=POLICY['max_private_bytes'],'PANEL_PRIVATE_CAP')
        output=ROOT.parent/OUT;output.mkdir(parents=True,exist_ok=True)
        public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==FP,'PANEL_EXISTING_RECIPIENT')
        encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=output/'capture.mxmenc')
    profile=verify_private(p) if p['complete'] else None
    result={'schema':'mxm.panel-quote-support-public.v1',**identity,'role':'spot-collect','accepted':p['complete'],
      'profile':profile,'failure_class':p['failure_class'],'failure_code':p.get('failure_code'),
      'failure_request_type':p.get('failure_request_type'),'provider_error_code':p.get('provider_error_code'),'cipher_sha256':bytes_digest((output/'capture.mxmenc').read_bytes()),
      'private_sha256':bytes_digest(raw),'orders':0,'strategy_trials':0,'economic_edge_proven':False,'hard21_proven':False,
      'historical_costs_proven':False,'historical_arrival_times_proven':False,'confirmation_eligible':False}
    (output/'producer.json').write_bytes(encoded(result)+b'\n');print('MXM_PANEL_PRODUCER '+encoded(result).decode(),flush=True)
    need(p['complete'],'PANEL_COLLECTION_INCOMPLETE_NO_RETRY')

def cold(identity):
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    output=ROOT.parent/OUT;producer=json.loads((output/'producer.json').read_bytes())
    for k,v in identity.items():need(producer[k]==v,'PANEL_PRODUCER_IDENTITY')
    route=GetOnly();jobs=route.json('actions/runs/'+str(identity['run_id'])+'/jobs?per_page=100')['jobs']
    source=[j for j in jobs if j['name']=='spot-collect'];need(len(source)==1 and source[0]['conclusion']=='success','PANEL_NATIVE_PRODUCER_SUCCESS')
    logs=route.data('actions/jobs/'+str(source[0]['id'])+'/logs').decode('utf-8')
    need(identity['source_sha'] in logs and NATIVE in logs and 'git log -1 --format=%H' in logs,'PANEL_NATIVE_CHECKOUT_LOG')
    cipher=(output/'capture.mxmenc').read_bytes();need(bytes_digest(cipher)==producer['cipher_sha256'],'PANEL_ORIGINAL_CIPHER')
    with tempfile.TemporaryDirectory() as tmp:
        key,fp=_private_key_from_secret(Path(tmp));need(fp==FP,'PANEL_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(tmp)),max_bytes=POLICY['max_private_bytes'])
        need(bytes_digest(raw)==producer['private_sha256'],'PANEL_ORIGINAL_PRIVATE_DIGEST')
        p=strict_json(raw,max_elements=3_000_000);need(p['identity']==identity,'PANEL_PRIVATE_NATIVE_IDENTITY')
        profile=verify_private(p);need(producer['accepted'] is True and profile==producer['profile'],'PANEL_SEPARATE_READBACK_PARITY')
    result={**producer,'role':'spot-cold','native_producer_job':source[0]['id'],'independently_redecoded_original_wire':True,
      'contact_start_utc':p['contact_start_utc'],'contact_end_utc':p['contact_end_utc']}
    declaration={'schema':'mxm.declared-quote-assets.v1','source_sha256':producer['private_sha256'],'symbols':profile['quote_assets']}
    (output/'quote-assets.json').write_bytes(encoded(declaration)+b'\n')
    (output/'cold.json').write_bytes(encoded(result)+b'\n');print('MXM_PANEL_COLD '+encoded(result).decode(),flush=True)

if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admission(ROOT)
    elif sys.argv[1:] in (['spot-collect'],['spot-cold']):
        identity=admission(ROOT.parent,native=True);(collect if sys.argv[1]=='spot-collect' else cold)(identity)
    else:raise ValueError('PANEL_EXACT_PHASE')
