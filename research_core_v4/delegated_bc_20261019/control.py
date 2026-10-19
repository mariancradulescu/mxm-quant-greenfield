"""Pure proposals for the immutable delegated B-C workload.

GitHub's native source seal and isolated App route admit this *new* source.
The historical OWNER-review source and its manifest are never reinterpreted.
"""
import copy
from research_core_v4.p0_supersession_20261016.authority import (
    OWNER_ROOT, ACTIVE_REF, canonical, digest, need, oid, sha256)

SOURCE = 'mxm-o04-successor-code-bc-v1'
WORKFLOW = '.github/workflows/mxm-delegated-bc.yml'
TASKS = ('B_COLD_RESTORE_1','B_COLD_RESTORE_2','C_PARTIAL_IDENTIFICATION','D_ECONOMIC_ADMISSION')
POLICY = {'schema':'mxm.native-configured-delegation.v1',
    'authorization_kind':'DELEGATED_OPERATIONAL_OWNER_NOT_PERSONAL_REVIEW',
    'source_branch':SOURCE,'authority_ref':ACTIVE_REF,'owner_root':list(OWNER_ROOT),
    'principal':'APP:5343530:172030470','repository_id':1374181010,
    'lease_seconds':60,'max_task_seconds':40,'max_items_per_run':1,
    'tasks':list(TASKS),'providers':['EXISTING_PRESERVED_CORPORA','PEPPERSTONE_AUTHORIZED_SCOPE'],
    'orders_allowed':False,'historical_restart_allowed':False,
    'code_updates_allowed':False,'native_owner_review_claimed':False,
    'owner_final_control':'REVOKE_APP_INSTALLATION_OR_ACTIVE_REF_GRANT_OR_SOURCE_ACCESS',
    'scientific_scope':'NEW_OFFLINE_POSTPROCESSING_OF_AUTHENTIC_EXISTING_SUMMARY_NO_KERNEL_REPLAY'}
POLICY_SHA = digest(canonical(POLICY))

def genesis(source,now,source_rule_id=1):
    need(oid(source) and type(now) is int and now>0,'BC_GENESIS_INPUT')
    return {'schema':'mxm.delegated-runtime.v1','source_sha':source,'policy_sha256':POLICY_SHA,
        'owner_root':list(OWNER_ROOT),'started_at':now,'source_rule_id':source_rule_id,'sequence':0,'lease':None,
        'revoked':False,'pending':None,'done':[],'checkpoint_sha256':None,'halt':None}

def lease(s,now):
    need(type(now) is int and now>=s['started_at'],'BC_CLOCK')
    index=(now-s['started_at'])//POLICY['lease_seconds']
    start=s['started_at']+index*POLICY['lease_seconds']
    return {'index':index,'not_before':start,'expires_at':start+POLICY['lease_seconds']}

