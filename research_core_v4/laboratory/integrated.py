"""Forward integration of the existing laboratory; original checkpoint is read-only.

The same Laboratory, TypedTrialBook, catalogue, crypto and atomic publisher are
used for preflight, claim, worker, publication, cold restart and native handoff.
"""
import base64,gzip,json,os,re,tempfile,urllib.error,urllib.request
from pathlib import Path
from .common import need,encoded,digest,bytes_digest
from .protocol import *
from .admission import TypedTrialBook
from .programs import Laboratory
from .data import DataCatalogue
from .execution import bind_native,preserve_node
from .budgets import historical_accounting
from .runtime import ROOT,anchors,file_at,module_digest,EVIDENCE_BRANCH
from .custody import atomic_publish,chunk_ciphertext,restore_ciphertext
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack

WF='.github/workflows/mxm-integrated-p0.yml'
TRIGGER='research_programs/admissions/EXECUTE_INTEGRATED_P0.json'
OUT=ROOT/'verification/integrated-p0'
INPUT=ROOT/'verification/integrated-p0-input'
AUTH='07d1ddbe0b83753bbf189770af1911623fef8d6f'

def output(**values):
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:
        for k,v in values.items():f.write(k+'='+str(v)+'\n')

def workload(job,keyless=False):
    need(os.environ['GITHUB_REPOSITORY']=='mariancradulescu/mxm-quant-greenfield' and os.environ['GITHUB_REF_NAME']=='mxm-remediation-p0-p4-20261015-v1' and os.environ['GITHUB_JOB']==job and os.environ['GITHUB_RUN_ATTEMPT']=='1','INTEGRATED_WORKLOAD')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'INTEGRATED_NO_APP_KEY')
    if job!='investigation' or os.environ.get('LAB_NATIVE_COLLECTION_ALLOWED')!='DEVELOPMENT_RESEARCH':need(not any(os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),'INTEGRATED_NO_BROKER_KEYS')
    if keyless:need(not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'),'INTEGRATED_KEYLESS')
    route=GetOnly();anchors(route)
    active=strict_json(file_at(route,'state.json',AUTH));need(active['revoked'] is False and active['pending'] is None,'INTEGRATED_AUTHORITY_REVOKED_OR_PENDING')
    return route

def current(route):return route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']

def state_at(route,oid):
    try:return strict_json(file_at(route,STATE_PATH,oid)),False
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        s=strict_json(file_at(route,'program-state.json',oid));need(s['sequence']==16 and s['source_sha']==ORIGINAL_SOURCE and s['ciphertext_sha256']==ORIGINAL_CIPHER,'INITIAL_PREDECESSOR');return s,True

def definition(route):
    ref=os.environ.get('LAB_ADMISSION_REF');path=os.environ.get('LAB_ADMISSION_PATH')
    if not ref:
        t=strict_json(file_at(route,TRIGGER,os.environ['GITHUB_SHA']));need(t['authority']==AUTH,'INTEGRATED_TRIGGER_AUTHORITY');ref=t['admission_ref'];path=t['admission_path']
    need(re.fullmatch('[a-f0-9]{40}',ref or '') and re.fullmatch(r'research_programs/admissions/[A-Z0-9_-]+\.json',path or ''),'INTEGRATED_ADMISSION_LOCATOR')
    a=strict_json(file_at(route,path,ref));need(a['schema']=='mxm.laboratory-admission.v2' and a['authority']==AUTH and a['module_sha256']==module_digest(),'INTEGRATED_ADMISSION_SOURCE')
    need(bytes_digest(file_at(route,WF,os.environ['GITHUB_SHA']))==a['workflow_sha256'],'ORCHESTRATION_WORKFLOW_DRIFT')
    need(a['mode'] in ('TECHNICAL_NONOUTCOME','DEVELOPMENT_RESEARCH'),'INTEGRATED_ADMISSION_MODE')
    if a['mode']=='TECHNICAL_NONOUTCOME':need(a['economic_release'] is False,'ECONOMIC_LANE_HELD')
    else:
        gate=strict_json(file_at(route,'typed-successor/END_TO_END_OPERATIONAL_ACCEPTANCE.json',a['technical_acceptance_ref']))
        need(a['economic_release'] is True,'ECONOMIC_LANE_HELD')
        economic_gate(gate,os.environ['LAB_SOURCE_SHA'],{name:route.json('branches/'+name)['protected'] for name in ('main','mxm-remediation-p0-p4-20261015-v1')})
    need(type(a['steps_per_segment']) is int and 0<a['steps_per_segment']<=16 and len(a['programmes'])>0,'INTEGRATED_STEP_BUDGET')
    ids=[m['id'] for m in a['programmes']];need(len(set(ids))==len(ids),'INTEGRATED_PROGRAMME_DUPLICATE')
    need(all(m['mode']==a['mode'] and m['source_sha256']==module_digest() for m in a['programmes']),'INTEGRATED_PROGRAMME_BINDING')
    if a['mode']=='TECHNICAL_NONOUTCOME':need(all(m['budget']['broker_requests']==identity_budget(m)==0 for m in a['programmes']),'TECHNICAL_ZERO_ECONOMIC_BUDGET')
    return a,ref,path

def open_private(route,s,oid,key,tmp):
    blob=restore_ciphertext(strict_json(file_at(route,s['ciphertext_path'],oid)),lambda p:file_at(route,p,oid))
    need(bytes_digest(blob)==s['ciphertext_sha256'],'INTEGRATED_INPUT_CIPHER')
    p=strict_json(unpack(owner.bounded_decrypt(blob,key,tmp)),max_elements=8000000)
    need(p['sequence']==s['sequence'] and p['pending'] is None and p['source_sha']==s['source_sha'],'INTEGRATED_COLD_BINDING')
    return p

def seal(private,key,tmp,target):
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    from research_core_v4.successor_c_20261018 import readback as old
    pub=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(pub)==old.FP,'INTEGRATED_RECIPIENT')
    raw=encoded(private);encrypt_shard(gzip.compress(raw,mtime=0),public_key=pub,output=target)
    need(unpack(owner.bounded_decrypt(target.read_bytes(),key,tmp))==raw,'INTEGRATED_ENCRYPTED_READBACK')
    changed=bytearray(target.read_bytes());changed[-1]^=1;rejected=False
    try:owner.bounded_decrypt(bytes(changed),key,tmp)
    except Exception:rejected=True
    need(rejected,'INTEGRATED_TAMPER_ACCEPTED')

