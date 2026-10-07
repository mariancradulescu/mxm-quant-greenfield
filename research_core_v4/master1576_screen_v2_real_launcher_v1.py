"""Durable authorization adapter around the byte-exact accepted V2 worker.

No real authorization is supplied by this module. Git authorization is the only
source of authority. The ephemeral worker ARM is a deterministic compatibility file.
"""
from __future__ import annotations
import argparse
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from research_core_v4 import master1576_screen_v2 as w

BASE='2c1ed67c2a7bcaddf25a4f891b7b3a5e30abcd53'
REPO='mariancradulescu/mxm-quant-greenfield'
BRANCH='performance-research-v3-20260922'
ARCH=w.S+'MASTER1576_QUALIFICATION_V2_REAL_EXECUTION_ARCHITECTURE_V1.json'
AUTH=w.S+'MASTER1576_QUALIFICATION_V2_REAL_SCREEN_AUTHORIZATION_V1.json'
RESULT=w.S+'MASTER1576_QUALIFICATION_V2_REAL_STRUCTURAL_SCREEN_RESULT_V1.json'
LAUNCHER='research_core_v4/master1576_screen_v2_real_launcher_v1.py'
WORKFLOW='.github/workflows/master1576-qualification-v2-real-screen.yml'
PROOF=w.S+'MASTER1576_QUALIFICATION_V2_EXECUTION_ARCHITECTURE_SYNTHETIC_PREFLIGHT_V1.json'
NEXT='PENDING_INDEPENDENT_AUDIT_OF_MASTER1576_V2_REAL_SCREEN_EXECUTION_ARCHITECTURE_BEFORE_DURABLE_REAL_AUTHORIZATION'
SCHEMA='mxm.v4.master1576.qualification-v2.real-screen-authorization.v1'
STATUS='AUTHORIZED_ONCE_STRUCTURAL_SCREEN_ONLY'
AUTH_KEYS={'schema','status','authorized_parent_head','protocol_sha256','worker_sha256','synthetic_preflight_sha256','campaign_acceptance_sha256','execution_architecture_sha256','final_manifest_sha256','release_identity','output_path'}
HASH_PATHS={'protocol_sha256':w.PROTOCOL,'worker_sha256':w.WORKER,'synthetic_preflight_sha256':w.PREFLIGHT,'campaign_acceptance_sha256':w.ACCEPTANCE,'execution_architecture_sha256':ARCH}
STATES=[w.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']

def require(ok,code):w.require(ok,code)
def raw(root,path):return (Path(root)/path).read_bytes()
def load(root,path):return w.strict_json(raw(root,path))
def git(root,*args):
    try:return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL,text=True).strip()
    except Exception:raise w.ScreenError('GIT_CONTROL_FAILURE') from None

def validate_schema(auth):
    require(isinstance(auth,dict) and set(auth)==AUTH_KEYS and auth['schema']==SCHEMA and auth['status']==STATUS,'DURABLE_AUTHORIZATION_SCHEMA_FAILURE')
    require(isinstance(auth['authorized_parent_head'],str) and re.fullmatch('[0-9a-f]{40}',auth['authorized_parent_head']) is not None,'AUTHORIZED_PARENT_FAILURE')
    for key in HASH_PATHS:require(re.fullmatch('[0-9a-f]{64}',str(auth[key])) is not None,'AUTHORIZATION_HASH_FAILURE')
    require(re.fullmatch('[0-9a-f]{64}',str(auth['final_manifest_sha256'])) is not None,'AUTHORIZATION_HASH_FAILURE')
    require(auth['output_path']==RESULT,'RESULT_PATH_FAILURE')

