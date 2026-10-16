import copy
import pathlib
import subprocess
import tempfile
import unittest
from ..writer_fencing_o04_20261016 import git_fence_lab as lab
from ..remediation_p0_p4_20261015.safety import ReadOnlyAPI
from .protocol import FixtureProtocol,SyntheticIssuer,accept_checkpoint,owner_reader
from .readers import ENTRYPOINTS,dry_run

class ProtocolTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();d=pathlib.Path(self.tmp.name);r=d/'remote.git'
  subprocess.run(['git','init','--bare','-q',str(r)],check=True);(r/'O04_SYNTHETIC_LAB_ONLY').write_text('synthetic\n')
  self.t=lab.GitFenceLab(d/'client',r);self.issuer=SyntheticIssuer(d/'issuer');self.clock=100
  self.p=FixtureProtocol(self.t,self.issuer,'a'*40,lambda:self.clock);self.p.genesis()
 def tearDown(self):self.tmp.cleanup()
 def test_transition_content_and_reader_regression(self):
  p=self.p;c=p.claim(p.read()[0],'s');proposal=p.proposal(c,'op');pending=p.pending(c,proposal);accepted=p.accept_fixture(pending);oid,s=p.read()
  self.assertEqual(accepted,oid);self.assertEqual(s['status'],'ACCEPTED');self.assertEqual(p.resolve('op',proposal['record']['manifest_sha256'])['status'],'SYNTHETIC_ACCEPTED_READBACK_NO_REPLAY')
  for e in ENTRYPOINTS:
   r=dry_run(e,'refs/heads/mxm-o04-stage-1',oid,s,self.issuer,'a'*40,'refs/heads/mxm-o04-stage-1')
   self.assertEqual(r['OWNER'],'NOT_AUTHORIZED');self.assertEqual(r['science'],'UNKNOWN');self.assertTrue(r['STAGING'].startswith('DRY_RUN_VALID_SYNTHETIC'))
   self.assertEqual(dry_run(e,'refs/heads/mxm-o04-stage-2',oid,s,self.issuer,'a'*40,'refs/heads/mxm-o04-stage-1')['STAGING'],'NOT_AUTHORIZED')
  changed=copy.deepcopy(s);changed['accepted']['1']['proposal']['record']['epoch']=0
  self.assertEqual(dry_run('frontier_restore','refs/heads/mxm-o04-stage-1',oid,changed,self.issuer,'a'*40,'refs/heads/mxm-o04-stage-1')['STAGING'],'QUARANTINED')
 def test_expired_fenced_and_signature(self):
  p=self.p;c=p.claim(p.read()[0],'s');q=p.proposal(c,'op');oid=p.read()[0]
  q['signature']='YmFk';self.assertRaises(lab.Denied,p.pending,c,q);self.assertEqual(p.read()[0],oid)
  q=p.proposal(c,'op');self.clock=221;self.assertRaises(lab.Denied,p.pending,c,q)
  new=p.claim(c,'s2');self.assertEqual(p.read()[1]['epoch'],2);self.assertRaises(lab.Denied,p.pending,c,q)
 def test_acceptance_and_owner_gate_cannot_be_enabled_by_caller(self):
  for v in (True,False,{},'PRODUCTION_GO'):
   self.assertRaisesRegex(lab.Denied,'PRINCIPAL_ISOLATION_NO_GO',accept_checkpoint,{'grant':v},PRODUCTION_GO=v)
   self.assertEqual(owner_reader('refs/heads/mxm-o04-active-v1',{'oid':'a'*40},PRODUCTION_GO=v),'NOT_AUTHORIZED')
 def test_readonly_transport_semantics_retained(self):
  calls=[];api=ReadOnlyAPI(lambda *a:calls.append(a) or {},[412686323,642889915])
  api('releases/412686323');self.assertEqual(len(calls),1)
  for method in ('POST','PATCH','PUT','DELETE'):
   with self.assertRaises(Exception):api('releases/412686323',method,{})
  self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main()