def preflight():
    route=workload('preflight');a,ref,path=definition(route);parent=current(route);s,initial=state_at(route,parent)
    need(s['pending'] is None,'PREFLIGHT_PENDING_REQUIRES_RECOVERY')
    expected=os.environ.get('LAB_PARENT_OID');need(not expected or expected==parent,'PREFLIGHT_STALE_PARENT')
    if os.environ.get('GITHUB_EVENT_NAME')=='push':need(strict_json(file_at(route,TRIGGER,os.environ['GITHUB_SHA']))['expected_evidence_parent']==parent,'PREFLIGHT_STALE_TRIGGER')
    original=file_at(route,'program-state.json',parent);need(bytes_digest(original)==ORIGINAL_PUBLIC,'PREFLIGHT_ORIGINAL_CHANGED')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    os.umask(0o077);OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as folder:
        tmp=Path(folder);key,fp=_private_key_from_secret(tmp);p=open_private(route,s,parent,key,tmp);history=historical_accounting(ROOT)
        if initial or p['source_sha']==ORIGINAL_SOURCE:
            candidates=[strict_json(x.read_bytes()) for x in sorted((ROOT/'discovery/candidates').glob('V2-C*.json'))]
            candidates.append(p['programmes']['VOLUME_SURPRISE_CLOSE_LOCATION_PRESSURE_20261019_A']['progress']['results']['freeze_pressure']['value'])
            p=migrate_private(p,s,history,candidates,os.environ['LAB_SOURCE_SHA'],bytes_digest(original))
        elif p['source_sha']!=os.environ['LAB_SOURCE_SHA']:p=typed_source_transition(p,s,a['typed_predecessor'],os.environ['LAB_SOURCE_SHA'],evidence_oid=parent)
        need(p['source_sha']==os.environ['LAB_SOURCE_SHA'] and 'typed_transition' in p,'PREFLIGHT_SUCCESSOR_SOURCE')
        prior_book=TypedTrialBook.restore(p['trial_book'])
        if prior_book.hash_version==1:
            candidates=[strict_json(x.read_bytes()) for x in sorted((ROOT/'discovery/candidates').glob('V2-C*.json'))]
            candidates.append(p['programmes']['VOLUME_SURPRISE_CLOSE_LOCATION_PRESSURE_20261019_A']['progress']['results']['freeze_pressure']['value'])
            upgrade_fingerprint(prior_book,candidates,os.environ['LAB_SOURCE_SHA']);p['trial_book']=prior_book.export()
        book=register_and_validate(p,a,history);p['history']=history
        p.setdefault('programme_origins',{}).setdefault(digest(a),s['sequence'])
        p.setdefault('programme_accounting_origins',{}).setdefault(digest(a),accounting(book.export()))
        # Validate every programme before claim, including cache/journal restoration.
        for m in a['programmes']:
            if m['id'] not in p['programmes']:Laboratory(m,history,book,cache=DataCatalogue.restore(p['shared_catalogue']))
        need(any(m['id'] not in p['programmes'] or not p['programmes'][m['id']]['progress']['safe_stop'] for m in a['programmes']),'PREFLIGHT_ALREADY_COMPLETE')
        seal(p,key,tmp,OUT/'prepared.mxmenc')
        cert={'schema':'mxm.integrated-preflight.v2','run_id':int(os.environ['GITHUB_RUN_ID']),'trigger_sha':os.environ['GITHUB_SHA'],'source_sha':os.environ['LAB_SOURCE_SHA'],
          'parent_oid':parent,'state_path':STATE_PATH,'base_state':s,'initial_successor':initial,'admission_ref':ref,'admission_path':path,'admission_sha256':digest(a),'module_sha256':module_digest(),
          'prepared_cipher_sha256':bytes_digest((OUT/'prepared.mxmenc').read_bytes()),'prepared_private_sha256':digest(p),'accounting':accounting(p['trial_book']),
          'all_programmes_validated':True,'original_public_sha256':bytes_digest(original),'orders':0,'economic_outcomes':0}
    need(current(route)==parent,'PREFLIGHT_PARENT_MOVED');(OUT/'preflight.json').write_bytes(encoded(cert));output(admission_ref=ref,admission_path=path,parent_oid=parent,mode=a['mode'])
    print(json.dumps({'state':'ALL_PROGRAMMES_VALIDATED_BEFORE_DURABLE_INTENT','parent_oid':parent,'initial_successor':initial,'accounting':cert['accounting']}))

