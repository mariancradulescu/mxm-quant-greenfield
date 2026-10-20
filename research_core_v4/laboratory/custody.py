"""Shared existing native git transaction for keyless evidence-plane writers."""
import base64,json,os,subprocess,tempfile
from pathlib import Path
from .common import *
_NATIVE_WRITER_SCOPE=None

WRITER_JOBS={'source-controls':'source-controls','claim':'segment-intent','fence':'execution-fence','publish':'durable-archive',
    'recover':'recover-before-exposure','handoff':'scientific-handoff',
    'fault-probes':'fault-probes','attest-v3':'attest-v3','certify-v3':'certify-v3'}

def build_native_workflow(source,predecessor):
    """Install the same integrated DAG with scoped secrets and existing App.

    Pure preparation; it does not install environments, admit work or dispatch.
    The final source SHA is supplied only after its native CI/source seal.
    """
    from copy import deepcopy
    import re
    need(re.fullmatch('[a-f0-9]{40}',source or ''),'APP_WORKFLOW_SOURCE')
    workflow=deepcopy(predecessor)
    # PyYAML's YAML1.1 reader treats the native YAML key `on` as True.
    # Emit an unambiguous JSON workflow regardless of the reader used.
    if True in workflow:
        need('on' not in workflow,'APP_WORKFLOW_AMBIGUOUS_TRIGGER')
        workflow['on']=workflow.pop(True)
    need(workflow.get('name')=='MXM integrated P0 technical recovery' and
         set(workflow['jobs'])=={'preflight','segment-intent','execution-fence','investigation',
         'durable-archive','recover-before-exposure','scientific-handoff','cold-readback'},
         'APP_WORKFLOW_EXISTING_DAG')
    workflow['permissions']={};workflow['env']['LAB_SOURCE_SHA']=source
    workflow['on']['workflow_dispatch']['inputs']['fault_before_fence']['description']='Controlled TECHNICAL_NONOUTCOME pre-fence fault; no automatic continuation'
    workflow['concurrency']={'group':'mxm-integrated-laboratory','cancel-in-progress':False}
    operations={v:k for k,v in WRITER_JOBS.items() if k not in ('certify-v3','source-controls')}
    for name,job in workflow['jobs'].items():
        job['permissions']={'contents':'read','actions':'write' if name=='scientific-handoff' else 'read'}
        job['environment']='mxm-p0-successor-issuer-v1' if name in operations else 'mxm-r3-custody-v1'
        if name=='preflight':
            job['steps']=[s for s in job['steps'] if s.get('name') not in (
                'New integration regression and affected typed accounting checks',
                'P0-17 refuse unverified economic acceptance certificates')]
        for step in job['steps']:
            if str(step.get('uses','')).startswith('actions/checkout@'):
                step['with']={'ref':source,'persist-credentials':False}
            env=step.get('env',{})
            for key in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN'):
                env.pop(key,None)
            if 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env:
                env['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM']='${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'
            if name in operations and 'run' in step and 'python3 -m research_core_v4.laboratory.' in step['run']:
                step['run']='python3 -m research_core_v4.laboratory.custody '+operations[name]
                step.setdefault('env',{})['SUCCESSOR_APP_PRIVATE_KEY']='${{ secrets.SUCCESSOR_APP_PRIVATE_KEY }}'
                if name=='segment-intent':step['env']['LAB_FAULT_BEFORE_FENCE']="${{ inputs.fault_before_fence || '0' }}"
        if name=='cold-readback':
            artifact=next(s for s in job['steps'] if str(s.get('uses','')).startswith('actions/upload-artifact@'))
            artifact['with']['path']='verification/integrated-p0/cold-readback.json\nverification/integrated-p0/authentic-adapter.json\n'
    def proof_job(operation,needs):
        steps=[{'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
                'with':{'ref':source,'persist-credentials':False}},
               {'run':'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock'}]
        if operation=='attest-v3':steps.append({'uses':'actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093',
            'with':{'name':'integrated-p0-cold-readback-${{ github.run_id }}','path':'verification/integrated-p0-input/'}})
        steps.append({'run':'python3 -m research_core_v4.laboratory.custody '+operation,
            'env':{'GH_TOKEN':'${{ github.token }}','SUCCESSOR_APP_PRIVATE_KEY':'${{ secrets.SUCCESSOR_APP_PRIVATE_KEY }}',
                   'LAB_PARENT_OID':'${{ needs.durable-archive.outputs.evidence_oid }}'}})
        return {'needs':needs,'if':"needs.durable-archive.result == 'success' && needs.durable-archive.outputs.next == 'STOP' && needs.cold-readback.result == 'success'"+
                (" && needs.fault-probes.result == 'success'" if operation=='attest-v3' else ''),
            'runs-on':'ubuntu-24.04','timeout-minutes':8,'environment':'mxm-p0-successor-issuer-v1',
            'permissions':{'contents':'read','actions':'read'},'steps':steps}
    workflow['jobs']['fault-probes']=proof_job('fault-probes',['preflight','durable-archive','cold-readback'])
    workflow['jobs']['attest-v3']=proof_job('attest-v3',['preflight','durable-archive','cold-readback','fault-probes'])
    workflow['jobs']['source-controls']={'if':workflow['jobs']['preflight']['if'],
        'runs-on':'ubuntu-24.04','timeout-minutes':8,'environment':'mxm-p0-successor-issuer-v1',
        'permissions':{'contents':'read','actions':'read'},'steps':[
            {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
             'with':{'ref':source,'persist-credentials':False}},
            {'run':'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock'},
            {'run':'python3 -m research_core_v4.laboratory.custody source-controls',
             'env':{'GH_TOKEN':'${{ github.token }}','SUCCESSOR_APP_PRIVATE_KEY':'${{ secrets.SUCCESSOR_APP_PRIVATE_KEY }}'}}]}
    workflow['jobs']['preflight']['needs']='source-controls'
    workflow['jobs']['scientific-handoff']['if']+=" && inputs.fault_before_fence != '1'"
    return workflow

