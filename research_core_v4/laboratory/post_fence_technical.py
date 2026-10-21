"""Conservative retirement of fenced technical work; never economic recovery.

Only the sealed zero-broker/zero-outcome operator language is eligible. A
possibly executed technical task is retired, not replayed or labelled complete.
Economic exposure remains an explicit HOLD until its separate ledger protocol.
"""
from copy import deepcopy
from .common import need,digest

POINTS={'BEFORE_DECRYPT','AFTER_RESTORE','AFTER_TASK'}
SCHEMA='mxm.technical-post-fence-retirement.v1'

def technical_scope(admission):
    need(admission.get('mode')=='TECHNICAL_NONOUTCOME' and
         admission.get('economic_release') is False and
         type(admission.get('programmes')) is list and admission['programmes'],
         'POST_FENCE_TECHNICAL_ONLY')
    for manifest in admission['programmes']:
        need(manifest.get('mode')=='TECHNICAL_NONOUTCOME' and
             manifest.get('orders')==0 and manifest['budget']['broker_requests']==
             manifest['budget']['new_identities']==0 and manifest.get('tasks'),
             'POST_FENCE_ZERO_RESOURCE_SCOPE')
        need(all(task.get('operator') in ('report','classify','native_corpus_readonly') and
                 task.get('trial_units')==0 for task in manifest['tasks'].values()),
             'POST_FENCE_ZERO_OUTCOME_OPERATORS')

def eligible(state,intent,admission,jobs,run):
    technical_scope(admission)
    pending=state.get('pending')
    need(type(pending) is dict and pending.get('phase')=='EXECUTION_FENCED' and
         pending=={**intent['pending'],'phase':'EXECUTION_FENCED'} and
         intent['preflight']['admission_sha256']==digest(admission),
         'POST_FENCE_EXACT_INTENT')
    need(run.get('id')==pending['run_id'] and run.get('run_attempt')==1 and
         run.get('head_branch')=='mxm-remediation-p0-p4-20261015-v1' and
         run.get('path')=='.github/workflows/mxm-integrated-p0.yml' and
         run.get('head_sha')==intent['preflight']['trigger_sha'],
         'POST_FENCE_NATIVE_RUN')
    by={job['name']:job for job in jobs}
    need(len(by)==len(jobs),'POST_FENCE_DUPLICATE_NATIVE_JOBS')
    required={'source-controls','preflight','segment-intent','execution-fence','investigation','durable-archive'}
    need(required<=set(by) and all(type(by[n].get('id')) is int and by[n]['id']>0 and
         by[n].get('run_id')==run['id'] for n in required) and
         len({by[n]['id'] for n in required})==len(required),'POST_FENCE_NATIVE_JOB_IDENTITIES')
    need(all(by.get(name,{}).get('status')=='completed' and
             by[name].get('conclusion')=='success' for name in
             ('source-controls','preflight','segment-intent','execution-fence')),
         'POST_FENCE_NATIVE_PREFIX')
    need(by.get('investigation',{}).get('status')=='completed' and
         by['investigation'].get('conclusion') in ('failure','cancelled','timed_out') and
         by.get('durable-archive',{}).get('status')=='completed' and
         by['durable-archive'].get('conclusion')=='skipped',
         'POST_FENCE_FAILED_WORKER_ONLY')
    base=intent['base_state']
    need(base.get('pending') is None and
         {k:v for k,v in state.items() if k!='pending'}==
         {k:v for k,v in base.items() if k!='pending'},
         'POST_FENCE_BASE_BYTES_CHANGED')
    return True

def retire(state,intent,admission,jobs,run,fence_oid):
    eligible(state,intent,admission,jobs,run)
    base=deepcopy(intent['base_state'])
    run_id=run['id'];key=str(run_id)
    retired=deepcopy(base.get('retired_technical_admissions',{}))
    need(key not in retired,'POST_FENCE_ALREADY_RETIRED')
    record={'schema':SCHEMA,'run_id':run_id,'source_sha':intent['preflight']['source_sha'],
        'trigger_sha':run['head_sha'],'fence_oid':fence_oid,
        'base_state_sha256':digest(intent['base_state']),
        'admission_ref':intent['preflight']['admission_ref'],
        'admission_path':intent['preflight']['admission_path'],
        'admission_sha256':digest(admission),
        'programme_manifests':{m['id']:digest(m) for m in admission['programmes']},
        'task_semantic_sha256':sorted({digest({'operator':t['operator'],'input':t.get('input')})
            for m in admission['programmes'] for t in m['tasks'].values()}),
        'worker_job_id':next(j['id'] for j in jobs if j['name']=='investigation'),
        'state':'TECHNICAL_EXECUTION_UNCERTAIN_RETIRED_WITHOUT_REPLAY',
        'programme_complete':False,'economic_scope_proven_absent':True,
        'economic_outcomes':0,'broker_requests':0,'orders':0,'refunds':0,
        'accounting_unchanged':base['accounting'],
        'ciphertext_sha256':base['ciphertext_sha256'],'sequence':base['sequence']}
    retired[key]={'record_sha256':digest(record),'admission_sha256':digest(admission),
                  'programme_manifests':record['programme_manifests'],
                  'task_semantic_sha256':record['task_semantic_sha256']}
    base['retired_technical_admissions']=retired
    base.pop('recovery_continuation',None)
    return base,record

