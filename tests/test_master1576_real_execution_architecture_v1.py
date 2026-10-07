"""Disposable Git commits and fake control API; no real shard or secret access."""
import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from research_core_v4 import master1576_screen_v2_real_launcher_v1 as l
from tests.test_master1576_screen_v2 import fixture, reduce_campaign
w=l.w
ROOT=Path(__file__).resolve().parents[1]
TEST='tests/test_master1576_real_execution_architecture_v1.py'
RUNNER='research_core_v4/master1576_real_execution_architecture_preflight_v1.py'
FROZEN={w.PROTOCOL:'25d8b45d97fe6302af96c603202cf0f68764e844312987e54d06621c09938a30',w.WORKER:'2f2ba2ce22515a1a0ba7cd121cb90171ec9726cf743515ec5bad5944386ce965',w.PREFLIGHT:'f0373ca4efa007a9761e534d3cb2c0a14bcc0cf5c73b77298642b773d6a18329',w.ACCEPTANCE:'73a7714757488bcffbc2ac48a34653e9deed50491d72e72cffc7a402f83ae38e'}
def write(root,path,value):
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(w.canonical(value))
def run(root,*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL,text=True).strip()
@contextmanager
def cwd(root):
    old=Path.cwd();os.chdir(root)
    try:yield
    finally:os.chdir(old)
class Provider:
    def __init__(self,head,acceptance):
        self.head=head;self.claims={};self.result=False;self.published=[];self.inv=copy.deepcopy(acceptance['exact_release_inventory']);self.inv['id']=self.inv.pop('release_id')
    def live_head(self):return self.head
    def result_exists(self,head):return self.result
    def release_inventory(self,tag):return self.inv
    def create_attempt_claim(self,ref,head):
        w.require(ref not in self.claims,'ATTEMPT_ALREADY_CLAIMED');self.claims[ref]=head
    def claim_head(self,ref):return self.claims.get(ref)
    def publish_result(self,path,data,head):
        w.require(path==l.RESULT and self.head==head and not self.result,'PUBLICATION_HEAD_DRIFT');self.published.append((path,data,head));self.result=True
        return {'status':'PUBLISHED_COMPLETE_STRUCTURAL_RESULT','commit':'d'*40,'result_sha256':w.sha(data)}
class GitFixture:
    def __init__(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='synthetic-master1576-git-');self.root=Path(self.tmp.name)
        arch=l.load(ROOT,l.ARCH)
        paths={b['ref'] for b in arch['bindings'].values()}|{l.ARCH,w.ACCEPTANCE,w.PROTOCOL,w.PREFLIGHT}
        for p in paths:
            dest=self.root/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,dest)
        proof={'status':'PASS_SYNTHETIC_ONLY_NO_REAL_AUTHORIZATION','tests_failed':0,'tests_skipped':0,'bindings':{'architecture':{'ref':l.ARCH,'sha256':w.sha(l.raw(self.root,l.ARCH))}}}
        write(self.root,l.PROOF,proof)
        for s in l.STATES:write(self.root,s,{'real_screen_execution_architecture_ref':l.ARCH,'real_screen_execution_architecture_sha256':w.sha(l.raw(self.root,l.ARCH)),'real_screen_execution_preflight_ref':l.PROOF,'real_screen_execution_preflight_sha256':w.sha(l.raw(self.root,l.PROOF)),'next_action':l.NEXT,'qualification_protocol_ref':w.PROTOCOL,'qualification_protocol_sha256':FROZEN[w.PROTOCOL],'current_authority':w.ACCEPTANCE})
        run(self.root,'init','-q');run(self.root,'config','user.name','Synthetic Architecture Fixture');run(self.root,'config','user.email','synthetic@example.invalid');run(self.root,'add','.');run(self.root,'commit','-qm','Synthetic audited architecture parent');self.parent=run(self.root,'rev-parse','HEAD')
        self.auth={'schema':l.SCHEMA,'status':l.STATUS,'authorized_parent_head':self.parent,**{k:w.sha(l.raw(self.root,p)) for k,p in l.HASH_PATHS.items()},'final_manifest_sha256':l.load(self.root,w.ACCEPTANCE)['final_manifest']['sha256'],'release_identity':arch['release_identity'],'output_path':l.RESULT}
        self.commit_auth();self.provider=Provider(self.head,l.load(self.root,w.ACCEPTANCE));self.receipt=self.root/'private/presecret.json';self.completed=self.root/'private/completed.json'
    def commit_auth(self,extra=False):
        write(self.root,l.AUTH,self.auth)
        if extra:write(self.root,'extra.json',{})
        run(self.root,'add','.');run(self.root,'commit','-qm','Synthetic one-file durable authorization');self.head=run(self.root,'rev-parse','HEAD');self.event={'event_name':'push','repository':l.REPO,'ref':'refs/heads/'+l.BRANCH,'run_attempt':'1','run_id':'12345','sha':self.head}
    def rebuild(self,extra=False):
        run(self.root,'reset','--hard',self.parent);self.commit_auth(extra);self.provider.head=self.head
    def validate(self):return l.validate_authorization(self.root,event=self.event,provider=self.provider)
    def presecret(self):return l.presecret(self.root,event=self.event,provider=self.provider,receipt=self.receipt)
    def close(self):self.tmp.cleanup()
class ArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f,p=fixture();cls.synthetic=reduce_campaign(f,p)
    def setUp(self):
        self.net=patch('urllib.request.urlopen',side_effect=AssertionError('Real network forbidden'));self.net.start()
        self.f=GitFixture();self.addCleanup(self.f.close);self.addCleanup(self.net.stop)
    def fail(self,code,call=None):
        with self.assertRaises(w.ScreenError) as e:(call or self.f.validate)()
        self.assertEqual(e.exception.code,code)
    def synthetic_worker(self,root,arm):
        original=subprocess.check_output
        def git_output(args,*a,**kw):
            if args[:2]==['git','ls-remote']:return self.f.head+'\trefs/heads/'+l.BRANCH+'\n'
            return original(args,*a,**kw)
        with patch.object(w.subprocess,'check_output',side_effect=git_output):
            got,out=w.verify_arm(root,arm);self.assertEqual(got['execution_head'],self.f.head)
        result=copy.deepcopy(self.synthetic);result['release_identity']=self.f.auth['release_identity']
        # Pure control fixture: counts are fabricated to test full-completion publication.
        # Scientific reducer was already independently accepted; no market row is read here.
        delta=3355389-result['processed_canonical_row_count'];result['processed_canonical_row_count']+=delta
        r=result['identities'][0];r['TOTAL_ROW_COUNT']+=delta;r['ROW_COUNT_BY_SEGMENT'][0]+=delta
        r['COMPLETE_REASON_LEDGER']['descriptive_non_gating']['activity_distribution']['zero_tick_volume_bars']+=delta
        write(root,l.RESULT,result);return {'status':'COMPLETE_STRUCTURAL_SCREEN','result_sha256':w.sha(l.raw(root,l.RESULT))}
    def complete(self):
        self.f.presecret()
        with cwd(self.f.root):return l.execute(self.f.root,event=self.f.event,provider=self.f.provider,receipt=self.f.receipt,completed_receipt=self.f.completed,worker_call=self.synthetic_worker)
    def test_01_constructible_durable_authorization_commit(self):
        c=self.f.validate();self.assertEqual(run(self.f.root,'show','-s','--format=%P','HEAD'),self.f.parent)
        self.assertNotIn(self.f.head,l.raw(self.f.root,l.AUTH).decode());self.assertEqual(c['head'],self.f.head)
        self.assertEqual(run(self.f.root,'diff-tree','--no-commit-id','--name-status','-r','HEAD'),'A\t'+l.AUTH)
    def test_02_schema_exact(self):
        self.f.auth['extra']=1;self.f.rebuild();self.fail('DURABLE_AUTHORIZATION_SCHEMA_FAILURE')
    def test_03_wrong_status(self):
        self.f.auth['status']='OTHER';self.f.rebuild();self.fail('DURABLE_AUTHORIZATION_SCHEMA_FAILURE')
    def test_04_wrong_parent(self):
        self.f.auth['authorized_parent_head']='a'*40;self.f.rebuild();self.fail('AUTHORIZED_PARENT_FAILURE')
    def test_05_extra_changed_file(self):
        self.f.rebuild(extra=True);self.fail('AUTHORIZATION_ONLY_COMMIT_FAILURE')
    def test_06_hash_drift(self):
        self.f.auth['protocol_sha256']='a'*64;self.f.rebuild();self.fail('AUTHORIZATION_HASH_FAILURE')
    def test_07_live_drift(self):
        self.f.provider.head='a'*40;self.fail('LIVE_BRANCH_DRIFT')
    def test_08_rerun_before_secret(self):
        self.f.event['run_attempt']='2';self.fail('RUN_ATTEMPT_FAILURE',self.f.presecret);self.assertFalse(self.f.provider.claims)
    def test_09_existing_result_before_secret(self):
        self.f.provider.result=True;self.fail('RESULT_ALREADY_PRESENT',self.f.presecret);self.assertFalse(self.f.provider.claims)
    def test_10_local_result_before_secret(self):
        write(self.f.root,l.RESULT,{});self.fail('RESULT_ALREADY_PRESENT',self.f.presecret)
    def test_11_inventory_drift(self):
        self.f.provider.inv['assets'][0]['digest']='sha256:'+'0'*64;self.fail('ASSET_INVENTORY_FAILURE',self.f.presecret);self.assertFalse(self.f.provider.claims)
    def test_12_auth_worktree_substitute(self):
        a=copy.deepcopy(self.f.auth);a['worker_sha256']='a'*64;write(self.f.root,l.AUTH,a);self.fail('AUTHORIZATION_WORKTREE_DRIFT')
    def test_13_ephemeral_arm_deterministic(self):
        c=self.f.validate();a=w.canonical(l.arm_value(c));b=w.canonical(l.arm_value(c));self.assertEqual(a,b)
        self.assertEqual(l.arm_value(c)['execution_head'],self.f.head);self.assertEqual(len(l.arm_value(c)),8)
    def test_14_original_worker_accepts_derived_arm(self):self.complete()
    def test_15_cleanup_success(self):
        with l.ephemeral_arm(self.f.validate()) as p:
            parent=p.parent;self.assertEqual(p.stat().st_mode & 0o777,0o600);self.assertEqual(parent.stat().st_mode & 0o777,0o700)
        self.assertFalse(parent.exists())
    def test_16_cleanup_failure(self):
        with self.assertRaises(RuntimeError):
            with l.ephemeral_arm(self.f.validate()) as p:parent=p.parent;raise RuntimeError('Synthetic failure')
        self.assertFalse(parent.exists())
    def test_17_one_time_claim_before_secret(self):
        self.f.presecret();self.assertEqual(len(self.f.provider.claims),1);self.fail('ATTEMPT_ALREADY_CLAIMED',self.f.presecret)
    def test_18_missing_receipt_cannot_execute(self):
        called=[]
        with cwd(self.f.root),self.assertRaises(FileNotFoundError):l.execute(self.f.root,event=self.f.event,provider=self.f.provider,receipt=self.f.receipt,completed_receipt=self.f.completed,worker_call=lambda *a:called.append(1))
        self.assertFalse(called)
    def test_19_complete_path_publication(self):
        self.complete();r=l.publish(self.f.root,event=self.f.event,provider=self.f.provider,receipt=self.f.receipt,completed_receipt=self.f.completed)
        self.assertEqual(r['status'],'PUBLISHED_COMPLETE_STRUCTURAL_RESULT');self.assertEqual(len(self.f.provider.published),1);self.assertEqual(self.f.provider.published[0][0],l.RESULT)
    def test_20_partial_asset_result_not_published(self):
        self.complete();r=l.load(self.f.root,l.RESULT);r['processed_asset_count']=99;write(self.f.root,l.RESULT,r)
        self.fail('PARTIAL_RESULT_FORBIDDEN',lambda:l.publish(self.f.root,event=self.f.event,provider=self.f.provider,receipt=self.f.receipt,completed_receipt=self.f.completed));self.assertFalse(self.f.provider.published)
    def test_21_partial_rows_not_published(self):
        self.complete();r=l.load(self.f.root,l.RESULT);r['processed_canonical_row_count']-=1;write(self.f.root,l.RESULT,r)
        self.fail('PARTIAL_RESULT_FORBIDDEN',lambda:l.publish(self.f.root,event=self.f.event,provider=self.f.provider,receipt=self.f.receipt,completed_receipt=self.f.completed))
    def test_22_raw_price_output_rejected(self):
        self.complete();r=l.load(self.f.root,l.RESULT);r['identities'][0]['RAW_OHLC']=[1];write(self.f.root,l.RESULT,r)
        self.fail('OUTPUT_SCHEMA_FAILURE',lambda:l.publish(self.f.root,event=self.f.event,provider=self.f.provider,receipt=self.f.receipt,completed_receipt=self.f.completed))
    def test_23_result_digest_changed_rejected(self):
        self.complete();r=l.load(self.f.root,l.RESULT);r['identities'][0]['FIRST_TIMESTAMP']='2026-08-20T00:05:00Z';write(self.f.root,l.RESULT,r)
        self.fail('PUBLICATION_RESULT_DIGEST_FAILURE',lambda:l.publish(self.f.root,event=self.f.event,provider=self.f.provider,receipt=self.f.receipt,completed_receipt=self.f.completed))
    def test_24_output_path_exact(self):
        self.f.auth['output_path']='different.json';self.f.rebuild();self.fail('RESULT_PATH_FAILURE')
    def test_25_workflow_secret_and_trigger_boundaries(self):
        text=l.raw(ROOT,l.WORKFLOW).decode();self.assertEqual(re.findall(r'secrets\.([A-Z0-9_]+)',text),['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'])
        self.assertNotIn('workflow'+'_dispatch',text);self.assertNotIn('CTRADER',text);self.assertNotIn('cancel-in-progress: true',text)
        trigger=text.split('permissions:')[0];self.assertIn(l.AUTH,trigger);self.assertNotIn(l.RESULT,trigger);self.assertEqual(trigger.count('      - '),1)
        self.assertLess(text.index(' presecret '),text.index('secrets.'));self.assertIn('if: always()',text)
    def test_26_no_broker_route(self):
        text=l.raw(ROOT,l.LAUNCHER).decode();self.assertNotIn('ctrader',text.lower());self.assertNotIn('download_asset(',text)
        self.assertNotIn('secrets.',text)
    def test_27_preservation_and_real_files_absent(self):
        for p,h in FROZEN.items():self.assertEqual(w.sha(l.raw(ROOT,p)),h)
        self.assertFalse((ROOT/l.AUTH).exists());self.assertFalse((ROOT/l.RESULT).exists())
        arch=l.load(ROOT,l.ARCH)
        for b in arch['bindings'].values():self.assertEqual(w.sha(l.raw(ROOT,b['ref'])),b['sha256'])
        self.assertEqual(len(arch['accepted_release_inventory']['assets']),100)
    def test_28_only_result_path_git_publication_and_atomic_ref(self):
        p=l.GitHubProvider('SYNTHETIC_NOT_A_SECRET');calls=[];heads=iter([self.f.head,self.f.head,'c'*40]);p.live_head=lambda:next(heads)
        def api(path,method='GET',body=None,allow404=False):
            calls.append((path,method,body))
            if path.startswith('/git/commits/') and method=='GET':return {'tree':{'sha':'t'*40}}
            if path=='/git/blobs':return {'sha':'b'*40}
            if path=='/git/trees':return {'sha':'t'*40}
            if path=='/git/commits':return {'sha':'c'*40}
            if path.startswith('/contents/'):return {'sha':'b'*40}
            return {}
        p.api=api;p.publish_result(l.RESULT,b'{}',self.f.head)
        tree=next(c[2] for c in calls if c[0]=='/git/trees');self.assertEqual([x['path'] for x in tree['tree']],[l.RESULT])
        ref=next(c[2] for c in calls if c[1]=='PATCH');self.assertFalse(ref['force'])
        self.assertEqual(next(c[2]['parents'] for c in calls if c[0]=='/git/commits' and c[1]=='POST'),[self.f.head])
    def test_29_publication_drift_fails_before_ref_update(self):
        p=l.GitHubProvider('SYNTHETIC');calls=[];heads=iter([self.f.head,'e'*40]);p.live_head=lambda:next(heads)
        def api(path,method='GET',body=None,allow404=False):
            calls.append(method);return {'tree':{'sha':'t'*40},'sha':'c'*40}
        p.api=api;self.fail('PUBLICATION_HEAD_DRIFT',lambda:p.publish_result(l.RESULT,b'{}',self.f.head));self.assertNotIn('PATCH',calls)
    def test_30_wrong_event_fails_closed(self):
        self.f.event['event_name']='workflow_dispatch';self.fail('WRONG_GITHUB_EVENT')
    def test_31_parent_state_bound(self):
        # State mutation cannot pass the single authorization-file commit law.
        write(self.f.root,l.STATES[0],{});run(self.f.root,'add','.');run(self.f.root,'commit','-qm','Unauthorized second file');self.f.event['sha']=run(self.f.root,'rev-parse','HEAD');self.fail('AUTHORIZED_PARENT_FAILURE')
    def test_32_final_state_hash_binding_when_materialized(self):
        if not (ROOT/l.PROOF).exists():return
        for s in l.STATES:
            d=l.load(ROOT,s);self.assertEqual(d['next_action'],l.NEXT);self.assertEqual(d['current_authority'],w.ACCEPTANCE)
            self.assertEqual(d['qualification_protocol_sha256'],FROZEN[w.PROTOCOL]);self.assertEqual(d['real_screen_execution_architecture_sha256'],w.sha(l.raw(ROOT,l.ARCH)));self.assertEqual(d['real_screen_execution_preflight_sha256'],w.sha(l.raw(ROOT,l.PROOF)))
        proof=l.load(ROOT,l.PROOF);self.assertEqual(proof['tests_failed'],0)
        for b in proof['bindings'].values():self.assertEqual(w.sha(l.raw(ROOT,b['ref'])),b['sha256'])

    def test_33_worker_failure_cleans_arm_and_no_publication(self):
        self.f.presecret();seen=[]
        def worker(root,arm):seen.append(arm.parent);raise w.ScreenError('SYNTHETIC_WORKER_FAILURE')
        with cwd(self.f.root):self.fail('SYNTHETIC_WORKER_FAILURE',lambda:l.execute(self.f.root,event=self.f.event,provider=self.f.provider,receipt=self.f.receipt,completed_receipt=self.f.completed,worker_call=worker))
        self.assertFalse(seen[0].exists());self.assertFalse(self.f.completed.exists());self.assertFalse(self.f.provider.published)
        self.assertEqual(len(self.f.provider.claims),1)
    def test_34_arm_bytes_equal_across_private_locations(self):
        c=self.f.validate()
        with l.ephemeral_arm(c) as p:a=p.read_bytes();one=p
        with l.ephemeral_arm(c) as p:b=p.read_bytes();two=p
        self.assertNotEqual(one,two);self.assertEqual(a,b)
    def test_35_missing_inventory_asset_fails_before_secret(self):
        self.f.provider.inv['assets'].pop();self.fail('ASSET_INVENTORY_FAILURE',self.f.presecret);self.assertFalse(self.f.provider.claims)
    def test_36_missing_authorization_rejected(self):
        (self.f.root/l.AUTH).unlink();self.fail('NO_DURABLE_AUTHORIZATION',self.f.presecret)
    def test_37_publisher_path_allowlist(self):
        p=l.GitHubProvider('SYNTHETIC');self.fail('RESULT_PATH_FAILURE',lambda:p.publish_result('arbitrary.json',b'{}',self.f.head))
    def test_38_accepted_manifest_release_primary_governance_preserved(self):
        arch=l.load(ROOT,l.ARCH)
        for key in ['final_manifest','segment_1','segment_2','segment_3','segment_4','master','PRIMARY145','discovery','selection']:
            b=arch['bindings'][key];self.assertEqual(w.sha(l.raw(ROOT,b['ref'])),b['sha256'])
        self.assertEqual(arch['preservation']['search_budget'],{'total':84,'used':21,'remaining':63,'refunds':0,'economic_outcomes_opened':29,'consume_this_task':0})
        self.assertFalse(arch['preservation']['protected_forward_opened']);self.assertFalse(arch['preservation']['confirmation_opened'])
