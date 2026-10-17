"""Native B publisher wiring. No entry is armed by repository publication.

Initial native OWNER review binds source, custody facts and renewable policy.
Ordinary runs verify that original review, current source seal and server ACL,
then renew deterministic finite leases without another human gate. Native App
credential and OWNER decryption key remain in one isolated process. The only B
worker installed here restores the real frozen journal; C economics is separate.
"""
import base64
import dataclasses
import json
import os
import pathlib
import tempfile
import time
import urllib.request
from .continuity import *
from . import recovery
from research_core_v4.p0_successor_a_20261017.publisher import GitCAS, AckUnknown
from research_core_v4.p0_successor_a_20261017.issuer import http, _app_token, KEY_FP, APP_ID
from research_core_v4.p0_owner_governance_20261017.governance import (
    GateBinding, GitHubReadOnly, verify_owner_review)
from research_core_v4.p0_supersession_20261016.authority import strict_json, Denied

SOURCE='mxm-o04-successor-code-b-v1'
WORKFLOW='.github/workflows/mxm-p0-successor-runtime-b.yml'
PREFIX='/repos/mariancradulescu/mxm-quant-greenfield/'
GATE_ID=24553414129
GATE='mxm-p0-owner-critical-v1'
REMOTE='https://github.com/mariancradulescu/mxm-quant-greenfield.git'

def workload():
    need(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
         os.environ.get('GITHUB_REF')=='refs/heads/'+SOURCE and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1','B_FROZEN_WORKLOAD')

def verify_bundle(b,now,*,initial=False):
    exact_fields(b,('root','access','manifest','binding'),'B_BUNDLE_FIELDS')
    p=b['root'];a=b['access'];m=b['manifest'];validate_root(p)
    binding=GateBinding(**b['binding'])
    need(binding.environment_id==GATE_ID and binding.environment_name==GATE and
         binding.workflow_path==WORKFLOW and binding.source_sha==p['source_sha'] and
         m['critical_operation']=='BOOTSTRAP_AND_DELEGATE' and
         m['policy_sha256']==digest(canonical({'root':p,'access':a})) and
         m['not_before']==p['not_before'],'B_NATIVE_ROOT_BINDING')
    if initial:need(m['not_before']<=now<m['expires_at'],'B_INITIAL_REVIEW_EXPIRED')
    exact_fields(a,('schema','app_id','installation_id','repository_id','source_branch',
                    'source_freeze_ruleset_id','private_key_fingerprint','old_custody_closed_at',
                    'custody_evidence_sha256','exclusive_custody_confirmed'), 'B_ACCESS_FIELDS')
    need(a['schema']=='mxm.successor-b-access.v1' and a['app_id']==5343530 and
         a['installation_id']==172030470 and a['repository_id']==1374181010 and
         a['source_branch']==SOURCE and a['private_key_fingerprint']==KEY_FP and
         type(a['source_freeze_ruleset_id']) is int and a['source_freeze_ruleset_id']>0 and
         type(a['old_custody_closed_at']) is int and a['old_custody_closed_at']>0 and
         now>=a['old_custody_closed_at']+3600 and sha256(a['custody_evidence_sha256']) and
         a['exclusive_custody_confirmed'] is True, 'B_CUSTODY_OR_TTL_NOT_PROVEN')
    need(os.environ['GITHUB_SHA']==p['source_sha'],'B_EXECUTION_SOURCE')
    verify_owner_review(GitHubReadOnly(),binding,m)
    return p,a

def verify_server(p,a,token,*,exact_acl):
    _,ref=http(PREFIX+'git/ref/heads/'+SOURCE,token)
    need(ref['object']['sha']==p['source_sha'],'B_SOURCE_CHANGED')
    _,freeze=http(PREFIX+'rulesets/'+str(a['source_freeze_ruleset_id']),token)
    need(freeze['enforcement']=='active' and
         freeze['conditions']['ref_name']=={'include':['refs/heads/'+SOURCE],'exclude':[]} and
         {'creation','update','deletion','non_fast_forward'}=={r['type'] for r in freeze['rules']},
         'B_SOURCE_NOT_SEALED')
    need(freeze.get('bypass_actors',None if exact_acl else [])==[],'B_SOURCE_BYPASS')
    _,acl=http(PREFIX+'rulesets/25268790',token)
    expected=[{'actor_id':APP_ID,'actor_type':'Integration','bypass_mode':'always'}]
    need(acl['enforcement']=='active' and
         acl['conditions']['ref_name']=={'include':[ACTIVE_REF],'exclude':[]} and
         {'creation','update','deletion','non_fast_forward'}=={r['type'] for r in acl['rules']} and
         acl.get('bypass_actors',None if exact_acl else expected)==expected,'B_SINGLE_PRINCIPAL_ACL')
    _,owner_ref=http(PREFIX+'git/ref/heads/mxm-o04-accepted-owner-1807-v1',token)
    need(owner_ref['object']['sha']==OWNER_ROOT[1],'B_OWNER_ROOT_CHANGED')

class NativeStore(GitCAS):
    """Reuse accepted receive-pack CAS, candidate and ACK semantics unchanged."""
    def __init__(self,folder,token,bundle):
        self.directory=pathlib.Path(folder);self.directory.mkdir()
        self.ref=ACTIVE_REF;self.bundle=bundle
        # A minimal child environment prevents the OWNER decoder key, App key,
        # runner commands and unrelated repository credentials entering Git.
        self.env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TMPDIR')}
        self.env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',
            GIT_AUTHOR_NAME='MXM successor B',GIT_COMMITTER_NAME='MXM successor B',
            GIT_AUTHOR_EMAIL='mxm@example.invalid',GIT_COMMITTER_EMAIL='mxm@example.invalid',
            GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
            GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+token).encode()).decode())
        self.git('init','-q')
    def read(self):
        h=self.head()
        if h is None:return None,None
        self.git('fetch','--quiet','--no-tags',REMOTE,h)
        s=strict_json(self.git('show',h+':state.json').stdout)
        exact_fields(s,('schema','bundle','control'),'B_NATIVE_STATE_FIELDS')
        need(s['schema']=='mxm.native-continuation.v1' and s['bundle']==self.bundle,'B_NATIVE_STATE_ROOT')
        validate_state(self.bundle['root'],s['control'])
        need(self.head()==h,'B_HEAD_MOVED')
        return h,s
    def wrap(self,s):return {'schema':'mxm.native-continuation.v1','bundle':self.bundle,'control':s}

