"""One delegated App issuer; atomic encrypted checkpoints; no OWNER review POST.

Admission is a native administrative installation of an immutable source and
its exclusive credential route. It is explicitly NOT evidence of a personal
OWNER review. The old review-gated workload is retired, not bypassed.
"""
import base64
import gzip
import io
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime
from .control import *
from . import science
from research_core_v4.delegated_bc_20261019 import control as predecessor_control
from research_core_v4.delegated_bc_20261019.native import Store as PredecessorStore
from research_core_v4.p0_successor_a_20261017.publisher import GitCAS, AckUnknown
from research_core_v4.p0_successor_a_20261017.issuer import http, _app_token
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json, unpack
from research_core_v4.successor_c_20261018 import verdict, readback

REPO='mariancradulescu/mxm-quant-greenfield'
PREFIX='/repos/'+REPO+'/'
REMOTE='https://github.com/'+REPO+'.git'
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'verification/delegated-campaign'
OLD_RUN=39147483523
OLD_SOURCE='95fc312a84f803276a408ca4f821a09b007e56b0'
ACL=[{'actor_id':5343530,'actor_type':'Integration','bypass_mode':'always'}]

def workload():
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==SOURCE and
         os.environ.get('GITHUB_JOB')=='delegated-issuer' and
         os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1','BC_FROZEN_WORKLOAD')

def public_rule_view(rule):
    # Native ruleset revisions fence even fields redacted from least-privilege tokens.
    stamp=rule.get('updated_at')
    need(type(stamp) is str,'BC_NATIVE_REVISION_MISSING')
    stamp=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
    return {'id':rule['id'],'updated_at_epoch':stamp,'target':rule['target'],
        'source_type':rule['source_type'],'source':rule['source'],'enforcement':rule['enforcement'],
        'conditions':rule['conditions'],'rules':sorted(rule['rules'],key=lambda r:r['type'])}

def check_rule(rule,*,source=False,exact=False,fence=None):
    target='refs/heads/'+SOURCE if source else ACTIVE_REF
    expected=[] if source else ACL
    need(rule['enforcement']=='active' and
         rule['conditions']['ref_name']=={'include':[target],'exclude':[]} and
         {r['type'] for r in rule['rules']}=={'creation','update','deletion','non_fast_forward'},
         'BC_NATIVE_RULE_SCOPE')
    if fence is not None:
        need(fence.get('bypass_actors')==expected and public_rule_view(rule)==public_rule_view(fence),
             'BC_NATIVE_ADMIN_REVISION_CHANGED')
        # Absence is documented API redaction, never interpreted as an empty ACL.
        # The native admin descriptor pins the full observed ACL and its revision.
        if 'bypass_actors' in rule:need(rule['bypass_actors']==expected,'BC_NATIVE_RULE_ACTORS')
    else:need(rule.get('bypass_actors',None if exact else expected)==expected,'BC_NATIVE_RULE_ACTORS')

def delegation_descriptor(rule_id):
    raw=os.environ.get('BC_NATIVE_DELEGATION','')
    need(0<len(raw)<=32768,'BC_NATIVE_ADMIN_DESCRIPTOR_MISSING')
    descriptor=strict_json(raw.encode())
    need(set(descriptor)=={'schema','source_sha','policy_sha256','source_seal','active_acl','append_only','predecessor'} and
         descriptor['schema']=='mxm.native-admin-delegation.v1' and
         descriptor['source_sha']==os.environ['GITHUB_SHA'] and descriptor['policy_sha256']==POLICY_SHA and
         descriptor['predecessor']==PREDECESSOR and descriptor['source_seal']['id']==rule_id and descriptor['active_acl']['id']==25268790 and
         descriptor['append_only']['id']==25222248,'BC_NATIVE_ADMIN_DESCRIPTOR_BINDING')
    return descriptor