def build_certifier_workflow(source):
    import re
    need(re.fullmatch('[a-f0-9]{40}',source or ''),'APP_WORKFLOW_SOURCE')
    return {'name':'MXM R3 native independent certification',
        'on':{'workflow_run':{'workflows':['MXM integrated P0 technical recovery'],'types':['completed']}},
        'permissions':{},'concurrency':{'group':'mxm-integrated-laboratory','cancel-in-progress':False},
        'env':{'LAB_SOURCE_SHA':source,'LAB_INTEGRATED_PROTOCOL':'v2'},'jobs':{'certify-v3':{
            'if':"github.repository == 'mariancradulescu/mxm-quant-greenfield' && github.run_attempt == 1 && github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.head_branch == 'mxm-remediation-p0-p4-20261015-v1'",
            'runs-on':'ubuntu-24.04','timeout-minutes':8,'environment':'mxm-p0-successor-issuer-v1',
            'permissions':{'contents':'read','actions':'read'},'steps':[
                {'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','with':{'ref':source,'persist-credentials':False}},
                {'run':'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock'},
                {'run':'python3 -m research_core_v4.laboratory.custody certify-v3','env':{
                    'GH_TOKEN':'${{ github.token }}','SUCCESSOR_APP_PRIVATE_KEY':'${{ secrets.SUCCESSOR_APP_PRIVATE_KEY }}'}}]}}}

def writer_metadata(operation):
    """Job identity is checked before any App key is read or token minted."""
    import re
    job=WRITER_JOBS.get(operation)
    branch='main' if operation=='certify-v3' else 'mxm-remediation-p0-p4-20261015-v1'
    path='.github/workflows/mxm-r3-certify-v3.yml' if operation=='certify-v3' else '.github/workflows/mxm-integrated-p0.yml'
    source=os.environ.get('LAB_SOURCE_SHA','');trigger=os.environ.get('GITHUB_SHA','')
    need(job and os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
         os.environ.get('GITHUB_JOB')==job and os.environ.get('GITHUB_REF_NAME')==branch and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
         os.environ.get('LAB_INTEGRATED_PROTOCOL')=='v2' and
         re.fullmatch('[a-f0-9]{40}',source) and re.fullmatch('[a-f0-9]{40}',trigger) and
         os.environ.get('GITHUB_WORKFLOW_SHA')==trigger and
         os.environ.get('GITHUB_WORKFLOW_REF')=='mariancradulescu/mxm-quant-greenfield/'+path+'@refs/heads/'+branch,
         'APP_WRITER_NATIVE_CONTEXT')
    need(os.environ.get('GITHUB_EVENT_NAME') in
         (('workflow_run',) if operation=='certify-v3' else ('push','workflow_dispatch')),
         'APP_WRITER_EVENT')
    need(not any(os.environ.get(k) for k in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM',
         'CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN',
         'R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_ACCESS_TOKEN')),
         'APP_WRITER_NO_DECRYPTION_OR_BROKER_KEYS')
    return {'source':source,'trigger':trigger,'job':job,'operation':operation}

