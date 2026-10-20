"""Keyless, independent evidence publication for a completed R3 native run.

Runs only as the attest-v3 job after cold-readback and fault-probes succeed.
Uses actual GitHub job IDs, reads the encrypted public checkpoint, validates
the cold-job artifact and native negative evidence, then atomically publishes
only immutable proof bytes. It cannot grant economic release.
"""
import json,os,re
from .common import need,encoded,digest
from .runtime import EVIDENCE_BRANCH
from .protocol import STATE_PATH,ORIGINAL_PUBLIC
from .evidence_v3 import COLD_SCHEMA,ADAPTER_SCHEMA,NEGATIVE_SCHEMA

def proof_paths(run_id):
    need(type(run_id) is int and run_id>0,'V3_NATIVE_RUN_ID')
    root='typed-successor/verification/R3_'
    return {'cold':root+'COLD_'+str(run_id)+'.json',
            'adapter':root+'ADAPTER_'+str(run_id)+'.json',
            'negative':root+'NEGATIVE_'+str(run_id)+'.json',
            'issuer':root+'ISSUER_'+str(run_id)+'.json'}

def native_jobs(route,run_id,names,require_completed_run=False,expected_head_sha=None):
    run=route.json('actions/runs/'+str(run_id))
    need(run['id']==run_id and run['path']=='.github/workflows/mxm-integrated-p0.yml'
         and run['head_branch']=='mxm-remediation-p0-p4-20261015-v1'
         and run['run_attempt']==1,'V3_NATIVE_RUN_IDENTITY')
    need(type(expected_head_sha) is str and re.fullmatch('[a-f0-9]{40}',expected_head_sha)
         and run.get('head_sha')==expected_head_sha,'V3_NATIVE_WORKFLOW_HEAD_MISMATCH')
    if require_completed_run:
        need(run['status']=='completed' and run['conclusion']=='success',
             'V3_NATIVE_RUN_NOT_TERMINAL_SUCCESS')
    jobs=route.json('actions/runs/'+str(run_id)+'/attempts/1/jobs?per_page=100')
    need(type(jobs.get('jobs')) is list and jobs.get('total_count',len(jobs['jobs']))<=100,
         'V3_NATIVE_JOB_LIST_INCOMPLETE')
    found={}
    for name in names:
        matched=[x for x in jobs['jobs'] if x.get('name')==name]
        need(len(matched)==1 and matched[0]['status']=='completed'
             and matched[0]['conclusion']=='success'
             and matched[0]['run_id']==run_id
             and type(matched[0].get('id')) is int,
             'V3_NATIVE_JOB_NOT_SUCCESS_'+name.upper().replace('-','_'))
        found[name]=matched[0]['id']
    return found

def validate_cold_artifact(cold,adapter,state,run_id,source,checkpoint_oid):
    need(type(cold) is dict and cold.get('schema')==COLD_SCHEMA
         and cold.get('run_id')==run_id
         and cold.get('source_sha')==state['source_sha']==source
         and cold.get('evidence_oid')==checkpoint_oid
         and cold.get('sequence')==state['sequence']
         and cold.get('ciphertext_sha256')==state['ciphertext_sha256']
         and cold.get('accounting')==state['accounting']
         and cold.get('original_unchanged') is True
         and cold.get('economic_workflow_released') is False
         and cold.get('orders')==cold.get('new_outcomes')==0
         and type(cold.get('programme_checkpoints')) is list
         and len(cold['programme_checkpoints'])>=1
         and type(cold.get('shared_catalogue_sha256')) is str
         and re.fullmatch('[a-f0-9]{64}',cold['shared_catalogue_sha256'])
         and type(cold.get('shared_catalogue_quarantine_sha256')) is str
         and re.fullmatch('[a-f0-9]{64}',cold['shared_catalogue_quarantine_sha256']),
         'V3_COLD_ARTIFACT_BINDING')
    ids=[x['id'] for x in cold['programme_checkpoints']]
    need(len(ids)==len(set(ids)) and
         all(x['safe_stop'] is True and type(x['steps_used']) is int
             and x['steps_used']>=0 and
             type(x['acquisition_remaining']) is int
             and x['acquisition_remaining']>=0 and
             all(type(x.get(k)) is str and re.fullmatch('[a-f0-9]{64}',x[k])
                 for k in ('checkpoint_sha256','progress_sha256',
                           'catalogue_sha256','acquisition_budget_sha256',
                           'native_receipts_sha256'))
             for x in cold['programme_checkpoints']) and
         type(cold.get('programme_execution_history_sha256')) is str and
         re.fullmatch('[a-f0-9]{64}',
                      cold['programme_execution_history_sha256']) and
         type(cold.get('private_sha256')) is str and
         re.fullmatch('[a-f0-9]{64}',cold['private_sha256']),
         'V3_COLD_PROGRAMME_ATTESTATION')
    if adapter is None:
        need(not cold['authentic_nonoutcome_results'],
             'V3_ADAPTER_MISSING_FOR_ACTUAL_RESULT')
    else:
        need(adapter.get('schema')==ADAPTER_SCHEMA and
             adapter.get('run_id')==run_id and
             adapter.get('source_sha')==source and
             adapter.get('checkpoint_oid')==checkpoint_oid and
             adapter.get('cold_private_sha256')==cold['private_sha256'] and
             adapter.get('cold_proof_sha256')==digest(cold) and
             adapter.get('nonoutcome_result_refs')==
             cold['authentic_nonoutcome_results'] and
             adapter.get('orders')==adapter.get('economic_outcomes')==0
             and adapter.get('fixture_only') is False,
             'V3_ADAPTER_COLD_ORIGIN_MISMATCH')

