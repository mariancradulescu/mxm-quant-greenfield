"""Deterministic renewable leases and at-most-once handoff proposals.

No credential loader, network client, implicit grant, scheduler or active writer.
Native installation must bind the root policy through the existing OWNER gate
and commit each proposal using Git receive-pack CAS before any consumer runs.
These components do not make the synthetic A issuer a production issuer.
"""
import copy
import re
from research_core_v4.p0_supersession_20261016.authority import (
    OWNER_ROOT, ACTIVE_REF, canonical, digest, need, oid, sha256, exact_fields)

PROVIDERS = ['EXISTING_PRESERVED_CORPORA', 'PEPPERSTONE_AUTHORIZED_SCOPE']
PHASES = ('B', 'C', 'D', 'E')

def validate_root(p):
    exact_fields(p, ('schema','owner_root','authority_ref','source_sha','principal',
                    'not_before','lease_seconds','max_items_per_lease','providers',
                    'orders_allowed','historical_restart_allowed'), 'B_ROOT_FIELDS')
    need(p['schema']=='mxm.renewable-continuation-root.v1' and
         p['owner_root']==list(OWNER_ROOT) and p['authority_ref']==ACTIVE_REF,
         'B_ROOT_SCOPE')
    need(oid(p['source_sha']) and p['principal']=='APP:5343530:172030470', 'B_ROOT_IDENTITY')
    need(type(p['not_before']) is int and p['not_before']>0 and
         type(p['lease_seconds']) is int and 60<=p['lease_seconds']<=86400 and
         type(p['max_items_per_lease']) is int and 1<=p['max_items_per_lease']<=100,
         'B_ROOT_BOUNDS')
    need(p['providers']==PROVIDERS and p['orders_allowed'] is False and
         p['historical_restart_allowed'] is False, 'B_ROOT_EXCLUSIONS')

def lease(p, now):
    validate_root(p)
    need(type(now) is int and now>=p['not_before'], 'B_CLOCK')
    index=(now-p['not_before'])//p['lease_seconds']
    start=p['not_before']+index*p['lease_seconds']
    return {'index':index,'not_before':start,'expires_at':start+p['lease_seconds'],
            'root_sha256':digest(canonical(p))}

def genesis(p):
    validate_root(p)
    return {'schema':'mxm.continuation-control.v1','root_sha256':digest(canonical(p)),
            'owner_root':list(OWNER_ROOT),'generation':1807,'phase':'B',
            'lease':None,'lease_items':0,'last_intent':None,'last_result_sha256':None,
            'journal_sha256':OWNER_ROOT[3],'pending':None,'revoked':False}

def validate_state(p,s):
    validate_root(p)
    exact_fields(s,genesis(p),'B_STATE_FIELDS')
    need(s['schema']=='mxm.continuation-control.v1' and
         s['root_sha256']==digest(canonical(p)) and s['owner_root']==list(OWNER_ROOT),
         'B_STATE_BINDING')
    need(type(s['generation']) is int and s['generation']>=1807 and
         s['phase'] in PHASES and type(s['revoked']) is bool and
         type(s['lease_items']) is int and 0<=s['lease_items']<=p['max_items_per_lease'] and
         sha256(s['journal_sha256']), 'B_STATE_FORMAT')
    if s['lease'] is None:
        need(s['generation']==1807 and s['lease_items']==0 and s['pending'] is None,
             'B_GENESIS_ONLY')
    else:
        l=s['lease'];exact_fields(l,('index','not_before','expires_at','root_sha256'),'B_LEASE_FIELDS')
        need(type(l['not_before']) is int and l==lease(p,l['not_before']), 'B_LEASE_BINDING')
    need((s['generation']==1807 and s['last_intent'] is None and s['last_result_sha256'] is None)
         or (s['generation']>1807 and type(s['last_intent']) is str and sha256(s['last_result_sha256'])),
         'B_RESULT_BINDING')
    if s['pending'] is not None:
        v=s['pending'];exact_fields(v,('intent','input_oid','input_sha256','generation','lease_index'), 'B_PENDING_FIELDS')
        need(oid(v['input_oid']) and sha256(v['input_sha256']) and
             v['generation']==s['generation']+1 and v['lease_index']==s['lease']['index'] and
             type(v['intent']) is str and re.fullmatch('[0-9a-f]{64}',v['intent']), 'B_PENDING_BINDING')

def propose(p,s,head,now,operation,*,input_sha256=None,result_sha256=None,
            journal_sha256=None,completed_phase=None,exclusivity_verified=False):
    """Return a CAS candidate, never write or execute it.

    Renewal is a deterministic child of the same OWNER policy, not approval of
    new source/scopes. Expired work cannot commit. An unresolved pending item
    prevents renewal/reexecution even after a timeout or a new process.
    """
    validate_state(p,s);need(oid(head), 'B_EXACT_HEAD')
    need(s['revoked'] is False, 'B_REVOKED')
    l=lease(p,now);out=copy.deepcopy(s)
    if operation=='revoke':
        out['revoked']=True
    elif operation=='renew':
        need(s['pending'] is None, 'B_PENDING_ACK_STOP')
        need(s['lease'] is None or l['index']>s['lease']['index'], 'B_RENEWAL_REPLAY_OR_ROLLBACK')
        out.update(lease=l,lease_items=0)
    else:
        need(s['lease']==l, 'B_LEASE_EXPIRED_OR_ROLLBACK')
        if operation=='claim':
            need(exclusivity_verified is True,'B_EXCLUSIVITY_NOT_PROVEN')
            need(s['pending'] is None and s['lease_items']<p['max_items_per_lease'], 'B_PENDING_OR_BUDGET')
            need(sha256(input_sha256), 'B_INPUT_DIGEST')
            item={'input_oid':head,'input_sha256':input_sha256,
                  'generation':s['generation']+1,'lease_index':l['index']}
            item['intent']=digest(canonical({'root':s['root_sha256'],**item}))
            out['pending']=item;out['lease_items']+=1
        elif operation=='complete':
            need(s['pending'] is not None and sha256(result_sha256) and sha256(journal_sha256),
                 'B_COMPLETION_BINDING')
            out.update(generation=s['pending']['generation'],last_intent=s['pending']['intent'],
                       last_result_sha256=result_sha256,journal_sha256=journal_sha256,pending=None)
        elif operation=='advance':
            need(s['pending'] is None and completed_phase==s['phase'] and completed_phase!='E',
                 'B_PHASE_TRANSITION')
            need(s['last_result_sha256']==result_sha256 and sha256(result_sha256), 'B_PHASE_EVIDENCE')
            need(s['phase']!='B' or exclusivity_verified is True, 'B_EXCLUSIVITY_NOT_PROVEN')
            out['phase']=PHASES[PHASES.index(s['phase'])+1]
        else:
            need(False,'B_OPERATION')
    validate_state(p,out)
    return {'expected_oid':head,'state':out,'state_sha256':digest(canonical(out)),
            'execution_allowed':False,'requires_native_CAS':True}

def reconcile(p,s,intent,result_sha256):
    validate_state(p,s)
    need(s['pending'] is None and s['last_intent']==intent and
         s['last_result_sha256']==result_sha256,'B_ACK_UNKNOWN_STOP')
    return {'status':'COMMITTED_READBACK_NO_REEXECUTION','generation':s['generation'],
            'execution_allowed':False,'retry_allowed':False}
