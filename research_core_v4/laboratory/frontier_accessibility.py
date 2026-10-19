"""One current metadata census; no prices, history, outcome or trading requests."""
import base64,gzip,json,os,re,tempfile
from collections import Counter,defaultdict
from datetime import datetime,timezone
from . import frontier_pregate as b
from .common import need,encoded,digest,bytes_digest
from .custody import chunk_ciphertext,restore_ciphertext,atomic_publish
from .runtime import file_at
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack

PARENT='e8e751007d0300f0fa5a232f3e440deb6113aee7'
BRANCH='mxm-o04-successor-code-frontier-accessibility-r1'
WF='.github/workflows/mxm-frontier-accessibility.yml'
PREFIX='diagnostics/frontier-accessibility-20261019'
OUT=b.ROOT/'verification/frontier-accessibility'
PLAN='research_programs/reconciliation/FRONTIER_ACCESSIBILITY_20261019.json'
ALLOW={'ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq','ProtoOASymbolsListReq','ProtoOASymbolByIdReq'}

def projection(light,archived,historical,full,sample):
    def index(rows):
        result={}
        for row in rows:
            sid=int(row['symbolId']);need(sid not in result,'ACCESSIBILITY_DUPLICATE_SYMBOL');result[sid]=row
        return result
    current=index(light);old=index(archived);hist={r['symbol_id']:r for r in historical}
    need(len(hist)==len(historical),'ACCESSIBILITY_DUPLICATE_HISTORY')
    rows=[];classes=defaultdict(Counter)
    for sid,h in sorted(hist.items()):
        c=current.get(sid);a=old.get(sid)
        if c is not None and a is not None:state='CURRENT_AND_ARCHIVED_AMBIGUOUS'
        elif c is not None:
            if c.get('symbolName')!=h['symbol']:state='IDENTITY_NAME_CHANGED_OR_MISSING'
            elif c.get('enabled') is True:state='CURRENT_LISTED_ENABLED_NOT_EXECUTION_QUALIFIED'
            elif c.get('enabled') is False:state='CURRENT_LISTED_DISABLED'
            else:state='CURRENT_LISTED_ENABLED_FIELD_UNKNOWN'
        elif a is not None:state='ARCHIVED_ONLY_NOT_CURRENT'
        else:state='NOT_LISTED_IN_THIS_ACCOUNT_SNAPSHOT'
        row={'symbol_id':sid,'historical_symbol':h['symbol'],'historical_class':h['broker_native_context'],'historical_primary145':h['historical_primary145'],'state':state,'current_name':c.get('symbolName') if c else None}
        rows.append(row);classes[h['broker_native_context']][state]+=1
    fields=('digits','minVolume','stepVolume','maxVolume','commission','commissionType','minCommission','swapLong','swapShort','schedule','scheduleTimeZone','tradingMode')
    detail=[]
    for h in sample:
        sid=h['symbol_id'];f=full.get(str(sid));c=current.get(sid)
        detail.append({'symbol_id':sid,'historical_symbol':h['symbol'],'historical_class':h['broker_native_context'],'current_identity_name_match':bool(c and c.get('symbolName')==h['symbol']),
          'detail_present':f is not None,'field_presence':{k:k in f for k in fields} if f is not None else {},'historical_terms_certified':False,'EUR200_margin_certified':False})
    states=dict(Counter(r['state'] for r in rows))
    summary={'historical_identities':len(hist),'historical_primary145':sum(r['historical_primary145'] for r in historical),'historical_class_counts':{k:dict(v) for k,v in sorted(classes.items())},
      'historical_accessibility_states':states,'current_list_count':len(current),'archived_list_count':len(old),'current_ids_outside_historical_roster':len(set(current)-set(hist)),
      'current_ids_with_same_historical_name':sum(current[sid].get('symbolName')==hist[sid]['symbol'] for sid in set(current)&set(hist)),
      'sample_current_detail_support':detail,'current_reference_not_historical_authority':True,'list_enabled_is_execution_or_liquidity_proof':False,
      'historical_frontier_is_permanent_cap':False,'new_current_ids_are_economically_qualified':False,'new_economic_outcomes':0}
    return {'summary':summary,'historical_membership_join':rows}

