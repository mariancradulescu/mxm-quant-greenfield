"""Fixed-SHA reader, existing decryption, finite economic selector and cold resume."""
import base64,gzip,io,json,os,re,subprocess,tempfile,urllib.request,zipfile
from pathlib import Path
from .core import *
from research_core_v4.successor_c_20261018 import readback as old
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.laboratory_completion_20261019_v2.runtime import source_admission
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'research_core_v4/autonomous_laboratory_20261019_v6'
OUT=ROOT/'verification/autonomous-laboratory-v6'
SOURCE_BRANCH='mxm-o04-successor-code-science-v6'
EVIDENCE_BRANCH='mxm-o04-scientific-evidence-v6'
WF='.github/workflows/mxm-scientific-program-v6.yml'


def registry():return json.loads((P/'REGISTRY.json').read_text())
def file_at(route,path,ref):
    v=route.json('contents/'+path+'?ref='+ref)
    need(v['encoding']=='base64' and v['size']<=16*1024*1024,'REMOTE_FILE')
    raw=base64.b64decode(v['content']);need(len(raw)==v['size'],'REMOTE_LENGTH');return raw


def anchors(route):
    r=registry();old.owner_unchanged(route)
    need(route.json('git/ref/heads/mxm-o04-active-v1')['object']['sha']==r['authority'],'AUTHORITY_DRIFT')
    source_admission(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),os.environ['V6_SOURCE_SHA'],
      route.json('git/ref/heads/'+SOURCE_BRANCH)['object']['sha'],route.json('rulesets/25222248'))


