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
from .execution import bind_native,preserve_node,next_admitted_programme
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
    need(route.json('git/ref/heads/mxm-remediation-p0-p4-20261015-v1')['object']['sha']==os.environ['GITHUB_SHA'],
         'INTEGRATED_WORKFLOW_REF_MOVED_STOP_RECONCILE')
    active=strict_json(file_at(route,'state.json',AUTH));need(active['revoked'] is False and active['pending'] is None,'INTEGRATED_AUTHORITY_REVOKED_OR_PENDING')
    return route

def current(route):return route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']

def verify_monotone_checkpoint(route,oid,state):
    """An ordinary forward commit cannot roll public state behind its archive."""
    tree_sha=route.json('git/commits/'+oid)['tree']['sha']
    for name in ('typed-successor','segments'):
        tree=route.json('git/trees/'+tree_sha)
        need(tree.get('truncated') is not True,'CHECKPOINT_TREE_INCOMPLETE')
        matches=[x for x in tree['tree'] if x['path']==name and x['type']=='tree']
        need(len(matches)==1,'CHECKPOINT_ARCHIVE_MISSING');tree_sha=matches[0]['sha']
    tree=route.json('git/trees/'+tree_sha)
    need(tree.get('truncated') is not True,'CHECKPOINT_SEGMENTS_INCOMPLETE')
    sequences=[int(x['path']) for x in tree['tree'] if x['type']=='tree' and re.fullmatch('[0-9]+',x['path'])]
    need(sequences and max(sequences)==state['sequence'],'CHECKPOINT_ROLLBACK_OR_UNARCHIVED_STATE')
    receipt=strict_json(file_at(route,'typed-successor/segments/'+str(state['sequence'])+'/receipt.json',oid))
    need(receipt['sequence']==state['sequence'] and receipt['source_sha']==state['source_sha'] and
         receipt['ciphertext_sha256']==state['ciphertext_sha256'] and
         receipt['accounting_after']==state['accounting'], 'CHECKPOINT_RECEIPT_STATE_MISMATCH')

def state_at(route,oid):
    try:
        state=strict_json(file_at(route,STATE_PATH,oid))
        verify_monotone_checkpoint(route,oid,state)
        return state,False
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
        economic_gate(gate,os.environ['LAB_SOURCE_SHA'],{name:route.json('branches/'+name)['protected'] for name in ('main','mxm-remediation-p0-p4-20261015-v1')},route=route)
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

