"""One native DOM capability capture, encrypted owner+verified-recipient delivery."""
import base64,hashlib,json,os,pathlib,subprocess,tempfile,time
from collections import Counter
from datetime import datetime,timedelta,timezone
from google.protobuf.json_format import MessageToDict
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,ACCOUNT_FINGERPRINT_SHA256
from research_core_v4.quote_path_recipient_recovery_20261013_v1 import delivery_contract_v1 as custody
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUB
from research_core_v4.dom_live_probe_20261013_v1.live_adapter_v1 import LiveReadOnlyTransport,DepthBook,LiveContractError,LiveWindowEnded,ALLOWED
from m6.ctrader_proto import OpenApiMessages_pb2 as m

e=rt.e;P='research_core_v4/dom_live_probe_20261013_v1/'
WF='.github/workflows/mxm-dom-live-probe-20261013-v1.yml';PHASE='GATE'
def need(v,c):e.w.old.need(bool(v),c)
def utc():return datetime.now(timezone.utc)
def when(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def plain(x):return MessageToDict(x,preserving_proto_field_name=True,use_integers_for_enums=True)
def inventory(ref):return dict(z.split('\t',1)[::-1] for z in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())

def gate():
    head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head)
    auth=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    scope=json.loads((e.a.ROOT/(P+'TECHNICAL_SCOPE_V1.json')).read_text())
    need(auth['authority']=='EXPLICIT_OWNER_ADDITIVE_LIVE_READ_ONLY_DOM_PROBE_20261013','NEW_LIVE_AUTHORITY')
    need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','EVENT_ATTEMPT')
    need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/'+WF+'@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
    need(not any(scope[k] for k in ('orders','cloud_deployment','economic_pilot','protected_forward','scientific_response','historical_requests')),'SCOPE')
    need(scope['classification']=='TECHNICAL_CAPABILITY_ONLY' and scope['maximum_connection_seconds']==1200,'TECHNICAL_LIMIT')
    need(scope['account_fingerprint_sha256']==ACCOUNT_FINGERPRINT_SHA256,'UNCHANGED_AUTHENTICATOR_ACCOUNT')
    public=(e.a.ROOT/auth['recipient_public_path']).read_bytes()
    ready=json.loads((e.a.ROOT/(P+'RECIPIENT_READY_V1.json')).read_text())
    need(custody.fingerprint(public)==auth['recipient_spki_sha256'],'RECIPIENT_FINGERPRINT')
    custody.require_ready(ready,public,auth['invocation_id'],when(scope['diagnostic_interval_utc'][1])+timedelta(minutes=40))
    e.a.ancestor(auth['base_head'],head);old,new=inventory(auth['base_head']),inventory(head)
    need(all(new.get(p)==blob for p,blob in old.items()),'ALL_OLD_FILES_BYTE_PRESERVED')
    for path,digest in auth['bindings'].items():need(e.w.old.filehash(path)==digest,'SOURCE_BINDING_DRIFT')
    partition=json.loads((e.a.ROOT/(P+'PROSPECTIVE_PARTITION_V1.json')).read_text())
    need(partition['classification']=='TECHNICAL_CAPABILITY_ONLY' and partition['eligible_for_development_or_protected_validation'] is False,'PARTITION_ROLE')
    need(partition['diagnostic_interval_utc']==scope['diagnostic_interval_utc'],'PARTITION_CLOCK')
    need(partition['existing_protected_boundary_file_unchanged'] is True,'HISTORICAL_FRONTIER_PRESERVED')
    start,end=map(when,scope['diagnostic_interval_utc'])
    need(start<end and (end-start).total_seconds()<=1200,'WINDOW_DURATION')
    # Current commit must predate future auxiliary acquisition. No old evidence relabel.
    committed=when(e.w.old.api('git/commits/'+head)['committer']['date'])
    need(committed<start and when(partition['frozen_utc'])<start,'PROSPECTIVE_BEFORE_CAPTURE')
    need(not partition['overlapping_explicit_protected_allocations'],'PROTECTED_ALLOCATION_OVERLAP')
    need(utc()<end,'EXPIRED_WINDOW')
    e.w.old.verify_science()
    need(not e.w.v2.existing_ref(auth['one_use_ref']),'ONE_USE_CONSUMED')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':head})
    return head,auth,scope,partition