def certificate(route):
    c=strict_json((INPUT/'preflight.json').read_bytes());a,ref,path=definition(route)
    need(c['schema']=='mxm.integrated-preflight.v2' and c['run_id']==int(os.environ['GITHUB_RUN_ID']) and c['trigger_sha']==os.environ['GITHUB_SHA'] and c['source_sha']==os.environ['LAB_SOURCE_SHA'],'PREFLIGHT_NATIVE_BINDING')
    need(c['admission_ref']==ref and c['admission_path']==path and c['admission_sha256']==digest(a) and c['all_programmes_validated'] is True and c['module_sha256']==module_digest(),'PREFLIGHT_COMPLETE_VALIDATION')
    need(c['original_public_sha256']==ORIGINAL_PUBLIC and c['orders']==c['economic_outcomes']==0,'PREFLIGHT_SCOPE')
    return c,a

def claim():
    route=workload('segment-intent',True);need(os.environ.get('NATIVE_PREFLIGHT_RESULT')=='success','CLAIM_NATIVE_PREFLIGHT_SUCCESS');c,a=certificate(route)
    parent=current(route);need(parent==c['parent_oid'],'CLAIM_STALE_PREFLIGHT');s,initial=state_at(route,parent);need(s==c['base_state'] and initial==c['initial_successor'],'CLAIM_BASE_CHANGED')
    from .claim import claim_state
    new=claim_state(s,int(os.environ['GITHUB_RUN_ID']),digest(a),parent,os.environ['LAB_SOURCE_SHA'])
    new['pending'].update(phase='PRE_EXPOSURE',preflight_sha256=digest(c));intent={'schema':'mxm.validated-intent.v2','preflight':c,'maximum_new_identity_reservation':sum(identity_budget(m) for m in a['programmes']),'base_state':s,'pending':new['pending']}
    oid=atomic_publish(route,parent,{STATE_PATH:encoded(new),'typed-successor/intents/'+os.environ['GITHUB_RUN_ID']+'.json':encoded(intent)},'Claim fully prevalidated typed successor segment; original checkpoint16 untouched')
    need(state_at(route,oid)[0]==new,'CLAIM_REMOTE_READBACK');output(claim_oid=oid)
    print(json.dumps({'state':'INTEGRATED_INTENT_DURABLE','evidence_oid':oid,'phase':'PRE_EXPOSURE'}))
    if os.environ.get('LAB_FAULT_BEFORE_FENCE')=='1':need(False,'INJECTED_CRASH_AFTER_CLAIM_BEFORE_FENCE')

def fence():
    route=workload('execution-fence',True);parent=current(route);need(parent==os.environ['LAB_PARENT_OID'],'FENCE_STALE');s,_=state_at(route,parent)
    need(s['pending']['run_id']==int(os.environ['GITHUB_RUN_ID']) and s['pending']['phase']=='PRE_EXPOSURE','FENCE_IDENTITY');s['pending']['phase']='EXECUTION_FENCED'
    oid=atomic_publish(route,parent,{STATE_PATH:encoded(s),'typed-successor/fences/'+os.environ['GITHUB_RUN_ID']+'.json':encoded({'run_id':int(os.environ['GITHUB_RUN_ID']),'claim_oid':parent,'phase':'EXECUTION_FENCED','no_automatic_retry':True})},'Fence worker execution before any possible outcome exposure')
    need(state_at(route,oid)[0]==s,'FENCE_READBACK');output(fence_oid=oid)