def transition_predecessor(route,state,parent,authority):
    """Authenticate one failed pre-fence claim over the sealed checkpoint20.

    Recovery only appends intent/proof and continuation metadata. It must not
    make the exact original checkpoint authority unusable, nor turn an arbitrary
    descendant or copied recovery label into a source migration grant.
    """
    origin=authority['evidence_oid']
    if parent==origin:return state,origin
    need(authority.get('source_sha') in ('eab050084982916ad0c67798b38b947bac66b2b2','e9f3582eeff11697bf14e0ad26506f5d4347b46f','c6bf7027647d9b1e8e1a4dac50008c3ec0543c1c') and
         type(state.get('recovery_continuation')) is dict,'TRANSITION_RECOVERY_REQUIRED')
    continuation=state['recovery_continuation'];prior=continuation.get('run_id')
    need(type(prior) is int and prior>0,'TRANSITION_RECOVERY_RUN')
    original=strict_json(file_at(route,STATE_PATH,origin))
    if authority.get('sequence')==24:verify_checkpoint24_public(original,authority,origin)
    elif authority.get('sequence')==23:verify_checkpoint23_public(original,authority,origin)
    else:verify_checkpoint20_public(original,authority,origin)
    recovery_path='typed-successor/recoveries/'+str(prior)+'.json'
    intent_path='typed-successor/intents/'+str(prior)+'.json'
    recovery_commit=route.json('commits/'+parent)
    need(len(recovery_commit.get('parents',[]))==1 and
         {(f['filename'],f['status']) for f in recovery_commit.get('files',[])}==
         {(STATE_PATH,'modified'),(recovery_path,'added')},'TRANSITION_EXACT_RECOVERY_COMMIT')
    claim_oid=recovery_commit['parents'][0]['sha'];claim_commit=route.json('commits/'+claim_oid)
    need([p['sha'] for p in claim_commit.get('parents',[])]==[origin] and
         {(f['filename'],f['status']) for f in claim_commit.get('files',[])}==
         {(STATE_PATH,'modified'),(intent_path,'added')},'TRANSITION_EXACT_CLAIM_COMMIT')
    intent=strict_json(file_at(route,intent_path,parent));proof=strict_json(file_at(route,recovery_path,parent))
    certificate=intent['preflight'];claim_state=strict_json(file_at(route,STATE_PATH,claim_oid))
    need(intent['base_state']==original and recovered_public_base(intent)==state and
         proof.get('run_id')==prior and proof.get('no_economic_exposure') is True and
         proof.get('refunds')==0 and proof.get('base_state_sha256')==digest(original) and
         intent['pending']==claim_state['pending'] and
         {k:v for k,v in claim_state.items() if k!='pending'}==
         {k:v for k,v in original.items() if k!='pending'} and
         claim_state['pending']['run_id']==prior and claim_state['pending']['phase']=='PRE_EXPOSURE' and
         claim_state['pending']['preflight_sha256']==digest(certificate),
         'TRANSITION_RECOVERY_BYTES')
    run=route.json('actions/runs/'+str(prior))
    need(run.get('status')=='completed' and run.get('conclusion')=='failure' and
         run.get('path')==WF and run.get('head_branch')=='mxm-remediation-p0-p4-20261015-v1' and
         run.get('run_attempt')==1 and certificate.get('run_id')==prior and
         certificate.get('source_sha')==os.environ['LAB_SOURCE_SHA'] and
         certificate.get('parent_oid')==origin and certificate.get('trigger_sha')==run.get('head_sha'),
         'TRANSITION_RECOVERY_NATIVE_RUN')
    jobs=route.json('actions/runs/'+str(prior)+'/attempts/1/jobs?per_page=100')
    need(jobs.get('total_count')==len(jobs['jobs']) and len(jobs['jobs'])<=100 and
         can_recover_before_exposure(claim_state,jobs['jobs']),'TRANSITION_RECOVERY_NATIVE_GRAPH')
    preflight=[j for j in jobs['jobs'] if j['name']=='preflight'];claim=[j for j in jobs['jobs'] if j['name']=='segment-intent']
    require_jobs(preflight,['preflight'])
    from .attest_v3 import native_checkout_provenance
    native_checkout_provenance(route,prior,os.environ['LAB_SOURCE_SHA'],run['head_sha'],
        {j['name']:j['id'] for j in preflight+claim})
    return original,origin

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
        elif p['source_sha']!=os.environ['LAB_SOURCE_SHA']:
            predecessor,origin=transition_predecessor(route,s,parent,a['typed_predecessor'])
            p=typed_source_transition(p,predecessor,a['typed_predecessor'],os.environ['LAB_SOURCE_SHA'],evidence_oid=origin)
        need(p['source_sha']==os.environ['LAB_SOURCE_SHA'] and 'typed_transition' in p,'PREFLIGHT_SUCCESSOR_SOURCE')
        prior_book=TypedTrialBook.restore(p['trial_book'])
        if prior_book.hash_version==1:
            candidates=[strict_json(x.read_bytes()) for x in sorted((ROOT/'discovery/candidates').glob('V2-C*.json'))]
            candidates.append(p['programmes']['VOLUME_SURPRISE_CLOSE_LOCATION_PRESSURE_20261019_A']['progress']['results']['freeze_pressure']['value'])
            upgrade_fingerprint(prior_book,candidates,os.environ['LAB_SOURCE_SHA']);p['trial_book']=prior_book.export()
        if a['mode']=='DEVELOPMENT_RESEARCH' and prior_book.hash_version==2:
            # Prospective transition only after both native reception gates.
            # Technical checkpoint20 migration retains its exact ledger bytes.
            candidates=[strict_json(x.read_bytes()) for x in sorted((ROOT/'discovery/candidates').glob('V2-C*.json'))]
            candidates.append(p['programmes']['VOLUME_SURPRISE_CLOSE_LOCATION_PRESSURE_20261019_A']['progress']['results']['freeze_pressure']['value'])
            prior_book.upgrade_semantic_schema(candidates,os.environ['LAB_SOURCE_SHA'])
            p['trial_book']=prior_book.export()
        if a['mode']=='DEVELOPMENT_RESEARCH':need(prior_book.hash_version==3,'SCHEMA_CANONICAL_FINGERPRINT_REQUIRED')
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
            m=next_admitted_programme(p,a,book)
            if m is None:break
            saved=p['programmes'].get(m['id']);lab=Laboratory.restore(saved,p['history'],shared_catalogue=p['shared_catalogue']) if saved else Laboratory(m,p['history'],book,cache=DataCatalogue.restore(p['shared_catalogue']));lab.book=book
            lazy=None
            try:
                if a['mode']=='DEVELOPMENT_RESEARCH':
                    from .runtime import corpus,preserved_registry
                    lazy=bind_native(lab,corpus(key,tmp,preserved_registry()))
                elif a['mode']=='TECHNICAL_NONOUTCOME':
                    candidate=lab.next()
                    if candidate and lab.m['tasks'][candidate]['operator']=='native_corpus_readonly':
                        # Read the existing authenticated sealed corpus, not an
                        # invented quote fixture and not a new broker collection.
                        from .runtime import corpus,preserved_registry
                        lab.authentic_corpus=corpus(key,tmp,preserved_registry())
                task=lab.next()
                event=None
                if task is not None:
                    before_ids=sorted(p['shared_catalogue']['assets'])
                    result=lab.execute(task)
                    done.append({'programme':m['id'],'task':task,'classification':result['classification']})
                    history=p.setdefault('programme_execution_history',[])
                    event={
                        'programme':m['id'],'task':task,
                        'result_sha256':digest(result),
                        'native_checkpoint_sequence':s['sequence']+1,
                        'within_segment_step':len(done),
                        'catalogue_before_asset_ids':before_ids,
                        'programme_budget_remaining':lab.acquisition.remaining,
                        'previous_event_sha256':history[-1]['event_sha256'] if history else None}
                lab.next();preserve_node(p,lab);book=lab.book
                if event is not None:
                    event['catalogue_after_asset_ids']=sorted(p['shared_catalogue']['assets'])
                    event['event_sha256']=digest(event)
                    p['programme_execution_history'].append(event)
                    p['programme_execution_history_seal']={
                        'count':len(p['programme_execution_history']),
                        'head_sha256':event['event_sha256']}
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
          'parent_oid':parent,'previous_public_state_sha256':digest(s),'sequence':p['sequence'],'state_path':STATE_PATH,'preflight_sha256':digest(c),'admission_ref':c['admission_ref'],'admission_path':c['admission_path'],'admission_sha256':digest(a),
          'ciphertext_sha256':bytes_digest((OUT/'result.mxmenc').read_bytes()),'accounting_before':before,'accounting_after':after,'completed':done,'safe_stop':p['safe_stop'],'cold_restored':True,
          'original_public_sha256':ORIGINAL_PUBLIC,'transition':p['typed_transition'],'private_sha256':digest(p),'pending':None,'orders':0,'new_outcomes':after['economic_observations']-before['economic_observations'],'new_economic_identities_opened':sum(v['outcome_charged'] for v in after['lanes'].values())-sum(v['outcome_charged'] for v in before['lanes'].values()),'new_identity_reservations':sum(v['encumbered'] for v in after['lanes'].values())-sum(v['encumbered'] for v in before['lanes'].values()),'broker_requests':sum(v for k,v in wire.items() if k in ('ProtoOAGetTickDataReq','ProtoOAGetTrendbarsReq')),'native_wire_counts':wire,'economic_release':a['economic_release'],'modified_cipher_rejected':True,'admission_start_sequence':p['programme_origins'][digest(a)]}
    need(current(route)==parent,'WORKER_EVIDENCE_MOVED');(OUT/'receipt.json').write_bytes(encoded(r));print('INTEGRATED_SEGMENT '+json.dumps(r,sort_keys=True))