def public_state():
    token=os.environ['GH_TOKEN']
    _,r=http(PREFIX+'contents/state.json?ref=mxm-o04-active-v1',token)
    need(r['size']<=1048576 and r['encoding']=='base64','B_NATIVE_STATE_BUDGET')
    s=strict_json(base64.b64decode(r['content']))
    need(s.get('schema')=='mxm.native-continuation.v1','B_NATIVE_STATE_SCHEMA')
    return s

def plan():
    workload();initial=os.environ['B_COMMAND']=='arm'
    if initial:
        a=json.loads(os.environ['B_ACCESS']);now=int(time.time())
        p={'schema':'mxm.renewable-continuation-root.v1','owner_root':list(OWNER_ROOT),
           'authority_ref':ACTIVE_REF,'source_sha':os.environ['GITHUB_SHA'],
           'principal':'APP:5343530:172030470','not_before':now,'lease_seconds':60,
           'max_items_per_lease':100,'providers':PROVIDERS,'orders_allowed':False,
           'historical_restart_allowed':False}
        m={'schema':'mxm.owner-critical-manifest.v2','critical_operation':'BOOTSTRAP_AND_DELEGATE',
           'operation_id':'MXM-B-'+os.environ['GITHUB_RUN_ID'],'source_sha':p['source_sha'],
           'policy_sha256':digest(canonical({'root':p,'access':a})),
           'audit_reception_sha256':digest(canonical({'B1':'OWNER_CONFIRMED_ACCEPTED_NO_REPEAT'})),
           'owner_root_oid':OWNER_ROOT[1],'not_before':now,'expires_at':now+86400}
        binding=GateBinding(int(os.environ['GITHUB_RUN_ID']),GATE_ID,GATE,p['source_sha'],WORKFLOW,digest(canonical(m)))
        b={'root':p,'access':a,'manifest':m,'binding':dataclasses.asdict(binding)}
    else:
        b=public_state()['bundle'];verify_bundle(b,int(time.time()))
    out=pathlib.Path('verification/successor-b');out.mkdir(parents=True,exist_ok=True)
    (out/'native-bundle.json').write_bytes(canonical(b))
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('bundle='+canonical(b).decode()+'\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
        f.write('B exact root: `'+digest(canonical(b))+'`\n\n')
        if initial:f.write('Native OWNER comment: `MXM_OWNER_CRITICAL_APPROVAL_V2 sha256='+b['binding']['manifest_sha256']+'`\n')

def execute():
    workload();need(os.environ.get('GITHUB_JOB')=='successor-issuer','B_ISSUER_JOB')
    b=json.loads(os.environ['B_BUNDLE']);initial=os.environ['B_COMMAND']=='arm'
    p,a=verify_bundle(b,int(time.time()),initial=initial)
    verify_server(p,a,os.environ['GH_TOKEN'],exact_acl=False)
    need('SUCCESSOR_APP_PRIVATE_KEY' in os.environ,'B_CREDENTIAL_NOT_INSTALLED')
    with _app_token(os.environ['SUCCESSOR_APP_PRIVATE_KEY']) as token, tempfile.TemporaryDirectory() as d:
        verify_server(p,a,token,exact_acl=True)
        t=NativeStore(pathlib.Path(d)/'publisher',token,b);h,s=t.read()
        if initial:
            need(h is None,'B_BOOTSTRAP_EXISTS')
            h=t.cas(None,t.wrap(genesis(p)));h,s=t.read()
        else:need(h is not None,'B_AUTHORITY_MISSING_NO_REBOOTSTRAP')
        control=s['control'];need(control['phase']=='B','B_NEXT_PHASE_REQUIRES_INSTALLED_C_WORKER')
        need(control['generation']<1809,'B_PROOF_COMPLETE_C_INSTALLATION_PENDING')
        prior_lease_index=None if control['lease'] is None else control['lease']['index']
        if control['lease']!=lease(p,int(time.time())):
            v=propose(p,control,h,int(time.time()),'renew');h=t.cas(h,t.wrap(v['state']));h,s=t.read();control=s['control']
        # Never start a restoration at the very end of a short proof lease.
        # Wait before claiming; a timeout here leaves no pending side effect.
        remaining=control['lease']['expires_at']-int(time.time())
        if remaining<30:
            need(control['pending'] is None,'B_PENDING_ACK_STOP')
            time.sleep(max(0,remaining)+1)
            h,s=t.read();control=s['control']
            v=propose(p,control,h,int(time.time()),'renew');h=t.cas(h,t.wrap(v['state']));h,s=t.read();control=s['control']
        # Any persisted pending work causes STOP here, never a callback retry.
        v=propose(p,control,h,int(time.time()),'claim',input_sha256=OWNER_ROOT[3],exclusivity_verified=True)
        h=t.cas(h,t.wrap(v['state']));h,s=t.read();control=s['control']
        route=recovery.owner.get;old_open=urllib.request.urlopen
        from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
        readonly=GetOnly();recovery.owner.get=readonly.json;urllib.request.urlopen=readonly.open
        try:receipt=recovery.recover()
        finally:recovery.owner.get=route;urllib.request.urlopen=old_open
        result=digest(canonical(receipt));intent=control['pending']['intent']
        # Check server revocation immediately before completion; native rules
        # enforce a concurrent revocation at receive-pack as well.
        verify_server(p,a,token,exact_acl=True)
        v=propose(p,control,h,int(time.time()),'complete',result_sha256=result,journal_sha256=OWNER_ROOT[3])
        h=t.cas(h,t.wrap(v['state']));h,s=t.read()
        final=reconcile(p,s['control'],intent,result)
        final.update(native_oid=h,root_sha256=s['control']['root_sha256'],
                     original_owner_generation=1807,research_executed=False,
                     B_worker='REAL_READ_ONLY_RESTORATION',C_worker_installed=False,
                     prior_lease_index=prior_lease_index,lease=s['control']['lease'])
        out=pathlib.Path('verification/successor-b/native-receipt.json');out.write_bytes(canonical(final))
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:
            f.write('next='+('continue' if s['control']['generation']==1808 else 'STOP_B_PROOF_COMPLETE_C_INSTALLATION_PENDING')+'\n')
            f.write('next_after='+str(s['control']['lease']['expires_at']+1)+'\n')
        print(canonical(final).decode())

if __name__=='__main__':
    import sys
    try:{'plan':plan,'execute':execute}[sys.argv[1]]()
    except Exception as error:
        # No uncertain native write is retried, including bootstrap. Future
        # recovery requires an exact readback/reconciliation, never reexecution.
        code=str(error) if isinstance(error,Denied) else type(error).__name__
        print(json.dumps({'state':'B_NATIVE_STOP','safe_code':code}))
        raise SystemExit(1) from None
