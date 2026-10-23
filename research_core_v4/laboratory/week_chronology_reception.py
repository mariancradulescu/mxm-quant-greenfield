"""Finite VIEW-only chronological transport reception, not economic research.

One prospectively fixed complete ISO UTC development week; raw native messages are
encrypted to the existing recipient. Separate existing custody job redecodes
them. Neither job can publish authority, trade, or evaluate a strategy.
"""
import base64,gzip,json,os,re,subprocess,tempfile,time
from pathlib import Path
from .common import need,encoded,bytes_digest
from .broker_access_reception import ENGINE,ENGINE_MODULE,REPO,BRANCH,SECRET_NAMES,AUTH_TYPES
from .runtime import module_digest,SOURCE_BRANCH,file_at,AUTHORITY
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack

PATH='.github/workflows/mxm-week-chronology-reception.yml'
SOURCE_REF='mxm-week-chronology-code-20261023'
NATIVE_SOURCE='d2fae5641b759b1c8c24161d83d62d39e104eafd'
MODULE='research_core_v4/laboratory/week_chronology_reception.py'
OUT=Path('verification/week-chronology')
# One DEVELOPMENT transport pilot, no candidate/instrument selection claim.
# ISO 2026-W37: Monday 7 Sep inclusive .. Monday 14 Sep exclusive UTC.
POLICY={'schema':'mxm.week-chronology-policy.v1','symbol_id':1,'symbol_name':'EURUSD',
 'from_ms':1788739200000,'to_ms':1789344000000,'history_request_cap':4096,
 'max_private_bytes':120_000_000,'max_wire_bytes':70_000_000,
 'max_collection_seconds':1200,'minimum_quote_events':10000,'orders':0,'economic_outcomes':0,
 'scope':'DEVELOPMENT_TRANSPORT_ONLY','automatic_retry':False,
 'iso_week':'2026-W37','strategy_trials':0,'confirmation_opened':False}
CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'
UPLOAD='actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
DOWNLOAD='actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093'
INSTALL='python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock'

def build_workflow(source):
    need(re.fullmatch('[a-f0-9]{40}',source or ''),'WEEK_SOURCE')
    def job(name,environment):
        steps=[{'uses':CHECKOUT,'with':{'ref':NATIVE_SOURCE,'persist-credentials':False}},
          {'uses':CHECKOUT,'with':{'ref':source,'path':'.week-code','persist-credentials':False}},
          {'run':INSTALL},
          {'run':'cp .week-code/'+MODULE+' '+MODULE}]
        if name=='chronology-cold':
            steps.append({'uses':DOWNLOAD,'with':{'name':'week-chronology-${{ github.run_id }}','path':str(OUT)}})
        env={'GH_TOKEN':'${{ github.token }}','LAB_CHRONOLOGY_SOURCE':source}
        if name=='chronology-collect':env.update({k:'${{ secrets.'+k+' }}' for k in SECRET_NAMES})
        else:env['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']='${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'
        steps.append({'run':'python3 -m research_core_v4.laboratory.week_chronology_reception '+name,'env':env})
        steps.append({'uses':UPLOAD,'if':'always()','with':{
          'name':('week-chronology-' if name=='chronology-collect' else 'week-chronology-cold-')+'${{ github.run_id }}',
          'path':str(OUT)+'/capture.mxmenc\n'+str(OUT)+'/producer.json' if name=='chronology-collect' else str(OUT)+'/cold.json',
          'if-no-files-found':'error','retention-days':90}})
        result={'runs-on':'ubuntu-24.04','timeout-minutes':25,'environment':environment,
          'permissions':{'contents':'read','actions':'read'},'steps':steps}
        if name=='chronology-cold':result.update(needs='chronology-collect',**{'if':'always()'})
        else:result['if']="github.repository == '"+REPO+"' && github.ref == 'refs/heads/"+BRANCH+"' && github.run_attempt == 1"
        return result
    return {'name':'MXM one complete ISO week VIEW chronology acquisition',
      'on':{'push':{'branches':[BRANCH],'paths':[PATH]},'workflow_dispatch':{}},
      'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},
      'jobs':{'chronology-collect':job('chronology-collect','mxm-r3-pepperstone-v1'),
              'chronology-cold':job('chronology-cold','mxm-r3-custody-v1')}}

