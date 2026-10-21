"""One manual transport observation in the existing observer role.

No checkpoint publisher: only two fixed, new diagnostic paths can be proposed.
The actual Git replies are retained without interpreting any failure as CAS.
"""
import base64,json,os,subprocess,tempfile,threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .common import need,encoded
from . import custody,integrated,runtime

def probe_path(run_id,writer):
    need(type(run_id) is int and run_id>0 and writer in ('A','B'),'TRANSPORT_FIXED_PATH')
    return 'typed-successor/transport-diagnostics/'+str(run_id)+'/'+writer+'.json'

def redact_reply(raw,secrets):
    text=raw.decode('utf-8',errors='replace')
    for secret in secrets:
        if secret:text=text.replace(secret,'[REDACTED]')
    return text[:16384]

def observe_transport(route):
    scope=custody._NATIVE_WRITER_SCOPE
    need(scope is not None and scope.get('operation')=='observer' and
         scope.get('job')==os.environ.get('GITHUB_JOB')=='ordinary-recovery' and
         os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and
         os.environ.get('LAB_CAS_TRANSPORT_DIAGNOSTIC')=='1',
         'TRANSPORT_MANUAL_EXISTING_OBSERVER_ONLY')
    scope['guard']()
    parent=integrated.current(route);state,initial=integrated.state_at(route,parent)
    need(not initial and state['source_sha']==scope['source'] and
         state['pending'] is None and state['safe_stop'] is True and state['orders']==0,
         'TRANSPORT_CLOSED_CURRENT_CHECKPOINT_ONLY')
    original=runtime.file_at(route,'program-state.json',parent)
    public=runtime.file_at(route,'typed-successor/program-state.json',parent)
    run_id=int(os.environ['GITHUB_RUN_ID']);branch=runtime.EVIDENCE_BRANCH
    token=scope['token'];auth=base64.b64encode(('x-access-token:'+token).encode()).decode()
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_TRACE') and
         k not in ('GIT_CURL_VERBOSE','SUCCESSOR_APP_PRIVATE_KEY','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')}
    env.update(GIT_TERMINAL_PROMPT='0',GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
               GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+auth)
    secrets=(token,auth,os.environ.get('GH_TOKEN',''))
    def git(directory,*args):
        r=subprocess.run(['git',*args],cwd=directory,env=env,capture_output=True,timeout=120)
        need(r.returncode==0,'TRANSPORT_PREPARE_'+args[0].upper());return r.stdout.decode().strip()
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as folder:
        dirs={};candidates={}
        for writer in ('A','B'):
            scope['guard']();d=Path(folder)/writer;d.mkdir();dirs[writer]=d
            git(d,'init','-q');git(d,'remote','add','origin','https://github.com/mariancradulescu/mxm-quant-greenfield.git')
            git(d,'fetch','--depth=1','origin',parent);git(d,'checkout','--detach','FETCH_HEAD')
            path=probe_path(run_id,writer);target=d/path;need(not target.exists(),'TRANSPORT_NO_OVERWRITE')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(encoded({'schema':'mxm.fixed-cas-transport-probe.v1','run_id':run_id,
                'writer':writer,'expected_oid':parent,'checkpoint_cipher_sha256':state['ciphertext_sha256'],
                'orders':0,'new_outcomes':0,'not_acceptance_proof':True}))
            git(d,'config','user.name','github-actions[bot]');git(d,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
            git(d,'add',path);git(d,'commit','-m','Observe native CAS transport response; fixed nonoutcome diagnostic '+writer)
            need(git(d,'diff-tree','--no-commit-id','--name-only','-r','HEAD')==path,
                 'TRANSPORT_ONLY_FIXED_DIAGNOSTIC_PATH')
            candidates[writer]=git(d,'rev-parse','HEAD')
        gate=threading.Barrier(2)
        def push(writer):
            scope['guard']();gate.wait(timeout=90)
            r=subprocess.run(['git','push','--porcelain','--force-with-lease=refs/heads/'+branch+':'+parent,
                'origin','HEAD:refs/heads/'+branch],cwd=dirs[writer],env=env,capture_output=True,timeout=120)
            result={'writer':writer,'candidate_oid':candidates[writer],'expected_oid':parent,
                'returncode':r.returncode,'stdout':redact_reply(r.stdout,secrets),
                'stderr':redact_reply(r.stderr,secrets)}
            print('MXM_CAS_TRANSPORT_REPLY '+json.dumps(result,sort_keys=True),flush=True)
            return result
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(push,('A','B')))
    observed=integrated.current(route)
    need(runtime.file_at(route,'program-state.json',observed)==original and
         runtime.file_at(route,'typed-successor/program-state.json',observed)==public,
         'TRANSPORT_CHECKPOINT_CHANGED_STOP')
    need(sum(r['returncode']==0 for r in results)==1 and observed in candidates.values(),
         'TRANSPORT_UNEXPECTED_NATIVE_RESULTS')
    need([p['sha'] for p in route.json('git/commits/'+observed)['parents']]==[parent],
         'TRANSPORT_NATIVE_PARENT_CHANGED')
    return {'state':'MANUAL_NATIVE_TRANSPORT_OBSERVED_NOT_CERTIFIED','expected_oid':parent,
        'observed_oid':observed,'checkpoint_unchanged':True,'results':results,
        'diagnostic_candidate_count':2,'operational_acceptance':False,'new_outcomes':0,'orders':0}