def validate_authorization(root, *, event, provider, allow_completed_local_result=False):
    root=Path(root).resolve()
    require(event.get('event_name')=='push' and event.get('repository')==REPO and event.get('ref')=='refs/heads/'+BRANCH,'WRONG_GITHUB_EVENT')
    require(str(event.get('run_attempt'))=='1' and re.fullmatch('[1-9][0-9]*',str(event.get('run_id'))) is not None,'RUN_ATTEMPT_FAILURE')
    require((root/AUTH).is_file(),'NO_DURABLE_AUTHORIZATION');auth=load(root,AUTH);validate_schema(auth)
    head=git(root,'rev-parse','HEAD');require(head==event.get('sha'),'EVENT_HEAD_FAILURE')
    parents=git(root,'show','-s','--format=%P',head).split();require(parents==[auth['authorized_parent_head']],'AUTHORIZED_PARENT_FAILURE')
    changes=git(root,'diff-tree','--no-commit-id','--name-status','-r',head).splitlines()
    require(changes==['A\t'+AUTH],'AUTHORIZATION_ONLY_COMMIT_FAILURE')
    # Current authorization must be the exact committed file, not an untracked substitute.
    require(git(root,'hash-object',AUTH)==git(root,'rev-parse',head+':'+AUTH),'AUTHORIZATION_WORKTREE_DRIFT')
    for key,path in HASH_PATHS.items():require(auth[key]==w.sha(raw(root,path)),'AUTHORIZATION_HASH_FAILURE')
    arch=load(root,ARCH);require(arch['status']=='FROZEN_PREFLIGHT_ONLY_NO_REAL_AUTHORIZATION_PENDING_INDEPENDENT_AUDIT','ARCHITECTURE_STATUS_FAILURE')
    for b in arch['bindings'].values():require(w.sha(raw(root,b['ref']))==b['sha256'],'ARCHITECTURE_HASH_FAILURE')
    acceptance=load(root,w.ACCEPTANCE)
    require(auth['final_manifest_sha256']==acceptance['final_manifest']['sha256'] and w.sha(raw(root,acceptance['final_manifest']['ref']))==auth['final_manifest_sha256'],'FINAL_MANIFEST_HASH_FAILURE')
    require(auth['release_identity']==acceptance['exact_release_inventory']['tag_name']==arch['release_identity'],'RELEASE_IDENTITY_FAILURE')
    # The durable authorization names its parent; its own SHA is never an input.
    # Parent must contain the frozen architecture and exact pending-audit rebind.
    for state_path in STATES:
        parent=w.strict_json(subprocess.check_output(['git','show',auth['authorized_parent_head']+':'+state_path],cwd=root))
        require(parent['real_screen_execution_architecture_ref']==ARCH and parent['real_screen_execution_architecture_sha256']==auth['execution_architecture_sha256'] and parent['next_action']==NEXT,'AUDITED_PARENT_STATE_FAILURE')
        require(parent['real_screen_execution_preflight_ref']==PROOF and parent['real_screen_execution_preflight_sha256']==w.sha(raw(root,PROOF)),'AUDITED_PARENT_STATE_FAILURE')
        require(parent['qualification_protocol_ref']==w.PROTOCOL and parent['qualification_protocol_sha256']==auth['protocol_sha256'] and parent['current_authority']==w.ACCEPTANCE,'AUDITED_PARENT_STATE_FAILURE')
    # Audit evidence is preserved at the parent and cannot be replaced by this one-file commit.
    proof=load(root,PROOF);require(proof['status']=='PASS_SYNTHETIC_ONLY_NO_REAL_AUTHORIZATION' and proof['tests_failed']==0 and proof['tests_skipped']==0,'ARCHITECTURE_PREFLIGHT_FAILURE')
    for b in proof['bindings'].values():require(w.sha(raw(root,b['ref']))==b['sha256'],'ARCHITECTURE_PREFLIGHT_HASH_FAILURE')
    require(provider.live_head()==head,'LIVE_BRANCH_DRIFT')
    require((allow_completed_local_result or not (root/RESULT).exists()) and not provider.result_exists(head),'RESULT_ALREADY_PRESENT')
    inventory=provider.release_inventory(auth['release_identity']);expected=acceptance['exact_release_inventory']
    require(inventory['id']==expected['release_id'] and inventory['tag_name']==expected['tag_name'] and inventory['body']==expected['body'],'RELEASE_BINDING_FAILURE')
    assets=inventory['assets'];require(len(assets)==100 and len({v['name'] for v in assets})==100,'ASSET_INVENTORY_FAILURE')
    by_name={v['name']:v for v in assets}
    require(set(by_name)=={v['name'] for v in expected['assets']},'ASSET_INVENTORY_FAILURE')
    for exp in expected['assets']:
        require(all(by_name[exp['name']].get(k)==v for k,v in exp.items()),'ASSET_INVENTORY_FAILURE')
    require(provider.live_head()==head,'LIVE_BRANCH_DRIFT')
    return {'auth':auth,'head':head,'authorization_sha256':w.sha(raw(root,AUTH)),'claim_ref':'refs/tags/mxm-master1576-v2-screen-attempt-'+head,'run_id':str(event['run_id'])}

