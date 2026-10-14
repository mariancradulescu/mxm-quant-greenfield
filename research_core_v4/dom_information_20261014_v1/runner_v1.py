"""One owner-authorized DOM information qualification; no response or orders."""
import base64,hashlib,json,os,pathlib,subprocess,tempfile,time
from collections import Counter
from datetime import datetime,timedelta,timezone
from google.protobuf.json_format import MessageToDict
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,ACCOUNT_FINGERPRINT_SHA256
from research_core_v4.quote_path_recipient_recovery_20261013_v1 import delivery_contract_v1 as custody
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUB
from research_core_v4.dom_live_probe_20261013_v1.live_adapter_v1 import LiveContractError,LiveWindowEnded,ALLOWED
from research_core_v4.dom_information_20261014_v1.live_adapter_v1 import InformationTransport,error_detail
from research_core_v4.dom_information_20261014_v1.information_v1 import InformationBook
from m6.ctrader_proto import OpenApiMessages_pb2 as m

e=rt.e;P='research_core_v4/dom_information_20261014_v1/'
WF='.github/workflows/mxm-dom-information-20261014-v1.yml';PHASE='GATE'
def need(v,c):e.w.old.need(bool(v),c)
def utc():return datetime.now(timezone.utc)
def when(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def plain(x):return MessageToDict(x,preserving_proto_field_name=True,use_integers_for_enums=True)
def inventory(ref):return dict(z.split('\t',1)[::-1] for z in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())

def gate():
    head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head)
    auth=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    scope=json.loads((e.a.ROOT/(P+'TECHNICAL_SCOPE_V1.json')).read_text())
    need(auth['authority']=='EXPLICIT_OWNER_DOM_INFORMATION_DEVELOPMENT_20261014','NEW_LIVE_AUTHORITY')
    need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','EVENT_ATTEMPT')
    need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/'+WF+'@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
    need(not any(scope[k] for k in ('orders','cloud_deployment','economic_pilot','protected_forward','scientific_response','historical_requests')),'SCOPE')
    need(scope['classification']=='DEVELOPMENT_INFORMATION_QUALIFICATION' and 0<scope['maximum_connection_seconds']<=3600,'TECHNICAL_LIMIT')
    need(scope['account_fingerprint_sha256']==ACCOUNT_FINGERPRINT_SHA256,'UNCHANGED_AUTHENTICATOR_ACCOUNT')
    public=(e.a.ROOT/auth['recipient_public_path']).read_bytes()
    ready=json.loads((e.a.ROOT/(P+'RECIPIENT_READY_V1.json')).read_text())
    need(custody.fingerprint(public)==auth['recipient_spki_sha256'],'RECIPIENT_FINGERPRINT')
    custody.require_ready(ready,public,auth['invocation_id'],when(scope['development_interval_utc'][1])+timedelta(minutes=40))
    e.a.ancestor(auth['base_head'],head);old,new=inventory(auth['base_head']),inventory(head)
    need(all(new.get(p)==blob for p,blob in old.items()),'ALL_OLD_FILES_BYTE_PRESERVED')
    for path,digest in auth['bindings'].items():need(e.w.old.filehash(path)==digest,'SOURCE_BINDING_DRIFT')
    partition=json.loads((e.a.ROOT/(P+'PROSPECTIVE_PARTITION_V1.json')).read_text())
    need(partition['classification']=='DEVELOPMENT_INFORMATION_QUALIFICATION' and partition['eligible_for_protected_validation'] is False,'PARTITION_ROLE')
    need(partition['development_interval_utc']==scope['development_interval_utc'],'PARTITION_CLOCK')
    need(partition['existing_protected_boundary_file_unchanged'] is True,'HISTORICAL_FRONTIER_PRESERVED')
    start,end=map(when,scope['development_interval_utc'])
    need(start<end and (end-start).total_seconds()<=3600,'WINDOW_DURATION')
    # Current commit must predate future auxiliary acquisition. No old evidence relabel.
    committed=when(e.w.old.api('git/commits/'+head)['committer']['date'])
    need(committed<start and when(partition['frozen_utc'])<start,'PROSPECTIVE_BEFORE_CAPTURE')
    need(not partition['overlapping_explicit_protected_allocations'],'PROTECTED_ALLOCATION_OVERLAP')
    prior=json.loads((e.a.ROOT/'research_core_v4/dom_live_probe_20261013_v1/PROSPECTIVE_PARTITION_V1.json').read_text())
    need(start>=when(prior['diagnostic_interval_utc'][1]),'DIAGNOSTIC_OVERLAP')
    need(e.w.old.filehash(partition['existing_protected_boundary_file'])==partition['existing_protected_boundary_sha256'],'BOUNDARY_DRIFT')
    need(partition['new_owner_designation_before_acquisition'] is True and not partition['existing_saved_market_evidence_reclassified'],'OWNER_PARTITION')
    need(utc()<end,'EXPIRED_WINDOW')
    e.w.old.verify_science()
    need(not e.w.v2.existing_ref(auth['one_use_ref']),'ONE_USE_CONSUMED')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':head})
    return head,auth,scope,partition

