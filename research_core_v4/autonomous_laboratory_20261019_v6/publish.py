"""Append-only documentation archive. No OWNER/App key or active authority writer.

A separate native job receives only ciphertext plus the public enum receipt.
It cannot update the App-only active authority. Code and native protection
checks remain distinct from this ordinary documentation publishing permission.
"""
import base64,json,os,re,subprocess,tempfile,urllib.request
from pathlib import Path
from .core import *
from .runtime import ROOT,P,OUT,EVIDENCE_BRANCH,registry,read_state,anchors,check_state
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
MAGIC=b'MXM_SHALLOW_M5_V2_ENC1\x00'
REPO='mariancradulescu/mxm-quant-greenfield'
ALLOWED={'schema','task','classification','source_sha','registry_sha256','run_id','trigger_sha',
'input_evidence_oid','parent_ciphertext_sha256','encrypted_sha256','next_task','completed','pending',
'safe_stop','strategy_trials','broker_requests','orders','app_key_used','active_authority_writer',
'cold_parent_consumed','cbot_qualified','numerical_economics_encrypted'}


def validate_receipt(receipt,blob,r,state):
    need(set(receipt)==ALLOWED and receipt['schema']=='mxm.scientific-public-receipt.v6','PUBLIC_SCHEMA')
    task=receipt['task'];need(task in r['tasks'] and receipt['classification'] in VERDICTS,'PUBLIC_ENUM')
    need(receipt['run_id']==int(os.environ['GITHUB_RUN_ID']) and receipt['trigger_sha']==os.environ['GITHUB_SHA']
      and receipt['source_sha']==os.environ['V6_SOURCE_SHA'] and receipt['registry_sha256']==sha(enc(r)),'RECEIPT_NATIVE_IDENTITY')
    need(blob.startswith(MAGIC) and sha(blob)==receipt['encrypted_sha256'] and len(blob)<=16*1024*1024,'CIPHERTEXT')
    need(all(receipt[k]==0 for k in ('strategy_trials','broker_requests','orders'))
      and all(receipt[k] is False for k in ('app_key_used','active_authority_writer','cbot_qualified'))
      and receipt['pending'] is None and receipt['numerical_economics_encrypted'] is True,'PUBLIC_SCOPE')
    next_id=next_task(task,receipt['classification'],state['completed'],r)
    need(receipt['next_task']==next_id and receipt['completed']==state['completed']+[task]
      and receipt['safe_stop']==(next_id is None) and receipt['parent_ciphertext_sha256']==state.get('last_ciphertext_sha256'),'SCIENTIFIC_ROUTE')


def main():
    need(os.environ['GITHUB_JOB']=='durable-archive' and os.environ['GITHUB_RUN_ATTEMPT']=='1'
      and not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'ARCHIVE_NO_KEYS')
    route=GetOnly();anchors(route);r=registry()
    receipt=json.loads((ROOT/'verification/science-input/receipt.json').read_text());blob=(ROOT/'verification/science-input/result.mxmenc').read_bytes()
    parent=route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']
    need(parent==receipt['input_evidence_oid'],'ARCHIVE_PARENT_MOVED')
    state=read_state(route,parent);check_state(state,r);validate_receipt(receipt,blob,r,state)
    jobs=route.json('actions/runs/'+os.environ['GITHUB_RUN_ID']+'/jobs?per_page=100')['jobs']
    need(any(j['name']=='investigation' and j['conclusion']=='success' for j in jobs),'SCIENCE_NATIVE_SUCCESS')
    new={**state,'completed':receipt['completed'],'next_task':receipt['next_task'],
      'last_ciphertext_sha256':receipt['encrypted_sha256'],'last_run_id':receipt['run_id'],
      'last_trigger_sha':receipt['trigger_sha'],'last_verdict':receipt['classification'],
      'pending':None,'safe_stop':receipt['safe_stop'],'feasibility_budget_remaining':2-len(receipt['completed'])}
    env={k:v for k,v in os.environ.items() if k not in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY')}
    auth=base64.b64encode(('x-access-token:'+os.environ['GH_TOKEN']).encode()).decode()
    env.update(GIT_TERMINAL_PROMPT='0',GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+auth)
    def git(directory,*args):
        v=subprocess.run(['git',*args],cwd=directory,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        need(v.returncode==0,'ARCHIVE_GIT_'+args[0].upper().replace('-','_'));return v.stdout.decode().strip()
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        d=Path(td);git(d,'init','-q');git(d,'remote','add','origin','https://github.com/'+REPO+'.git')
        git(d,'fetch','--depth=1','origin',parent);git(d,'checkout','--detach','FETCH_HEAD')
        need(json.loads((d/'program-state.json').read_text())==state,'ARCHIVE_COLD_STATE')
        target=d/'results'/receipt['task'];need(not target.exists(),'ARCHIVE_DUPLICATE')
        target.mkdir(parents=True);(target/'result.mxmenc.b64').write_bytes(base64.b64encode(blob)+b'\n')
        (target/'receipt.json').write_bytes(enc(receipt));(d/'program-state.json').write_bytes(enc(new))
        git(d,'config','user.name','github-actions[bot]');git(d,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        git(d,'add','program-state.json','results/'+receipt['task']);git(d,'commit','-m','Archive encrypted '+receipt['task']+' and registered scientific successor; no active authority write')
        commit=git(d,'rev-parse','HEAD')
        # One native receive-pack transaction: public state and private ciphertext
        # appear in the same tree. No API release PATCH, blind push retry or reset.
        git(d,'push','--force-with-lease=refs/heads/'+EVIDENCE_BRANCH+':'+parent,'origin','HEAD:refs/heads/'+EVIDENCE_BRANCH)
    need(route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']==commit,'ARCHIVE_ACK_AMBIGUOUS')
    need(read_state(route,commit)==new,'ARCHIVE_REMOTE_STATE')
    from .runtime import file_at
    restored=base64.b64decode(file_at(route,'results/'+receipt['task']+'/result.mxmenc.b64',commit))
    need(restored==blob,'ARCHIVE_REMOTE_CIPHER')
    anchors(route)
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:
        f.write('next_task='+(receipt['next_task'] or 'STOP')+'\n'+'evidence_oid='+commit+'\n')
    print(json.dumps({'state':'DURABLE_ENCRYPTED_SCIENTIFIC_CHECKPOINT','task':receipt['task'],'evidence_oid':commit,
      'ciphertext_sha256':receipt['encrypted_sha256'],'next_task':receipt['next_task'],'safe_stop':receipt['safe_stop'],
      'active_authority_write':False,'app_key_used':False},sort_keys=True))

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'state':'ARCHIVE_SAFE_STOP_NO_DISPATCH','safe_code':str(e) if re.fullmatch(r'V6_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
