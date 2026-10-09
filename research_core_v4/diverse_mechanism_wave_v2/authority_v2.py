"""Separate exact one-use wave authority. No acceptance is minted by code."""
import json,re
from datetime import datetime,timezone
from research_core_v4.numeric_development_v3 import authority_v3 as olda
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n

ROOT=old.ROOT
PREFIX='research_core_v4/diverse_mechanism_wave_v2/'
SCIENCE_PREFIX='research_core_v4/diverse_mechanism_wave_v1/'
DESIGN=SCIENCE_PREFIX+'DESIGN_FREEZE_V1.json'
DESIGN_SHA='e9318ce49b35e2f37390d21213ccbff3a673e68cd481f2d34565744db4ac28a1'
KERNEL=SCIENCE_PREFIX+'kernel_v1.py'
BINDINGS=PREFIX+'SOURCE_SHA256_BINDINGS_V2.json'
ARM=PREFIX+'EXACT_REAL_WAVE_ARM_CANDIDATE_V2.json'
APPROVAL=PREFIX+'INDEPENDENT_ACCEPTANCE_V2.json'
WORKFLOW='.github/workflows/mxm-master1576-diverse-wave-real-v2.yml'
need=olda.need;enc=olda.enc;sha=olda.sha;read=olda.read;digest=olda.digest;git=olda.git;ancestor=olda.ancestor
WORKER=PREFIX+'worker_v2.py'
AUTHORITY=PREFIX+'authority_v2.py'
RECOVERY=PREFIX+'INDEPENDENT_RECOVERY_ACCEPTANCE_V2.json'
REPORTING={'every_cell':read(DESIGN)['reporting']['every_cell'],'diagnostic_reference':'H2 sign(C2-O2), fully elapsed second feature hour','diagnostic_fields':['eligible','agreements','disagreements','undefined'],'supported_subset':True,'weekly_identity_full_reconciliation':True,'privacy':'ENCRYPTED_ONLY','undefined_emitted_cases':0}
RECOVERY_POLICY={'protocol':'EXISTING_AUTHENTICATED_V2_PREFIX_AND_V3_FINALIZATION','separate_independent_recovery_acceptance':True,'resume_next_unprocessed_shard':True,'durable_replay':False,'atomic_receipt_claim':True,'total_original_budget_preserved':True,'real_prefixes':[25,50,75,100]}
BUDGET={'wall_seconds':3600,'cpu_seconds':7200,'ram_kib':8388608,'workers':1}
SCOPE={'experiment':'MASTER1576_TWO_HOUR_RANGE_TRANSLATION_AND_ACTIVITY_IMPACT_DECELERATION_WAVE_V1','mechanisms':['RANGE_TRANSLATION_CONTINUATION','ACTIVITY_IMPACT_DECELERATION_REVERSAL'],'comparisons':6,'lags_seconds':[0,300,900],'response_horizon_seconds':3600,'identities':1576,'source_shards':100,'historical_rows':3355389,'calendar_start_UTC':'2026-08-20T00:00:00Z','calendar_end_exclusive_UTC':'2026-09-17T00:00:00Z','attempts':1,'automatic_retries':0,'broker_requests':0,'protected_forward':False,'new_alpha':False,'live_orders':False,'purpose':'STANDALONE_GROSS_EXPLORATORY_DEVELOPMENT_ONLY'}

def candidate(source,bindings,mode='real'):
    need(digest(DESIGN)==DESIGN_SHA,'FROZEN_WAVE_DESIGN_DRIFT')
    return {'schema':'mxm.diverse.wave.arm.v2','status':'CANDIDATE_NOT_AUTHORIZED','mode':mode,'source_head':source,'bindings':bindings,'design_sha256':DESIGN_SHA,'kernel_sha256':digest(KERNEL),'worker_sha256':digest(WORKER),'authority_sha256':digest(AUTHORITY),'workflow_sha256':digest(WORKFLOW),'source_manifest_sha256':digest(BINDINGS),'reporting':REPORTING,'recovery':RECOVERY_POLICY,'manifest_sha256':n.MANIFEST_SHA,'key_spki_sha256':old.FP,'invocation_id':sha(enc({'design':DESIGN_SHA,'data':n.MANIFEST_SHA,'operational_version':'DIVERSE_WAVE_V2'})),'scope':SCOPE,'budget':BUDGET,'expires_UTC':'2026-10-16T23:59:59Z'}

def bindings(head,arm):
    ancestor(arm['source_head'],head)
    need(set(read(SCIENCE_PREFIX+'SOURCE_SHA256_BINDINGS_V1.json')['bindings']).issubset(arm['bindings']) and {WORKER,AUTHORITY,WORKFLOW,KERNEL,DESIGN}.issubset(arm['bindings']),'WAVE_BINDING_COMPLETENESS')
    need(arm['bindings']==read(BINDINGS)['bindings'],'WAVE_BINDING_MANIFEST')
    need(sha(git('show',arm['source_head']+':'+BINDINGS))==digest(BINDINGS),'SOURCE_MANIFEST_DRIFT')
    for p,h in arm['bindings'].items():
        need(re.fullmatch('[0-9a-f]{64}',h) is not None and digest(p)==h and sha(git('show',arm['source_head']+':'+p))==h,'WAVE_BOUND_SOURCE_DRIFT')