def execute():
    route=workload('investigation');c,a=certificate(route);parent=current(route);need(parent==os.environ['LAB_PARENT_OID'],'WORKER_STALE_FENCE');s,_=state_at(route,parent)
    need(s['pending']['phase']=='EXECUTION_FENCED' and s['pending']['run_id']==int(os.environ['GITHUB_RUN_ID']) and s['pending']['preflight_sha256']==digest(c),'WORKER_DURABLE_FENCE')
    blob=(INPUT/'prepared.mxmenc').read_bytes();need(bytes_digest(blob)==c['prepared_cipher_sha256'],'WORKER_PREPARED_CIPHER')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    OUT.mkdir(parents=True,exist_ok=True);os.umask(0o077)
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as folder:
        tmp=Path(folder);key,fp=_private_key_from_secret(tmp);p=strict_json(unpack(owner.bounded_decrypt(blob,key,tmp)),max_elements=8000000)
        need(digest(p)==c['prepared_private_sha256'] and p['sequence']==s['sequence'],'WORKER_PREFLIGHT_PRIVATE')
        book=register_and_validate(p,a,p['history']);before=accounting(book.export());done=[];wire={}
        for _ in range(a['steps_per_segment']):
            m=next((m for m in a['programmes'] if m['id'] not in p['programmes'] or not p['programmes'][m['id']]['progress']['safe_stop']),None)
            if m is None:break
            saved=p['programmes'].get(m['id']);lab=Laboratory.restore(saved,p['history'],shared_catalogue=p['shared_catalogue']) if saved else Laboratory(m,p['history'],book,cache=DataCatalogue.restore(p['shared_catalogue']));lab.book=book
            lazy=None
            try:
                if a['mode']=='DEVELOPMENT_RESEARCH':
                    from .runtime import corpus,preserved_registry
                    lazy=bind_native(lab,corpus(key,tmp,preserved_registry()))
                task=lab.next()
                if task is not None:result=lab.execute(task);done.append({'programme':m['id'],'task':task,'classification':result['classification']})
                lab.next();preserve_node(p,lab);book=lab.book
            finally:
                if lazy:
                    if lazy.instance is not None:
                        for kind,count in lazy.instance.wire_types.items():wire[kind]=wire.get(kind,0)+count
                    lazy.close()
        p['trial_book']=book.export();after=accounting(p['trial_book']);check_accounting(after,before,a)
        p.update(sequence=p['sequence']+1,last_run_id=int(os.environ['GITHUB_RUN_ID']),parent_oid=parent,pending=None,admission_ref=c['admission_ref'],admission_path=c['admission_path'],admission_sha256=digest(a))
        p['safe_stop']=all(p['programmes'].get(m['id'],{}).get('progress',{}).get('safe_stop',False) for m in a['programmes'])
        seal(p,key,tmp,OUT/'result.mxmenc')
        r={'schema':'mxm.integrated-segment-receipt.v2','run_id':int(os.environ['GITHUB_RUN_ID']),'trigger_sha':os.environ['GITHUB_SHA'],'source_sha':os.environ['LAB_SOURCE_SHA'],
          'parent_oid':parent,'sequence':p['sequence'],'state_path':STATE_PATH,'preflight_sha256':digest(c),'admission_ref':c['admission_ref'],'admission_path':c['admission_path'],'admission_sha256':digest(a),
          'ciphertext_sha256':bytes_digest((OUT/'result.mxmenc').read_bytes()),'accounting_before':before,'accounting_after':after,'completed':done,'safe_stop':p['safe_stop'],'cold_restored':True,
          'original_public_sha256':ORIGINAL_PUBLIC,'transition':p['typed_transition'],'private_sha256':digest(p),'pending':None,'orders':0,'new_outcomes':after['economic_observations']-before['economic_observations'],'new_economic_identities_opened':sum(v['outcome_charged'] for v in after['lanes'].values())-sum(v['outcome_charged'] for v in before['lanes'].values()),'new_identity_reservations':sum(v['encumbered'] for v in after['lanes'].values())-sum(v['encumbered'] for v in before['lanes'].values()),'broker_requests':sum(v for k,v in wire.items() if k in ('ProtoOAGetTickDataReq','ProtoOAGetTrendbarsReq')),'native_wire_counts':wire,'economic_release':a['economic_release'],'modified_cipher_rejected':True,'admission_start_sequence':p['programme_origins'][digest(a)]}
    need(current(route)==parent,'WORKER_EVIDENCE_MOVED');(OUT/'receipt.json').write_bytes(encoded(r));print('INTEGRATED_SEGMENT '+json.dumps(r,sort_keys=True))

