"""One GET-only successor analysis, anchored to completed C V3, no writer."""
import gzip,json,os,re,subprocess,tempfile,urllib.request
from datetime import datetime
from pathlib import Path
from .analysis import analyze,need
from research_core_v4.successor_c_20261018 import readback as old
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015.safety import sha,strict_json,unpack

ROOT=Path(__file__).resolve().parents[2]
P='research_core_v4/paired_support_20261019_v1/'
OUT=ROOT/'verification/paired-support'
ACTIVE='07d1ddbe0b83753bbf189770af1911623fef8d6f'
CIPHER='9e00d40aa8ba5038c15518e97b227defb7bb67b9cba130d02a3feec2a2c028e8'
SOURCE_BRANCH='mxm-o04-successor-code-support-v4'

def anchors(route):
    old.owner_unchanged(route)
    need(route.json('git/ref/heads/mxm-o04-active-v1')['object']['sha']==ACTIVE,'AUTHORITY_MOVED')
    need(route.json('git/ref/heads/'+SOURCE_BRANCH)['object']['sha']==os.environ['PS_SOURCE_SHA'],'SOURCE_MOVED')
    r=route.json('rulesets/'+os.environ['PS_SEAL_ID'])
    need(r['enforcement']=='active' and r['conditions']['ref_name']=={'include':['refs/heads/'+SOURCE_BRANCH],'exclude':[]} and
         {v['type'] for v in r['rules']}=={'creation','update','deletion','non_fast_forward'} and
         datetime.fromisoformat(r['updated_at'].replace('Z','+00:00')).timestamp()==datetime.fromisoformat(os.environ['PS_SEAL_REVISION'].replace('Z','+00:00')).timestamp() and
         ('bypass_actors' not in r or r['bypass_actors']==[]),'SOURCE_SEAL')

def main(route):
    os.umask(0o077)
    need(os.environ.get('GITHUB_REPOSITORY')==old.REPO and os.environ.get('GITHUB_REF_NAME')==old.BRANCH and
         os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_JOB')=='paired-support' and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1','WORKLOAD')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'NO_APP_KEY')
    source=os.environ['PS_SOURCE_SHA']
    need(re.fullmatch('[0-9a-f]{40}',source) and subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==source,'CHECKOUT_PIN')
    design=json.loads((ROOT/P/'DESIGN.json').read_text())
    need(design['predecessor_native_oid']==ACTIVE and design['predecessor_checkpoint_sha256']==CIPHER,'DESIGN_ANCHOR')
    anchors(route)
    run=route.json('actions/runs/'+str(old.SOURCE['run_id']))
    need(run['conclusion']=='success' and run['head_sha']==old.SOURCE['head_sha'] and run['run_attempt']==1,'ACCEPTED_SOURCE_RUN')
    # A second delivery for this trigger/head fails closed. No retries or tag writes.
    runs=route.json('actions/runs?per_page=100')['workflow_runs']
    same=[r for r in runs if r['path']=='.github/workflows/mxm-paired-support-v4.yml' and r['head_sha']==os.environ['GITHUB_SHA']]
    need(len(same)==1 and same[0]['id']==int(os.environ['GITHUB_RUN_ID']),'DUPLICATE_RUN')
    from research_core_v4.remediation_p0_p4_20261015.control import lookup
    asset=lookup(route.json,old.SOURCE['release_id'],old.SOURCE['asset_id'],old.SOURCE['ciphertext_sha256'])
    need(asset['name']=='quotepath-private-result.mxmenc' and asset['size']<=16*1024*1024,'ASSET_SCOPE')
    with route.open(asset['browser_download_url']) as response:blob=response.read(asset['size']+1)
    need(len(blob)==asset['size'] and sha(blob)==old.SOURCE['ciphertext_sha256'],'INPUT_CIPHER')
    from research_core_v4.remediation_p0_p4_20261015.owner import bounded_decrypt
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as directory:
        tmp=Path(directory);key,fp=_private_key_from_secret(tmp);need(fp==old.FP,'OWNER_KEY')
        raw=unpack(bounded_decrypt(blob,key,tmp));full=strict_json(raw,max_elements=8000000)
        need(old.original_encoding(full)==raw and sha(old.original_encoding(full['summary']))==old.SUMMARY_SHA,'INPUT_CANONICAL_SUMMARY')
        old.assess_summary(full['summary']) # validation of existing identity/scope, no replay
        result=analyze(full)
        private={'schema':'mxm.paired-support-private-result.v1','design':design,
                 'design_sha256':sha((ROOT/P/'DESIGN.json').read_bytes()),'source_sha':source,
                 'run_id':int(os.environ['GITHUB_RUN_ID']),'input':old.SOURCE,'result':result}
        result_raw=old.encoded(private);public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
        need(public_spki_sha256(public)==old.FP,'RECIPIENT')
        target=OUT/'paired-support.mxmenc'
        encrypt_shard(gzip.compress(result_raw,mtime=0),public_key=public,output=target)
        need(unpack(bounded_decrypt(target.read_bytes(),key,tmp))==result_raw,'ENCRYPTED_READBACK')
    anchors(route)
    receipt={'schema':'mxm.paired-support-public-receipt.v1','state':'ENCRYPTED_ROW_LEVEL_AUDIT_COMPLETE',
             'source_sha':source,'trigger_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
             'predecessor_native_oid':ACTIVE,'predecessor_checkpoint_sha256':CIPHER,
             'design_sha256':sha((ROOT/P/'DESIGN.json').read_bytes()),
             'encrypted_sha256':sha(target.read_bytes()),'accepted_experiment_replays':0,
             'checkpoint_writer_used':False,'app_key_used':False,'broker_requests':0,'orders':0,
             'cbot_qualified':False,'completed_queue_restarted':False,'authority_unchanged':True}
    (OUT/'public-receipt.json').write_bytes(old.encoded(receipt));print(json.dumps(receipt,sort_keys=True))

if __name__=='__main__':
    route=GetOnly();original=urllib.request.urlopen;urllib.request.urlopen=route.open
    try:main(route)
    except Exception as error:
        code=str(error) if re.fullmatch(r'(PS|C)_[A-Z0-9_]+',str(error)) else type(error).__name__
        print(json.dumps({'state':'PAIRED_SUPPORT_STOP','safe_code':code}));raise SystemExit(1) from None
    finally:urllib.request.urlopen=original