def capture(scope):
    start,end=map(when,scope['development_interval_utc'])
    # Gate/signature checked before bounded waiting; no broker connection before start.
    while utc()<start:
        need((start-utc()).total_seconds()<=180,'START_WAIT_CAP')
        time.sleep(min(1,max(0,(start-utc()).total_seconds())))
    raw=[];books={};byte_count=0;json_byte_count=0;metadata={};responses={};errors=[];account=None;stream_end=None;markers=[]
    raw_count_cap=scope['raw_event_cap'];raw_bytes_cap=scope['raw_envelope_bytes_cap']
    def handle(message,stamp,envelope):
        nonlocal byte_count,json_byte_count
        wire=envelope.SerializeToString();need(len(raw)<raw_count_cap and byte_count+len(wire)<=raw_bytes_cap,'RAW_CAPTURE_RESOURCE_CAP')
        byte_count+=len(wire);name=type(message).__name__
        record={'type':name,**stamp,'raw_envelope_b64':base64.b64encode(wire).decode(),'raw_envelope_sha256':hashlib.sha256(wire).hexdigest()}
        record['processing_begin_monotonic_ns']=time.monotonic_ns()
        size=len(e.a.enc(record));need(json_byte_count+size<=scope['raw_canonical_bytes_cap'],'RAW_CANONICAL_RESOURCE_CAP')
        json_byte_count+=size;raw.append(record)
        b=books[int(message.symbolId)]
        if name=='ProtoOADepthEvent':b.depth_event(message,stamp)
        else:b.spot_event(message,stamp)
        record['processing_end_monotonic_ns']=time.monotonic_ns()
    tr=InformationTransport(maximum_connection_seconds=scope['maximum_connection_seconds'],marker_handler=markers.append,start_utc=start,end_utc=end,account_fingerprint=scope['account_fingerprint_sha256'],
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
                books[sid]=InformationBook(sid,int(symbol.digits),start_utc=start,rules=scope['information_rules'])
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
                tr.marker('DEVELOPMENT_SUBSCRIPTIONS_ACCEPTED')
                print('MXM_DEVELOPMENT_INFORMATION_CAPTURE_ACTIVE_NO_RESPONSE',flush=True)
                # Finish with time remaining for explicit unsubscribe, within 20-minute cap.
                deadline=min(tr.contact_deadline-20,tr._clock()+max(0,(end-utc()).total_seconds()-20))
                stream_end=tr.stream_until(deadline)
            else:stream_end='SUBSCRIPTION_REJECTED_OR_UNEXPECTED_RESPONSE'
        else:stream_end='NO_AUTHENTICATED_NOMINEES'
    except Exception as exc:
        # Private bounded reason; no exception containing credentials is printed publicly.
        errors.append(error_detail(exc));tr.marker('CAPTURE_EXCEPTION',detail=errors[-1])
    finally:
        actual_end=utc().isoformat()
        end_ns=time.monotonic_ns()
        for book in books.values():book.finish(end_ns)
        tr.marker('CAPTURE_STOP',stream_end=stream_end)
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
    summary={'schema':'mxm.dom.information.summary.v1','classification':'DEVELOPMENT_INFORMATION_QUALIFICATION','state':state,
             'authentication':auth_state,'identity':metadata.get('identity'),'nominees':selection,'symbols':summaries,
             'subscription_responses':responses,'unsubscribe_responses':cleanup,'actual_contact_start_utc':actual_start,
             'capture_end_utc':actual_end,'authorized_interval_utc':scope['development_interval_utc'],
             'stream_end':stream_end,'interruptions_or_capture_errors':errors,'outbound_requests':dict(tr.wire_counts),
             'received_message_types':dict(tr.receive_counts),'raw_market_events':len(raw),'raw_envelope_bytes':byte_count,'raw_canonical_bytes':json_byte_count,
             'connection_epochs':tr.connection_epochs,'reconnects':0,
             'chronology':'ACTUAL_LOCAL_RECEIPT_SEQUENCE_UTC_AND_MONOTONIC;NO_DOM_SERVER_TIMESTAMP',
             'initialization_limit':'BOTH_SIDES_OBSERVED_IS_NOT_SERVER_CERTIFIED_COMPLETE_INITIAL_BOOK',
             'cloud_reproducible_observables':['RECEIVE_CALLBACK_ORDER','BID_ASK_PRICE_LEVELS','QUOTED_VOLUME_IN_UNITS','TOP_THREE_LEVEL_SUMS'],
             'cloud_parity_measured':False,'cloud_native_ids_or_deleted_quote_events':'NOT_EXPOSED_BY_MARKETDEPTHENTRY',
             'economic_pilot':False,'orders':0,'historical_requests':0,'protected_forward':False,
             'this_capture_future_return_testing_allowed':False,'gross_eur':None,'net_eur':None,'alpha_claim':False}
    summary['information_verdict']='SUPPORTED_FOR_SEPARATE_PROSPECTIVE_DIRECTIONAL_STUDY_DESIGN' if len(summaries)==3 and all(x.get('information',{}).get('verdict')=='DISTINCT_QUOTED_QUANTITY_OBSERVED_SUPPORTED_FOR_SEPARATE_STUDY_DESIGN' for x in summaries) else 'INFORMATION_SUPPORT_INSUFFICIENT_OR_PANEL_NOT_FULLY_DISTINCT'
    summary['periodic_heartbeat_stamps']=tr.heartbeat_stamps
    summary['periodic_heartbeat_count']=len(tr.heartbeat_stamps)
    summary['legacy_six_window_capability_requirement']='NOT_RUN_NOT_CERTIFIED_NOT_RELAXED'
    return {'summary':summary,'raw_market_envelopes':raw,'current_authenticated_metadata':metadata,'chronology_markers':markers,'private_transport_errors':tr.private_errors,'quantity_event_records':{str(sid):b.records for sid,b in books.items()},'fresh_complete_intervals_monotonic_ns':{str(sid):b.complete_intervals for sid,b in books.items()}}

def publish(head,auth,scope,partition,tmp,key,fp,full):
    full=e.w.old.crypto.strict_json(e.a.enc(full))
    path=PUB+'OWNER_DOM_INFORMATION_V1.json'
    status={'schema':e.w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'NOT_PERSISTED','failure_code':'NONE','run_id':int(os.environ['GITHUB_RUN_ID'])}
    release=e.w.old.api('releases',{'tag_name':'mxm-dom-information-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],
        'target_commitish':head,'name':'MXM encrypted DOM information qualification; no price response',
        'prerelease':True,'body':validate_public_blob(path,status).decode()})
    full.update(source_head=head,run_id=int(os.environ['GITHUB_RUN_ID']),prospective_partition=partition,scope=scope)
    out=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');out.release=release
    primary=out.encrypted(full,'dom-information-owner-result.mxmenc')
    loaded,proof=load_asset(key,fp,tmp,{'release_id':release['id'],'asset_id':primary['id'],'ciphertext_sha256':primary['ciphertext_sha256']})
    need(e.a.enc(loaded)==e.a.enc(full),'OWNER_REAL_READBACK_PARITY')
    summary=loaded['summary'];summary_sha=e.a.sha(e.a.enc(summary))
    envelope={'schema':'mxm.dom.information.verified.recipient.summary.v1','source_run':int(os.environ['GITHUB_RUN_ID']),
              'source_head':head,'original_primary':proof,'recipient_spki_sha256':auth['recipient_spki_sha256'],
              'summary_canonical_sha256':summary_sha,'summary':summary,'OWNER_READBACK_SUCCESS':True,
              'NUMERIC_SUCCESS':True,'numeric_kind':'INFORMATION_QUALIFICATION_COUNTERS_ONLY','DELIVERY_SUCCESS':False,
              'economic_pilot':False,'delivery_state':'PENDING_ACTUAL_RECIPIENT_READBACK'}
    delivered=e.upload_extra(release,tmp,e.a.ROOT/auth['recipient_public_path'],envelope,'dom-information-recipient-summary.mxmenc')
    attestation=out.encrypted({'schema':'mxm.dom.information.attestation.v1','primary':proof,'delivery':delivered,
                              'summary_canonical_sha256':summary_sha,'OWNER_READBACK_SUCCESS':True,
                              'recipient_readback_verified':False,'economic_pilot':False,'summary':summary},'dom-information-attestation.mxmenc')
    status.update(status='PASS',phase='FINAL',encrypted_artifact_name=delivered['name'],encrypted_artifact_sha256=delivered['ciphertext_sha256'])
    body=validate_public_blob(path,status);e.w.old.api('releases/'+str(release['id']),{'body':body.decode()},method='PATCH')
    need(e.w.old.api('releases/'+str(release['id']))['body'].encode()==body,'PUBLIC_STATUS_READBACK')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['owner_readback_completion_ref'],'sha':head})
    print(body.decode().strip(),flush=True)

def main():
    global PHASE
    os.umask(0o077);head,auth,scope,partition=gate()
    with tempfile.TemporaryDirectory(prefix='mxm-dom-information-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY_BINDING')
        synthetic=e.a.enc({'synthetic_only':True,'recipient':fp})
        synthetic_path=tmp/'owner-precontact-selftest.mxmenc'
        e.w.old.encrypt_shard(synthetic,public_key=e.a.ROOT/e.w.old.PUBLIC_KEY,output=synthetic_path)
        need(e.w.old.crypto.decrypt_package(synthetic_path.read_bytes(),private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)==synthetic,'OWNER_PRECONTACT_CRYPTO_ROUNDTRIP')
        synthetic_path.unlink()
        PHASE='ONE_DEVELOPMENT_INFORMATION_CAPTURE';full=capture(scope)
        PHASE='OWNER_AND_RECIPIENT_ENCRYPTED_PUBLICATION';publish(head,auth,scope,partition,tmp,key,fp,full)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
