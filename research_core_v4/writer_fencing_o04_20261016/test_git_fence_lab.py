"""Real local Git receive-pack races; no repository data, network or secrets."""
import concurrent.futures
import hashlib
import json
import pathlib
import subprocess
import tempfile
import threading
import unittest
from .git_fence_lab import GitFenceLab, Denied, Unknown, production_backend

D1=hashlib.sha256(b'synthetic checkpoint 1').hexdigest()
D2=hashlib.sha256(b'synthetic checkpoint 2').hexdigest()

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.tmp.name)
        self.remote=self.root/'server.git'
        subprocess.run(['git','init','--bare','-q',str(self.remote)],check=True)
        subprocess.run(['git','--git-dir='+str(self.remote),'config','receive.denyNonFastforwards','true'],check=True)
        subprocess.run(['git','--git-dir='+str(self.remote),'config','receive.denyDeletes','true'],check=True)
        (self.remote/'O04_SYNTHETIC_LAB_ONLY').write_text('synthetic\n')
        self.a=GitFenceLab(self.root/'a',self.remote)
        self.b=GitFenceLab(self.root/'b',self.remote)
        self.genesis=self.a.initialize_synthetic()

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_writers_same_parent_atomic_receive_pack_cas(self):
        # Both construct a valid successor of exactly the same remote OID, then
        # race two distinct receive-pack sessions. Not a serialized fake API.
        barrier=threading.Barrier(2)
        def race(client,owner):
            oid,state=client.read()
            self.assertEqual(oid,self.genesis)
            state.update(epoch=1,owner=owner,deadline=60)
            barrier.wait(timeout=10)
            try:return ('ACCEPTED',client._publish(oid,state))
            except Denied:return ('REJECTED',None)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(race,self.a,'writer-a'),pool.submit(race,self.b,'writer-b')]
            results=[f.result() for f in futures]
        self.assertEqual(sorted(x[0] for x in results),['ACCEPTED','REJECTED'])
        _,state=self.a.read();self.assertEqual(state['epoch'],1)

    def test_delayed_writer_fenced_after_expiry_and_new_epoch(self):
        old=self.a.claim(self.genesis,'writer-a',100,ttl=5)
        new=self.b.claim(old.oid,'writer-b',105)
        self.assertGreater(new.epoch,old.epoch)
        with self.assertRaisesRegex(Denied,'FENCED_WRITER'):
            self.a.accept(old,1,D1,'stale',106)
        self.b.accept(new,1,D2,'current',106)
        self.assertEqual(self.a.read()[1]['accepted']['1']['digest'],D2)

    def test_restart_after_claim_does_not_reuse_epoch(self):
        old=self.a.claim(self.genesis,'writer-a',100,ttl=5)
        restarted=GitFenceLab(self.root/'restarted',self.remote)
        with self.assertRaisesRegex(Denied,'LEASE_HELD'):
            restarted.claim(old.oid,'writer-b',104)
        new=restarted.claim(old.oid,'writer-b',105)
        restarted.accept(new,1,D1,'resume',106)
        with self.assertRaises(Denied):self.a.accept(old,1,D2,'late',106)

    def test_lost_accept_ack_readback_then_no_replay_after_restart(self):
        token=self.a.claim(self.genesis,'writer-a',100)
        with self.assertRaises(Unknown):self.a.accept(token,1,D1,'lost-ack',101,lose_ack=True)
        restarted=GitFenceLab(self.root/'restarted',self.remote)
        self.assertEqual(restarted.resolve(1,D1,'lost-ack'),'ACCEPTED_READBACK_NO_REPLAY')
        with self.assertRaises(Denied):restarted.accept(token,1,D1,'lost-ack',102)
        new=restarted.claim(restarted.read()[0],'writer-b',103)
        with self.assertRaisesRegex(Denied,'OPERATION_REPLAY'):restarted.accept(new,2,D2,'lost-ack',104)

    def test_missing_principal_denied_before_ref_mutation(self):
        with self.assertRaisesRegex(Denied,'AUTHORITY_MISSING'):
            self.a.claim(self.genesis,'untrusted',100)
        self.assertEqual(self.a.read()[0],self.genesis)

    def test_accepted_checkpoint_cannot_be_overwritten(self):
        token=self.a.claim(self.genesis,'writer-a',100)
        accepted=self.a.accept(token,1,D1,'first',101)
        next_token=self.b.claim(accepted,'writer-b',102)
        with self.assertRaisesRegex(Denied,'CHECKPOINT_VERSION'):
            self.b.accept(next_token,1,D2,'overwrite',103)
        self.b.accept(next_token,2,D2,'second',103)
        self.assertEqual(self.a.read()[1]['accepted']['1'],{'digest':D1,'operation':'first'})
        # Verify server rejects rollback even with force and a correct old OID.
        p=self.a.git('push','--force',str(self.remote),self.genesis+':refs/heads/o04-lab-state',check=False)
        self.assertNotEqual(p.returncode,0)

    def test_missing_global_admin_boundary_always_denies_production(self):
        with self.assertRaisesRegex(Denied,'GLOBAL_AUTHORITY_NOT_VERIFIED_NO_GO'):
            production_backend()
        with self.assertRaisesRegex(Denied,'LIVE_BACKEND_DISABLED'):
            GitFenceLab(self.root/'live','https://github.com/example/blocked.git')

    def test_client_validation_does_not_stop_unrestricted_legacy_credential(self):
        # Counterexample: a direct authorized Git writer can append fabricated
        # state despite local validation. This is why admin isolation is required.
        oid,state=self.b.read();state['accepted']['0']['digest']=D2
        self.b._publish(oid,state)
        self.assertEqual(self.a.read()[1]['accepted']['0']['digest'],D2)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    out=pathlib.Path('verification');out.mkdir(exist_ok=True)
    (out/'o04-tests.json').write_text(json.dumps({'schema':'mxm.o04.tests.v1','tests':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'scope':'SYNTHETIC_LOCAL_GIT_RECEIVE_PACK;NOT_LIVE_GITHUB_AUTHORIZATION',
        'production_enabled':False,'O04.1':'NO_GO_GLOBAL_AUTHORITY_UNVERIFIED'},sort_keys=True)+'\n')
    raise SystemExit(not result.wasSuccessful())