def refuse_replay(state,admission):
    programmes={m['id']:digest(m) for m in admission['programmes']}
    tasks={digest({'operator':t['operator'],'input':t.get('input')})
           for m in admission['programmes'] for t in m['tasks'].values()}
    for retired in state.get('retired_technical_admissions',{}).values():
        need(retired['admission_sha256']!=digest(admission) and
             not set(programmes)&set(retired['programme_manifests']) and
             not tasks&set(retired['task_semantic_sha256']),
             'POST_FENCE_RETIRED_PROGRAMME_NO_REPLAY')

def verify_inventory(route,oid,state):
    """Reconstruct retained retirements from immutable native runs, not booleans."""
    import urllib.error
    from .runtime import file_at
    from .attest_v3 import native_checkout_provenance
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    rows=state.get('retired_technical_admissions',{})
    need(type(rows) is dict and len(rows)<=128,'POST_FENCE_RETIREMENT_INVENTORY_LIMIT')
    try:files=route.json('contents/typed-successor/post-fence-retirements?ref='+oid)
    except urllib.error.HTTPError as error:
        if error.code!=404:raise
        files=[]
    need(type(files) is list and len(files)<=128 and
         all(f.get('type')=='file' and f.get('name','').endswith('.json') for f in files) and
         {f['name'][:-5] for f in files}==set(rows),'POST_FENCE_RETIREMENT_INVENTORY_CHANGED')
    for key,row in rows.items():
        need(key.isdigit() and int(key)>0,'POST_FENCE_RETIREMENT_RUN_ID')
        record=strict_json(file_at(route,'typed-successor/post-fence-retirements/'+key+'.json',oid))
        need(record.get('schema')==SCHEMA and digest(record)==row.get('record_sha256'),
             'POST_FENCE_RETIREMENT_RECORD_CHANGED')
        fence_oid=record['fence_oid'];run_id=int(key)
        intent=strict_json(file_at(route,'typed-successor/intents/'+key+'.json',fence_oid))
        admission=strict_json(file_at(route,record['admission_path'],record['admission_ref']))
        fenced=strict_json(file_at(route,'typed-successor/program-state.json',fence_oid))
        run=route.json('actions/runs/'+key)
        need(run.get('status')=='completed' and run.get('conclusion') in
             ('failure','cancelled','timed_out'),'POST_FENCE_RETIREMENT_NATIVE_NOT_TERMINAL')
        inventory=route.json('actions/runs/'+key+'/attempts/1/jobs?per_page=100')
        need(inventory.get('total_count')==len(inventory['jobs'])<=100,
             'POST_FENCE_RETIREMENT_COMPLETE_JOBS')
        restored,expected=retire(fenced,intent,admission,inventory['jobs'],run,fence_oid)
        need(record==expected and row==restored['retired_technical_admissions'][key],
             'POST_FENCE_RETIREMENT_NOT_NATIVE_DERIVED')
        prefix={j['name']:j['id'] for j in inventory['jobs'] if j['name'] in
                ('source-controls','preflight','segment-intent','execution-fence','investigation')}
        native_checkout_provenance(route,run_id,record['source_sha'],record['trigger_sha'],prefix)
    return len(rows)

def inject(point,admission):
    import os
    selected=os.environ.get('LAB_FAULT_AFTER_FENCE','')
    need(selected=='' or selected in POINTS,'POST_FENCE_FAULT_POINT')
    if selected:
        technical_scope(admission)
        if selected==point:need(False,'INJECTED_TECHNICAL_POST_FENCE_'+point)