def verify_server(rule_id,token,*,exact=False):
    descriptor=delegation_descriptor(rule_id)
    _,r=http(PREFIX+'git/ref/heads/'+SOURCE,token)
    need(r['object']['sha']==os.environ['GITHUB_SHA'],'BC_SOURCE_MOVED')
    _,rule=http(PREFIX+'rulesets/'+str(rule_id),token)
    check_rule(rule,source=True,exact=exact,fence=descriptor['source_seal'])
    _,acl=http(PREFIX+'rulesets/25268790',token)
    check_rule(acl,exact=exact,fence=descriptor['active_acl'])
    _,append=http(PREFIX+'rulesets/25222248',token)
    need(append['enforcement']=='active' and
         append['conditions']['ref_name']=={'include':['refs/heads/mxm-o04-*'],'exclude':[]} and
         {r['type'] for r in append['rules']}=={'deletion','non_fast_forward','required_linear_history'},
         'BC_APPEND_ONLY_REQUIRED')
    need(descriptor['append_only']['bypass_actors']==[] and
         public_rule_view(append)==public_rule_view(descriptor['append_only']) and
         ('bypass_actors' not in append or append['bypass_actors']==[]),'BC_APPEND_NATIVE_REVISION')
    _,owner=http(PREFIX+'git/ref/heads/mxm-o04-accepted-owner-1807-v1',token)
    need(owner['object']['sha']==OWNER_ROOT[1],'BC_OWNER_ROOT_CHANGED')
    _,old=http(PREFIX+'actions/runs/'+str(OLD_RUN),os.environ['GH_TOKEN'])
    need(old['status']=='completed' and old['conclusion']=='cancelled' and
         old['head_sha']==OLD_SOURCE and old['run_attempt']==1,'BC_OLD_RUN_NOT_RETIRED')
    _,reviews=http(PREFIX+'actions/runs/'+str(OLD_RUN)+'/approvals',os.environ['GH_TOKEN'])
    need(reviews==[],'BC_UNEXPECTED_OLD_REVIEW')

class Store(GitCAS):
    def __init__(self,path,token,source):
        self.directory=Path(path);self.directory.mkdir();self.ref=ACTIVE_REF;self.source=source
        self.cipher=None
        self.env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TMPDIR')}
        self.env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',
            GIT_AUTHOR_NAME='MXM delegated Director',GIT_COMMITTER_NAME='MXM delegated Director',
            GIT_AUTHOR_EMAIL='mxm@example.invalid',GIT_COMMITTER_EMAIL='mxm@example.invalid',
            GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
            GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+token).encode()).decode())
        self.git('init','-q')

    def read(self):
        h=self.head()
        if h is None:self.cipher=None;return None,None
        self.git('fetch','--quiet','--no-tags',REMOTE,h)
        s=strict_json(self.git('show',h+':state.json').stdout);validate(s,self.source)
        need(s['checkpoint_sha256'] is not None,'BC_MIGRATION_ARCHIVE_REQUIRED')
        parents=self.git('rev-list','--parents','-n','1',h).stdout.decode().split()[1:]
        need(len(parents)<=1,'BC_MERGE_PARENT_DENIED')
        if s['checkpoint_sha256'] is not None:
            self.cipher=self.git('show',h+':checkpoint.mxmenc').stdout
            need(len(self.cipher)<=16*1024*1024 and digest(self.cipher)==s['checkpoint_sha256'],
                 'BC_CHECKPOINT_CIPHER')
        else:self.cipher=None
        need(self.head()==h,'BC_HEAD_MOVED_READ')
        return h,s

    def candidate(self,expected,state):
        validate(state,self.source)
        # A migration uses a separate verified reader; fetch its exact parent into this writer.
        if expected and self.git('cat-file','-e',expected,check=False).returncode:
            self.git('fetch','--quiet','--no-tags',REMOTE,expected)
        rows=[]
        for name,data in [('state.json',canonical(state)),('checkpoint.mxmenc',self.cipher)]:
            if data is None:continue
            blob=self.git('hash-object','-w','--stdin',data=data).stdout.decode().strip()
            rows.append('100644 blob '+blob+'\t'+name+'\n')
        need(state['checkpoint_sha256']==(None if self.cipher is None else digest(self.cipher)),
             'BC_ATOMIC_CIPHER_BINDING')
        tree=self.git('mktree',data=''.join(sorted(rows,key=lambda r:r.split('\t')[1])).encode()).stdout.decode().strip()
        args=['commit-tree',tree]
        if expected:args+=['-p',expected]
        return self.git(*args,data=b'MXM delegated atomic encrypted checkpoint\n').stdout.decode().strip()

def private_key(tmp):
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    key,fp=_private_key_from_secret(tmp);need(fp==readback.FP,'BC_OWNER_KEY_PIN');return key

def decrypt(blob,key,tmp):
    from research_core_v4.remediation_p0_p4_20261015.owner import bounded_decrypt
    return strict_json(unpack(bounded_decrypt(blob,key,tmp)),max_elements=8000000)

def seal(value,key,tmp):
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    from research_core_v4.remediation_p0_p4_20261015.owner import bounded_decrypt
    public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public)==readback.FP,'BC_OUTPUT_RECIPIENT')
    raw=canonical(value);path=tmp/'checkpoint.mxmenc'
    encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=path)
    blob=path.read_bytes();need(unpack(bounded_decrypt(blob,key,tmp))==raw,'BC_ENCRYPTED_READBACK')
    return blob