def validate(s,source):
    need(type(s) is dict and set(s)==set(genesis(source,1)),'BC_STATE_FIELDS')
    need(s['schema']=='mxm.delegated-runtime.v1' and s['source_sha']==source and
         s['policy_sha256']==POLICY_SHA and s['owner_root']==list(OWNER_ROOT),'BC_STATE_BINDING')
    need(type(s['started_at']) is int and s['started_at']>0 and type(s['sequence']) is int and
         0<=s['sequence']<=len(TASKS) and type(s['revoked']) is bool and
         type(s['source_rule_id']) is int and s['source_rule_id']>0,'BC_STATE_TYPES')
    need(type(s['done']) is list and len(s['done'])==s['sequence'],'BC_SEQUENCE')
    for n,row in enumerate(s['done']):
        need(set(row)=={'task','intent','input_oid','result_sha256','run_id','lease_index'} and
             row['task']==TASKS[n] and sha256(row['intent']) and oid(row['input_oid']) and
             sha256(row['result_sha256']) and type(row['run_id']) is int and row['run_id']>0 and
             type(row['lease_index']) is int and row['lease_index']>=0,'BC_DONE_RECORD')
    need(len({r['intent'] for r in s['done']})==len(s['done']),'BC_REPLAY')
    need((s['sequence']==0 and s['checkpoint_sha256'] is None) or
         (s['sequence']>0 and sha256(s['checkpoint_sha256'])),'BC_CHECKPOINT_BINDING')
    if s['lease'] is not None:
        need(type(s['lease']) is dict and type(s['lease'].get('not_before')) is int and
             s['lease']==lease(s,s['lease']['not_before']),'BC_LEASE_BINDING')
    if s['pending'] is not None:
        p=s['pending']
        need(set(p)=={'task','intent','input_oid','run_id','lease_index'} and
             s['sequence']<len(TASKS) and p['task']==TASKS[s['sequence']] and
             sha256(p['intent']) and oid(p['input_oid']) and type(p['run_id']) is int and
             p['run_id']>0 and s['lease'] is not None and
             p['lease_index']==s['lease']['index'],'BC_PENDING_BINDING')
        fields={k:v for k,v in p.items() if k!='intent'}
        need(p['intent']==digest(canonical({'source':source,'policy':POLICY_SHA,**fields})),
             'BC_PENDING_INTENT')
    need(s['halt'] in (None,'REGISTERED_QUEUE_COMPLETE_NO_CBOT_QUALIFICATION'), 'BC_HALT')
    need(s['halt'] is None or s['sequence']==len(TASKS),'BC_PREMATURE_HALT')

def propose(s,source,head,now,operation,*,run_id=None,result_sha256=None,checkpoint_sha256=None):
    validate(s,source);need(oid(head),'BC_EXACT_PARENT')
    out=copy.deepcopy(s)
    if operation=='revoke':
        out['revoked']=True
    else:
        need(not s['revoked'] and s['halt'] is None,'BC_REVOKED_OR_HALTED')
        current=lease(s,now)
        if operation=='renew':
            need(s['pending'] is None,'BC_PENDING_STOP_NO_REEXECUTION')
            need(s['lease'] is None or current['index']>s['lease']['index'],'BC_RENEWAL_REPLAY')
            out['lease']=current
        elif operation=='claim':
            need(s['lease']==current and now+POLICY['max_task_seconds']<=current['expires_at'],
                 'BC_LEASE_TOO_SHORT')
            need(s['pending'] is None and s['sequence']<len(TASKS),'BC_PENDING_OR_TASKS_DONE')
            need(type(run_id) is int and run_id>0,'BC_RUN_ID')
            if s['done']:
                need(run_id!=s['done'][-1]['run_id'],'BC_FRESH_RUN_REQUIRED')
                need(current['index']>s['done'][-1]['lease_index'],'BC_FRESH_LEASE_REQUIRED')
            p={'task':TASKS[s['sequence']],'input_oid':head,'run_id':run_id,
               'lease_index':current['index']}
            p['intent']=digest(canonical({'source':source,'policy':POLICY_SHA,**p}))
            out['pending']=p
        elif operation=='complete':
            need(s['lease']==current and s['pending'] is not None and
                 s['pending']['run_id']==run_id,'BC_COMPLETION_LEASE_OR_RUN')
            need(sha256(result_sha256) and sha256(checkpoint_sha256),'BC_COMPLETION_DIGEST')
            row={**s['pending'],'result_sha256':result_sha256}
            out['done'].append(row);out['pending']=None;out['sequence']+=1
            out['checkpoint_sha256']=checkpoint_sha256
            if out['sequence']==len(TASKS):out['halt']='REGISTERED_QUEUE_COMPLETE_NO_CBOT_QUALIFICATION'
        else:need(False,'BC_OPERATION')
    validate(out,source)
    return out

def scheduling(s,source,now):
    validate(s,source)
    if s['revoked']:return 'REVOKED'
    if s['pending'] is not None:return 'PENDING_STOP_NO_REEXECUTION'
    if s['halt'] is not None:return s['halt']
    lease(s,now)  # a backwards clock must never dispatch
    return 'CONTINUE'