def recover_native(route,oid,state):
    """Existing keyless recovery job; finite native provenance before its CAS."""
    import os,json
    from . import integrated as engine
    from .protocol import STATE_PATH,ORIGINAL_PUBLIC
    from .custody import atomic_publish
    from .runtime import file_at
    from .common import encoded,bytes_digest
    from .attest_v3 import native_checkout_provenance
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    admission,ref,path=engine.definition(route)
    # Economic or unknown modes remain a HOLD, never a presumed no-exposure.
    if admission.get('mode')!='TECHNICAL_NONOUTCOME':
        engine.output(next='HELD');print(json.dumps({'state':'POST_FENCE_ECONOMIC_EXPOSURE_HELD_NO_REPLAY'}));return
    run_id=state['pending']['run_id']
    external=os.environ.get('GITHUB_JOB')=='ordinary-recovery'
    need(external or run_id==int(os.environ['GITHUB_RUN_ID']),'POST_FENCE_NATIVE_RECOVERY_CONTEXT')
    run=route.json('actions/runs/'+str(run_id))
    if external:
        need(run.get('status')=='completed' and run.get('conclusion') in
             ('failure','cancelled','timed_out'),'POST_FENCE_OBSERVER_TERMINAL_RUN')
    inventory=route.json('actions/runs/'+str(run_id)+'/attempts/1/jobs?per_page=100')
    need(inventory['total_count']==len(inventory['jobs'])<=100,'POST_FENCE_COMPLETE_NATIVE_JOB_INVENTORY')
    jobs=inventory['jobs']
    intent=strict_json(file_at(route,'typed-successor/intents/'+str(run_id)+'.json',oid))
    need(intent['preflight']['admission_ref']==ref and intent['preflight']['admission_path']==path,
         'POST_FENCE_ADMISSION_LOCATOR')
    need(intent['preflight']['source_sha']==os.environ['LAB_SOURCE_SHA'],'POST_FENCE_SOURCE_IDENTITY')
    eligible(state,intent,admission,jobs,run)
    commit=route.json('commits/'+oid)
    fence_path='typed-successor/fences/'+str(run_id)+'.json'
    need(len(commit.get('parents',[]))==1 and
         {(f['filename'],f['status']) for f in commit.get('files',[])}==
         {(STATE_PATH,'modified'),(fence_path,'added')},'POST_FENCE_EXACT_FENCE_COMMIT')
    fence=strict_json(file_at(route,fence_path,oid));claim_oid=commit['parents'][0]['sha']
    need(fence=={'run_id':run_id,'claim_oid':claim_oid,'phase':'EXECUTION_FENCED','no_automatic_retry':True},
         'POST_FENCE_EXACT_FENCE_BYTES')
    claim=route.json('commits/'+claim_oid)
    need([p['sha'] for p in claim.get('parents',[])]==[intent['preflight']['parent_oid']] and
         {(f['filename'],f['status']) for f in claim.get('files',[])}==
         {(STATE_PATH,'modified'),('typed-successor/intents/'+str(run_id)+'.json','added')},
         'POST_FENCE_EXACT_CLAIM_COMMIT')
    need(strict_json(file_at(route,STATE_PATH,intent['preflight']['parent_oid']))==intent['base_state'] and
         strict_json(file_at(route,STATE_PATH,claim_oid))==
         {**intent['base_state'],'pending':intent['pending']},'POST_FENCE_EXACT_CLAIM_BYTES')
    prefix={j['name']:j['id'] for j in jobs if j['name'] in
            ('source-controls','preflight','segment-intent','execution-fence','investigation')}
    native_checkout_provenance(route,run_id,os.environ['LAB_SOURCE_SHA'],run['head_sha'],prefix)
    new,record=retire(state,intent,admission,jobs,run,oid)
    record_path='typed-successor/post-fence-retirements/'+str(run_id)+'.json'
    need(bytes_digest(file_at(route,'program-state.json',oid))==ORIGINAL_PUBLIC,
         'POST_FENCE_ORIGINAL_AUTHORITY_CHANGED')
    published=atomic_publish(route,oid,{STATE_PATH:encoded(new),record_path:encoded(record)},
        'Retire uncertain zero-outcome technical segment after native worker failure; no replay or refund')
    need(engine.state_at(route,published)[0]==new and file_at(route,record_path,published)==encoded(record),
         'POST_FENCE_RETIREMENT_READBACK')
    engine.output(next='NONE',evidence_oid=published)
    print('MXM_TECHNICAL_POST_FENCE_RETIREMENT '+json.dumps({'evidence_oid':published,'record':record},sort_keys=True))
    return published