def capture(scope):
    start,end=map(when,scope['diagnostic_interval_utc'])
    # Gate/signature checked before bounded waiting; no broker connection before start.
    while utc()<start:
        need((start-utc()).total_seconds()<=180,'START_WAIT_CAP')
        time.sleep(min(1,max(0,(start-utc()).total_seconds())))
    raw=[];books={};byte_count=0;json_byte_count=0;metadata={};responses={};errors=[];account=None;stream_end=None
    raw_count_cap=scope['raw_event_cap'];raw_bytes_cap=scope['raw_envelope_bytes_cap']
    def handle(message,stamp,envelope):
        nonlocal byte_count,json_byte_count
        wire=envelope.SerializeToString();need(len(raw)<raw_count_cap and byte_count+len(wire)<=raw_bytes_cap,'RAW_CAPTURE_RESOURCE_CAP')
        byte_count+=len(wire);name=type(message).__name__
        record={'type':name,**stamp,'raw_envelope_b64':base64.b64encode(wire).decode(),'raw_envelope_sha256':hashlib.sha256(wire).hexdigest()}
        size=len(e.a.enc(record));need(json_byte_count+size<=scope['raw_canonical_bytes_cap'],'RAW_CANONICAL_RESOURCE_CAP')
        json_byte_count+=size;raw.append(record)
        b=books[int(message.symbolId)]
        if name=='ProtoOADepthEvent':b.depth_event(message,stamp)
        else:b.spot_event(message,stamp)
    tr=LiveReadOnlyTransport(start_utc=start,end_utc=end,account_fingerprint=scope['account_fingerprint_sha256'],
                             event_handler=handle,connect_timeout=15,response_timeout=20)
    auth_state='NOT_ATTEMPTED';selection=[];actual_start=None;actual_end=None;cleanup={}
    def req(message):
        response=tr.request(message,timeout=20)
        if hasattr(response,'ctidTraderAccountId'):need(int(response.ctidTraderAccountId)==account,'METADATA_ACCOUNT_BINDING')
        if isinstance(response,m.ProtoOAErrorRes):raise LiveContractError('BROKER_METADATA_ERROR:'+response.errorCode)
        return response
    try:
        tr.connect();actual_start=utc().isoformat()
        account=authenticate_segment(tr,*[os.environ[n] for n in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')])
        auth_state='EXPLICIT_VIEW_EXISTING_LIVE_ACCOUNT_FINGERPRINT_PASS'
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account)).trader
        assets=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account)).asset
        asset_names={int(a.assetId):a.name for a in assets}
        need('pepperstone' in trader.brokerName.casefold() and asset_names.get(int(trader.depositAssetId))=='EUR','PEPPERSTONE_EUR_IDENTITY')
        metadata['identity']={'broker_name':trader.brokerName,'deposit_currency':'EUR','scope':'SCOPE_VIEW','live':True,
                              'account_fingerprint_sha256':scope['account_fingerprint_sha256']}
        result=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False))
        lights={int(s.symbolId):s for s in result.symbol};metadata['catalog_symbol_count']=len(lights)
        for nominee in scope['nominees']:
            light=lights.get(nominee['symbol_id'])
            if light is None or light.symbolName!=nominee['symbol'] or not light.enabled:
                selection.append({**nominee,'state':'EXACT_AUTHENTICATED_SYMBOL_NOT_ENABLED_OR_NOT_FOUND'});continue
            selection.append({**nominee,'state':'AUTHENTICATED_EXACT_SYMBOL_ENABLED','native_light':plain(light)})
        tr.selected={r['symbol_id'] for r in selection if r['state']=='AUTHENTICATED_EXACT_SYMBOL_ENABLED'}
        if tr.selected:
            full_req=m.ProtoOASymbolByIdReq(ctidTraderAccountId=account);full_req.symbolId.extend(sorted(tr.selected))
            full={int(s.symbolId):s for s in req(full_req).symbol}
            need(set(full)==tr.selected,'EXACT_FULL_CONTRACTS')
            metadata['contracts']={str(sid):plain(s) for sid,s in full.items()}
            metadata['expected_margin']={}
            for sid,symbol in full.items():
                books[sid]=DepthBook(sid,int(symbol.digits))
                margin_req=m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=sid,volume=[int(symbol.minVolume)])
                response=tr.request(margin_req,timeout=20)
                metadata['expected_margin'][str(sid)]={'response_type':type(response).__name__,
                    'broker_error':response.errorCode if isinstance(response,m.ProtoOAErrorRes) else None,
                    'native':plain(response) if not isinstance(response,m.ProtoOAErrorRes) else None}
            # Same one authenticated TLS connection; no OAuth app/account substitution.
            for cls in (m.ProtoOASubscribeSpotsReq,m.ProtoOASubscribeDepthQuotesReq):
                request=cls(ctidTraderAccountId=account);request.symbolId.extend(sorted(tr.selected))
                if cls is m.ProtoOASubscribeSpotsReq:request.subscribeToSpotTimestamp=True
                response=tr.request(request,timeout=20)
                if hasattr(response,'ctidTraderAccountId'):need(int(response.ctidTraderAccountId)==account,'SUBSCRIPTION_ACCOUNT_BIND')
                responses[cls.__name__]={'response_type':type(response).__name__,
                    'broker_error':response.errorCode if isinstance(response,m.ProtoOAErrorRes) else None}
            if responses['ProtoOASubscribeDepthQuotesReq']['response_type']=='ProtoOASubscribeDepthQuotesRes':
                print('MXM_TECHNICAL_DOM_CAPTURE_ACTIVE_NO_ECONOMIC_RESPONSE',flush=True)
                # Finish with time remaining for explicit unsubscribe, within 20-minute cap.
                deadline=min(tr.contact_deadline-20,tr._clock()+max(0,(end-utc()).total_seconds()-20))
                stream_end=tr.stream_until(deadline)
            else:stream_end='SUBSCRIPTION_REJECTED_OR_UNEXPECTED_RESPONSE'
        else:stream_end='NO_AUTHENTICATED_NOMINEES'
    except Exception as exc:
        # Private bounded reason; no exception containing credentials is printed publicly.
        reason=str(exc) if isinstance(exc,LiveContractError) or isinstance(exc,e.w.n.NumericalStop) else getattr(exc,'code',type(exc).__name__)
        errors.append({'type':type(exc).__name__,'reason':reason})
    finally:
        actual_end=utc().isoformat()
        if account is not None:cleanup=tr.unsubscribe_all(account)
        else:tr.close();cleanup={'connection':'CLOSED_BEFORE_ACCOUNT_AUTH'}
    summaries=[]
    for row in selection:
        if row['symbol_id'] in books:summaries.append({'symbol':row['symbol'],**books[row['symbol_id']].summary()})
        else:summaries.append({'symbol':row['symbol'],'symbol_id':row['symbol_id'],'state':row['state'],'counts':{}})
    n=sum(x.get('counts',{}).get('depth_events',0) for x in summaries)
    if n:state='DOM_EVENTS_AUTHENTICALLY_OBSERVED'
    elif responses.get('ProtoOASubscribeDepthQuotesReq',{}).get('response_type')=='ProtoOASubscribeDepthQuotesRes':state='SUBSCRIPTION_ACCEPTED_NO_DOM_EVENTS_OBSERVED'
    elif responses.get('ProtoOASubscribeDepthQuotesReq',{}).get('broker_error'):state='BROKER_SUBSCRIPTION_REJECTED'
    else:state='CAPTURE_NOT_ESTABLISHED'
    summary={'schema':'mxm.dom.live.technical.summary.v1','classification':'TECHNICAL_CAPABILITY_ONLY','state':state,
             'authentication':auth_state,'identity':metadata.get('identity'),'nominees':selection,'symbols':summaries,
             'subscription_responses':responses,'unsubscribe_responses':cleanup,'actual_contact_start_utc':actual_start,
             'capture_end_utc':actual_end,'authorized_interval_utc':scope['diagnostic_interval_utc'],
             'stream_end':stream_end,'interruptions_or_capture_errors':errors,'outbound_requests':dict(tr.wire_counts),
             'received_message_types':dict(tr.receive_counts),'raw_market_events':len(raw),'raw_envelope_bytes':byte_count,'raw_canonical_bytes':json_byte_count,
             'connection_epochs':tr.connection_epochs,'reconnects':0,
             'chronology':'ACTUAL_LOCAL_RECEIPT_SEQUENCE_UTC_AND_MONOTONIC;NO_DOM_SERVER_TIMESTAMP',
             'initialization_limit':'BOTH_SIDES_OBSERVED_IS_NOT_SERVER_CERTIFIED_COMPLETE_INITIAL_BOOK',
             'cloud_reproducible_observables':['RECEIVE_CALLBACK_ORDER','BID_ASK_PRICE_LEVELS','QUOTED_VOLUME_IN_UNITS','TOP_THREE_LEVEL_SUMS'],
             'cloud_parity_measured':False,'cloud_native_ids_or_deleted_quote_events':'NOT_EXPOSED_BY_MARKETDEPTHENTRY',
             'economic_pilot':False,'orders':0,'historical_requests':0,'protected_forward':False,
             'diagnostic_data_allowed_for_future_economic_testing':False,'gross_eur':None,'net_eur':None,'alpha_claim':False}
    return {'summary':summary,'raw_market_envelopes':raw,'current_authenticated_metadata':metadata}