def publish():
    route=workload('durable-archive',True);need(os.environ.get('NATIVE_WORKER_RESULT')=='success','PUBLISH_NATIVE_WORKER_SUCCESS')
    r=strict_json((INPUT/'receipt.json').read_bytes());blob=(INPUT/'result.mxmenc').read_bytes();a,ref,path=definition(route);parent=current(route);s,_=state_at(route,parent)
    need(r['schema']=='mxm.integrated-segment-receipt.v2' and r['parent_oid']==parent and r['run_id']==int(os.environ['GITHUB_RUN_ID']) and r['trigger_sha']==os.environ['GITHUB_SHA'] and r['source_sha']==os.environ['LAB_SOURCE_SHA'],'PUBLISH_NATIVE_BINDING')
    need(s['pending']['phase']=='EXECUTION_FENCED' and s['pending']['run_id']==r['run_id'] and s['pending']['preflight_sha256']==r['preflight_sha256'],'PUBLISH_FENCE_BINDING')
    need(r['admission_sha256']==digest(a) and r['admission_ref']==ref and r['admission_path']==path and r['sequence']==s['sequence']+1 and len(r['completed'])<=a['steps_per_segment'],'PUBLISH_ADMISSION_BUDGET')
    need(r['orders']==0 and r['economic_release']==a['economic_release'] and r['pending'] is None and r['modified_cipher_rejected'] is True and r['new_outcomes']==r['accounting_after']['economic_observations']-r['accounting_before']['economic_observations'],'PUBLISH_SCOPE')
    need(type(r['broker_requests']) is int and 0<=r['broker_requests']<=sum(m['budget']['broker_requests'] for m in a['programmes']),'PUBLISH_NETWORK_BUDGET')
    need(set(r['native_wire_counts'])<={'ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq','ProtoOAGetTickDataReq','ProtoOAGetTrendbarsReq'} and all(type(v) is int and v>=0 for v in r['native_wire_counts'].values()),'PUBLISH_READ_ONLY_NATIVE_TYPES')
    need(r['new_economic_identities_opened']==sum(v['outcome_charged'] for v in r['accounting_after']['lanes'].values())-sum(v['outcome_charged'] for v in r['accounting_before']['lanes'].values()) and r['new_identity_reservations']==sum(v['encumbered'] for v in r['accounting_after']['lanes'].values())-sum(v['encumbered'] for v in r['accounting_before']['lanes'].values()),'PUBLISH_IDENTITY_OUTCOME_UNITS')
    if a['mode']=='TECHNICAL_NONOUTCOME':need(r['new_outcomes']==r['broker_requests']==0 and r['native_wire_counts']=={},'TECHNICAL_NO_EXPOSURE')
    need(r['original_public_sha256']==ORIGINAL_PUBLIC and r['transition']['original_source']==ORIGINAL_SOURCE and r['transition']['original_cipher']==ORIGINAL_CIPHER,'PUBLISH_TRANSITION_AUTHORITY')
    check_accounting(r['accounting_after'],r['accounting_before'],a);need(bytes_digest(blob)==r['ciphertext_sha256'] and blob.startswith(b'MXM_SHALLOW_M5_V2_ENC1\x00'),'PUBLISH_CIPHER')
    prefix='typed-successor/segments/'+str(r['sequence']);files,manifest=chunk_ciphertext(blob,prefix);files[prefix+'/checkpoint.parts.json']=encoded(manifest);files[prefix+'/receipt.json']=encoded(r)
    new={**s,'source_sha':r['source_sha'],'ciphertext_format':'CHUNKED_ENCRYPTED_ENVELOPE_V1','ciphertext_path':prefix+'/checkpoint.parts.json','ciphertext_sha256':r['ciphertext_sha256'],'sequence':r['sequence'],'pending':None,'safe_stop':r['safe_stop'],'last_run_id':r['run_id'],'last_trigger_sha':r['trigger_sha'],'admission_ref':ref,'admission_path':path,'admission_sha256':digest(a),'accounting':r['accounting_after'],'original_public_sha256':ORIGINAL_PUBLIC,'admission_start_sequence':r['admission_start_sequence']}
    new.pop('recovery_continuation',None)
    files[STATE_PATH]=encoded(new);oid=atomic_publish(route,parent,files,'Preserve typed successor checkpoint '+str(r['sequence'])+' and consume fenced intent atomically')
    need(state_at(route,oid)[0]==new and bytes_digest(file_at(route,'program-state.json',oid))==ORIGINAL_PUBLIC,'PUBLISH_PUBLIC_READBACK')
    need(restore_ciphertext(strict_json(file_at(route,new['ciphertext_path'],oid)),lambda p:file_at(route,p,oid))==blob,'PUBLISH_REMOTE_CIPHER')
    output(evidence_oid=oid,next='STOP' if r['safe_stop'] else 'CONTINUE');print(json.dumps({'state':'INTEGRATED_TYPED_CHECKPOINT_DURABLE','evidence_oid':oid,'sequence':r['sequence'],'safe_stop':r['safe_stop'],'accounting':r['accounting_after']}))