def publish():
    route=workload('durable-archive',True);need(os.environ.get('NATIVE_WORKER_RESULT')=='success','PUBLISH_NATIVE_WORKER_SUCCESS')
    r=strict_json((INPUT/'receipt.json').read_bytes());blob=(INPUT/'result.mxmenc').read_bytes();a,ref,path=definition(route);parent=current(route);s,_=state_at(route,parent)
    need(r['schema']=='mxm.integrated-segment-receipt.v2' and r['parent_oid']==parent and r['run_id']==int(os.environ['GITHUB_RUN_ID']) and r['trigger_sha']==os.environ['GITHUB_SHA'] and r['source_sha']==os.environ['LAB_SOURCE_SHA'],'PUBLISH_NATIVE_BINDING')
    need(r['previous_public_state_sha256']==digest(s),'PUBLISH_PUBLIC_PREDECESSOR_CHANGED')
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
    """Immediate handoff plus one bounded recovery of a genuinely uncertain ACK.

    A second dispatch is allowed only after an atomic new evidence-parent marker.
    The first, delayed dispatch then has a stale parent and cannot claim/fence.
    """
    from time import time
    from .handoff_recovery import inspect_dispatch
    record_path='typed-successor/dispatches/'+str(s['sequence'])+'-'+s['ciphertext_sha256']+'.json'
    retry_path=record_path[:-5]+'.retry1.json'
    need(s['pending'] is None and s['safe_stop'] is False,'DISPATCH_NO_OPEN_ADMITTED_WORK')
    need(current(route)==oid,'HANDOFF_PARENT_CHANGED')
    try:
        record=strict_json(file_at(route,record_path,oid))
        need(record['ciphertext_sha256']==s['ciphertext_sha256'] and
             record['admission_ref']==ref and record['admission_path']==path and
             record['source_sha']==os.environ['LAB_SOURCE_SHA'] and
             record['sequence']==s['sequence'],'DISPATCH_RECORD_BINDING')
        try:
            strict_json(file_at(route,retry_path,oid))
            print(json.dumps({'state':'BOUNDED_RETRY_ALREADY_RECORDED_NO_REISSUE',
                              'record_path':retry_path}));return
        except urllib.error.HTTPError as e:
            if e.code!=404:raise
        if record.get('schema')!='mxm.native-dispatch-intent.v3':
            print(json.dumps({'state':'LEGACY_UNCERTAIN_ACK_HELD',
                              'record_path':record_path}));return
        # Do not mistake an ancestor's record for a dispatch made at HEAD.
        commit=route.json('commits/'+oid)
        need(any(f.get('filename')==record_path and f.get('status')=='added'
                 for f in commit.get('files',[])),'DISPATCH_ORIGIN_NOT_HEAD_HOLD')
        from .handoff_recovery import dispatch_inventory
        now=int(time());inventory=dispatch_inventory(route,record['issued_at_unix'],now)
        safe_failures=[]
        for run in inventory:
            if run.get('status')!='completed' or run.get('conclusion') not in ('failure','cancelled','timed_out'):continue
            data=route.json('actions/runs/'+str(run['id'])+'/attempts/1/jobs?per_page=100')
            jobs=data['jobs'];names={j['name']:j for j in jobs}
            if (run.get('run_attempt')==1 and len(names)==len(jobs)==data.get('total_count') and
                names.get('preflight',{}).get('conclusion') in ('failure','cancelled','timed_out') and
                all(names.get(n,{}).get('conclusion')=='skipped' for n in
                    ('segment-intent','execution-fence','investigation','durable-archive'))):
                safe_failures.append(run['id'])
        need(current(route)==oid and state_at(route,oid)[0]==s,'DISPATCH_STATE_MOVED_HOLD')
        decision=inspect_dispatch(record,oid,inventory,now,preclaim_failed_run_ids=safe_failures)
        if decision!='REISSUE_AFTER_ATOMIC_STALE_PARENT_INVALIDATION':
            print(json.dumps({'state':decision,'record_path':record_path}));return
        retry={'schema':'mxm.native-dispatch-recovery.v1',
               'original_issuer_run_id':record['issuer_run_id'],
               'original_dispatch_oid':oid,'sequence':s['sequence'],
               'ciphertext_sha256':s['ciphertext_sha256'],
               'retry_number':1,'no_economic_exposure_before_claim':True,
               'reason':'OLDER_PARENT_NOW_INVALIDATED_BY_CAS'}
        dispatch_oid=atomic_publish(route,oid,{retry_path:encoded(retry)},
                       'One bounded handoff retry marker; invalidate original dispatch parent')
        state='BOUNDED_NATIVE_REISSUE'
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        record={'schema':'mxm.native-dispatch-intent.v3','parent_checkpoint_oid':oid,
                'ciphertext_sha256':s['ciphertext_sha256'],'sequence':s['sequence'],
                'source_sha':os.environ['LAB_SOURCE_SHA'],'admission_ref':ref,
                'admission_path':path,'issuer_run_id':int(os.environ['GITHUB_RUN_ID']),
                'issued_at_unix':int(time()),'retry_budget':1,'automatic_post_retry':True}
        dispatch_oid=atomic_publish(route,oid,{record_path:encoded(record)},
                       'Durably record native handoff before workflow_dispatch; bounded missing-ACK recovery')
        state='IMMEDIATE_NATIVE_HANDOFF'
    body={'ref':'mxm-remediation-p0-p4-20261015-v1',
          'inputs':{'parent_oid':dispatch_oid,'admission_ref':ref,
                    'admission_path':path,'fault_before_fence':'0'}}
    req=urllib.request.Request(
        'https://api.github.com/repos/mariancradulescu/mxm-quant-greenfield/actions/workflows/mxm-integrated-p0.yml/dispatches',
        data=encoded(body),method='POST',
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],
                 'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:
        need(response.status==204,'HANDOFF_ACK_UNRESOLVED_NO_BLIND_RETRY')
    print(json.dumps({'state':state,'parent_oid':dispatch_oid,
                      'bootstrap':False,'record_path':retry_path if state=='BOUNDED_NATIVE_REISSUE' else record_path}))

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
    """Native, keyless negative proofs, recorded to the evidence branch.

    No economic programme or original checkpoint is executed. The controlled
    ACK fault is enabled only inside this named proof job and restored even on
    error; it cannot leak into ordinary publisher execution.
    """
    route=workload('fault-probes',True)
    parent=current(route)
    original=file_at(route,'program-state.json',parent)
    state,_=state_at(route,parent)
    need(state['safe_stop'] is True and state['pending'] is None,
         'PROBES_TERMINAL_ONLY')
    need(state['last_run_id']==int(os.environ['GITHUB_RUN_ID']),
         'PROBES_NATIVE_RUN')
    configured=os.environ['GH_TOKEN']
    denied=False
    try:
        os.environ['GH_TOKEN']='MXM_INVALID_AUTHORIZATION_FIXTURE_ONLY'
        try:GetOnly().json('git/ref/heads/'+EVIDENCE_BRANCH)
        except urllib.error.HTTPError as error:denied=error.code==401
    finally:os.environ['GH_TOKEN']=configured
    need(denied,'PROBES_TOKEN_LOSS_NOT_REJECTED')
    manifest=strict_json(file_at(route,state['ciphertext_path'],parent))
    incomplete=False
    try:
        restore_ciphertext(manifest,lambda p:file_at(route,p,parent)[:-12]
                           if p==manifest['parts'][0]['path']
                           else file_at(route,p,parent))
    except Exception:incomplete=True
    need(incomplete,'PROBES_INCOMPLETE_CHECKPOINT_ACCEPTED')
    # Actual keyless native process: source entry cannot decrypt without secret.
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    missing_credentials_refused=False
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as tmp:
        try:_private_key_from_secret(Path(tmp))
        except Exception:missing_credentials_refused=True
    need(missing_credentials_refused,'PROBES_MISSING_PRIVATE_KEY_NOT_REFUSED')
    # A pre-fence proof must have exercised this R3 source. An old R2 crash
    # remains historical evidence and can never qualify the current source.
    admitted,_,_=definition(route)
    negative_run=admitted.get('native_pre_fence_run_id')
    need(type(negative_run) is int and negative_run>0 and
         negative_run!=int(os.environ['GITHUB_RUN_ID']),'PROBES_NATIVE_R3_CRASH_REFERENCE_REQUIRED')
    old_run=route.json('actions/runs/'+str(negative_run))
    old_jobs=route.json('actions/runs/'+str(negative_run)+'/attempts/1/jobs?per_page=100')['jobs']
    need(old_run['path']==WF and old_run['conclusion']=='failure' and
         can_recover_before_exposure({'pending':{'phase':'PRE_EXPOSURE'}},old_jobs),
         'PROBES_PRE_FENCE_CRASH_PROOF')
    old_path='typed-successor/recoveries/'+str(negative_run)+'.json'
    recovered=strict_json(file_at(route,old_path,parent))
    need(recovered['run_id']==negative_run and
         recovered['no_economic_exposure'] is True and
         recovered['refunds']==0,'PROBES_HISTORICAL_RECOVERY_PROOF')
    # Deliberate ACK loss is exclusively inside this fault-probes workload.
    ack_path='typed-successor/fault-probes/'+os.environ['GITHUB_RUN_ID']+'/ack.json'
    ack_bytes=encoded({'kind':'SYNTHETIC_ACK_LOSS_CAS_NONOUTCOME',
                       'native_run_id':int(os.environ['GITHUB_RUN_ID']),
                       'checkpoint_cipher_sha256':state['ciphertext_sha256'],
                       'orders':0,'new_outcomes':0})
    prior_fault=os.environ.get('LAB_FAULT_ACK')
    try:
        os.environ['LAB_FAULT_ACK']='AFTER_PUSH'
        ack_oid=atomic_publish(route,parent,{ack_path:ack_bytes},
                               'Native controlled ACK-fault reconciliation only; no economic work')
    finally:
        if prior_fault is None:os.environ.pop('LAB_FAULT_ACK',None)
        else:os.environ['LAB_FAULT_ACK']=prior_fault
    need(file_at(route,ack_path,ack_oid)==ack_bytes and
         file_at(route,'typed-successor/program-state.json',ack_oid)==
         file_at(route,'typed-successor/program-state.json',parent),
         'PROBES_ACK_EXACT_READBACK')
    from concurrent.futures import ThreadPoolExecutor
    from .custody import CASRefused
    def writer(name):
        try:
            result={'writer':name,'accepted':True,'expected_oid':ack_oid,'oid':atomic_publish(
            route,ack_oid,{'typed-successor/fault-probes/'+
                           os.environ['GITHUB_RUN_ID']+'/'+name+'.json':
                           encoded({'probe':name,'not_economic':True})},
            'Concurrent native evidence-plane writer proof '+name)}
        except CASRefused as refusal:
            result={'writer':name,'accepted':False,'expected_oid':refusal.parent,
                    'candidate_oid':refusal.candidate,'observed_oid':refusal.observed,
                    'reason':'NATIVE_GIT_EXPECTED_REF_REFUSED','native_reply':refusal.reply}
        # Separate native job log, subsequently read by the keyless verifier.
        print('MXM_CAS_RESULT '+json.dumps(result,sort_keys=True),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(writer,['A','B']))
    need(sum(x['accepted'] for x in results)==1,
         'PROBES_WRITER_EXCLUSION')
    checkpoint_oid=current(route)
    need(file_at(route,'program-state.json',checkpoint_oid)==original and
         state_at(route,checkpoint_oid)[0]==state,
         'PROBES_CHECKPOINT_CHANGED')
    proof={
        'schema':'mxm.e2e.native-negatives.v3',
        'run_id':int(os.environ['GITHUB_RUN_ID']),
        'source_sha':os.environ['LAB_SOURCE_SHA'],
        'sequence':state['sequence'],
        'ciphertext_sha256':state['ciphertext_sha256'],
        'checkpoint_parent_oid':parent,
        'ack_commit_oid':ack_oid,'ack_path':ack_path,
        'ack_sha256':bytes_digest(ack_bytes),
        'concurrent_writers':results,
        'cas_base_oid':ack_oid,'cas_final_oid':checkpoint_oid,
        'pre_fence_native_run_id':negative_run,
        'pre_fence_recovery_path':old_path,
        'unauthorized_get_http_code':401,
        'incomplete_checkpoint_rejected':incomplete,
        'missing_private_key_refused':missing_credentials_refused,
        'original_public_sha256':bytes_digest(original),
        'original_unchanged':True,'orders':0,'new_outcomes':0}
    file_name='typed-successor/verification/R3_NEGATIVE_'+os.environ['GITHUB_RUN_ID']+'.json'
    oid=atomic_publish(route,checkpoint_oid,{file_name:encoded(proof)},
                        'Record native negative controls with exact lineage and CAS readback')
    need(file_at(route,file_name,oid)==encoded(proof) and
         file_at(route,'program-state.json',oid)==original,
         'PROBES_NATIVE_RECORD_READBACK')
    print('INTEGRATED_FAULT_PROBES_V3 '+json.dumps({
        'evidence_oid':oid,'proof_path':file_name,'ack_commit_oid':ack_oid,
        'concurrent_successes':1,'run_id':proof['run_id'],
        'historical_crash_run':negative_run,'orders':0},sort_keys=True))

