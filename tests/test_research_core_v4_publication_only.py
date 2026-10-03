"""Synthetic structural evidence only; never import or call scientific execution."""
import copy,hashlib,io,json,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from research_core_v4 import publication_only_v1 as p

def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
def emitted(payload):
 x=copy.deepcopy(payload);x[p.SELF_FIELD]=p.sha(canonical(payload));return canonical(x)
def make_zip(members):
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in members.items():z.writestr(name,data)
 return out.getvalue()
class PublicationOnlyTests(unittest.TestCase):
 def setUp(self):
  self.provenance={'authority_sha256':'d'*64,'fixture':'SYNTHETIC_ONLY'}
  self.prepared={'provenance':self.provenance,'response_opened':False}
  self.payload={'schema':'mxm.research-core-v4.development-response-result.v2','execution_provenance':self.provenance,'confirmation_execution_authorized':False,'broker_acquisition_authorized':False,'candidate_promotion_authorized':False,'synthetic_nested':{2:{3:'x',11:'y'},10:{1:'z',20:'w'}},'unicode':'ș ☃ escaped " brace } comma ,'}
  self.raw=emitted(self.payload)
  self.members={p.RAW_NAME:self.raw,'prepared.json':canonical(self.prepared),p.RAW_NAME+'.opening.lock':('d'*64+'\n').encode(),'failure-classification.json':canonical({'classification':'RAW_RESULT_RECOVERABLE_PUBLICATION_ONLY_NO_RECOMPUTATION','arm_commit':'b'*40,'fence_commit':'c'*40,'owner_run_id':'13','automatic_retry':False,'market_outcome_interpreted':False})}
  self.archive=make_zip(self.members)
  self.expected={'repository':'synthetic/repository','branch':'synthetic-branch','certified_parent':'a'*40,'arm_commit':'b'*40,'fence_commit':'c'*40,'run_id':13,'artifact_id':17,'artifact_name':'v4-raw-recovery-13-1','artifact_zip_sha256':p.sha(self.archive),'member_hashes':{k:p.sha(v) for k,v in self.members.items()},'raw_size':len(self.raw),'producer_self_digest':p.sha(canonical(self.payload))}
  self.identity={'repository':'synthetic/repository','id':17,'name':'v4-raw-recovery-13-1','expired':False,'digest':'sha256:'+p.sha(self.archive),'workflow_run':{'id':13,'head_sha':'b'*40,'head_branch':'synthetic-branch'}}
  self.run={'id':13,'run_attempt':1,'head_sha':'b'*40,'status':'completed','conclusion':'failure','path':'.github/workflows/v4-greenfield-recovery-v4.yml'}
  self.history={'branch_head':'c'*40,'fence_commit':'c'*40,'fence_parent':'b'*40,'arm_commit':'b'*40,'arm_parent':'a'*40}
  self.arm=canonical({'pre_arm_parent_head':'a'*40,'accepted_canonical_result_limit':1,'automatic_retry':False})
  self.fence=canonical({'arm_commit':'b'*40,'arm_document_sha256':p.sha(self.arm),'owner_run_id':'13','owner_run_attempt':1,'prepared_sha256':p.sha(self.members['prepared.json']),'canonical_result_limit':1,'automatic_retry':False})
 def verify(self,**extra):
  return p.verify_evidence(self.archive,self.identity,self.run,self.history,self.arm,self.fence,self.expected,**extra)
 def test_01_reproduce_native_integer_key_false_rejection(self):
  decoded=json.loads(self.raw);declared=decoded.pop(p.SELF_FIELD)
  self.assertNotEqual(p.sha(canonical(decoded)),declared)
  _,proof=p.original_byte_self_digest(self.raw)
  self.assertEqual(proof['producer_self_digest'],declared)
 def test_02_valid_bundle_exact_byte_identity(self):
  members,_=self.verify();self.assertEqual(members[p.RAW_NAME],self.raw)
 def test_03_changed_raw_bytes_rejected(self):
  with self.assertRaises(PermissionError):p.original_byte_self_digest(self.raw.replace(b'"x"',b'"q"'))
 def test_04_altered_embedded_digest_rejected(self):
  old=self.expected['producer_self_digest'].encode()
  with self.assertRaises(PermissionError):p.original_byte_self_digest(self.raw.replace(old,b'0'*64))
 def test_05_wrong_artifact_id_rejected(self):
  self.identity['id']=18
  with self.assertRaises(PermissionError):self.verify()
 def test_06_wrong_raw_file_sha_rejected(self):
  self.expected['member_hashes'][p.RAW_NAME]='0'*64
  with self.assertRaises(PermissionError):self.verify()
 def test_07_wrong_prepared_sha_rejected(self):
  self.expected['member_hashes']['prepared.json']='0'*64
  with self.assertRaises(PermissionError):self.verify()
 def test_08_provenance_mismatch_rejected_even_with_valid_self_digest(self):
  payload=copy.deepcopy(self.payload);payload['execution_provenance']={'authority_sha256':'e'*64}
  with self.assertRaises(PermissionError):p.verify_candidate_metadata(emitted(payload),self.prepared)
 def test_09_wrong_arm_commit_rejected(self):
  self.history['arm_commit']='e'*40
  with self.assertRaises(PermissionError):self.verify()
 def test_10_wrong_fence_commit_rejected(self):
  self.history['fence_commit']='e'*40
  with self.assertRaises(PermissionError):self.verify()
 def test_11_second_identical_result_rejected(self):
  with self.assertRaises(PermissionError):self.verify(existing_result=self.raw)
 def test_12_second_different_result_rejected(self):
  with self.assertRaises(PermissionError):self.verify(existing_result=b'different')
 def test_13_nonzero_accepted_count_rejected(self):
  with self.assertRaises(PermissionError):self.verify(accepted_count=1)
 def test_14_wrong_zip_digest_rejected(self):
  self.archive+=b'changed'
  with self.assertRaises(PermissionError):self.verify()
 def test_15_wrong_run_owner_rejected(self):
  self.identity['workflow_run']['id']=14
  with self.assertRaises(PermissionError):self.verify()
 def test_16_rerun_attempt_rejected(self):
  self.run['run_attempt']=2
  with self.assertRaises(PermissionError):self.verify()
 def test_17_wrong_fence_prepared_binding_rejected(self):
  lock=json.loads(self.fence);lock['prepared_sha256']='e'*64;self.fence=canonical(lock)
  with self.assertRaises(PermissionError):self.verify()
 def test_18_wrong_arm_document_bytes_rejected(self):
  self.arm+=b' '
  with self.assertRaises(PermissionError):self.verify()
 def test_19_duplicate_self_member_rejected(self):
  raw=self.raw[:-2]+b',"raw_result_sha256_without_self_field":"'+b'0'*64+b'"}\n'
  with self.assertRaises(PermissionError):p.original_byte_self_digest(raw)
 def test_20_duplicate_nested_member_rejected(self):
  raw=emitted({'nested':{'x':1}}).replace(b'"x":1',b'"x":1,"x":1')
  with self.assertRaises(PermissionError):p.original_byte_self_digest(raw)
 def test_21_first_middle_last_and_only_self_field(self):
  for payload in ({},{'a':1},{'z':1},{'a':1,'z':2}):
   raw=emitted(payload);_,proof=p.original_byte_self_digest(raw);self.assertEqual(proof['producer_self_digest'],p.sha(canonical(payload)))
 def test_22_generic_positive_negative_zero_fixtures_same_acceptance(self):
  for value in (-999,0,999):
   raw=emitted({'synthetic':{2:value,10:-value}});_,proof=p.original_byte_self_digest(raw);self.assertEqual(proof['original_raw_sha256'],p.sha(raw))
 def test_23_no_scientific_imports(self):
  import sys
  self.verify()
  for name in ('research_core_v4.development_execution_runner_v1','research_core_v4.response_evaluator_v3','research_core_v4.numeric_worker_v1'):
   self.assertNotIn(name,sys.modules)
 def test_24_local_opening_lock_member_corruption_rejected(self):
  self.expected['member_hashes'][p.RAW_NAME+'.opening.lock']='0'*64
  with self.assertRaises(PermissionError):self.verify()
 def test_25_failure_member_corruption_rejected(self):
  self.expected['member_hashes']['failure-classification.json']='0'*64
  with self.assertRaises(PermissionError):self.verify()
 def test_26_missing_self_digest_rejected(self):
  with self.assertRaises(PermissionError):p.original_byte_self_digest(canonical({'x':1}))
 def test_28_installed_transaction_delegates_to_byte_verifier(self):
  from research_core_v4 import recovery_v4_transaction_v1 as t
  with tempfile.TemporaryDirectory() as temp:
   candidate=Path(temp)/'synthetic.json';candidate.write_bytes(self.raw)
   value=t.verify_candidate(candidate,self.prepared)
   self.assertEqual(value['execution_provenance'],self.provenance)
   self.assertNotIn(p.SELF_FIELD,value)
 def test_27_duplicate_archive_member_rejected(self):
  buffer=io.BytesIO(self.archive)
  with zipfile.ZipFile(buffer,'a') as z:z.writestr('prepared.json',self.members['prepared.json'])
  self.archive=buffer.getvalue();self.expected['artifact_zip_sha256']=p.sha(self.archive);self.identity['digest']='sha256:'+p.sha(self.archive)
  with self.assertRaises(PermissionError):self.verify()