def recover():
    route=workload('recover-before-exposure',True);definition(route);oid=current(route);s,_=state_at(route,oid)
    if not s['pending']:output(next='NONE');return
    jobs=native_dependency_jobs() if s['pending']['run_id']==int(os.environ['GITHUB_RUN_ID']) else route.json('actions/runs/'+str(s['pending']['run_id'])+'/attempts/1/jobs?per_page=100')['jobs']
    if not can_recover_before_exposure(s,jobs):output(next='HELD');print(json.dumps({'state':'AMBIGUOUS_EXPOSURE_HELD_NO_RETRY'}));return
    intent=strict_json(file_at(route,'typed-successor/intents/'+str(s['pending']['run_id'])+'.json',oid));base=intent['base_state']
    need(base['pending'] is None and base['ciphertext_sha256']==s['ciphertext_sha256'] and base['sequence']==s['sequence'],'RECOVERY_PREDECESSOR_UNCHANGED')
    record={'run_id':s['pending']['run_id'],'state':'ABORTED_BEFORE_FENCE_NATIVE_SKIPPED_WORKER','no_economic_exposure':True,'refunds':0,'old_intent_retained':True,'base_state_sha256':digest(base)}
    base=recovered_public_base(intent)
    commit=atomic_publish(route,oid,{STATE_PATH:encoded(base),'typed-successor/recoveries/'+str(record['run_id'])+'.json':encoded(record)},'Recover proven pre-exposure failed intent; preserve history and budgets without replay or refund')
    output(next='CONTINUE',evidence_oid=commit);print(json.dumps({'state':'INTEGRATED_PRE_EXPOSURE_RECOVERY_DURABLE','evidence_oid':commit,'record':record}))

def handoff():
    route=workload('scientific-handoff',True);oid=os.environ['LAB_PARENT_OID'];need(current(route)==oid,'HANDOFF_STALE_SUCCESSOR');s,_=state_at(route,oid);need(s['pending'] is None,'HANDOFF_PENDING')
    a,ref,path=definition(route)
    if s['safe_stop'] and s.get('admission_sha256')==digest(a) and not s.get('recovery_continuation'):print(json.dumps({'state':'INTEGRATED_PROGRAMME_COMPLETE_NO_DISPATCH'}));return
    need(s['sequence']<=s.get('admission_start_sequence',s['sequence'])+sum(m['budget']['steps'] for m in a['programmes']),'HANDOFF_FINITE_TOTAL')
    jobs=native_dependency_jobs();names={j['name']:j for j in jobs}
    if names.get('durable-archive',{}).get('conclusion')=='success':require_jobs(jobs,['preflight','segment-intent','execution-fence','investigation','durable-archive'])
    else:
        require_jobs(jobs,['preflight','recover-before-exposure']);need(names.get('investigation',{}).get('conclusion')=='skipped','HANDOFF_RECOVERY_NO_WORKER')
        need(strict_json(file_at(route,'typed-successor/recoveries/'+os.environ['GITHUB_RUN_ID']+'.json',oid))['no_economic_exposure'] is True,'HANDOFF_RECOVERY_PROOF')
    # workflow_dispatch is a permitted GITHUB_TOKEN event; duplicate ACKs cannot
    # duplicate work because preflight and claim require the exact evidence parent.
    return dispatch_once(route,oid,s,ref,path)

def native_dependency_jobs():
    graph=strict_json(os.environ['NATIVE_CHAIN_RESULTS'].encode());required={'preflight','segment-intent','execution-fence','investigation','durable-archive'}
    need(required<=set(graph),'NATIVE_DEPENDENCY_GRAPH_INCOMPLETE')
    need(all(v['result'] in ('success','failure','cancelled','skipped') for v in graph.values()),'NATIVE_DEPENDENCY_RESULT')
    return [{'name':k,'status':'completed','conclusion':v['result']} for k,v in graph.items()]