def arm_value(control):
    a=control['auth']
    return {'schema':'mxm.v4.master1576.structural-screen-real-arm.v1','status':STATUS,'execution_head':control['head'],'protocol_sha256':a['protocol_sha256'],'worker_sha256':a['worker_sha256'],'preflight_sha256':a['synthetic_preflight_sha256'],'campaign_acceptance_sha256':a['campaign_acceptance_sha256'],'output_path':a['output_path']}

@contextmanager
def ephemeral_arm(control, *, temp_parent=None):
    with tempfile.TemporaryDirectory(prefix='mxm-master1576-v2-arm-',dir=temp_parent) as td:
        os.chmod(td,0o700);p=Path(td)/'worker-arm.json';p.write_bytes(w.canonical(arm_value(control)));p.chmod(0o600)
        yield p

def receipt_write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(w.canonical(value));f.flush();os.fsync(f.fileno())

def presecret(root, *, event, provider, receipt):
    c=validate_authorization(root,event=event,provider=provider)
    # Git tag is immutable to this launcher; a failed/crashed attempt retains it.
    provider.create_attempt_claim(c['claim_ref'],c['head'])
    require(provider.claim_head(c['claim_ref'])==c['head'],'ATTEMPT_CLAIM_FAILURE')
    require(provider.live_head()==c['head'],'LIVE_BRANCH_DRIFT')
    receipt_write(receipt,{k:c[k] for k in ['head','authorization_sha256','claim_ref','run_id']})
    return {'status':'PASS_PRESECRET_DURABLE_AUTHORIZATION_AND_CLAIM','head':c['head']}

def validate_receipt(control,receipt,provider):
    r=w.strict_json(Path(receipt).read_bytes())
    require(r=={k:control[k] for k in ['head','authorization_sha256','claim_ref','run_id']},'PRESECRET_RECEIPT_FAILURE')
    require(provider.claim_head(control['claim_ref'])==control['head'],'ATTEMPT_CLAIM_FAILURE')

def validate_complete_result(root,control):
    result=load(root,RESULT);w.validate_output(result)
    a=control['auth'];acceptance=load(root,w.ACCEPTANCE)
    require(result['protocol_sha256']==a['protocol_sha256'] and result['campaign_acceptance_sha256']==a['campaign_acceptance_sha256'] and result['final_manifest_sha256']==a['final_manifest_sha256'] and result['release_identity']==a['release_identity'] and result['master_sha256']==acceptance['master1576_sha256'],'RESULT_BINDING_FAILURE')
    require(result['processed_asset_count']==100 and result['processed_canonical_row_count']==3355389 and result['identity_count']==1576,'PARTIAL_RESULT_FORBIDDEN')
    master=load(root,load(root,w.PROTOCOL)['bindings']['master']['ref'])
    require([(r['MASTER_ORDINAL'],r['SYMBOL_ID'],r['BROKER_NATIVE_CONTEXT']) for r in result['identities']]==[(i,x['symbol_id'],x['asset_class']) for i,x in enumerate(master,1)],'RESULT_IDENTITY_FAILURE')
    require(sum(r['TOTAL_ROW_COUNT'] for r in result['identities'])==3355389,'PARTIAL_RESULT_FORBIDDEN')
    require(all(len(r['ROW_COUNT_BY_SEGMENT'])==4 and sum(r['ROW_COUNT_BY_SEGMENT'])==r['TOTAL_ROW_COUNT'] for r in result['identities']),'PARTIAL_RESULT_FORBIDDEN')
    require(sum(result['classification_counts'].values())==1576 and result['eligible_count']==sum(bool(r['COMPLETE_REASON_LEDGER']['hard_gates_pass']) for r in result['identities']),'RESULT_ACCOUNTING_FAILURE')
    return raw(root,RESULT)