def validate_negative_artifact(route,proof,run_id,source,state):
    from .runtime import file_at
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    need(proof.get('schema')==NEGATIVE_SCHEMA and
         proof.get('run_id')==run_id and proof.get('source_sha')==source and
         proof.get('sequence')==state['sequence'] and
         proof.get('ciphertext_sha256')==state['ciphertext_sha256'] and
         proof.get('orders')==proof.get('new_outcomes')==0 and
         proof.get('unauthorized_get_http_code')==401 and
         proof.get('missing_private_key_refused') is True and
         proof.get('incomplete_checkpoint_rejected') is True and
         proof.get('original_public_sha256')==ORIGINAL_PUBLIC and
         proof.get('original_unchanged') is True,
         'V3_NATIVE_NEGATIVE_FIELDS')
    writers=proof['concurrent_writers']
    need(len(writers)==2 and
         sum(x['accepted'] is True for x in writers)==1 and
         set(x['writer'] for x in writers)=={'A','B'},
         'V3_NATIVE_WRITER_COLLISION')
    winner=next(x for x in writers if x['accepted'] is True)
    loser=next(x for x in writers if x['accepted'] is not True)
    base=proof.get('cas_base_oid');final=proof.get('cas_final_oid')
    need(all(type(x) is str and re.fullmatch('[a-f0-9]{40}',x)
             for x in (base,final,winner.get('oid'),loser.get('candidate_oid'))) and
         base==proof['ack_commit_oid'] and final==winner['oid'] and
         loser.get('observed_oid')==final and loser.get('candidate_oid')!=final and
         loser.get('reason')=='NATIVE_GIT_STALE_INFO' and
         all(x.get('expected_oid')==base for x in writers),
         'V3_NATIVE_CAS_IDENTITIES')
    commit=route.json('git/commits/'+final)
    need(commit.get('sha')==final and
         [p['sha'] for p in commit.get('parents',[])]==[base],
         'V3_NATIVE_WINNER_COMMIT')
    name=winner['writer'];path='typed-successor/fault-probes/'+str(run_id)+'/'+name+'.json'
    need(strict_json(file_at(route,path,final))=={'probe':name,'not_economic':True},
         'V3_NATIVE_WINNER_PAYLOAD')
    from .protocol import STATE_PATH
    need(file_at(route,STATE_PATH,base)==file_at(route,STATE_PATH,final),
         'V3_NATIVE_CAS_STATE_CHANGED')
    job=native_jobs(route,run_id,('fault-probes',),expected_head_sha=state.get('last_trigger_sha'))['fault-probes']
    log=route.data('actions/jobs/'+str(job)+'/logs').decode('utf-8')
    records=[strict_json(m.encode()) for m in re.findall(r'MXM_CAS_RESULT (\{[^\r\n]*\})',log)]
    need(len(records)==2 and sorted(records,key=lambda x:x['writer'])==
         sorted(writers,key=lambda x:x['writer']),
         'V3_NATIVE_CAS_LOG_MISMATCH')
    ack_oid=proof['ack_commit_oid']
    checkpoint_parent=proof['checkpoint_parent_oid']
    need(type(ack_oid) is str and re.fullmatch('[a-f0-9]{40}',ack_oid)
         and type(checkpoint_parent) is str and
         re.fullmatch('[a-f0-9]{40}',checkpoint_parent),
         'V3_NEGATIVE_COMMIT_IDENTITY')
    relation=route.json('compare/'+checkpoint_parent+'...'+ack_oid)
    need(relation.get('status')=='ahead' and
         relation.get('ahead_by')==1 and relation.get('behind_by')==0 and
         relation.get('base_commit',{}).get('sha')==checkpoint_parent,
         'V3_ACK_PROOF_NOT_DIRECT_CAS_DESCENDANT')
    ack=strict_json(file_at(route,proof['ack_path'],ack_oid))
    need(ack['native_run_id']==run_id and
         ack['checkpoint_cipher_sha256']==state['ciphertext_sha256'] and
         ack['orders']==ack['new_outcomes']==0
         and digest(ack)==proof['ack_sha256'],
         'V3_NATIVE_ACK_NOT_PERSISTED')
    prior=proof['pre_fence_native_run_id']
    need(prior==39322312307,'V3_HISTORICAL_CRASH_ID')
    negative_run=route.json('actions/runs/'+str(prior))
    need(negative_run['conclusion']=='failure' and
         negative_run['path']=='.github/workflows/mxm-integrated-p0.yml',
         'V3_HISTORICAL_NATIVE_CRASH_NOT_PROVEN')
    jobs=route.json('actions/runs/'+str(prior)+'/attempts/1/jobs?per_page=100')['jobs']
    from .protocol import can_recover_before_exposure
    need(can_recover_before_exposure({'pending':{'phase':'PRE_EXPOSURE'}},jobs),
         'V3_PRE_FENCE_JOB_GRAPH_MISMATCH')
    historical=strict_json(file_at(route,proof['pre_fence_recovery_path'],
                                   proof['checkpoint_parent_oid']))
    need(historical['run_id']==prior and
         historical['no_economic_exposure'] is True and
         historical['refunds']==0,'V3_PRE_FENCE_RECOVERY_MISSING')

