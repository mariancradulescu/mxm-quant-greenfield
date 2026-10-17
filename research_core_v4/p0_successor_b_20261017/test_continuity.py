import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from .continuity import *
from .lab import Lab
from research_core_v4.p0_supersession_20261016.authority import Denied

def root():
    return {'schema':'mxm.renewable-continuation-root.v1','owner_root':list(OWNER_ROOT),
            'authority_ref':ACTIVE_REF,'source_sha':'a'*40,'principal':'APP:5343530:172030470',
            'not_before':1000,'lease_seconds':86400,'max_items_per_lease':2,
            'providers':PROVIDERS.copy(),'orders_allowed':False,'historical_restart_allowed':False}

class Controls(unittest.TestCase):
    def setUp(self):
        self.p=root();self.s=genesis(self.p);self.h='b'*40
        self.s=propose(self.p,self.s,self.h,1000,'renew')['state']
    def reject(self,code,*args,**kwargs):
        with self.assertRaisesRegex(Denied,code):propose(*args,**kwargs)
    def claim(self):
        return propose(self.p,self.s,self.h,1001,'claim',input_sha256='c'*64,exclusivity_verified=True)['state']
    def test_renew_after_24h_same_owner_root(self):
        v=propose(self.p,self.s,self.h,1000+3*86400,'renew')['state']
        self.assertEqual(v['lease']['index'],3);self.assertEqual(v['root_sha256'],self.s['root_sha256'])
        self.assertEqual(v['generation'],1807)
    def test_renewal_replay_clock_rollback(self):
        self.reject('REPLAY_OR_ROLLBACK',self.p,self.s,self.h,1001,'renew')
        v=propose(self.p,self.s,self.h,87400,'renew')['state']
        self.reject('REPLAY_OR_ROLLBACK',self.p,v,self.h,1001,'renew')
    def test_missing_exclusivity(self):
        self.reject('EXCLUSIVITY',self.p,self.s,self.h,1001,'claim',input_sha256='c'*64)
    def test_timeout_pending_blocks_renewal_and_reexecution(self):
        v=self.claim()
        self.reject('PENDING_ACK_STOP',self.p,v,self.h,87400,'renew')
        self.reject('PENDING_OR_BUDGET',self.p,v,self.h,1001,'claim',input_sha256='c'*64,exclusivity_verified=True)
        self.reject('LEASE_EXPIRED',self.p,v,self.h,87400,'complete',result_sha256='d'*64,journal_sha256='e'*64)
    def test_revocation_all_continuation(self):
        v=propose(self.p,self.s,self.h,1001,'revoke')['state']
        for op in ('renew','claim','complete','advance'):
            self.reject('REVOKED',self.p,v,self.h,87400,op)
    def test_complete_readback_no_reexecution(self):
        v=self.claim();intent=v['pending']['intent']
        v=propose(self.p,v,self.h,1002,'complete',result_sha256='d'*64,journal_sha256='e'*64)['state']
        self.assertEqual(v['generation'],1808)
        self.assertFalse(reconcile(self.p,v,intent,'d'*64)['retry_allowed'])
        with self.assertRaises(Denied):reconcile(self.p,v,intent,'f'*64)
        self.reject('COMPLETION_BINDING',self.p,v,self.h,1003,'complete',result_sha256='d'*64,journal_sha256='e'*64)
    def test_budget_enforced(self):
        v=self.s
        for i in range(2):
            v=propose(self.p,v,self.h,1001,'claim',input_sha256='c'*64,exclusivity_verified=True)['state']
            v=propose(self.p,v,self.h,1001,'complete',result_sha256='d'*64,journal_sha256='e'*64)['state']
        self.reject('PENDING_OR_BUDGET',self.p,v,self.h,1001,'claim',input_sha256='c'*64,exclusivity_verified=True)
    def test_root_source_scope_tamper(self):
        for field,value in [('source_sha','f'*40),('orders_allowed',True),('providers',['BINANCE']),('historical_restart_allowed',True)]:
            p=copy.deepcopy(self.p);p[field]=value
            with self.assertRaises(Denied):propose(p,self.s,self.h,1001,'renew')
    def test_phase_requires_matching_completion_and_exclusivity(self):
        self.reject('PHASE_EVIDENCE',self.p,self.s,self.h,1001,'advance',completed_phase='B',result_sha256='d'*64,exclusivity_verified=True)
        v=self.claim();v=propose(self.p,v,self.h,1001,'complete',result_sha256='d'*64,journal_sha256='e'*64)['state']
        self.reject('EXCLUSIVITY',self.p,v,self.h,1001,'advance',completed_phase='B',result_sha256='d'*64)
        v=propose(self.p,v,self.h,1001,'advance',completed_phase='B',result_sha256='d'*64,exclusivity_verified=True)['state']
        self.assertEqual(v['phase'],'C')
    def test_concurrent_git_expected_oid_only_one_wins(self):
        with tempfile.TemporaryDirectory() as d:
            lab=Lab(pathlib.Path(d)/'b-continuity-fixture.git');lab.initialize();head=lab.cas(None,self.s)
            a=propose(self.p,self.s,head,1001,'claim',input_sha256='c'*64,exclusivity_verified=True)['state']
            b=propose(self.p,self.s,head,1001,'claim',input_sha256='d'*64,exclusivity_verified=True)['state']
            def run(state):
                try:lab.cas(head,state);return 'WIN'
                except Denied:return 'FENCED'
            with ThreadPoolExecutor(2) as pool:results=list(pool.map(run,[a,b]))
            self.assertEqual(sorted(results),['FENCED','WIN'])
    def test_cold_process_cannot_reexecute_pending(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'state.json';path.write_bytes(canonical({'policy':self.p,'state':self.claim()}))
            r=subprocess.run([sys.executable,'-m',__package__+'.test_continuity','--cold',str(path)],capture_output=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['state'],'PENDING_STOP_NO_REEXECUTION')

def phase1(folder):
    folder=pathlib.Path(folder);folder.mkdir(parents=True,exist_ok=True)
    p=root();lab=Lab(folder/'b-continuity-fixture.git');lab.initialize()
    h=lab.cas(None,genesis(p));h=lab.cas(h,propose(p,genesis(p),h,1000,'renew')['state'])
    _,s=lab.read();s=propose(p,s,h,1001,'claim',input_sha256='c'*64,exclusivity_verified=True)['state'];h=lab.cas(h,s)
    intent=s['pending']['intent'];s=propose(p,s,h,1002,'complete',result_sha256='d'*64,journal_sha256='e'*64)['state'];h=lab.cas(h,s)
    (folder/'handoff.json').write_bytes(canonical({'policy':p,'head':h,'intent':intent,'state_sha256':digest(canonical(s))}))

def phase2(folder):
    folder=pathlib.Path(folder);v=json.loads((folder/'handoff.json').read_bytes());p=v['policy']
    lab=Lab(folder/'b-continuity-fixture.git');h,s=lab.read()
    need(h==v['head'] and digest(canonical(s))==v['state_sha256'],'B_FIXTURE_ARTIFACT_DRIFT')
    need(reconcile(p,s,v['intent'],'d'*64)['retry_allowed'] is False,'B_FIXTURE_REPLAY')
    next_state=propose(p,s,h,1000+2*86400,'renew')['state'];h=lab.cas(h,next_state)
    need(next_state['generation']==1808 and next_state['lease']['index']==2,'B_FIXTURE_CONTINUITY')
    receipt={'scope':'LOCAL_GIT_FIXTURE_TWO_JOBS_NOT_ACTIVE_AUTHORITY','cold_handoff':True,
             'renewed_after_seconds':2*86400,'owner_root_unchanged':True,'generation':1808,
             'native_GitHub_App_exclusivity_proven':False,'writer_active':False,'final_fixture_oid':h}
    (folder/'cold-receipt.json').write_bytes(canonical(receipt));print(canonical(receipt).decode())

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--cold':
        v=json.loads(pathlib.Path(sys.argv[2]).read_bytes())
        try:propose(v['policy'],v['state'],'b'*40,87400,'renew')
        except Denied as e:
            need(str(e)=='B_PENDING_ACK_STOP','B_FIXTURE_FAILURE');print('{"state":"PENDING_STOP_NO_REEXECUTION"}')
        else:raise SystemExit(1)
    elif len(sys.argv)>1 and sys.argv[1] in ('--phase1','--phase2'):
        {'--phase1':phase1,'--phase2':phase2}[sys.argv[1]](sys.argv[2])
    else:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
        out=pathlib.Path('verification/successor-b');out.mkdir(parents=True,exist_ok=True)
        (out/'tests.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),
            'errors':len(result.errors),'scope':'NEW_B_COMPONENTS_ONLY','B1_repeated':False}))
        raise SystemExit(not result.wasSuccessful())
