"""Upgrade the existing periodic observer for the unchanged sealed R3 engine.

Only the observer control file is new. All engine modules must retain the exact
accepted source digest. The existing App/CAS/dispatch implementations and issuer
environment are reused. Uncertain execution exposure remains a conservative
HOLD, never a refund, task replay or invented recovery.
"""
import contextlib
import json
import os
import re
import subprocess
from pathlib import Path
from .common import need,encoded,bytes_digest,digest
from . import custody,integrated as engine,runtime
from .protocol import STATE_PATH,ORIGINAL_PUBLIC,can_recover_before_exposure,recovered_public_base,require_jobs
from .attest_v3 import native_checkout_provenance
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json

REPO='mariancradulescu/mxm-quant-greenfield'
ENGINE='c6f8b46685dec3b9f9ee2ee6dd3cf12f0609add2'
ENGINE_MODULE='704e5e92c2b05a486af1d2c75a4ccd85d57fad295e073f229faf0c1e19d52840'
PATH='.github/workflows/mxm-integrated-p0-recovery.yml'

def build_workflow(source):
    need(type(source) is str and re.fullmatch('[a-f0-9]{40}',source),'OBSERVER_SOURCE_PIN')
    return {'name':'MXM integrated P0 ordinary recovery',
        'on':{'push':{'branches':['main'],'paths':[PATH]},
              'schedule':[{'cron':'11,26,41,56 * * * *'}],
              'workflow_run':{'workflows':['MXM integrated P0 technical recovery'],'types':['completed']},
              'workflow_dispatch':{'inputs':{'cas_transport_probe':{
                  'description':'Manual fixed-path CAS reply diagnostic on closed checkpoint; no reception claim',
                  'type':'boolean','default':False,'required':True}}}},'permissions':{},
        'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False,'queue':'max'},
        'jobs':{'ordinary-recovery':{
            'if':"github.repository == 'mariancradulescu/mxm-quant-greenfield' && github.run_attempt == 1",
            'runs-on':'ubuntu-24.04','timeout-minutes':8,
            'environment':'mxm-p0-successor-issuer-v1',
            'permissions':{'contents':'read','actions':'write'},'steps':[
                {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
                 'with':{'ref':source,'persist-credentials':False}},
                {'run':'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock'},
                {'name':'Verify observer role, bounded recovery and exact engine module identity',
                 'run':'python3 -m unittest research_core_v4.laboratory.test_recovery_v3 -v'},
                {'name':'Observe durable R3 state; recover only proven pre-exposure failures or missing handoffs',
                 'run':'python3 -m research_core_v4.laboratory.recovery_v3',
                 'env':{'GH_TOKEN':'${{ github.token }}','LAB_SOURCE_SHA':ENGINE,
                        'LAB_INTEGRATED_PROTOCOL':'v2','LAB_OBSERVER_SOURCE_SHA':source,
                        'SUCCESSOR_APP_PRIVATE_KEY':'${{ secrets.SUCCESSOR_APP_PRIVATE_KEY }}',
                        'R3_CONTROL_WITNESS':'${{ vars.R3_CONTROL_WITNESS }}',
                        'LAB_CAS_TRANSPORT_DIAGNOSTIC':"${{ github.event_name == 'workflow_dispatch' && inputs.cas_transport_probe && '1' || '0' }}"}}]}}}

def context(route):
    source=os.environ.get('LAB_OBSERVER_SOURCE_SHA','');trigger=os.environ.get('GITHUB_SHA','')
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')=='main'
         and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')=='ordinary-recovery'
         and os.environ.get('GITHUB_EVENT_NAME') in ('schedule','push','workflow_run','workflow_dispatch')
         and os.environ.get('GITHUB_WORKFLOW_SHA')==trigger
         and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/main'
         and os.environ.get('LAB_SOURCE_SHA')==ENGINE and os.environ.get('LAB_INTEGRATED_PROTOCOL')=='v2'
         and re.fullmatch('[a-f0-9]{40}',source) and re.fullmatch('[a-f0-9]{40}',trigger),
         'R3_OBSERVER_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM',
         'CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID',
         'R3_CTRADER_CLIENT_SECRET','R3_CTRADER_ACCESS_TOKEN')),'R3_OBSERVER_NO_CUSTODY_OR_BROKER')
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==source and
         subprocess.run(['git','diff','--quiet','HEAD','--'],capture_output=True).returncode==0,
         'R3_OBSERVER_UNMODIFIED_CHECKOUT')
    # This separate existing control-plane role has an additional observer file,
    # while every engine module is exactly the sealed ENGINE implementation.
    need(runtime.module_digest()==ENGINE_MODULE,'R3_OBSERVER_ENGINE_MODULE_DRIFT')
    need(route.json('git/ref/heads/'+runtime.SOURCE_BRANCH)['object']['sha']==ENGINE,
         'R3_OBSERVER_ENGINE_REF_DRIFT')
    need(route.json('git/ref/heads/main')['object']['sha']==trigger,
         'R3_OBSERVER_WORKFLOW_MOVED')
    need(strict_json(runtime.file_at(route,PATH,trigger))==build_workflow(source),
         'R3_OBSERVER_EXACT_WORKFLOW')
    runtime.old.owner_unchanged(route)
    need(route.json('git/ref/heads/mxm-o04-active-v1')['object']['sha']==engine.AUTH,
         'R3_OBSERVER_AUTHORITY_DRIFT')
    active=strict_json(runtime.file_at(route,'state.json',engine.AUTH))
    need(active['revoked'] is False and active['pending'] is None,'R3_OBSERVER_REVOKED_OR_PENDING')
    rule=route.json('rulesets/25222248')
    runtime.source_admission(ENGINE,ENGINE,ENGINE,rule)
    return {'observer_source_sha':source,'engine_source_sha':ENGINE,'trigger_sha':trigger}

