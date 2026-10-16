"""O04 engineering proof on a run-scoped SYNTHETIC GitHub ref only.

Reuse the previously tested claim/accept/resolve/CAS implementation unchanged.
No live OWNER checkpoint writer is supplied or enabled. The accepted OWNER
authority will remain frozen under a separate no-bypass update restriction.
"""
import base64
import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import tempfile
import threading
import urllib.error
import urllib.request
from . import git_fence_lab as lab

REPO='mariancradulescu/mxm-quant-greenfield'
REMOTE='https://github.com/'+REPO+'.git'
PREFIX='refs/heads/mxm-o04-proof-'
OWNER_JOURNAL='ea93f6c38768824521d4ad3e316c0cd507c837e5c089c5e3b6f63d20d79e7470'

def get(path):
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'},method='GET')
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)

def scope():
    lab.need(os.environ.get('GITHUB_REPOSITORY')==REPO,'REPOSITORY_SCOPE')
    lab.need(os.environ.get('GITHUB_REF_NAME')=='mxm-remediation-p0-p4-20261015-v1','BRANCH_SCOPE')
    lab.need(os.environ.get('GITHUB_RUN_ATTEMPT')=='1','ATTEMPT_SCOPE')
    lab.need(os.environ.get('GITHUB_ACTOR')=='mariancradulescu','ACTOR_SCOPE')
    lab.need(re.fullmatch(r'\d+',os.environ.get('GITHUB_RUN_ID','')) is not None,'RUN_SCOPE')
    lab.REF=PREFIX+os.environ['GITHUB_RUN_ID']
    r=get('rulesets/25222248')
    lab.need(r['enforcement']=='active','RULESET_SCOPE')
    # The job token omits administrative bypass metadata. Absence is not proof
    # of an empty list: that list was verified through UI and the operator App.
    # The live server rollback-negative below additionally proves this token
    # cannot bypass the actual protected ref. Never grant admin to inspect it.
    if 'bypass_actors' in r:lab.need(r['bypass_actors']==[],'RULESET_BYPASS')
    lab.need({'deletion','non_fast_forward','required_linear_history'}<={x['type'] for x in r['rules']},'RULESET_RULES')
    lab.need(r['conditions']['ref_name']=={'include':['refs/heads/mxm-o04-*'],'exclude':[]},'RULESET_TARGET')

class RemoteProof(lab.GitFenceLab):
    def __init__(self,workspace):
        lab.need(lab.REF==PREFIX+os.environ['GITHUB_RUN_ID'],'SYNTHETIC_REF_ONLY')
        self.workspace=pathlib.Path(workspace);self.workspace.mkdir()
        self.remote=REMOTE;self.principals=frozenset({'writer-a','writer-b'})
        self.env={k:v for k,v in os.environ.items() if not k.startswith(('GIT_','GH_','GITHUB_','SSH_'))}
        self.env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME='MXM O04 synthetic proof',GIT_AUTHOR_EMAIL='proof@example.invalid',
            GIT_COMMITTER_NAME='MXM O04 synthetic proof',GIT_COMMITTER_EMAIL='proof@example.invalid',GIT_TERMINAL_PROMPT='0',
            GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
            GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+os.environ['GH_TOKEN']).encode()).decode())
        self.git('init','-q')
        # Secrets are never passed as command arguments, printed, or persisted.

def denied(fn):
    try:fn()
    except lab.Denied:return
    raise ValueError('EXPECTED_DENIAL_MISSING')