def execute(root, *, event, provider, receipt, completed_receipt, worker_call=None, temp_parent=None):
    root=Path(root).resolve();require(Path.cwd().resolve()==root,'WORKER_CWD_FAILURE')
    c=validate_authorization(root,event=event,provider=provider);validate_receipt(c,receipt,provider)
    # No global monkey patch and no worker rewrite; production calls exact run_authorized.
    with ephemeral_arm(c,temp_parent=temp_parent) as arm:
        response=(worker_call or w.run_authorized)(root,arm)
    require(response.get('status')=='COMPLETE_STRUCTURAL_SCREEN','WORKER_NOT_COMPLETE')
    result=validate_complete_result(root,c);require(w.sha(result)==response.get('result_sha256'),'WORKER_RESULT_DIGEST_FAILURE')
    receipt_write(completed_receipt,{'head':c['head'],'authorization_sha256':c['authorization_sha256'],'run_id':c['run_id'],'result_sha256':w.sha(result),'processed_asset_count':100,'processed_canonical_row_count':3355389})
    return {'status':'COMPLETE_STRUCTURAL_RESULT_NOT_YET_PUBLISHED','result_sha256':w.sha(result)}

def publish(root, *, event, provider, receipt, completed_receipt):
    root=Path(root);r=w.strict_json(Path(completed_receipt).read_bytes())
    c=validate_authorization(root,event=event,provider=provider,allow_completed_local_result=True)
    head=c['head']
    validate_receipt(c,receipt,provider)
    require(r['head']==head and r['authorization_sha256']==c['authorization_sha256'] and r['run_id']==c['run_id'] and r['processed_asset_count']==100 and r['processed_canonical_row_count']==3355389,'COMPLETION_RECEIPT_FAILURE')
    result=validate_complete_result(root,c);require(r['result_sha256']==w.sha(result),'PUBLICATION_RESULT_DIGEST_FAILURE')
    require(not provider.result_exists(head),'RESULT_ALREADY_PRESENT')
    return provider.publish_result(RESULT,result,head)