def predecessor(state,run,jobs):
    need(run.get('path')==engine.WF and run.get('head_branch')==custody_branch()
         and run.get('run_attempt')==1,'R3_OBSERVER_PRIOR_WORKLOAD')
    if run.get('status')!='completed':return 'WAIT_ACTIVE_NATIVE_RUN'
    names={j['name']:j for j in jobs}
    need(len(names)==len(jobs),'R3_OBSERVER_DUPLICATE_JOB')
    if state.get('pending'):
        return 'RECOVER_PRE_EXPOSURE' if can_recover_before_exposure(state,jobs) else 'HOLD_AMBIGUOUS_EXPOSURE'
    require_jobs(jobs,['preflight','segment-intent','execution-fence','investigation','durable-archive'])
    return 'CONTINUE_DURABLE_SUCCESSOR'

def custody_branch():return 'mxm-remediation-p0-p4-20261015-v1'

def controlled_fault(route,run_id,jobs):
    claims=[j for j in jobs if j['name']=='segment-intent']
    need(len(claims)==1 and claims[0].get('run_id')==run_id,'R3_OBSERVER_CLAIM_JOB')
    log=route.data('actions/jobs/'+str(claims[0]['id'])+'/logs').decode('utf-8')
    flags=re.findall(r'^\S+Z\s+LAB_FAULT_BEFORE_FENCE:\s*([01])\s*$',log,re.M)
    need(len(flags)==1,'R3_OBSERVER_CONTROLLED_FAULT_PROVENANCE')
    return flags[0]=='1'

@contextlib.contextmanager
def observer_scope(route):
    need(custody._NATIVE_WRITER_SCOPE is None,'R3_OBSERVER_NESTED_SCOPE')
    identity=context(route)
    from research_core_v4.p0_successor_a_20261017.issuer import _app_token,http
    from .operational_acceptance import verify_effective_controls
    # This is the same existing, admin-controlled environment witness used by
    # the integrated source-control writer; it cannot come from an admission.
    witness=strict_json(os.environ.get('R3_CONTROL_WITNESS','').encode())
    need(bool(os.environ.get('SUCCESSOR_APP_PRIVATE_KEY')),'R3_OBSERVER_EXISTING_KEY_REQUIRED')
    key=os.environ.pop('SUCCESSOR_APP_PRIVATE_KEY')
    try:
        with _app_token(key) as token:
            key=None
            class Controls:
                def json(self,path):
                    need(path.startswith(('rulesets/','rules/branches/')),'R3_OBSERVER_CONTROL_READ_NAMESPACE')
                    _,value=http('/repos/'+REPO+'/'+path,token)
                    if path.startswith('rulesets/') and any(r.get('type')=='update' for r in value.get('rules',[])):
                        return custody.resolve_control_policy(value,witness,ENGINE)
                    return value
            controls=Controls()
            def guard():
                context(route);verify_effective_controls(controls)
                need(bytes_digest(runtime.file_at(route,'program-state.json',engine.current(route)))==ORIGINAL_PUBLIC,
                     'R3_OBSERVER_ORIGINAL_CHANGED')
            custody._NATIVE_WRITER_SCOPE={'source':ENGINE,'job':'ordinary-recovery','operation':'observer',
                'token':token,'guard':guard,'controls':controls}
            try:
                guard();yield identity
            finally:custody._NATIVE_WRITER_SCOPE=None
    finally:key=None