def main():
    scope();before=get('releases/412686323')['body'];owner=json.loads(before)
    lab.need(owner['generation']==1807 and owner['state']=='STOP_FAIL_CLOSED' and owner['current_journal']['canonical_sha256']==OWNER_JOURNAL,'OWNER_ANCHOR')
    results={}
    with tempfile.TemporaryDirectory() as tmp:
        root=pathlib.Path(tmp);a=RemoteProof(root/'a');b=RemoteProof(root/'b')
        genesis=a.initialize_synthetic();barrier=threading.Barrier(2)
        def race(client,writer):
            oid,state=client.read();lab.need(oid==genesis,'RACE_SNAPSHOT')
            state.update(epoch=1,owner=writer,deadline=101)
            barrier.wait(timeout=30)
            try:client._publish(oid,state);return 'ACCEPTED'
            except lab.Denied:return 'REJECTED'
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(race,a,'writer-a'),pool.submit(race,b,'writer-b')]
            outcome=sorted(f.result() for f in futures)
        lab.need(outcome==['ACCEPTED','REJECTED'],'REMOTE_RACE');results['two_real_remote_writers']=outcome
        oid,_=a.read();old=a.claim(oid,'writer-a',102,ttl=1)
        current=b.claim(old.oid,'writer-b',103)
        denied(lambda:a.accept(old,1,'a'*64,'delayed',103))
        # Also bypass the local precheck and send an actual stale old-OID push.
        stale_oid,stale=a.read();stale.update(epoch=current.epoch+1,owner='writer-a')
        denied(lambda:a._publish(old.oid,stale));results['delayed_writer']='LOCAL_AND_REMOTE_CAS_REJECTED'
        digest=hashlib.sha256(b'O04 synthetic checkpoint').hexdigest()
        try:b.accept(current,1,digest,'accepted-lost-ack',104,lose_ack=True)
        except lab.Unknown:pass
        else:raise ValueError('LOST_ACK_NOT_INJECTED')
        cold=RemoteProof(root/'cold')
        lab.need(cold.resolve(1,digest,'accepted-lost-ack')=='ACCEPTED_READBACK_NO_REPLAY','COLD_READBACK')
        denied(lambda:cold.accept(current,1,digest,'accepted-lost-ack',104))
        results['cold_restart_and_ack_unknown']='READBACK_ACCEPTED_REPLAY_DENIED'
        oid,state=cold.read();next_token=cold.claim(oid,'writer-a',105)
        denied(lambda:cold.accept(next_token,1,'b'*64,'overwrite',106))
        lab.need(cold.read()[1]['accepted']['1']['digest']==digest,'ACCEPTED_DIGEST_CHANGED')
        results['accepted_checkpoint_overwrite']='REJECTED'
        denied(lambda:b.claim(cold.read()[0],'untrusted',106));results['ungranted_principal']='DENIED'
        p=cold.git('push','--force',REMOTE,genesis+':'+lab.REF,check=False)
        lab.need(p.returncode!=0 and cold.read()[0]==next_token.oid,'SERVER_ROLLBACK_ALLOWED')
        lab.need(b'GH013' in p.stderr or b'repository rule' in p.stderr.lower(),'SERVER_RULE_PROOF_MISSING')
        results['privileged_force_rollback']='GITHUB_RULESET_REJECTED'
        # Forward child exists solely for a later read-only-token negative test.
        oid,state=cold.read();blob=cold.git('hash-object','-w','--stdin',data=lab.canonical({**state,'unauthorized_attempt':True})).decode().strip()
        tree=cold.git('mktree',data=('100644 blob '+blob+'\tstate.json\n').encode()).decode().strip()
        candidate=cold.git('commit-tree',tree,'-p',oid,data=b'O04 unauthorized synthetic candidate\n').decode().strip()
        # Upload objects through a separate run-scoped carrier ref, not accept.
        carrier=lab.REF+'-candidate'
        cold.git('push',REMOTE,candidate+':'+carrier)
        receipt={'schema':'mxm.o04.live-synthetic-proof.v1','head':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],
            'synthetic_ref':lab.REF,'final_oid':oid,'unauthorized_candidate':candidate,'carrier_ref':carrier,
            'results':results,'OWNER_release_body_sha256':hashlib.sha256(before.encode()).hexdigest(),
            'OWNER_checkpoint_writes':0,'new_broker_requests':0,'orders':0,'research_executed':False}
    lab.need(get('releases/412686323')['body']==before,'OWNER_ANCHOR_CHANGED')
    out=pathlib.Path('verification');out.mkdir(exist_ok=True)
    (out/'o04-live-proof.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:
            f.write('proof_ref='+lab.REF+'\ncandidate='+candidate+'\nexpected='+oid+'\n')
    print(json.dumps(receipt,sort_keys=True))

def unauthorized():
    scope();ref=os.environ['PROOF_REF'];candidate=os.environ['CANDIDATE'];expected=os.environ['EXPECTED']
    lab.need(ref==PREFIX+os.environ['GITHUB_RUN_ID'] and re.fullmatch('[0-9a-f]{40}',candidate) is not None,'UNAUTHORIZED_SCOPE')
    lab.need(get('git/ref/'+ref.removeprefix('refs/'))['object']['sha']==expected,'UNAUTHORIZED_BEFORE')
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/git/refs/'+ref.removeprefix('refs/'),method='PATCH',
        data=json.dumps({'sha':candidate,'force':False}).encode(),headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30):raise ValueError('UNAUTHORIZED_WRITE_ACCEPTED')
    except urllib.error.HTTPError as ex:
        lab.need(ex.code==403,'UNEXPECTED_AUTHORIZATION_RESPONSE');status=ex.code
    lab.need(get('git/ref/'+ref.removeprefix('refs/'))['object']['sha']==expected,'UNAUTHORIZED_CHANGED_REF')
    result={'schema':'mxm.o04.live-unauthorized.v1','run_id':os.environ['GITHUB_RUN_ID'],'head':os.environ['GITHUB_SHA'],
        'synthetic_ref':ref,'HTTP_status':status,'ref_unchanged':True,'OWNER_writes':0}
    pathlib.Path('verification').mkdir(exist_ok=True)
    pathlib.Path('verification/o04-unauthorized.json').write_text(json.dumps(result,sort_keys=True)+'\n');print(json.dumps(result))

if __name__=='__main__':
    import sys
    if '--unauthorized' in sys.argv:unauthorized()
    else:main()