def validate_public_state(state,run_id,source):
    need(state['sequence']>=21 and state['source_sha']==source
         and state['last_run_id']==run_id
         and state['safe_stop'] is True and state['pending'] is None
         and state['orders']==0 and state['original_public_sha256']==ORIGINAL_PUBLIC
         and state['accounting']['lanes']['V2']['outcome_charged']==21
         and state['accounting']['lanes']['V2']['reservation_holds']==1
         and state['accounting']['refunds']==0,
         'V3_PUBLIC_CHECKPOINT_INVARIANTS')

def build_issuer(route,run_id,source,checkpoint_oid,cold,adapter,negative,state):
    validate_public_state(state,run_id,source)
    validate_cold_artifact(cold,adapter,state,run_id,source,checkpoint_oid)
    validate_negative_artifact(route,negative,run_id,source,state)
    jobs=native_jobs(route,run_id,('preflight','segment-intent',
                'execution-fence','investigation','durable-archive',
                'cold-readback','fault-probes'),expected_head_sha=state.get('last_trigger_sha'))
    return {'schema':'mxm.e2e.native-proof-issuer.v3',
            'source_sha':source,'run_id':run_id,
            'checkpoint_oid':checkpoint_oid,'sequence':state['sequence'],
            'ciphertext_sha256':state['ciphertext_sha256'],
            'job_ids':jobs,'cold_sha256':digest(cold),
            'adapter_sha256':digest(adapter) if adapter is not None else None,
            'negative_sha256':digest(negative),
            'economic_release':False,'orders':0}

def publish():
    from .runtime import anchors,file_at
    from .integrated import workload,current,state_at
    from .custody import atomic_publish
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    need(os.environ['GITHUB_JOB']=='attest-v3'
         and not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')
         and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),
         'V3_KEYLESS_ISSUER')
    route=workload('attest-v3',True)
    run_id=int(os.environ['GITHUB_RUN_ID']);source=os.environ['LAB_SOURCE_SHA']
    checkpoint_oid=os.environ['LAB_PARENT_OID']
    head=current(route);state,_=state_at(route,head)
    # Fault-probes may have appended immutable evidence but not changed state.
    original=strict_json(file_at(route,STATE_PATH,checkpoint_oid))
    need(state==original,'V3_CHECKPOINT_CHANGED_SINCE_COLD')
    from pathlib import Path
    cold=strict_json(Path('verification/integrated-p0-input/cold-readback.json').read_bytes())
    adapter_path=Path('verification/integrated-p0-input/authentic-adapter.json')
    adapter=strict_json(adapter_path.read_bytes()) if adapter_path.exists() else None
    neg_path=proof_paths(run_id)['negative']
    negative=strict_json(file_at(route,neg_path,head))
    issuer=build_issuer(route,run_id,source,checkpoint_oid,cold,adapter,negative,state)
    paths=proof_paths(run_id)
    data={paths['cold']:encoded(cold),paths['issuer']:encoded(issuer)}
    if adapter is not None:data[paths['adapter']]=encoded(adapter)
    # Publisher is unique and CAS-protected. Refuse to overwrite any proof.
    oid=atomic_publish(route,head,data,'R3 keyless proof archive; economic gate still closed')
    need(all(file_at(route,p,oid)==v for p,v in data.items()),
         'V3_ARCHIVED_BYTE_READBACK')
    print(json.dumps({'state':'R3_NATIVE_PROOFS_SEALED_NOT_ACCEPTED',
                      'evidence_oid':oid,'source_sha':source,
                      'run_id':run_id,'adapter_present':adapter is not None,
                      'end_to_end_operational_accepted':False},sort_keys=True))
if __name__=='__main__':
    publish()