def one_shot_history(value,run_id):
    need(value['total_count']==len(value['workflow_runs'])==1 and
         value['workflow_runs'][0]['id']==run_id and
         value['workflow_runs'][0]['run_attempt']==1,'WEEK_ONE_SHOT_ALREADY_STARTED')

def verify_refs(route,source,trigger):
    expected={SOURCE_BRANCH:ENGINE,BRANCH:trigger,SOURCE_REF:source,
      'mxm-o04-active-v1':AUTHORITY,
      'mxm-o04-accepted-owner-1807-v1':'a830c132521bd4348454653f713e04f6107484fe'}
    for name,sha in expected.items():
        need(route.json('git/ref/heads/'+name)['object']['sha']==sha,'WEEK_SOURCE_OR_AUTHORITY_REF_MOVED')

def context(route,phase):
    source=os.environ.get('LAB_CHRONOLOGY_SOURCE','');trigger=os.environ.get('GITHUB_SHA','')
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and
      os.environ.get('GITHUB_EVENT_NAME') in ('push','workflow_dispatch') and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
      os.environ.get('GITHUB_JOB')==phase and os.environ.get('GITHUB_WORKFLOW_SHA')==trigger and
      os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH and
      re.fullmatch('[a-f0-9]{40}',source) and re.fullmatch('[a-f0-9]{40}',trigger),'WEEK_NATIVE_CONTEXT')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY') and not os.environ.get('R3_CTRADER_REFRESH_TOKEN'),
      'WEEK_NO_WRITER_OR_REFRESH_KEY')
    forbidden=('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM') if phase=='chronology-collect' else SECRET_NAMES
    need(not any(os.environ.get(k) for k in forbidden+('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),
      'WEEK_ROLE_ISOLATION')
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==NATIVE_SOURCE and
      subprocess.check_output(['git','-C','.week-code','rev-parse','HEAD'],text=True).strip()==source and
      subprocess.run(['git','diff','--quiet','HEAD','--'],capture_output=True).returncode==0 and
      subprocess.run(['git','-C','.week-code','diff','--quiet','HEAD','--'],capture_output=True).returncode==0 and
      Path(MODULE).read_bytes()==Path('.week-code',MODULE).read_bytes() and
      module_digest()==ENGINE_MODULE,'WEEK_UNMODIFIED_PINNED_CODE_AND_NATIVE_ENGINE')
    verify_refs(route,source,trigger)
    need(strict_json(file_at(route,PATH,trigger))==build_workflow(source),'WEEK_WORKFLOW_CHANGED')
    run_id=int(os.environ['GITHUB_RUN_ID'])
    one_shot_history(route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100'),run_id)
    return {'source_sha':source,'native_decoder_source_sha':NATIVE_SOURCE,'engine_source_sha':ENGINE,
      'trigger_sha':trigger,'run_id':run_id,'attempt':1}

def decode_record(record,account):
    from m6.ctrader_transport import decode_envelope,extract_payload
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    req_type=record['request_type'];klass=getattr(m,req_type)
    req=klass.FromString(base64.b64decode(record['request_b64'],validate=True))
    request_envelope=decode_envelope(base64.b64decode(record['request_envelope_b64'],validate=True))
    need(request_envelope.payload==req.SerializeToString() and
         int(request_envelope.payloadType)==int(req.payloadType) and
         re.fullmatch(r'mxm-[0-9]{12}',request_envelope.clientMsgId),'CHRONOLOGY_REQUEST_WIRE_BINDING')
    need(req.IsInitialized() and req.ctidTraderAccountId==account,'CHRONOLOGY_REQUEST_ACCOUNT')
    envelope=decode_envelope(base64.b64decode(record['response_envelope_b64'],validate=True))
    need(envelope.clientMsgId==request_envelope.clientMsgId,'CHRONOLOGY_RESPONSE_WIRE_CORRELATION')
    res=extract_payload(envelope)
    need(res.IsInitialized() and getattr(res,'ctidTraderAccountId',None)==account,'CHRONOLOGY_RESPONSE_ACCOUNT')
    need(req_type in ('ProtoOASymbolsListReq','ProtoOASymbolByIdReq','ProtoOAGetTickDataReq'),
         'CHRONOLOGY_READ_ONLY_RECEIPT')
    return req,res

def decode_ticks(req,res):
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    from m6.cost_evidence import decode_ctrader_tick_page
    need(isinstance(res,m.ProtoOAGetTickDataRes) and res.HasField('hasMore'),'CHRONOLOGY_TICK_TYPE_HASMORE')
    rows=decode_ctrader_tick_page([{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in res.tickData])
    need(all(req.fromTimestamp<=r.timestamp_ms<=req.toTimestamp and r.raw_tick>0 for r in rows),
         'CHRONOLOGY_TICK_WINDOW_PRICE')
    return [(r.timestamp_ms,r.raw_tick) for r in rows]

def split_collect(send,account,side,lo,hi,remaining):
    """Inclusive disjoint children preserve same-ms revisions; never page by -1 tick."""
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    stack=[(lo,hi)];tree=[]
    while stack:
        if remaining()==0:
            tree.extend({'lo':a,'hi':b,'state':'REQUEST_CAP_UNRESOLVED'} for a,b in reversed(stack));break
        a,b=stack.pop();req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=POLICY['symbol_id'],
            type=side,fromTimestamp=a,toTimestamp=b)
        index,res=send(req);rows=decode_ticks(req,res)
        node={'lo':a,'hi':b,'receipt_index':index,'state':'LEAF_COMPLETE'};tree.append(node)
        if res.hasMore:
            if a==b:node['state']='SAME_MS_TRUNCATION_UNRESOLVED';continue
            mid=(a+b)//2;node['state']='SPLIT';stack.extend([(mid+1,b),(a,mid)])
    return tree

def verify_tree(tree,receipts,account,side):
    pending=[(POLICY['from_ms'],POLICY['to_ms']-1)];rows=[];used=[];complete=True
    for node in tree:
        need(pending and pending.pop()==(node['lo'],node['hi']),'CHRONOLOGY_TREE_GAP_OR_OVERLAP')
        if node['state']=='REQUEST_CAP_UNRESOLVED':complete=False;continue
        index=node['receipt_index'];need(type(index) is int and 0<=index<len(receipts),'CHRONOLOGY_RECEIPT_INDEX')
        used.append(index);req,res=decode_record(receipts[index],account)
        need(type(req).__name__=='ProtoOAGetTickDataReq' and req.symbolId==POLICY['symbol_id'] and req.type==side and
             req.fromTimestamp==node['lo'] and req.toTimestamp==node['hi'],'CHRONOLOGY_TREE_REQUEST_BINDING')
        ticks=decode_ticks(req,res)
        if node['state']=='SPLIT':
            need(res.hasMore and node['lo']<node['hi'],'CHRONOLOGY_FALSE_SPLIT')
            mid=(node['lo']+node['hi'])//2;pending.extend([(mid+1,node['hi']),(node['lo'],mid)])
        elif node['state']=='SAME_MS_TRUNCATION_UNRESOLVED':
            need(res.hasMore and node['lo']==node['hi'],'CHRONOLOGY_FALSE_SAME_MS_FAILURE');complete=False
        else:
            need(node['state']=='LEAF_COMPLETE' and not res.hasMore,'CHRONOLOGY_INCOMPLETE_LEAF')
            rows.extend(ticks)
    need(not pending and len(used)==len(set(used)),'CHRONOLOGY_TREE_INCOMPLETE_OR_REUSED')
    need(all(a[0]<=b[0] for a,b in zip(rows,rows[1:])),'CHRONOLOGY_NOT_ORDERED')
    return rows,complete,used

def replay(private):
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    from research_core_v4.shallow_m5_support_v2_production import _fingerprint,ACCOUNT_FINGERPRINT_SHA256
    need(private['capture_complete'] is True and private['policy']==POLICY and tuple(private['auth_requests'])==AUTH_TYPES and
         _fingerprint(private['account'])==ACCOUNT_FINGERPRINT_SHA256,'CHRONOLOGY_AUTH_POLICY')
    receipts=private['receipts'];account=private['account']
    need(2<=len(receipts)<=POLICY['history_request_cap']+2,'CHRONOLOGY_REQUEST_CAP')
    wire_bytes=sum(len(base64.b64decode(row[key],validate=True)) for row in receipts
                   for key in ('request_envelope_b64','response_envelope_b64'))
    need(wire_bytes<=POLICY['max_wire_bytes'],'CHRONOLOGY_RAW_WIRE_CAP')
    req,res=decode_record(receipts[0],account)
    need(isinstance(req,m.ProtoOASymbolsListReq) and isinstance(res,m.ProtoOASymbolsListRes),
         'CHRONOLOGY_NATIVE_SYMBOL_CATALOGUE')
    symbols=[s for s in res.symbol if s.symbolId==POLICY['symbol_id']]
    need(len(symbols)==1 and symbols[0].symbolName==POLICY['symbol_name'],'CHRONOLOGY_NATIVE_SYMBOL_NAME')
    req,res=decode_record(receipts[1],account)
    need(isinstance(req,m.ProtoOASymbolByIdReq) and list(req.symbolId)==[POLICY['symbol_id']] and
         isinstance(res,m.ProtoOASymbolByIdRes) and len(res.symbol)==1 and
         res.symbol[0].symbolId==POLICY['symbol_id'] and res.symbol[0].HasField('digits'),
         'CHRONOLOGY_NATIVE_METADATA')
    from .common import DEVELOPMENT_END_MS
    need(POLICY['to_ms']<=DEVELOPMENT_END_MS,'CHRONOLOGY_PROTECTED_FORWARD')
    bid,bc,bu=verify_tree(private['trees']['BID'],receipts,account,1)
    ask,ac,au=verify_tree(private['trees']['ASK'],receipts,account,2)
    need(len(bu+au)==len(set(bu+au)) and set(bu+au)==set(range(2,len(receipts))),
         'CHRONOLOGY_EXACT_RECEIPT_INVENTORY')
    # Event replay preserves within-side order. Cross-side same-ms ordering is
    # explicitly unknown; it is never turned into an executable price path.
    started=time.monotonic();i=j=events=ambiguous=0;last_bid=last_ask=None;crossed=0
    while i<len(bid) or j<len(ask):
        stamp=min(bid[i][0] if i<len(bid) else 2**63,ask[j][0] if j<len(ask) else 2**63)
        b0=i;a0=j
        while i<len(bid) and bid[i][0]==stamp:last_bid=bid[i][1];i+=1
        while j<len(ask) and ask[j][0]==stamp:last_ask=ask[j][1];j+=1
        events+=(i-b0)+(j-a0)
        ambiguous+=int(i>b0 and j>a0)
        if last_bid is not None and last_ask is not None:crossed+=int(last_ask<last_bid)
    seconds=time.monotonic()-started
    return {'provider_window_complete':bc and ac,'bid_events':len(bid),'ask_events':len(ask),
            'chronological_events_processed':events,'chronological_seconds':seconds,
            'events_per_second':events/max(seconds,1e-9),'same_ms_cross_side_order_unknown':ambiguous,
            'crossed_causal_snapshots':crossed,'history_requests':len(receipts)-2,'metadata_requests':2,
            'window_ms':POLICY['to_ms']-POLICY['from_ms'],'first_bid_ms':bid[0][0] if bid else None,
            'last_bid_ms':bid[-1][0] if bid else None,'first_ask_ms':ask[0][0] if ask else None,
            'last_ask_ms':ask[-1][0] if ask else None,'orders':0,'economic_outcomes':0,
            'requested_complete_iso_utc_weeks':1,'hard21_proven':False,'continuous_market_coverage_proven':False,'historical_arrival_times_proven':False,
            'dated_costs_proven':False,'economic_engine_throughput_measured':False,
            'economic_fidelity_accepted':False,'research_capability_accepted':False}

def collect(identity):
    from m6.ctrader_transport import StdlibCTraderTransport,decode_envelope
    from m6.ctrader_proto import OpenApiMessages_pb2 as m
    from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,encrypt_shard,public_spki_sha256
    from research_core_v4.successor_c_20261018.readback import FP
    from .runtime import ROOT
    private={'schema':'mxm.week-native-chronology-private.v1','identity':identity,'policy':POLICY,
             'receipts':[],'trees':{},'auth_requests':[]}
    class Wire(StdlibCTraderTransport):
        envelope=None;receipt=None;request_payload_type=None
        def _send_bytes(self,frame):
            if self.receipt is not None:
                e=decode_envelope(frame[4:])
                if int(e.payloadType)==self.request_payload_type:
                    need('request_envelope_b64' not in self.receipt,'CHRONOLOGY_NO_SECOND_SEND')
                    self.receipt['request_envelope_b64']=base64.b64encode(e.SerializeToString()).decode()
                    self.receipt['client_msg_id']=e.clientMsgId
            return super()._send_bytes(frame)
        def receive_envelope(self,*,deadline):
            e=super().receive_envelope(deadline=deadline)
            if self.receipt is not None and e.clientMsgId==self.receipt.get('client_msg_id'):
                self.envelope=e
            return e
        def request(self,request,**kw):
            name=type(request).__name__
            if name in AUTH_TYPES:
                need(len(private['auth_requests'])<3 and name==AUTH_TYPES[len(private['auth_requests'])],
                     'CHRONOLOGY_AUTH_SEQUENCE');private['auth_requests'].append(name)
            else:
                need(len(private['auth_requests'])==3 and name in ('ProtoOASymbolsListReq','ProtoOASymbolByIdReq','ProtoOAGetTickDataReq'),
                     'CHRONOLOGY_WIRE_READ_ONLY')
            return super().request(request,**kw)
    transport=Wire();history_count=0;last_send=0.0;wire_bytes=0;collection_started=time.monotonic()
    def send(req):
        nonlocal history_count,last_send,wire_bytes
        if type(req).__name__=='ProtoOAGetTickDataReq':
            need(history_count<POLICY['history_request_cap'],'CHRONOLOGY_HISTORY_CAP')
            need(time.monotonic()-collection_started<POLICY['max_collection_seconds'],'WEEK_TIME_CAP')
            time.sleep(max(0,0.22-(time.monotonic()-last_send)));last_send=time.monotonic();history_count+=1
        row={'request_type':type(req).__name__,'request_b64':base64.b64encode(req.SerializeToString()).decode(),
             'state':'SENT_OR_ACK_UNKNOWN'}
        private['receipts'].append(row);transport.envelope=None;transport.receipt=row;transport.request_payload_type=int(req.payloadType)
        try:
            res=transport.request(req,timeout=30)
            need(transport.envelope is not None,'CHRONOLOGY_RAW_NATIVE_RESPONSE_REQUIRED')
            row.update(response_envelope_b64=base64.b64encode(transport.envelope.SerializeToString()).decode(),state='RECEIVED')
            wire_bytes+=len(base64.b64decode(row['request_envelope_b64']))+len(transport.envelope.SerializeToString())
            need(wire_bytes<=POLICY['max_wire_bytes'],'CHRONOLOGY_RAW_WIRE_CAP')
            return len(private['receipts'])-1,res
        finally:transport.receipt=None;transport.request_payload_type=None
    try:
        need(all(os.environ.get(k) for k in SECRET_NAMES),'CHRONOLOGY_EXISTING_CREDENTIALS')
        values=tuple(os.environ.pop(k) for k in SECRET_NAMES);transport.connect()
        private['account']=authenticate_segment(transport,*values);values=None
        send(m.ProtoOASymbolsListReq(ctidTraderAccountId=private['account']))
        send(m.ProtoOASymbolByIdReq(ctidTraderAccountId=private['account'],symbolId=[POLICY['symbol_id']]))
        for name,side in (('BID',1),('ASK',2)):
            private['trees'][name]=split_collect(send,private['account'],side,POLICY['from_ms'],POLICY['to_ms']-1,
                lambda:POLICY['history_request_cap']-history_count)
        private['capture_complete']=True
    except Exception as error:
        private['capture_complete']=False;private['failure_class']=type(error).__name__
        raise
    finally:
        transport.close();values=None
        for key in SECRET_NAMES:os.environ.pop(key,None)
        raw=encoded(private);need(len(raw)<=POLICY['max_private_bytes'],'CHRONOLOGY_PRIVATE_SIZE_CAP')
        public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
        need(public_spki_sha256(public)==FP,'CHRONOLOGY_EXISTING_RECIPIENT')
        encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=OUT/'capture.mxmenc')
    result=replay(private);result['collection_seconds']=time.monotonic()-collection_started
    return result

def cold(route,identity):
    # Require the actual producer checkout and native job identity before key access.
    run_id=identity['run_id'];jobs=route.json('actions/runs/'+str(run_id)+'/attempts/1/jobs?per_page=100')
    need(jobs['total_count']==len(jobs['jobs'])==2,'CHRONOLOGY_NATIVE_JOB_INVENTORY')
    producer=[j for j in jobs['jobs'] if j['name']=='chronology-collect']
    need(len(producer)==1 and producer[0]['run_id']==run_id and producer[0]['status']=='completed',
         'CHRONOLOGY_NATIVE_PRODUCER_TERMINAL')
    job=producer[0];steps=job['steps']
    need(len([s for s in steps if s['name']=='Run '+CHECKOUT and s['conclusion']=='success'])==2,
         'CHRONOLOGY_NATIVE_CHECKOUT_STEP')
    log=route.data('actions/jobs/'+str(job['id'])+'/logs').decode('utf-8')
    need(identity['source_sha'] in log and NATIVE_SOURCE in log and "git log -1 --format=%H" in log,
         'CHRONOLOGY_NATIVE_CHECKOUT_LOG')
    producer=strict_json((OUT/'producer.json').read_bytes())
    need(job['conclusion']=='success' and producer['accepted'] is True and
         all(producer[k]==v for k,v in identity.items()) and producer['policy']==POLICY and
         producer['ciphertext_sha256']==bytes_digest((OUT/'capture.mxmenc').read_bytes()) and
         'MXM_WEEK_CHRONOLOGY '+json.dumps(producer,sort_keys=True) in log,
         'WEEK_NATIVE_PRODUCER_RECEIPT_AND_CIPHER')
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    started=time.monotonic()
    with tempfile.TemporaryDirectory() as folder:
        tmp=Path(folder);key,fp=_private_key_from_secret(tmp)
        need(fp==FP,'CHRONOLOGY_COLD_RECIPIENT')
        raw=unpack(owner.bounded_decrypt((OUT/'capture.mxmenc').read_bytes(),key,tmp))
        need(len(raw)<=POLICY['max_private_bytes'],'CHRONOLOGY_COLD_SIZE')
        private=strict_json(raw,max_elements=8_000_000)
        need(private['identity']==identity,'CHRONOLOGY_COLD_IDENTITY')
        result=replay(private)
    result.update(native_producer_job_id=job['id'],native_producer_conclusion=job['conclusion'],
                  independently_redecoded=True,private_sha256=bytes_digest(raw),
                  cold_decrypt_decode_verify_seconds=time.monotonic()-started)
    return result

def main(phase):
    OUT.mkdir(parents=True,exist_ok=True);os.umask(0o077)
    result={'schema':'mxm.week-native-chronology-public.v1','phase':phase,'accepted':False,
            'orders':0,'economic_outcomes':0,'research_capability_accepted':False,'policy':POLICY}
    try:
        route=GetOnly();identity=context(route,phase);result.update(identity)
        result.update(collect(identity) if phase=='chronology-collect' else cold(route,identity))
        result['ciphertext_sha256']=bytes_digest((OUT/'capture.mxmenc').read_bytes())
        result['accepted']=(result['provider_window_complete'] and result['bid_events']>0 and
            result['ask_events']>0 and result['chronological_events_processed']>=POLICY['minimum_quote_events'])
        if phase=='chronology-cold':
            result['accepted']=result['accepted'] and result['native_producer_conclusion']=='success'
    except Exception as error:
        result['failure_class']=type(error).__name__
        if type(error).__name__=='LabError' and re.fullmatch('[A-Z][A-Z0-9_]{2,100}',str(error)):
            result['failure_code']=str(error)
    finally:
        (OUT/('producer.json' if phase=='chronology-collect' else 'cold.json')).write_bytes(encoded(result))
        print('MXM_WEEK_CHRONOLOGY '+json.dumps(result,sort_keys=True),flush=True)
    return 0 if result['accepted'] else 1

if __name__=='__main__':
    import sys
    need(len(sys.argv)==2 and sys.argv[1] in ('chronology-collect','chronology-cold'),'CHRONOLOGY_PHASE')
    raise SystemExit(main(sys.argv[1]))