def corpus(key,tmp,r):
    manifest=json.loads((ROOT/r['cached_input']['manifest']).read_text());archive=bytearray()
    for i,p in enumerate(manifest['parts']):
        need(p['index']==i and p['offset']==len(archive),'INPUT_PART_ORDER')
        b=(ROOT/p['path']).read_bytes();need(len(b)==p['length'] and sha(b)==p['sha256'],'INPUT_PART')
        archive.extend(b)
    need(sha(archive)==r['cached_input']['archive_sha256'],'INPUT_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:blob=z.read('recovery.mxmenc')
    need(sha(blob)==r['cached_input']['ciphertext_sha256'],'INPUT_CIPHER')
    cp=strict_json(unpack(owner.bounded_decrypt(blob,key,tmp)),max_elements=8000000)
    need(cp['stage']=='recovery' and cp['source_sha']==r['cached_input']['source_sha']
      and cp['run_id']==r['cached_input']['run_id'] and cp['pending'] is None,'INPUT_CHECKPOINT')
    return cp['values']['corpus']


def read_state(route,ref):return strict_json(file_at(route,'program-state.json',ref))
def check_state(state,r):
    need(state['schema']=='mxm.scientific-evidence-state.v6' and state['registry_sha256']==sha(enc(r))
        and state['authority']==r['authority'] and state['source_sha']==os.environ['V6_SOURCE_SHA']
        and state['pending'] is None and state['strategy_trials']==0,'STATE_BINDING')
    need(len(state['completed'])==len(set(state['completed'])) and len(state['completed'])<=2,'STATE_BUDGET')


def main(task):
    r=registry();need(task in r['tasks'],'TASK')
    need(os.environ['GITHUB_REPOSITORY']==old.REPO and os.environ['GITHUB_REF_NAME']==old.BRANCH
      and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_JOB']=='investigation'
      and os.environ['GITHUB_EVENT_NAME'] in ('push','workflow_dispatch')
      and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'WORKLOAD')
    route=GetOnly();orig=urllib.request.urlopen;urllib.request.urlopen=route.open
    try:
        anchors(route)
        evidence=route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha'];state=read_state(route,evidence);check_state(state,r)
        need(task not in state['completed'] and state['next_task']==task and len(state['completed'])<2,'TASK_NOT_ADMITTED')
        if os.environ.get('V6_PARENT_OID'):need(evidence==os.environ['V6_PARENT_OID'],'PARENT_MOVED')
        # Native execution identity is the no-replay record even before output exists.
        runs=route.json('actions/runs?per_page=100')['workflow_runs']
        matches=[x for x in runs if x['path']==WF and x['display_title']=='MXM V6 '+task]
        need(len(matches)==1 and matches[0]['id']==int(os.environ['GITHUB_RUN_ID']),'DUPLICATE_EXECUTION')
        from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
        from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
        os.umask(0o077);OUT.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
            tmp=Path(td);key,fp=_private_key_from_secret(tmp);need(fp==old.FP,'OWNER_KEY')
            if state['completed']:
                parent_task=state['completed'][-1];parent_blob=base64.b64decode(file_at(route,'results/'+parent_task+'/result.mxmenc.b64',evidence))
                need(sha(parent_blob)==state['last_ciphertext_sha256'],'PARENT_CIPHER')
                previous=strict_json(unpack(owner.bounded_decrypt(parent_blob,key,tmp)),max_elements=8000000)
                need(previous['task']==parent_task and previous['registry_sha256']==sha(enc(r))
                  and previous['pending'] is None and previous['next_task']==task,'COLD_SCIENTIFIC_SELECTION')
                parent_run=route.json('actions/runs/'+str(state['last_run_id']))
                jobs=route.json('actions/runs/'+str(state['last_run_id'])+'/jobs?per_page=100')['jobs']
                need(parent_run['run_attempt']==1 and parent_run['path']==WF and parent_run['head_sha']==state['last_trigger_sha']
                  and all(any(j['name']==name and j['conclusion']=='success' for j in jobs) for name in ('investigation','durable-archive')),'PARENT_NATIVE_COMPLETION')
            data=corpus(key,tmp,r)
            if task==TASKS[0]:result=carry_temporal_authority(data)
            else:
                from research_core_v4.cost_frequency_discovery_v1 import accounts_v1
                result=capital_scale(data,accounts_v1)
            next_id=next_task(task,result['classification'],state['completed'],r)
            private={'schema':'mxm.scientific-result.v6','task':task,'source_sha':os.environ['V6_SOURCE_SHA'],
              'registry_sha256':sha(enc(r)),'run_id':int(os.environ['GITHUB_RUN_ID']),
              'input_evidence_oid':evidence,'parent_ciphertext_sha256':state.get('last_ciphertext_sha256'),
              'authentic_corpus_ciphertext_sha256':r['cached_input']['ciphertext_sha256'],
              'result':result,'next_task':next_id,'pending':None}
            raw=enc(private);public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
            need(public_spki_sha256(public)==old.FP,'RECIPIENT')
            target=OUT/'result.mxmenc';encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=target)
            need(unpack(owner.bounded_decrypt(target.read_bytes(),key,tmp))==raw,'RESULT_READBACK')
        anchors(route)
        need(route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']==evidence,'EVIDENCE_MOVED_DURING_READ')
        receipt={'schema':'mxm.scientific-public-receipt.v6','task':task,'classification':result['classification'],
          'source_sha':os.environ['V6_SOURCE_SHA'],'registry_sha256':sha(enc(r)),
          'run_id':int(os.environ['GITHUB_RUN_ID']),'trigger_sha':os.environ['GITHUB_SHA'],
          'input_evidence_oid':evidence,'parent_ciphertext_sha256':state.get('last_ciphertext_sha256'),
          'encrypted_sha256':sha(target.read_bytes()),'next_task':next_id,'completed':state['completed']+[task],
          'pending':None,'safe_stop':next_id is None,'strategy_trials':0,'broker_requests':0,'orders':0,
          'app_key_used':False,'active_authority_writer':False,'cold_parent_consumed':bool(state['completed']),
          'cbot_qualified':False,'numerical_economics_encrypted':True}
        (OUT/'receipt.json').write_bytes(enc(receipt))
        print(json.dumps(receipt,sort_keys=True))
    finally:urllib.request.urlopen=orig

if __name__=='__main__':
    import sys
    try:main(sys.argv[1])
    except Exception as e:
        print(json.dumps({'state':'SCIENTIFIC_SAFE_STOP','safe_code':str(e) if re.fullmatch(r'V6_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