def validate_candidate(head,arm,mode):
    need(arm==candidate(arm['source_head'],arm['bindings'],mode),'EXACT_WAVE_ARM_DRIFT')
    need(datetime.now(timezone.utc)<=datetime.strptime(arm['expires_UTC'],'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc),'STALE_WAVE_ARM')
    bindings(head,arm)
    return arm

def real_gate(head):
    need((ROOT/ARM).is_file() and (ROOT/APPROVAL).is_file(),'MISSING_INDEPENDENT_WAVE_ACCEPTANCE')
    arm=read(ARM);need((ROOT/ARM).read_bytes()==enc(arm),'WAVE_ARM_CANONICAL_BYTES')
    validate_candidate(head,arm,'real');approval=read(APPROVAL)
    need(set(approval)=={'schema','status','mode','role','arm_sha256','source_head','arm_commit','audit_receipt_sha256','explicit_acceptance'},'WAVE_ACCEPTANCE_FIELDS')
    need(approval['schema']=='mxm.diverse.wave.independent.acceptance.v2' and approval['status']=='INDEPENDENT_ACCEPTANCE_PASS' and approval['mode']=='real' and approval['role']=='INDEPENDENT_AUDITOR' and approval['explicit_acceptance'] is True,'INDEPENDENT_WAVE_ACCEPTANCE_REQUIRED')
    need(approval['arm_sha256']==digest(ARM) and approval['source_head']==arm['source_head'] and re.fullmatch('[0-9a-f]{64}',approval['audit_receipt_sha256'] or ''),'WAVE_ACCEPTANCE_BINDING')
    ac=approval['arm_commit'];ancestor(arm['source_head'],ac);ancestor(ac,head)
    need(sha(git('show',ac+':'+ARM))==digest(ARM),'WAVE_ARM_INTRODUCTION')
    pc=git('log','-1','--format=%H',head,'--',APPROVAL).decode().strip();ancestor(ac,pc)
    need(pc not in (ac,arm['source_head']) and git('diff-tree','--no-commit-id','--name-only','-r',pc).decode().splitlines()==[APPROVAL] and git('rev-list','--parents','-n','1',pc).decode().count(' ')==1,'WAVE_ACCEPTANCE_SEPARATE_ONE_FILE_COMMIT')
    return arm

def real_event_gate():
    import os
    need(os.environ.get('GITHUB_EVENT_NAME') in ('push','workflow_dispatch') and os.environ.get('GITHUB_WORKFLOW_REF')==old.REPO+'/'+WORKFLOW+'@refs/heads/'+old.BRANCH and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','WAVE_EVENT_OR_RETRY_DENIED')

def unavailable_acceptance_preflight():
    need(not (ROOT/APPROVAL).exists(),'UNEXPECTED_REAL_WAVE_ACCEPTANCE')
    original=read('research_core_v4/numeric_development_v3/EXACT_REAL_DEVELOPMENT_ARM_CANDIDATE_V3.json')
    need(candidate('',{})['invocation_id']!=original['invocation_id'],'ORIGINAL_INVOCATION_REUSE')

# Reuse the accepted V2 recovery law. Only the fabricated adapter prefix is 1.
from research_core_v4.numeric_development_v2 import authority_v2 as recovery_authority
original_recovery_gate=recovery_authority.recovery_gate
def recovery_gate(auth,arm,approval_sha,previous,body):
    if arm['mode']=='synthetic':
        need(auth.get('next_shard')==1,'FABRICATED_EXACT_PREFIX')
        original_recovery_gate({**auth,'next_shard':25},arm,approval_sha,previous,body)
    else:original_recovery_gate(auth,arm,approval_sha,previous,body)

def stopped_original_preflight(arm,previous):
    need(type(previous) is int and previous>0,'PREVIOUS_RUN_FORMAT')
    refs=old.api('git/matching-refs/tags/mxm-numeric-v2-claim-real-'+arm['invocation_id'])
    matches=[r for r in refs if r['ref']=='refs/tags/mxm-numeric-v2-claim-real-'+arm['invocation_id']]
    need(len(matches)==1,'ORIGINAL_INVOCATION_NOT_CLAIMED')
    run=old.api('actions/runs/'+str(previous))
    need(run['id']==previous and run['head_sha']==matches[0]['object']['sha'] and run['run_attempt']==1 and run['path']==WORKFLOW and run['status']=='completed' and run['conclusion'] in ('failure','cancelled','timed_out'),'ORIGINAL_RUN_MUST_BE_STOPPED_AND_FAILED')

def recovery_document(head):
    need((ROOT/RECOVERY).is_file(),'MISSING_SEPARATE_RECOVERY_ACCEPTANCE')
    rc=git('log','-1','--format=%H',head,'--',RECOVERY).decode().strip()
    need(git('diff-tree','--no-commit-id','--name-only','-r',rc).decode().splitlines()==[RECOVERY] and git('rev-list','--parents','-n','1',rc).decode().count(' ')==1,'RECOVERY_ACCEPTANCE_SEPARATION')
    pc=git('log','-1','--format=%H',head,'--',APPROVAL).decode().strip()
    ancestor(pc,rc);need(pc!=rc,'RECOVERY_ACCEPTANCE_LATER')
    return read(RECOVERY)