def verify():
    """Decrypt published bytes in a fresh cold job and produce v3 proof.

    The proof remains a GitHub Actions artifact until a separate keyless
    evidence publisher has checked this job and committed its exact bytes.
    No certificate is issued from this decrypting job.
    """
    route=workload('cold-readback')
    oid=os.environ['LAB_PARENT_OID']
    need(current(route)==oid,'VERIFY_PARENT')
    state,_=state_at(route,oid)
    need(state['safe_stop'] and state['pending'] is None,'VERIFY_NOT_TERMINAL')
    admission,ref,path=definition(route)
    from .evidence_v3 import cold_attestation,native_adapter_attestation
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as folder:
        tmp=Path(folder);key,fp=_private_key_from_secret(tmp)
        private=open_private(route,state,oid,key,tmp)
        # Native decrypt validates ciphertext and private sequence/source; the
        # producer also verifies every saved programme/cached shared asset.
        proof=cold_attestation(private,state,admission,oid,
                              int(os.environ['GITHUB_RUN_ID']),
                              os.environ['LAB_SOURCE_SHA'])
        adapter=None
        if proof['authentic_nonoutcome_results']:
            adapter=native_adapter_attestation(proof)
        need(bytes_digest(file_at(route,'program-state.json',oid))==ORIGINAL_PUBLIC,
             'VERIFY_ORIGINAL_CHANGED')
        need(current(route)==oid,'VERIFY_PARENT_MOVED')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'cold-readback.json').write_bytes(encoded(proof))
    if adapter is not None:
        (OUT/'authentic-adapter.json').write_bytes(encoded(adapter))
    print('INTEGRATED_COLD_READBACK_V3 '+json.dumps({
        'source_sha':proof['source_sha'],'evidence_oid':oid,
        'sequence':proof['sequence'],'programme_count':len(proof['programme_checkpoints']),
        'multi_program_A_B_A_verified':proof['multi_program_A_B_A_verified'],
        'authentic_nonoutcome_count':len(proof['authentic_nonoutcome_results']),
        'economic_release':False,'orders':0},sort_keys=True))

if __name__=='__main__':
    import sys
    try:
        functions={'preflight':preflight,'fence':fence,'recover':recover,'verify':verify,'observer':observer,'fault-probes':fault_probes}
        need(len(sys.argv)==2 and sys.argv[1] in functions,'INTEGRATED_MODE');functions[sys.argv[1]]()
    except Exception as e:
        code=str(e);print(json.dumps({'state':'INTEGRATED_SAFE_STOP','safe_code':code if re.fullmatch(r'LAB_[A-Z0-9_]+',code) else type(e).__name__}));raise SystemExit(1) from None