def anchors(route):
    b.SOURCE_BRANCH=BRANCH;b.anchors(route)

def worker():
    need(os.environ['GITHUB_JOB']=='census' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_REPOSITORY']==b.old.REPO and os.environ['GITHUB_REF_NAME']==b.old.BRANCH,'ACCESSIBILITY_WORKLOAD')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'ACCESSIBILITY_NO_APP_KEY')
    route=GetOnly();anchors(route);plan=strict_json((b.ROOT/PLAN).read_bytes())
    need(plan['budget']=={'native_invocations':1,'symbol_list_requests':1,'symbol_detail_batches':1,'detail_symbols_max':29,'history_requests':0,'price_requests':0,'orders':0,'new_economic_identities':0,'new_outcomes':0,'automatic_retries':0},'ACCESSIBILITY_FINITE_BUDGET')
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'ACCESSIBILITY_PARENT')
    runs=route.json('actions/runs?per_page=100')['workflow_runs'];own=[r for r in runs if r['path']==WF]
    need(len(own)==1 and own[0]['id']==int(os.environ['GITHUB_RUN_ID']),'ACCESSIBILITY_SINGLE_INVOCATION')
    need(not any(r['id']!=int(os.environ['GITHUB_RUN_ID']) and r['status'] in ('queued','in_progress','waiting','pending') and r['path'] in (WF,'.github/workflows/mxm-integrated-laboratory.yml','.github/workflows/mxm-typed-admission-proof.yml') for r in runs),'ACCESSIBILITY_CONCURRENT_RESEARCH')
    original=file_at(route,'program-state.json',PARENT);s=strict_json(original);need(s['sequence']==16 and s['pending'] is None and s['safe_stop'],'ACCESSIBILITY_ORIGINAL_STATE')
    metadata=strict_json((b.ROOT/'research_core_v4/master_frontier_v1/MACHINE_METADATA_RECONCILIATION_RESULT_V1.json').read_bytes(),max_elements=8000000)
    history=metadata['frontier_membership'];sample=plan['fixed_sample'];need(len(history)==1576 and sum(h['historical_primary145'] for h in history)==145 and len(sample)==29,'ACCESSIBILITY_ROSTER')
    prior_sample=strict_json(file_at(route,'research_programs/reconciliation/FRONTIER_SUPPORT_PREGATE_B.json','ac4c24e11c04e77be5c94fc176d02a23e9d1207a'))['sample'];need(sample==prior_sample,'ACCESSIBILITY_SAMPLE_NOT_RETURN_SELECTED')
    from m6.ctrader_transport import StdlibCTraderTransport
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,encrypt_shard,public_spki_sha256
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from google.protobuf.json_format import MessageToDict
    class MetadataTransport(StdlibCTraderTransport):
        counts=Counter();last_metadata=None
        def request(self,req,**kwargs):
            name=type(req).__name__;need(name in ALLOW,'ACCESSIBILITY_REQUEST_ALLOWLIST')
            cap=1;need(self.counts[name]<cap and sum(self.counts.values())<5,'ACCESSIBILITY_WIRE_CAP')
            self.counts[name]+=1;return super().request(req,**kwargs)
        def receive_envelope(self,*,deadline):
            env=super().receive_envelope(deadline=deadline)
            if int(env.payloadType) in (int(m.ProtoOASymbolsListRes().payloadType),int(m.ProtoOASymbolByIdRes().payloadType)):self.last_metadata=env
            return env
    os.umask(0o077);OUT.mkdir(parents=True,exist_ok=True);receipts=[];tr=None;result=None;failure=None;auth='NOT_ATTEMPTED';full={};light=[];archived=[]
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        tmp=b.Path(td);key,fp=_private_key_from_secret(tmp);need(fp==b.old.FP,'ACCESSIBILITY_OWNER_KEY')
        try:
            creds=[os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')];need(all(creds),'ACCESSIBILITY_EXISTING_CREDENTIALS_MISSING')
            tr=MetadataTransport(connect_timeout=15,response_timeout=25);tr.connect();aid=authenticate_segment(tr,*creds);auth='EXPLICIT_VIEW_EXACT_EXISTING_LIVE_ACCOUNT_FINGERPRINT'
            def capture(req,klass):
                start=datetime.now(timezone.utc).isoformat();res=tr.request(req,timeout=25);end=datetime.now(timezone.utc).isoformat()
                if isinstance(res,m.ProtoOAErrorRes):
                    receipts.append({'request_type':type(req).__name__,'request_b64':base64.b64encode(req.SerializeToString()).decode(),'response_b64':base64.b64encode(res.SerializeToString()).decode(),'start_utc':start,'end_utc':end})
                    need(False,'ACCESSIBILITY_PROVIDER_ERROR')
                need(isinstance(res,klass) and res.IsInitialized() and int(res.ctidTraderAccountId)==aid,'ACCESSIBILITY_NATIVE_RESPONSE_BINDING')
                env=tr.last_metadata;need(env is not None and env.payload==res.SerializeToString() and env.clientMsgId==f'mxm-{tr._sequence:012d}','ACCESSIBILITY_RAW_ENVELOPE_BINDING')
                receipts.append({'request_type':type(req).__name__,'request_b64':base64.b64encode(req.SerializeToString()).decode(),'response_envelope_b64':base64.b64encode(env.SerializeToString()).decode(),'start_utc':start,'end_utc':end})
                return res
            req=m.ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=True);res=capture(req,m.ProtoOASymbolsListRes)
            plain=lambda x:MessageToDict(x,preserving_proto_field_name=True,use_integers_for_enums=True)
            light=[plain(x) for x in res.symbol];archived=[plain(x) for x in res.archivedSymbol]
            cmap={int(x['symbolId']):x for x in light};ids=sorted(h['symbol_id'] for h in sample if cmap.get(h['symbol_id'],{}).get('symbolName')==h['symbol'])
            if ids:
                req=m.ProtoOASymbolByIdReq(ctidTraderAccountId=aid);req.symbolId.extend(ids);res=capture(req,m.ProtoOASymbolByIdRes)
                full={str(x.symbolId):plain(x) for x in res.symbol};need(len(full)==len(res.symbol) and set(map(int,full))<=set(ids),'ACCESSIBILITY_DETAIL_SCOPE')
            result=projection(light,archived,history,full,sample)
        except Exception as e:
            # No automatic credential renewal, reconnect, provider retry or broadened scope.
            code=str(e);failure=code if re.fullmatch(r'LAB_[A-Z0-9_]+',code) else type(e).__name__
        finally:
            if tr is not None:tr.close()
        counts=dict(tr.counts) if tr is not None else {};state='CURRENT_METADATA_CENSUS_COMPLETE' if result is not None else 'CURRENT_METADATA_CENSUS_UNRESOLVED'
        receipt={'schema':'mxm.frontier-current-accessibility-public.v1','source_sha':os.environ['PREGATE_SOURCE_SHA'],'trigger_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
          'parent_evidence':PARENT,'original_state_sha256':bytes_digest(original),'state':state,'failure_class':failure,'authentication':auth,'wire_counts':counts,
          'summary':result['summary'] if result else None,'new_reservations':0,'new_outcomes':0,'history_requests':0,'price_requests':0,'orders':0,'confirmation_opened':False,'safe_stop':True,
          'B_budget_reset':False,'historical_costs_certified':False,'EUR200_margin_certified':False,'economic_admission_released':False,'metadata_is_protected_forward_price_data':False}
        private={'receipt':receipt,'raw_metadata_receipts':receipts,'current_light':light,'current_archived':archived,'sample_full_details':full,'projection':result,'plan_sha256':digest(plan)}
        raw=encoded(private);need(len(raw)<=16*1024*1024,'ACCESSIBILITY_DATA_CAP');pub=b.ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(pub)==b.old.FP,'ACCESSIBILITY_RECIPIENT')
        target=OUT/'result.mxmenc';encrypt_shard(gzip.compress(raw,mtime=0),public_key=pub,output=target);need(unpack(owner.bounded_decrypt(target.read_bytes(),key,tmp))==raw,'ACCESSIBILITY_ENCRYPTED_READBACK')
    anchors(route);receipt['ciphertext_sha256']=bytes_digest(target.read_bytes());(OUT/'receipt.json').write_bytes(encoded(receipt));print('MXM_ACCESSIBILITY_RESULT '+json.dumps(receipt,sort_keys=True))

