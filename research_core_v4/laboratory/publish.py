"""Reuse V6 keyless atomic evidence publication, generalized to programmes."""
import base64,json,os,re,subprocess,tempfile
from pathlib import Path
from .common import *
from .runtime import ROOT,OUT,EVIDENCE_BRANCH,anchors,read_state,validate_state,admission
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
MAGIC=b'MXM_SHALLOW_M5_V2_ENC1\x00'
ALLOWED={'schema','authority','source_sha','parent_oid','sequence','run_id','trigger_sha','admission_ref','admission_path','admission_sha256','ciphertext_sha256','safe_stop','pending','completed_steps','cold_restored','modified_cipher_rejected','mode','orders','new_economic_outcomes','app_key_used','active_authority_write','cbot_qualified','native_acquisition_state','authentic_cache_validated'}

def main():
    need(os.environ['GITHUB_JOB']=='durable-archive' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'ARCHIVE_NO_KEYS')
    route=GetOnly();anchors(route);receipt=json.loads((ROOT/'verification/laboratory-input/receipt.json').read_bytes());blob=(ROOT/'verification/laboratory-input/result.mxmenc').read_bytes()
    need(set(receipt)==ALLOWED and receipt['schema']=='mxm.general-laboratory-receipt.v1','PUBLIC_RECEIPT')
    parent=route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha'];need(parent==receipt['parent_oid'],'PARENT_MOVED');s=read_state(route,parent);validate_state(s)
    a=admission(route,receipt['admission_ref'],receipt['admission_path'])
    need(receipt['admission_sha256']==digest(a) and receipt['mode']==a['mode'],'ADMISSION_BINDING')
    need(receipt['sequence']==s['sequence']+1 and receipt['source_sha']==os.environ['LAB_SOURCE_SHA'] and receipt['trigger_sha']==os.environ['GITHUB_SHA'] and receipt['run_id']==int(os.environ['GITHUB_RUN_ID']),'NATIVE_RECEIPT')
    need(receipt['authentic_cache_validated'] is True and receipt['native_acquisition_state'] in ('COMPLETE_EXACT_WINDOW','TRANSPORT_UNRESOLVED','PROVIDER_ERROR','HASMORE_UNRESOLVED','PAGE_CAP_INCOMPLETE','ACQUISITION_UNRESOLVED'),'DATA_ATTESTATION')
    need(receipt['orders']==0 and all(receipt[k] is False for k in ('app_key_used','active_authority_write','cbot_qualified')) and receipt['pending'] is None and receipt['modified_cipher_rejected'] is True,'RECEIPT_SCOPE')
    need(blob.startswith(MAGIC) and bytes_digest(blob)==receipt['ciphertext_sha256'] and len(blob)<700000,'CIPHERTEXT_BOUNDED')
    need(type(receipt['completed_steps']) is int and 0<=receipt['completed_steps']<=a['steps_per_segment'] and type(receipt['safe_stop']) is bool,'SEGMENT_BUDGET')
    jobs=route.json('actions/runs/'+os.environ['GITHUB_RUN_ID']+'/jobs?per_page=100')['jobs'];need(any(j['name']=='investigation' and j['conclusion']=='success' for j in jobs),'NATIVE_WORKER_COMPLETION')
    path='segments/'+str(receipt['sequence'])+'/result.mxmenc.b64'
    new={**s,'sequence':receipt['sequence'],'ciphertext_path':path,'ciphertext_sha256':receipt['ciphertext_sha256'],'last_run_id':receipt['run_id'],'last_trigger_sha':receipt['trigger_sha'],
      'source_sha':receipt['source_sha'],'admission_ref':receipt['admission_ref'],'admission_path':receipt['admission_path'],'admission_sha256':receipt['admission_sha256'],'safe_stop':receipt['safe_stop'],'pending':None}
    env={k:v for k,v in os.environ.items() if k not in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY')}
    auth=base64.b64encode(('x-access-token:'+os.environ['GH_TOKEN']).encode()).decode();env.update(GIT_TERMINAL_PROMPT='0',GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+auth)
    def git(directory,*args):
        v=subprocess.run(['git',*args],cwd=directory,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120);need(v.returncode==0,'ARCHIVE_GIT_'+args[0].upper().replace('-','_'));return v.stdout.decode().strip()
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        d=Path(td);git(d,'init','-q');git(d,'remote','add','origin','https://github.com/mariancradulescu/mxm-quant-greenfield.git');git(d,'fetch','--depth=1','origin',parent);git(d,'checkout','--detach','FETCH_HEAD')
        need(json.loads((d/'program-state.json').read_text())==s,'ARCHIVE_COLD_STATE');target=d/path;need(not target.exists(),'DUPLICATE_ARCHIVE');target.parent.mkdir(parents=True)
        target.write_bytes(base64.b64encode(blob)+b'\n');(target.parent/'receipt.json').write_bytes(encoded(receipt));(d/'program-state.json').write_bytes(encoded(new))
        git(d,'config','user.name','github-actions[bot]');git(d,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com');git(d,'add','program-state.json',str(target.parent.relative_to(d)))
        git(d,'commit','-m','Preserve encrypted general laboratory segment '+str(receipt['sequence'])+' atomically; no active authority write');commit=git(d,'rev-parse','HEAD')
        git(d,'push','--force-with-lease=refs/heads/'+EVIDENCE_BRANCH+':'+parent,'origin','HEAD:refs/heads/'+EVIDENCE_BRANCH)
    need(route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']==commit,'ARCHIVE_ACK_AMBIGUOUS');need(read_state(route,commit)==new,'REMOTE_STATE')
    from .runtime import file_at
    need(base64.b64decode(file_at(route,path,commit))==blob,'REMOTE_CIPHER')
    anchors(route)
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('next='+('STOP' if receipt['safe_stop'] else 'CONTINUE')+'\nevidence_oid='+commit+'\nadmission_ref='+receipt['admission_ref']+'\nadmission_path='+receipt['admission_path']+'\n')
    print(json.dumps({'state':'GENERAL_LABORATORY_DURABLE_CHECKPOINT','sequence':receipt['sequence'],'evidence_oid':commit,'safe_stop':receipt['safe_stop'],'ciphertext_sha256':receipt['ciphertext_sha256'],'active_authority_write':False}))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'state':'ARCHIVE_SAFE_STOP_NO_DISPATCH','safe_code':str(e) if re.fullmatch(r'LAB_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
