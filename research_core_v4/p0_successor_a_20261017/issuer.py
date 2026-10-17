"""Single-process App issuer, never called by A workflows with an App secret.

Private key may be supplied ONLY after B config + native OWNER gate reception.
No public token-return API: mint/use/revoke occurs inside run_checkpoint_batch.
A access configuration is disabled. No bootstrap is performed by this module.
"""
import base64, contextlib, hashlib, json, os, pathlib, subprocess, tempfile, time, urllib.request, urllib.error
from .publisher import *
from .pipeline import Successor
from research_core_v4.p0_owner_governance_20261017.governance import NoRedirect
APP_ID=5343530
INSTALLATION_ID=172030470
REPO_ID=1374181010
ISSUER_ENV='mxm-p0-successor-issuer-v1'
KEY_FP='SHA256:if9s0/vBUMyiKrKc5p6RJoXtcI2sL6HGIWRjNhpRKpk='

def http(path,token,method='GET',body=None):
    # Fixed GitHub API origin, no redirect, caller cannot supply arbitrary URL.
    need(path.startswith(('/app','/installation','/repos/'+REPO+'/')),'API_ORIGIN')
    request=urllib.request.Request('https://api.github.com'+path,method=method,
        data=None if body is None else canonical(body),headers={'Authorization':'Bearer '+token,
        'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    with urllib.request.build_opener(NoRedirect).open(request,timeout=30) as r:
        return r.status,None if r.status==204 else json.load(r)

def admit(grant,config,clock=lambda:int(time.time())):
    need(type(grant) is Grant and grant.synthetic is False,'NATIVE_OWNER_GRANT_REQUIRED')
    p=grant.policy
    need(digest(canonical(config))==p['access_sha256'],'OWNER_ACCESS_CONFIG_HASH')
    need(config.get('enabled') is True and config.get('schema')=='mxm.successor-access.v1','ACTIVATION_B_NOT_AUTHORIZED')
    need(config['app_id']==APP_ID and config['installation_id']==INSTALLATION_ID and
         config['repository_id']==REPO_ID and config['environment']==ISSUER_ENV and
         config['code_branch']==SOURCE_BRANCH and config['private_key_fingerprint']==KEY_FP,'EXACT_APP_CONFIG')
    need(type(config['old_custody_closed_at']) is int and clock()>=config['old_custody_closed_at']+3600,
         'OLD_ISSUANCE_AND_TOKEN_TTL_NOT_CLOSED')
    need(os.environ.get('GITHUB_REF')=='refs/heads/'+SOURCE_BRANCH and os.environ.get('GITHUB_SHA')==p['source_sha']
         and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')=='successor-issuer',
         'FROZEN_ISSUER_WORKLOAD')
    need(config['authority_ref']==ACTIVE_REF and config['research_go'] is False,'NO_RESEARCH')
    grant.check(clock(),os.environ['GITHUB_SHA'],'APP:5343530:172030470')
    native=os.environ['GH_TOKEN'];prefix='/repos/'+REPO+'/'
    _,ref=http(prefix+'git/ref/heads/'+SOURCE_BRANCH,native)
    need(ref['object']['sha']==p['source_sha'],'SOURCE_REF_CHANGED')
    _,rule=http(prefix+'rulesets/'+str(config['source_freeze_ruleset_id']),native)
    need(rule['enforcement']=='active' and rule['conditions']['ref_name']=={'include':['refs/heads/'+SOURCE_BRANCH],'exclude':[]}
         and {'creation','update','deletion','non_fast_forward'}<={r['type'] for r in rule['rules']}
         and ('bypass_actors' not in rule or rule['bypass_actors']==[]),'SOURCE_FREEZE_NOT_PROVABLE')
    _,acl=http(prefix+'rulesets/25268790',native)
    need(acl['enforcement']=='active' and acl['conditions']['ref_name']=={'include':[ACTIVE_REF],'exclude':[]}
         and {r['type'] for r in acl['rules']}=={'creation','update','deletion','non_fast_forward'}
         and ('bypass_actors' not in acl or acl['bypass_actors']==[{'actor_id':APP_ID,'actor_type':'Integration','bypass_mode':'always'}]),
         'FINAL_AUTHORITY_ACL_NOT_PROVABLE')
    # Native read token may omit bypass_actors. Exact ACL is checked with the
    # contents-write App principal AFTER minting but BEFORE any Git write.
    return p

def _b64(raw):return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()

@contextlib.contextmanager
def _app_token(private_key):
    token=None
    with tempfile.TemporaryDirectory() as d:
        key=pathlib.Path(d)/'key';key.write_text(private_key);key.chmod(0o600)
        public=subprocess.check_output(['openssl','pkey','-in',str(key),'-pubout','-outform','DER'],stderr=subprocess.DEVNULL)
        fp='SHA256:'+base64.b64encode(hashlib.sha256(public).digest()).decode()
        need(fp==KEY_FP,'APP_KEY_PIN')
        now=int(time.time());message=(_b64(canonical({'alg':'RS256','typ':'JWT'}))+'.'+
            _b64(canonical({'iss':str(APP_ID),'iat':now-30,'exp':now+300}))).encode()
        signature=subprocess.run(['openssl','dgst','-sha256','-sign',str(key)],input=message,capture_output=True,check=True).stdout
        jwt=message.decode()+'.'+_b64(signature)
        _,app=http('/app',jwt);need(app['id']==APP_ID,'APP_IDENTITY')
        _,installation=http('/app/installations/'+str(INSTALLATION_ID),jwt)
        need(installation['app_id']==APP_ID and installation['account']['id']==322088485,'APP_INSTALLATION')
        _,issued=http('/app/installations/'+str(INSTALLATION_ID)+'/access_tokens',jwt,'POST',
                      {'repository_ids':[REPO_ID],'permissions':{'contents':'write'}})
        token=issued.pop('token')
        try:
            need(issued['permissions'].get('contents')=='write' and set(issued['permissions'])<={'contents','metadata'},'TOKEN_PERMISSIONS')
            _,repos=http('/installation/repositories',token)
            need([r['id'] for r in repos['repositories']]==[REPO_ID],'TOKEN_REPOSITORY')
            yield token
        finally:
            if token:
                status,_=http('/installation/token',token,'DELETE');need(status==204,'TOKEN_REVOCATION_FAILED')
                token=None

def run_checkpoint_batch(grant,config,payloads):
    # Check every public admission condition BEFORE reading private-key env.
    p=admit(grant,config)
    need(type(payloads) is list and 0<len(payloads)<=100,'FINITE_BATCH')
    need('SUCCESSOR_APP_PRIVATE_KEY' in os.environ,'CREDENTIAL_NOT_INSTALLED')
    with _app_token(os.environ['SUCCESSOR_APP_PRIVATE_KEY']) as token, tempfile.TemporaryDirectory() as d:
        prefix='/repos/'+REPO+'/'
        _,freeze=http(prefix+'rulesets/'+str(config['source_freeze_ruleset_id']),token)
        _,acl=http(prefix+'rulesets/25268790',token)
        need(freeze.get('bypass_actors')==[] and acl.get('bypass_actors')==[{'actor_id':APP_ID,'actor_type':'Integration','bypass_mode':'always'}],'NATIVE_EXACT_ACL_NOT_PROVABLE')
        t=GitCAS(pathlib.Path(d)/'publisher',token,grant)
        publisher=Publisher(t,grant,p['source_sha'],p['principal'])
        results=[]
        for intent,payload in payloads:
            publisher.guard();head,_=t.read();need(head is not None,'BOOTSTRAP_NOT_AUTHORIZED_BY_BATCH')
            proposal=publisher.issue(head,intent,payload)
            try:oid=publisher.publish(proposal)
            except AckUnknown:
                # One read-only reconciliation, never resubmit or reexecute.
                result=publisher.reconcile(intent,digest(payload));results.append(result);break
            pipeline=Successor(publisher)
            results.append({'oid':oid,'restore':pipeline.restore(expected_oid=oid).generation,
                            'handoff':pipeline.handoff(expected_oid=oid).generation,
                            'economic':pipeline.economic(expected_oid=oid)})
        return results

def bootstrap_and_delegate(grant,config,payloads):
    p=admit(grant,config)
    need('SUCCESSOR_APP_PRIVATE_KEY' in os.environ,'CREDENTIAL_NOT_INSTALLED')
    with _app_token(os.environ['SUCCESSOR_APP_PRIVATE_KEY']) as token, tempfile.TemporaryDirectory() as d:
        prefix='/repos/'+REPO+'/'
        _,freeze=http(prefix+'rulesets/'+str(config['source_freeze_ruleset_id']),token)
        _,acl=http(prefix+'rulesets/25268790',token)
        need(freeze.get('bypass_actors')==[] and acl.get('bypass_actors')==[{'actor_id':APP_ID,'actor_type':'Integration','bypass_mode':'always'}],'NATIVE_EXACT_ACL_NOT_PROVABLE')
        t=GitCAS(pathlib.Path(d)/'publisher',token,grant)
        publisher=Publisher(t,grant,p['source_sha'],p['principal'])
        head,state=t.read()
        if head is None:
            try:head=publisher.bootstrap()
            except AckUnknown:
                # Bootstrap ambiguity never starts the ordinary checkpoint loop.
                raise AckUnknown('BOOTSTRAP_ACK_UNKNOWN_STOP_READONLY_RECEPTION_REQUIRED') from None
        else:
            # A rerun cannot silently bootstrap again or reexecute past work.
            raise Denied('AUTHORITY_ALREADY_EXISTS_RECOVERY_REQUIRES_EXACT_SCOPE')
        need(type(payloads) is list and len(payloads)<=100,'FINITE_BATCH')
        results=[]
        for item in payloads:
            need(set(item)=={'intent','payload'},'BATCH_ITEM')
            proposal=publisher.issue(head,item['intent'],canonical(item['payload']))
            try:head=publisher.publish(proposal)
            except AckUnknown:
                results.append(publisher.reconcile(item['intent'],digest(canonical(item['payload']))));break
            pipeline=Successor(publisher)
            results.append({'oid':head,'restored':pipeline.restore(expected_oid=head).generation,
                            'worker':pipeline.worker(expected_oid=head),
                            'handoff':pipeline.handoff(expected_oid=head).generation,'economic':pipeline.economic(expected_oid=head)})
        return {'bootstrap_oid':t.git('rev-list','--max-parents=0',head).stdout.decode().strip(),
                'final_oid':head,'checkpoints':results,'research_go':False}

def main():
    bundle=json.loads(os.environ['SUCCESSOR_BUNDLE']);manifest=bundle['manifest'];p=bundle['policy']
    binding=GateBinding(int(os.environ['GITHUB_RUN_ID']),GATE_ENV_ID,GATE_ENV,os.environ['GITHUB_SHA'],PATH,digest(canonical(manifest)))
    grant=Grant(p,manifest,binding,GitHubReadOnly(),int(time.time()))
    result=bootstrap_and_delegate(grant,bundle['access'],bundle['payloads'])
    print(canonical(result).decode())
if __name__=='__main__':main()