class AtomicPublicationProof(unittest.TestCase):
 def test_atomic_successor_exact_bytes_single_count_and_ref_race(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);repo=root/'repo';remote=root/'remote.git';repo.mkdir()
   def cmd(*args):return subprocess.check_output(list(args),cwd=repo,stderr=subprocess.DEVNULL).decode().strip()
   cmd('git','init','-b','synthetic');cmd('git','config','user.name','Synthetic');cmd('git','config','user.email','synthetic@example.invalid')
   (repo/'ARM').write_bytes(b'synthetic original ARM');(repo/'FENCE').write_bytes(b'synthetic durable fence')
   cmd('git','add','.');cmd('git','commit','-m','synthetic fence');fence=cmd('git','rev-parse','HEAD')
   cmd('git','init','--bare',str(remote));cmd('git','remote','add','origin',str(remote));cmd('git','push','origin','HEAD:synthetic')
   original=emitted({'synthetic':{2:1,10:-1}});(repo/'RESULT').write_bytes(original);(repo/'STATE').write_text('{"accepted_count":1,"interpreted":false}')
   cmd('git','add','RESULT','STATE');cmd('git','commit','-m','synthetic publication only');successor=cmd('git','rev-parse','HEAD')
   self.assertEqual(cmd('git','rev-parse','HEAD^'),fence)
   self.assertEqual((repo/'ARM').read_bytes(),b'synthetic original ARM');self.assertEqual((repo/'FENCE').read_bytes(),b'synthetic durable fence')
   cmd('git','push','--force-with-lease=refs/heads/synthetic:'+fence,'origin',successor+':refs/heads/synthetic')
   self.assertEqual(cmd('git','--git-dir='+str(remote),'rev-parse','refs/heads/synthetic'),successor)
   self.assertEqual(subprocess.check_output(['git','--git-dir='+str(remote),'show','refs/heads/synthetic:RESULT'],cwd=repo),original)
   # A stale expected parent cannot publish a second successor, even an ancestor reset.
   (repo/'different').write_text('synthetic');cmd('git','add','different');cmd('git','commit','-m','synthetic forbidden second result')
   attempt=subprocess.run(['git','push','--force-with-lease=refs/heads/synthetic:'+fence,'origin','HEAD:refs/heads/synthetic'],cwd=repo,capture_output=True)
   self.assertNotEqual(attempt.returncode,0)
   self.assertEqual(cmd('git','--git-dir='+str(remote),'rev-parse','refs/heads/synthetic'),successor)
   # Reading the already-published identical commit after acknowledgement loss is idempotent.
   self.assertEqual(cmd('git','--git-dir='+str(remote),'rev-parse','refs/heads/synthetic'),successor)

if __name__=='__main__':unittest.main()