def publish():
    need(os.environ['GITHUB_JOB']=='durable-census' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ.get('NATIVE_CENSUS_RESULT')=='success','ACCESSIBILITY_NATIVE_DEPENDENCY')
    need(not any(os.environ.get(k) for k in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY','CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),'ACCESSIBILITY_KEYLESS_WRITER')
    route=GetOnly();anchors(route);d=b.ROOT/'verification/accessibility-input';r=strict_json((d/'receipt.json').read_bytes());blob=(d/'result.mxmenc').read_bytes()
    need(r['source_sha']==os.environ['PREGATE_SOURCE_SHA'] and r['trigger_sha']==os.environ['GITHUB_SHA'] and r['run_id']==int(os.environ['GITHUB_RUN_ID']) and r['parent_evidence']==PARENT,'ACCESSIBILITY_ARTIFACT_BINDING')
    need(all(r[k]==0 for k in ('new_reservations','new_outcomes','history_requests','price_requests','orders')) and not r['confirmation_opened'] and not r['B_budget_reset'],'ACCESSIBILITY_SCOPE')
    need(bytes_digest(blob)==r['ciphertext_sha256'] and blob.startswith(b'MXM_SHALLOW_M5_V2_ENC1\x00'),'ACCESSIBILITY_CIPHER')
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'ACCESSIBILITY_PUBLISH_PARENT')
    original=file_at(route,'program-state.json',PARENT);need(bytes_digest(original)==r['original_state_sha256'],'ACCESSIBILITY_ORIGINAL_BINDING')
    files,manifest=chunk_ciphertext(blob,PREFIX);files[PREFIX+'/checkpoint.parts.json']=encoded(manifest);files[PREFIX+'/receipt.json']=encoded(r)
    oid=atomic_publish(route,PARENT,files,'Preserve finite current metadata accessibility census; no prices, history, economics or checkpoint16 mutation')
    need(file_at(route,'program-state.json',oid)==original and restore_ciphertext(strict_json(file_at(route,PREFIX+'/checkpoint.parts.json',oid)),lambda p:file_at(route,p,oid))==blob,'ACCESSIBILITY_REMOTE_READBACK');anchors(route)
    print(json.dumps({'state':'CURRENT_METADATA_CENSUS_DURABLE','evidence_oid':oid,'census_state':r['state'],'new_outcomes':0,'ciphertext_sha256':r['ciphertext_sha256']}))

if __name__=='__main__':
    import sys
    try:
        need(len(sys.argv)==2 and sys.argv[1] in ('worker','publish'),'ACCESSIBILITY_MODE');worker() if sys.argv[1]=='worker' else publish()
    except Exception as e:
        code=str(e);print(json.dumps({'state':'ACCESSIBILITY_SAFE_STOP','failure_class':code if re.fullmatch(r'LAB_[A-Z0-9_]+',code) else type(e).__name__}));raise SystemExit(1) from None