def run_native_writer(operation):
    """Reuse the existing App mint/use/revoke in one process; never return a token.

    No keyless GITHUB_TOKEN fallback. No App key/token in called workload env,
    artifacts or outputs. All source/authority controls precede publication.
    Installation of an environment grant is deliberately a separate operation.
    """
    global _NATIVE_WRITER_SCOPE
    need(_NATIVE_WRITER_SCOPE is None,'APP_WRITER_NESTED_SCOPE')
    identity=writer_metadata(operation)
    from .runtime import anchors
    from .integrated import definition
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    from .operational_acceptance import verify_effective_controls
    route=GetOnly()
    # Only the isolated read-only probe may mint when native bypass fields are
    # redacted. Every data/workload job waits for its independent native proof.
    anchors(route,allow_redacted_app_probe=operation=='source-controls')
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==identity['source'],
         'APP_WRITER_CHECKOUT_PIN')
    need(subprocess.run(['git','diff','--quiet','HEAD','--'],capture_output=True).returncode==0,
         'APP_WRITER_MODIFIED_SOURCE')
    if operation not in ('certify-v3','source-controls'):
        admission,_,_=definition(route)
        need(admission['mode']=='TECHNICAL_NONOUTCOME' and admission['economic_release'] is False,
             'APP_WRITER_TECHNICAL_ONLY')
    from research_core_v4.p0_successor_a_20261017.issuer import _app_token
    need(bool(os.environ.get('SUCCESSOR_APP_PRIVATE_KEY')),'APP_WRITER_CREDENTIAL_NOT_INSTALLED')
    private_key=os.environ.pop('SUCCESSOR_APP_PRIVATE_KEY')
    original_token=os.environ['GH_TOKEN']
    try:
        with _app_token(private_key) as token:
            private_key=None
            class AppControls(GetOnly):
                def data(self,path,limit=16*1024*1024):
                    import urllib.request
                    need(path.startswith(('rulesets/','rules/branches/')),'APP_CONTROL_READ_NAMESPACE')
                    request=urllib.request.Request('https://api.github.com/repos/mariancradulescu/mxm-quant-greenfield/'+path,
                        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
                    with self.open(request) as response:value=response.read(limit+1)
                    need(len(value)<=limit,'APP_CONTROL_READ_SIZE');return value
            controls=AppControls()
            def guard():
                # Exact bypass actors are read as the actual existing App,
                # while ordinary workflow/job reads keep native Actions scope.
                # Do not swap process environment: the native CAS proof has
                # two threads, each requiring the same independent reader.
                verify_effective_controls(controls)
                anchors(GetOnly())
                need(GetOnly().json('git/ref/heads/'+os.environ['GITHUB_REF_NAME'])['object']['sha']==identity['trigger'],
                     'APP_WRITER_WORKFLOW_REF_MOVED_STOP_RECONCILE')
            _NATIVE_WRITER_SCOPE={**identity,'token':token,'guard':guard,'controls':controls}
            try:
                guard()
                if operation=='source-controls':
                    from .runtime import SOURCE_BRANCH
                    restrictions=[r for r in controls.json('rules/branches/'+SOURCE_BRANCH) if r['type']=='update']
                    policies=[controls.json('rulesets/'+str(r['ruleset_id'])) for r in restrictions]
                    print('MXM_SOURCE_CONTROL '+json.dumps({'schema':'mxm.native-source-control.v1',
                        'run_id':int(os.environ['GITHUB_RUN_ID']),'attempt':1,
                        'source_sha':identity['source'],'trigger_sha':identity['trigger'],
                        'source_policies':policies,'writes':0,'orders':0,'economic_outcomes':0},sort_keys=True),flush=True)
                    return
                if operation=='attest-v3':
                    from .attest_v3 import publish
                    return publish()
                if operation=='certify-v3':
                    from .certify_v3 import main
                    return main()
                from . import integrated
                return getattr(integrated,{'fault-probes':'fault_probes'}.get(operation,operation))()
            finally:_NATIVE_WRITER_SCOPE=None
    finally:
        private_key=None;os.environ['GH_TOKEN']=original_token

def effective_controls_reader(route):
    scope=_NATIVE_WRITER_SCOPE
    if scope is not None and scope['job']==os.environ.get('GITHUB_JOB') and scope['source']==os.environ.get('LAB_SOURCE_SHA'):
        return scope['controls']
    return route

def verify_native_source_control(route,observed):
    """Read a same-run pinned job's real log; detect policy movement afterward.

    This reuses the existing App and native proof verifier, not another key or
    custodian. A passed unrelated/older job or copied favorable JSON is no grant.
    """
    import re
    from .attest_v3 import native_checkout_provenance,native_jobs
    run=os.environ.get('GITHUB_RUN_ID','');source=os.environ.get('LAB_SOURCE_SHA','');trigger=os.environ.get('GITHUB_SHA','')
    if os.environ.get('GITHUB_JOB')=='certify-v3' and os.environ.get('GITHUB_EVENT_NAME')=='workflow_run':
        event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())['workflow_run']
        need(event.get('status')=='completed' and event.get('conclusion')=='success' and
             event.get('path')=='.github/workflows/mxm-integrated-p0.yml',
             'SOURCE_CONTROL_CERTIFIER_EVENT')
        run=str(event['id']);trigger=event['head_sha']
    need(run.isdecimal() and int(run)>0 and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
         re.fullmatch('[a-f0-9]{40}',source) and re.fullmatch('[a-f0-9]{40}',trigger),
         'SOURCE_CONTROL_NATIVE_CONTEXT_REQUIRED')
    run_id=int(run)
    need(route.json('git/ref/heads/mxm-remediation-p0-p4-20261015-v1')['object']['sha']==trigger,
         'SOURCE_CONTROL_WORKFLOW_REF_MOVED_STOP_RECONCILE')
    jobs=native_jobs(route,run_id,('source-controls',),expected_head_sha=trigger)
    native_checkout_provenance(route,run_id,source,trigger,jobs)
    log=route.data('actions/jobs/'+str(jobs['source-controls'])+'/logs').decode('utf-8')
    records=[json.loads(v) for v in re.findall(r'MXM_SOURCE_CONTROL (\{[^\r\n]*\})',log)]
    need(len(records)==1,'SOURCE_CONTROL_NATIVE_LOG_RECORD_REQUIRED');proof=records[0]
    need(proof.get('schema')=='mxm.native-source-control.v1' and proof.get('run_id')==run_id and
         proof.get('attempt')==1 and proof.get('source_sha')==source and proof.get('trigger_sha')==trigger and
         proof.get('writes')==proof.get('orders')==proof.get('economic_outcomes')==0,
         'SOURCE_CONTROL_NATIVE_PROOF_BINDING')
    matches=[p for p in proof.get('source_policies',[]) if p.get('id')==observed.get('id')]
    need(len(matches)==1,'SOURCE_CONTROL_EXACT_POLICY_REQUIRED');policy=matches[0]
    # Policy revision is independently re-read at each custody/worker entry.
    # Never accept a bypass change hidden from the native reader's response.
    fields=('id','enforcement','conditions','rules','updated_at')
    need(type(observed.get('updated_at')) is str and
         all(k in observed and k in policy and observed[k]==policy[k] for k in fields) and
         policy.get('bypass_actors')==[],'SOURCE_CONTROL_POLICY_MOVED_OR_BYPASS')
    return policy