def publish(head,auth,scope,partition,tmp,key,fp,full):
    path=PUB+'OWNER_DOM_LIVE_TECHNICAL_V1.json'
    status={'schema':e.w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'NOT_PERSISTED','failure_code':'NONE','run_id':int(os.environ['GITHUB_RUN_ID'])}
    release=e.w.old.api('releases',{'tag_name':'mxm-dom-technical-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],
        'target_commitish':head,'name':'MXM encrypted native DOM technical capability; no economic pilot',
        'prerelease':True,'body':validate_public_blob(path,status).decode()})
    full.update(source_head=head,run_id=int(os.environ['GITHUB_RUN_ID']),prospective_partition=partition,scope=scope)
    out=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');out.release=release
    primary=out.encrypted(full,'dom-technical-owner-result.mxmenc')
    loaded,proof=load_asset(key,fp,tmp,{'release_id':release['id'],'asset_id':primary['id'],'ciphertext_sha256':primary['ciphertext_sha256']})
    need(e.a.enc(loaded)==e.a.enc(full),'OWNER_REAL_READBACK_PARITY')
    summary=loaded['summary'];summary_sha=e.a.sha(e.a.enc(summary))
    envelope={'schema':'mxm.dom.technical.verified.recipient.summary.v1','source_run':int(os.environ['GITHUB_RUN_ID']),
              'source_head':head,'original_primary':proof,'recipient_spki_sha256':auth['recipient_spki_sha256'],
              'summary_canonical_sha256':summary_sha,'summary':summary,'OWNER_READBACK_SUCCESS':True,
              'NUMERIC_SUCCESS':True,'numeric_kind':'TECHNICAL_COUNTERS_ONLY','DELIVERY_SUCCESS':False,
              'economic_pilot':False,'delivery_state':'PENDING_ACTUAL_RECIPIENT_READBACK'}
    delivered=e.upload_extra(release,tmp,e.a.ROOT/auth['recipient_public_path'],envelope,'dom-technical-recipient-summary.mxmenc')
    attestation=out.encrypted({'schema':'mxm.dom.technical.attestation.v1','primary':proof,'delivery':delivered,
                              'summary_canonical_sha256':summary_sha,'OWNER_READBACK_SUCCESS':True,
                              'recipient_readback_verified':False,'economic_pilot':False},'dom-technical-attestation.mxmenc')
    status.update(status='PASS',phase='FINAL',encrypted_artifact_name=delivered['name'],encrypted_artifact_sha256=delivered['ciphertext_sha256'])
    body=validate_public_blob(path,status);e.w.old.api('releases/'+str(release['id']),{'body':body.decode()},method='PATCH')
    need(e.w.old.api('releases/'+str(release['id']))['body'].encode()==body,'PUBLIC_STATUS_READBACK')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['owner_readback_completion_ref'],'sha':head})
    print(body.decode().strip(),flush=True)

def main():
    global PHASE
    os.umask(0o077);head,auth,scope,partition=gate()
    with tempfile.TemporaryDirectory(prefix='mxm-dom-technical-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY_BINDING')
        PHASE='BOUNDED_NATIVE_DOM_TECHNICAL_CAPTURE';full=capture(scope)
        PHASE='OWNER_AND_RECIPIENT_ENCRYPTED_PUBLICATION';publish(head,auth,scope,partition,tmp,key,fp,full)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