class GitHubProvider:
    """Repository-scoped JSON API. No release-asset download or broker route here."""
    def __init__(self,token):self.token=token
    def api(self,path,method='GET',body=None,allow404=False):
        require(path.startswith('/') and not path.startswith('//'),'GITHUB_API_PATH_FAILURE')
        req=urllib.request.Request('https://api.github.com/repos/'+REPO+path,method=method,data=w.canonical(body) if body is not None else None,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'})
        try:
            with urllib.request.urlopen(req,timeout=60) as response:return w.strict_json(response.read())
        except urllib.error.HTTPError as e:
            if allow404 and e.code==404:return None
            raise w.ScreenError('GITHUB_CONTROL_API_FAILURE') from None
        except Exception:raise w.ScreenError('GITHUB_CONTROL_API_FAILURE') from None
    def live_head(self):return self.api('/git/ref/heads/'+BRANCH)['object']['sha']
    def result_exists(self,head):return self.api('/contents/'+RESULT+'?ref='+head,allow404=True) is not None
    def release_inventory(self,tag):
        require(re.fullmatch(r'mxm-shallow-m5-v2-v4-[0-9a-f]{64}',tag) is not None,'RELEASE_IDENTITY_FAILURE')
        d=self.api('/releases/tags/'+tag)
        # Release GET is bounded by GitHub's embedded list. Explicitly paginate to
        # prove the whole asset inventory rather than assume its default page size.
        assets=[];page=1
        while True:
            batch=self.api('/releases/'+str(d['id'])+'/assets?per_page=100&page='+str(page));assets.extend(batch)
            require(len(assets)<=100,'ASSET_INVENTORY_FAILURE')
            if len(batch)<100:break
            page+=1
        return {'id':d['id'],'tag_name':d['tag_name'],'body':w.strict_json(d['body']),'assets':[{k:x[k] for k in ['id','name','size','digest','state']} for x in assets]}
    def create_attempt_claim(self,ref,head):
        require(ref=='refs/tags/mxm-master1576-v2-screen-attempt-'+head,'ATTEMPT_CLAIM_FAILURE')
        self.api('/git/refs','POST',{'ref':ref,'sha':head})
    def claim_head(self,ref):return self.api('/git/ref/'+ref.removeprefix('refs/'))['object']['sha']
    def publish_result(self,path,data,head):
        require(path==RESULT,'RESULT_PATH_FAILURE');require(self.live_head()==head,'PUBLICATION_HEAD_DRIFT')
        commit=self.api('/git/commits/'+head)
        blob=self.api('/git/blobs','POST',{'content':base64.b64encode(data).decode(),'encoding':'base64'})
        tree=self.api('/git/trees','POST',{'base_tree':commit['tree']['sha'],'tree':[{'path':RESULT,'mode':'100644','type':'blob','sha':blob['sha']}]})
        new=self.api('/git/commits','POST',{'message':'Publish complete MASTER1576 V2 outcome-blind structural screen','tree':tree['sha'],'parents':[head]})
        require(self.live_head()==head,'PUBLICATION_HEAD_DRIFT')
        # Non-force fast-forward rejects a concurrent sibling commit atomically.
        self.api('/git/refs/heads/'+BRANCH,'PATCH',{'sha':new['sha'],'force':False})
        require(self.live_head()==new['sha'],'PUBLICATION_HEAD_DRIFT')
        stored=self.api('/contents/'+RESULT+'?ref='+new['sha'])
        require(stored['sha']==blob['sha'],'PUBLICATION_ROUNDTRIP_FAILURE')
        return {'status':'PUBLISHED_COMPLETE_STRUCTURAL_RESULT','commit':new['sha'],'result_sha256':w.sha(data)}

def github_event():
    return {'event_name':os.environ.get('GITHUB_EVENT_NAME'),'repository':os.environ.get('GITHUB_REPOSITORY'),'ref':os.environ.get('GITHUB_REF'),'sha':os.environ.get('GITHUB_SHA'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'run_id':os.environ.get('GITHUB_RUN_ID')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['presecret','execute','publish']);parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));parser.add_argument('--receipt',required=True);parser.add_argument('--completed-receipt');args=parser.parse_args()
    try:
        require(bool(os.environ.get('GH_TOKEN')),'GITHUB_ROUTE_UNAVAILABLE');provider=GitHubProvider(os.environ['GH_TOKEN']);event=github_event()
        if args.mode=='presecret':result=presecret(args.root,event=event,provider=provider,receipt=args.receipt)
        elif args.mode=='execute':result=execute(args.root,event=event,provider=provider,receipt=args.receipt,completed_receipt=args.completed_receipt)
        else:result=publish(args.root,event=event,provider=provider,receipt=args.receipt,completed_receipt=args.completed_receipt)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as e:
        code=e.code if isinstance(e,w.ScreenError) else 'EXECUTION_CONTROL_FAILED_CLOSED'
        print(json.dumps({'status':'FAILED_CLOSED','code':code}));return 1
if __name__=='__main__':raise SystemExit(main())