def dispatch_once(route,oid,s,ref,path):
    record_path='typed-successor/dispatches/'+str(s['sequence'])+'-'+s['ciphertext_sha256']+'.json'
    try:
        record=strict_json(file_at(route,record_path,oid));need(record['ciphertext_sha256']==s['ciphertext_sha256'],'DISPATCH_RECORD_BINDING')
        print(json.dumps({'state':'DISPATCH_ALREADY_ISSUED_NO_BLIND_RETRY','record_path':record_path}));return
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
    need(current(route)==oid,'HANDOFF_PARENT_CHANGED')
    record={'schema':'mxm.native-dispatch-intent.v2','parent_checkpoint_oid':oid,'ciphertext_sha256':s['ciphertext_sha256'],'sequence':s['sequence'],'source_sha':os.environ['LAB_SOURCE_SHA'],'admission_ref':ref,'admission_path':path,'issuer_run_id':int(os.environ['GITHUB_RUN_ID']),'automatic_post_retry':False}
    dispatch_oid=atomic_publish(route,oid,{record_path:encoded(record)},'Record one native continuation issuance before workflow_dispatch; uncertain ACK cannot create duplicate issuance')
    body={'ref':'mxm-remediation-p0-p4-20261015-v1','inputs':{'parent_oid':dispatch_oid,'admission_ref':ref,'admission_path':path,'fault_before_fence':'0'}}
    req=urllib.request.Request('https://api.github.com/repos/mariancradulescu/mxm-quant-greenfield/actions/workflows/mxm-integrated-p0.yml/dispatches',data=encoded(body),method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:need(response.status==204,'HANDOFF_ACK_UNRESOLVED_NO_BLIND_RETRY')
    print(json.dumps({'state':'INTEGRATED_NATIVE_CONTINUATION_DISPATCHED','parent_oid':dispatch_oid,'bootstrap':False,'dispatch_record':record_path}))

def observer():
    need(os.environ['GITHUB_REPOSITORY']=='mariancradulescu/mxm-quant-greenfield' and os.environ['GITHUB_REF_NAME']=='main' and os.environ['GITHUB_JOB']=='ordinary-recovery' and os.environ['GITHUB_RUN_ATTEMPT']=='1','OBSERVER_WORKLOAD')
    need(not any(os.environ.get(k) for k in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY','CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),'OBSERVER_KEYLESS')
    route=GetOnly();anchors(route);oid=current(route);s,initial=state_at(route,oid)
    if initial:print(json.dumps({'state':'NO_SUCCESSOR_NO_BOOTSTRAP'}));return
    if s['pending']:
        prior=s['pending']['run_id'];run=route.json('actions/runs/'+str(prior));need(run['path']==WF and run['head_branch']=='mxm-remediation-p0-p4-20261015-v1' and run['run_attempt']==1,'OBSERVER_PRIOR_WORKLOAD')
        jobs=route.json('actions/runs/'+str(prior)+'/attempts/1/jobs?per_page=100')['jobs']
        if can_recover_before_exposure(s,jobs):
            intent=strict_json(file_at(route,'typed-successor/intents/'+str(prior)+'.json',oid));base=intent['base_state'];need(base['pending'] is None and base['ciphertext_sha256']==s['ciphertext_sha256'],'OBSERVER_RECOVERY_BASE')
            record={'run_id':prior,'state':'ABORTED_BEFORE_FENCE_NATIVE_SKIPPED_WORKER','no_economic_exposure':True,'refunds':0,'old_intent_retained':True,'base_state_sha256':digest(base)}
            base=recovered_public_base(intent)
            oid=atomic_publish(route,oid,{STATE_PATH:encoded(base),'typed-successor/recoveries/'+str(prior)+'.json':encoded(record)},'Native recovery of proven pre-exposure failed intent');s=base
        else:print(json.dumps({'state':'PENDING_OR_AMBIGUOUS_WORKER_HELD_NO_RETRY'}));return
    if s['safe_stop'] and s['sequence']>16 and not s.get('recovery_continuation'):print(json.dumps({'state':'ADMITTED_PROGRAMME_COMPLETE_NO_DISPATCH'}));return
    ref=s.get('admission_ref');path=s.get('admission_path')
    if s.get('recovery_continuation'):
        recovery=s['recovery_continuation'];proof=strict_json(file_at(route,'typed-successor/recoveries/'+str(recovery['run_id'])+'.json',oid));need(proof['no_economic_exposure'] is True,'OBSERVER_RECOVERED_ADMISSION_PROOF');ref=recovery['admission_ref'];path=recovery['admission_path']
    elif s['sequence']==16:
        # Only a proven recovery supplies a new admission; no bootstrap from the
        # old C033 admission or a missing initial checkpoint is permitted.
        runs=route.json('actions/runs?per_page=100')['workflow_runs'];failed=[r for r in runs if r['path']==WF and r['conclusion']=='failure']
        need(failed,'OBSERVER_NO_RECOVERY_ISSUER');rid=failed[0]['id'];intent=strict_json(file_at(route,'typed-successor/intents/'+str(rid)+'.json',oid))
        need(strict_json(file_at(route,'typed-successor/recoveries/'+str(rid)+'.json',oid))['no_economic_exposure'],'OBSERVER_RECOVERY_RECEIPT');ref=intent['preflight']['admission_ref'];path=intent['preflight']['admission_path']
    os.environ['LAB_ADMISSION_REF']=ref;os.environ['LAB_ADMISSION_PATH']=path;a,ref,path=definition(route)
    origin=s['sequence'] if s.get('recovery_continuation') else s.get('admission_start_sequence',16)
    need(s['sequence']<=origin+sum(m['budget']['steps'] for m in a['programmes']),'OBSERVER_FINITE_TOTAL')
    dispatch_once(route,oid,s,ref,path)

def fault_probes():
    route=workload('fault-probes',True);parent=current(route);original=file_at(route,'program-state.json',parent);s,_=state_at(route,parent);need(s['safe_stop'] and not s['pending'],'PROBES_TERMINAL_ONLY')
    # Real authorization-denial GET, using a deliberately invalid fixture token.
    # The configured token is restored without logging or serializing it.
    configured=os.environ['GH_TOKEN'];denied=False
    try:
        os.environ['GH_TOKEN']='MXM_INVALID_AUTHORIZATION_FIXTURE_ONLY'
        try:GetOnly().json('git/ref/heads/'+EVIDENCE_BRANCH)
        except urllib.error.HTTPError as e:denied=e.code==401
    finally:os.environ['GH_TOKEN']=configured
    need(denied,'PROBES_TOKEN_LOSS_NOT_REJECTED')
    manifest=strict_json(file_at(route,s['ciphertext_path'],parent));incomplete=False
    try:
        restore_ciphertext(manifest,lambda p:file_at(route,p,parent)[:-12] if p==manifest['parts'][0]['path'] else file_at(route,p,parent))
    except Exception:incomplete=True
    need(incomplete,'PROBES_INCOMPLETE_CHECKPOINT_ACCEPTED')
    from concurrent.futures import ThreadPoolExecutor
    def writer(name):
        try:return {'writer':name,'accepted':True,'oid':atomic_publish(route,parent,{'typed-successor/fault-probes/'+os.environ['GITHUB_RUN_ID']+'/'+name+'.json':encoded({'probe':name,'not_economic':True})},'Controlled concurrent writer probe '+name)}
        except Exception:return {'writer':name,'accepted':False}
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(writer,['A','B']))
    need(sum(r['accepted'] for r in results)==1,'PROBES_WRITER_EXCLUSION');oid=current(route);need(file_at(route,'program-state.json',oid)==original and state_at(route,oid)[0]==s,'PROBES_CHECKPOINT_CHANGED')
    proof={'schema':'mxm.integrated-fault-probes.v2','run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['LAB_SOURCE_SHA'],'concurrent_writers':results,'exactly_one_writer_accepted':True,'unauthorized_token_get_rejected_401':denied,'incomplete_checkpoint_rejected':incomplete,'original_unchanged':True,'typed_checkpoint_unchanged':True,'new_outcomes':0}
    final=atomic_publish(route,oid,{'typed-successor/fault-probes/'+os.environ['GITHUB_RUN_ID']+'/result.json':encoded(proof)},'Preserve actual native concurrent-writer exclusion proof')
    print('INTEGRATED_FAULT_PROBES '+json.dumps({'evidence_oid':final,'proof':proof},sort_keys=True))

def verify():
    route=workload('cold-readback');oid=os.environ['LAB_PARENT_OID'];need(current(route)==oid,'VERIFY_PARENT');s,_=state_at(route,oid);need(s['safe_stop'] and s['pending'] is None,'VERIFY_NOT_TERMINAL');a,ref,path=definition(route)
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as folder:
        tmp=Path(folder);key,fp=_private_key_from_secret(tmp);p=open_private(route,s,oid,key,tmp);book=register_and_validate(p,a,p['history'])
        need(accounting(book.export())==s['accounting'] and book.baseline['legacy_snapshot']['used']['V2']==22,'VERIFY_PERSISTENT_TYPED_ACCOUNTING')
        for m in a['programmes']:need(Laboratory.restore(p['programmes'][m['id']],p['history'],shared_catalogue=p['shared_catalogue']).next() is None,'VERIFY_PROGRAMME_NOT_COMPLETE')
        need(bytes_digest(file_at(route,'program-state.json',oid))==ORIGINAL_PUBLIC,'VERIFY_ORIGINAL_CHANGED')
        origin=p.get('programme_accounting_origins',{}).get(digest(a),{'economic_observations':29})
        proof={'schema':'mxm.integrated-cold-readback.v2','evidence_oid':oid,'run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['LAB_SOURCE_SHA'],'sequence':s['sequence'],'ciphertext_sha256':s['ciphertext_sha256'],'private_sha256':digest(p),'accounting':s['accounting'],'all_admitted_programmes_complete':True,'original_unchanged':True,'new_outcomes':s['accounting']['economic_observations']-origin['economic_observations'],'orders':0,'economic_workflow_released':a['economic_release']}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'cold-readback.json').write_bytes(encoded(proof));print('INTEGRATED_COLD_READBACK '+json.dumps(proof,sort_keys=True))

if __name__=='__main__':
    import sys
    try:
        functions={'preflight':preflight,'fence':fence,'recover':recover,'verify':verify,'observer':observer,'fault-probes':fault_probes}
        need(len(sys.argv)==2 and sys.argv[1] in functions,'INTEGRATED_MODE');functions[sys.argv[1]]()
    except Exception as e:
        code=str(e);print(json.dumps({'state':'INTEGRATED_SAFE_STOP','safe_code':code if re.fullmatch(r'LAB_[A-Z0-9_]+',code) else type(e).__name__}));raise SystemExit(1) from None