def observe(route):
    oid=engine.current(route);state,initial=engine.state_at(route,oid)
    if initial or state.get('source_sha')!=ENGINE:
        return {'state':'OTHER_SOURCE_NO_BOOTSTRAP','dispatches':0}
    if state['pending'] is None and state['safe_stop']:
        return {'state':'ADMITTED_PROGRAMME_COMPLETE_NO_DISPATCH','dispatches':0}
    prior=state['pending']['run_id'] if state['pending'] else state['last_run_id']
    run=route.json('actions/runs/'+str(prior));metadata=route.json('actions/runs/'+str(prior)+'/attempts/1/jobs?per_page=100')
    jobs=metadata['jobs'];need(run.get('id')==prior and len(jobs)==metadata.get('total_count') and
         all(j.get('run_id')==prior for j in jobs),'R3_OBSERVER_COMPLETE_JOB_INVENTORY')
    action=predecessor(state,run,jobs)
    if action in ('WAIT_ACTIVE_NATIVE_RUN','HOLD_AMBIGUOUS_EXPOSURE'):
        return {'state':action,'dispatches':0}
    if action=='RECOVER_PRE_EXPOSURE':
        names={j['name']:j['id'] for j in jobs if j['name'] in ('preflight','segment-intent')}
        native_checkout_provenance(route,prior,ENGINE,run['head_sha'],names)
        intent=strict_json(runtime.file_at(route,'typed-successor/intents/'+str(prior)+'.json',oid))
        need(intent['pending']['run_id']==prior and intent['preflight']['source_sha']==ENGINE
             and intent['preflight']['run_id']==prior and intent['base_state']['pending'] is None
             and intent['base_state']['ciphertext_sha256']==state['ciphertext_sha256'],
             'R3_OBSERVER_EXACT_RECOVERY_INTENT')
        controlled=controlled_fault(route,prior,jobs);base=recovered_public_base(intent)
        record={'run_id':prior,'state':'ABORTED_BEFORE_FENCE_NATIVE_SKIPPED_WORKER',
                'no_economic_exposure':True,'refunds':0,'old_intent_retained':True,
                'base_state_sha256':digest(intent['base_state']),'controlled_technical_fault':controlled}
        oid=custody.atomic_publish(route,oid,{STATE_PATH:encoded(base),
            'typed-successor/recoveries/'+str(prior)+'.json':encoded(record)},
            'Existing R3 observer recovers only proven native pre-exposure intent')
        state=base
        if controlled:return {'state':'CONTROLLED_TECHNICAL_FAULT_RECOVERED_NO_AUTOMATIC_DISPATCH','dispatches':0}
        if state.get('source_sha')!=ENGINE or state['safe_stop']:
            return {'state':'CLOSED_PREDECESSOR_RECOVERED_NO_BOOTSTRAP','dispatches':0}
    ref=state.get('admission_ref');path=state.get('admission_path')
    if state.get('recovery_continuation'):
        recovery=state['recovery_continuation'];ref=recovery['admission_ref'];path=recovery['admission_path']
        prior=recovery['run_id'];proof=strict_json(runtime.file_at(route,'typed-successor/recoveries/'+str(prior)+'.json',oid))
        need(proof.get('no_economic_exposure') is True and proof.get('refunds')==0,'R3_OBSERVER_RECOVERY_PROOF')
        if proof.get('controlled_technical_fault') is True:
            return {'state':'CONTROLLED_TECHNICAL_FAULT_NO_AUTOMATIC_DISPATCH','dispatches':0}
        if 'controlled_technical_fault' not in proof:
            jobs=route.json('actions/runs/'+str(prior)+'/attempts/1/jobs?per_page=100')['jobs']
            if controlled_fault(route,prior,jobs):
                return {'state':'CONTROLLED_TECHNICAL_FAULT_NO_AUTOMATIC_DISPATCH','dispatches':0}
    os.environ['LAB_ADMISSION_REF']=ref;os.environ['LAB_ADMISSION_PATH']=path
    admission,ref,path=engine.definition(route)
    need(admission['mode']=='TECHNICAL_NONOUTCOME' and admission['economic_release'] is False,
         'R3_OBSERVER_TECHNICAL_ONLY')
    need(state['sequence']<=state.get('admission_start_sequence',state['sequence'])+
         sum(m['budget']['steps'] for m in admission['programmes']),'R3_OBSERVER_FINITE_TOTAL')
    # Reuse the durable issuance record, paginated native inventory, exact
    # stale-parent invalidation and single retry budget. No blind POST retry.
    engine.dispatch_once(route,oid,state,ref,path)
    return {'state':'R3_OBSERVER_EXISTING_HANDOFF_PROTOCOL_COMPLETED','prior_run_id':prior}

def main():
    route=GetOnly()
    with observer_scope(route) as identity:
        if os.environ.get('LAB_CAS_TRANSPORT_DIAGNOSTIC')=='1':
            from .transport_diagnostic import observe_transport
            result=observe_transport(route)
        else:result=observe(route)
        print('MXM_R3_OBSERVER '+json.dumps({**identity,**result,'orders':0,'new_economic_outcomes':0},sort_keys=True))
    print('MXM_R3_OBSERVER_EXISTING_TOKEN_REVOKED',flush=True)

if __name__=='__main__':main()