def existing_summary(key,tmp):
    archive=base64.b64decode((ROOT/'research_core_v4/successor_c_20261018/READBACK_39126863721.zip.b64').read_text().strip(),validate=True)
    need(digest(archive)==verdict.ZIP_SHA,'BC_INPUT_ARCHIVE_PIN')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        need(set(z.namelist())=={'economic-readback.mxmenc','public-status.json'},'BC_INPUT_FILES')
        blob=z.read('economic-readback.mxmenc')
    need(digest(blob)==verdict.CIPHER_SHA,'BC_INPUT_CIPHER_PIN')
    result=decrypt(blob,key,tmp)
    need(result['schema']=='mxm.c-private-readback.v1' and result['cold_run_id']==39126863721,
         'BC_INPUT_RUN_PIN')
    summary=result['original_summary']
    need(digest(readback.original_encoding(summary))==readback.SUMMARY_SHA,'BC_INPUT_SUMMARY_PIN')
    return summary

def execute():
    workload();mode=os.environ['BC_COMMAND'];source=os.environ['GITHUB_SHA'];run=int(os.environ['GITHUB_RUN_ID'])
    need(mode in ('migrate','continue','revoke'),'BC_COMMAND')
    if mode=='migrate':rule_id=int(os.environ['BC_SOURCE_RULESET_ID'])
    else:
        _,entry=http(PREFIX+'contents/state.json?ref=mxm-o04-active-v1',os.environ['GH_TOKEN'])
        need(entry['encoding']=='base64' and entry['size']<=1048576,'BC_PUBLIC_STATE_SIZE')
        public=strict_json(base64.b64decode(entry['content']));validate(public,source)
        rule_id=public['source_rule_id']
    verify_server(rule_id,os.environ['GH_TOKEN'])  # public native controls before App key use
    print(json.dumps({'phase':'BC_PUBLIC_NATIVE_ADMISSION_VERIFIED'}))
    OUT.mkdir(parents=True,exist_ok=True)
    with _app_token(os.environ['SUCCESSOR_APP_PRIVATE_KEY']) as token, tempfile.TemporaryDirectory() as folder:
        print(json.dumps({'phase':'BC_APP_IDENTITY_INSTALLATION_AND_TOKEN_SCOPE_VERIFIED'}))
        verify_server(rule_id,token,exact=True)
        print(json.dumps({'phase':'BC_APP_NATIVE_REVISION_FENCES_VERIFIED'}))
        store=Store(Path(folder)/'git',token,source);bootstrap_oid=None
        if mode=='migrate':
            old=PredecessorStore(Path(folder)/'predecessor',token,PREDECESSOR['source_sha'])
            old_h,old_state=old.read()
            check_predecessor(old_state,old_h)
            _,old_rule=http(PREFIX+'rulesets/'+str(PREDECESSOR['source_rule_id']),token)
            need(old_rule['enforcement']=='active' and old_rule['conditions']['ref_name']==
                 {'include':['refs/heads/'+predecessor_control.SOURCE],'exclude':[]} and
                 {r['type'] for r in old_rule['rules']}=={'creation','update','deletion','non_fast_forward'},
                 'BC_PREDECESSOR_SEAL')
            with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as private_folder:
                tmp=Path(private_folder);key=private_key(tmp);previous=decrypt(old.cipher,key,tmp)
                archived={'public_state':old_state,'journal':previous};check_archive(archived)
                state=genesis(source,int(time.time()),rule_id)
                journal={'schema':'mxm.delegated-private-checkpoint.v1','source_sha':source,'policy_sha256':POLICY_SHA,
                    'predecessor':archived,'results':[]}
                store.cipher=seal(journal,key,tmp);state['checkpoint_sha256']=digest(store.cipher)
                h=store.cas(old_h,state);bootstrap_oid=h
            # The sole migration is a child of the existing authority; never an absent-ref bootstrap.
        h,state=store.read();need(h is not None,'BC_MISSING_AUTHORITY_NO_REBOOTSTRAP')
        need(state['source_rule_id']==rule_id,'BC_SEAL_ID_CHANGED')
        if mode=='revoke':
            state=propose(state,source,h,int(time.time()),'revoke');h=store.cas(h,state)
            action='REVOKED';next_after=None
        else:
            action=scheduling(state,source,int(time.time()))
            need(action=='CONTINUE','BC_'+action)
            # A persisted intent is never executed again after crash, timeout or unknown ACK.
            while True:
                now=int(time.time());current=lease(state,now)
                prior_index=state['done'][-1]['lease_index'] if state['done'] else -1
                if current['index']>prior_index and now+POLICY['max_task_seconds']<=current['expires_at']:break
                time.sleep(max(1,current['expires_at']-now+1))
                h,state=store.read();need(scheduling(state,source,int(time.time()))=='CONTINUE','BC_CHANGED_WHILE_WAITING')
            if state['lease']!=lease(state,int(time.time())):
                state=propose(state,source,h,int(time.time()),'renew');h=store.cas(h,state)
            # Validate the cold encrypted journal BEFORE claiming the next operation.
            with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as private_folder:
                tmp=Path(private_folder);key=private_key(tmp)
                journal={'schema':'mxm.delegated-private-checkpoint.v1','source_sha':source,
                         'policy_sha256':POLICY_SHA,'results':[]}
                if store.cipher is not None:
                    journal=decrypt(store.cipher,key,tmp)
                    need(journal['schema']=='mxm.delegated-private-checkpoint.v1' and
                         journal['source_sha']==source and journal['policy_sha256']==POLICY_SHA and
                         len(journal['results'])==state['sequence'],'BC_COLD_JOURNAL_BINDING')
                    check_archive(journal.get('predecessor',{}))
                    for row,done in zip(journal['results'],state['done']):
                        need(row['task']==done['task'] and row['intent']==done['intent'] and
                             digest(canonical(row['result']))==done['result_sha256'],'BC_COLD_RESULT_CHAIN')
                verify_server(rule_id,token,exact=True)
                state=propose(state,source,h,int(time.time()),'claim',run_id=run);h=store.cas(h,state)
                task=state['pending']['task'];intent=state['pending']['intent']
                if task=='C_MISSINGNESS_FRONTIER':result=science.missingness(existing_summary(key,tmp))
                elif task=='C_COST_SENSITIVITY':result=science.cost_sensitivity(existing_summary(key,tmp))
                else:
                    need([r['task'] for r in journal['results']]==list(TASKS[:2]),'BC_SCIENCE_DEPENDENCY')
                    result=science.admission([r['result'] for r in journal['results']])
                journal['results'].append({'task':task,'intent':intent,'result':result})
                cipher=seal(journal,key,tmp)
                verify_server(rule_id,token,exact=True)
                candidate=propose(state,source,h,int(time.time()),'complete',run_id=run,
                    result_sha256=digest(canonical(result)),checkpoint_sha256=digest(cipher))
                store.cipher=cipher;h=store.cas(h,candidate);h,state=store.read()
                cold=decrypt(store.cipher,key,tmp)
                need(cold==journal and state['pending'] is None and state['done'][-1]['intent']==intent,
                     'BC_NATIVE_COMMIT_READBACK')
                (OUT/'checkpoint.mxmenc').write_bytes(store.cipher)
            action=scheduling(state,source,int(time.time()));next_after=state['lease']['expires_at']+1
        receipt={'schema':'mxm.delegated-campaign-receipt.v1','source_sha':source,'run_id':run,
            'policy_sha256':POLICY_SHA,'native_oid':h,'sequence':state['sequence'],
            'state':action,'lease':state['lease'],'migration_oid':bootstrap_oid,'bootstrap_dispatches':0,'predecessor_oid':PREDECESSOR['native_oid'],
            'native_stale_cas_rejected':None,'predecessor_cold_verified':True,
            'cold_encrypted_checkpoint_verified':state['checkpoint_sha256'] is not None,
            'checkpoint_sha256':state['checkpoint_sha256'],'owner_root_unchanged':True,
            'native_owner_review_claimed':False,'orders':0,'broker_requests':0,
            'acl_evidence':'NATIVE_ADMIN_DESCRIPTOR_AND_CURRENT_REVISION_FENCE',
            'new_app_token_per_run':True,'token_revocation':'CHECK_AFTER_CONTEXT_EXIT'}
    # Emitted only AFTER the App context confirms successful token revocation.
    receipt['token_revocation']='CONFIRMED_204'
    (OUT/'receipt.json').write_bytes(canonical(receipt));print(canonical(receipt).decode())
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:
        f.write('next='+('continue' if action=='CONTINUE' else 'stop')+'\n')
        f.write('next_after='+str(next_after or 0)+'\n')

if __name__=='__main__':
    try:execute()
    except Exception as error:
        import re
        code=str(error) if re.fullmatch(r'(BC|B|APP|TOKEN|NATIVE|STALE|SERVER)_[A-Z0-9_]+',str(error)) else type(error).__name__
        print(json.dumps({'state':'BC_STOP_NO_REEXECUTION','safe_code':code,
            'http_status':getattr(error,'code',None)}))
        raise SystemExit(1) from None