class CASRefused(LabError):
    """A native git push explicitly rejected its stale expected ref."""
    def __init__(self,parent,candidate,observed):
        super().__init__('LAB_NATIVE_CAS_STALE_REFUSED')
        self.parent=parent;self.candidate=candidate;self.observed=observed

def atomic_publish(route,parent,files,message):
    from .runtime import EVIDENCE_BRANCH,read_state
    need(not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'WRITER_NO_KEYS')
    scope=_NATIVE_WRITER_SCOPE
    need(scope is not None and scope.get('operation')!='source-controls' and scope['job']==os.environ.get('GITHUB_JOB') and
         scope['source']==os.environ.get('LAB_SOURCE_SHA'),'APP_WRITER_SCOPE_REQUIRED')
    scope['guard']()
    env={k:v for k,v in os.environ.items() if k not in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY')}
    auth=base64.b64encode(('x-access-token:'+scope['token']).encode()).decode();env.update(GIT_TERMINAL_PROMPT='0',GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+auth)
    def git(directory,*args):
        v=subprocess.run(['git',*args],cwd=directory,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120);need(v.returncode==0,'ATOMIC_GIT_'+args[0].upper().replace('-','_'));return v.stdout.decode().strip()
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        d=Path(td);git(d,'init','-q');git(d,'remote','add','origin','https://github.com/mariancradulescu/mxm-quant-greenfield.git');git(d,'fetch','--depth=1','origin',parent);git(d,'checkout','--detach','FETCH_HEAD')
        for path,content in files.items():
            need(not path.startswith('/') and '..' not in path.split('/') and path not in ('','.git') and not path.startswith('.git/'),'EVIDENCE_PATH')
            p=d/path
            if path not in ('program-state.json','typed-successor/program-state.json'):need(not p.exists(),'DUPLICATE_EVIDENCE_WRITE')
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
        git(d,'config','user.name','github-actions[bot]');git(d,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com');git(d,'add',*files)
        git(d,'commit','-m',message);commit=git(d,'rev-parse','HEAD')
        try:
            result=subprocess.run(['git','push','--force-with-lease=refs/heads/'+EVIDENCE_BRANCH+':'+parent,'origin','HEAD:refs/heads/'+EVIDENCE_BRANCH],cwd=d,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
            if result.returncode:
                observed=route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']
                # Network/auth/permission errors are NOT evidence of CAS exclusion.
                if b'(stale info)' in result.stderr and observed not in (parent,commit):
                    raise CASRefused(parent,commit,observed)
                need(False,'ATOMIC_GIT_PUSH')
            if os.environ.get('LAB_FAULT_ACK')=='AFTER_PUSH':raise ValueError('INJECTED_ACK_LOSS')
        except CASRefused:raise
        except Exception:
            # A lost ACK is resolved by exact committed bytes, never a second push.
            from .runtime import file_at
            need(route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']==commit,'ATOMIC_PUSH_UNRESOLVED_OR_CONCURRENT_WRITER')
            need(all(file_at(route,p,commit)==v for p,v in files.items()),'ATOMIC_COMMITTED_BYTES_MISMATCH')
            print(json.dumps({'state':'ATOMIC_ACK_RECONCILED_BY_EXACT_REMOTE_BYTES','commit':commit,'second_push':False}))
    need(route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']==commit,'ATOMIC_ACK_AMBIGUOUS')
    return commit

def chunk_ciphertext(blob,prefix,part_size=256000):
    need(not prefix.startswith('/') and '..' not in prefix.split('/') and type(part_size) is int and 0<part_size<=256000,'CHECKPOINT_PART_PARAMETERS')
    need(0<len(blob)<=16*1024*1024,'CHECKPOINT_TECHNICAL_SIZE')
    files={};parts=[]
    for i,offset in enumerate(range(0,len(blob),part_size)):
        part=blob[offset:offset+part_size];path=prefix+'/ciphertext.parts/part'+str(i).zfill(4)+'.b64'
        files[path]=base64.b64encode(part)+b'\n';parts.append({'index':i,'offset':offset,'length':len(part),'sha256':bytes_digest(part),'path':path})
    manifest={'schema':'mxm.encrypted-checkpoint-parts.v1','sha256':bytes_digest(blob),'size':len(blob),'parts':parts}
    return files,manifest

def restore_ciphertext(manifest,fetch):
    need(manifest['schema']=='mxm.encrypted-checkpoint-parts.v1' and 0<manifest['size']<=16*1024*1024,'CIPHER_PART_MANIFEST')
    need(0<len(manifest['parts'])<=66,'CIPHER_PART_COUNT');value=bytearray()
    for i,p in enumerate(manifest['parts']):
        need(p['index']==i and p['offset']==len(value) and 0<p['length']<=256000,'CIPHER_PART_ORDER')
        need(not p['path'].startswith('/') and '..' not in p['path'].split('/'),'CIPHER_PART_PATH')
        b=base64.b64decode(fetch(p['path']).strip(),validate=True);need(len(b)==p['length'] and bytes_digest(b)==p['sha256'],'CIPHER_PART_CHANGED');value.extend(b)
    need(len(value)==manifest['size'] and bytes_digest(value)==manifest['sha256'],'CIPHER_PARTS_AGGREGATE')
    return bytes(value)

if __name__=='__main__':
    import sys
    need(len(sys.argv)==2 and sys.argv[1] in WRITER_JOBS,'APP_WRITER_OPERATION')
    run_native_writer(sys.argv[1])
