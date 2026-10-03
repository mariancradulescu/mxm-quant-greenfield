"""Production V4 mechanics, synthetic RSA/OpenPGP inputs, real disposable Git refs.
Only the scientific-core call is replaced by a declared synthetic known answer.
No accepted broker bytes or real response evaluation enter these fixtures.
"""
import hashlib,io,json,os,shutil,subprocess,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from research_core_v4 import asymmetric_recovery_v4_gate as g
from research_core_v4 import recovery_v4_transaction_v1 as t
from research_core_v4 import development_execution_runner_v1 as runner
SOURCE=g.ROOT

def cmd(cwd,*args):return subprocess.check_output(list(args),cwd=cwd,stderr=subprocess.DEVNULL).decode().strip()
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(root,rel,x):
 p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,sort_keys=True)+'\n')
def init(root):
 root.mkdir(exist_ok=True);cmd(root,'git','init','-b',g.BRANCH);cmd(root,'git','config','user.name','Synthetic proof');cmd(root,'git','config','user.email','synthetic@example.invalid')
def commit(root,msg):cmd(root,'git','add','.');cmd(root,'git','commit','-m',msg);return cmd(root,'git','rev-parse','HEAD')
class ActualPathTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.keytemp=tempfile.TemporaryDirectory();d=Path(cls.keytemp.name)
  subprocess.check_call(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:4096','-out',str(d/'key')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  subprocess.check_call(['openssl','pkey','-in',str(d/'key'),'-pubout','-out',str(d/'pub')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cls.key=(d/'key').read_text();cls.pub=(d/'pub').read_bytes()
 @classmethod
 def tearDownClass(cls):cls.keytemp.cleanup()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.crypto=self.base/'gnupg';self.crypto.mkdir(mode=0o700);self.root=self.base/'repo';init(self.root)
  self.science=self.base/'science';init(self.science)
  for _,(rel,_) in g.FROZEN.items():
   for root in [self.root,self.science]:p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SOURCE/rel,p)
  self.scihead=commit(self.science,'exact frozen code synthetic repository')
  extra=['research_core_v4/state/EXACT_SUPPORT_GEOMETRY_CALIBRATION_FULL_V3.json',g.SUPERSESSION_REL,g.WORKFLOW_REL]+g.arm_binding_files()[4:]
  for rel in extra:
   p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SOURCE/rel,p)
  pp=self.root/g.PUBLIC_REL;pp.parent.mkdir(parents=True,exist_ok=True);pp.write_bytes(self.pub)
  der=subprocess.check_output(['openssl','pkey','-pubin','-in',str(pp),'-outform','DER']);self.spki=hashlib.sha256(der).hexdigest()
  put(self.root,g.PROBE_REL,dict(conclusion='PASS',private_key_parse_status='VALID',fingerprint_status='MATCH',private_derived_public_spki_sha256=self.spki,run_id=1))
  self.series=[];tar=self.base/'data.tar'
  with tarfile.open(tar,'w',format=tarfile.USTAR_FORMAT) as tf:
   for i in range(1,19):
    b=b'time_utc,open,high,low,close\n2025-01-01T00:00:00Z,1,1,1,1\n2025-01-01T00:05:00Z,1,1,1,1\n'
    info=tarfile.TarInfo(f'{i}_M5.csv');info.size=len(b);tf.addfile(info,io.BytesIO(b))
    self.series.append(dict(symbol=f'S{i}',symbol_id=i,series_sha256=hashlib.sha256(b).hexdigest(),row_count=2,first_timestamp_utc='2025-01-01T00:00:00Z',last_timestamp_utc='2025-01-01T00:05:00Z'))
  (self.base/'pass').write_text('synthetic-only-passphrase')
  subprocess.check_call(['gpg','--batch','--yes','--pinentry-mode','loopback','--passphrase-file',str(self.base/'pass'),'--cipher-algo','AES256','--output',str(self.base/'cipher'),'--symmetric',str(tar)],env={**os.environ,'GNUPGHOME':str(self.crypto)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cipher=(self.base/'cipher').read_bytes();self.parts=[];stride=len(cipher)//5
  for i in range(5):
   b=cipher[i*stride:(i+1)*stride] if i<4 else cipher[i*stride:];rel=f'research_core_v4/runtime_inputs/synthetic-cipher-{i}'
   p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);self.parts.append((rel,len(b),h(p)))
  wrap=self.root/g.WRAPPED_REL
  subprocess.check_call(['openssl','pkeyutl','-encrypt','-pubin','-inkey',str(pp),'-in',str(self.base/'pass'),'-out',str(wrap),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  payload=self.root/g.PAYLOAD_REL;payload.write_bytes(b'synthetic encrypted fixture envelope')
  manifest=dict(schema='mxm.research-core-v4.exact-m5-input-manifest.v2',canonical_repository=g.REPO,research_branch=g.BRANCH,scientific_source_head=self.scihead,public_key_spki_sha256=self.spki,plaintext_bundle_sha256=h(tar),encrypted_bundle_sha256=h(self.base/'cipher'),exact_series_count=18,exact_18_series=self.series,market_outcome_inspected=False,plaintext_persisted=False,private_key_persisted=False,raw_bundle_passphrase_persisted=False,key_wrap=dict(algorithm='RSA_OAEP',hash='SHA256',mgf1_hash='SHA256'),wrapped_bundle_key=dict(filename=g.WRAPPED_REL,sha256=h(wrap),size_bytes=512),encrypted_parts=[dict(filename=rel,size_bytes=size,sha256=sha) for rel,size,sha in self.parts])
  put(self.root,g.MANIFEST_REL,manifest)
  cert=dict(schema='mxm.research-core-v4.recovery-v4-greenfield-input-staging-certificate.v1',status='STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED',canonical_repository=g.REPO,research_branch=g.BRANCH,scientific_source_head=self.scihead,transport_payload_file=g.PAYLOAD_REL,transport_payload_sha256=h(payload),rsa_public_key_spki_sha256=self.spki,rsa_oaep_parameters=dict(algorithm='RSA_OAEP',hash='SHA256',mgf1_hash='SHA256'),wrapped_bundle_key=manifest['wrapped_bundle_key'],plaintext_bundle_sha256=h(tar),encrypted_bundle_sha256=h(self.base/'cipher'),exact_18_series=self.series,accepted_canonical_result_count=0,arm_present_at_staging=False,attempt_lock_present_at_staging=False,real_execution_authorized_at_staging=False,installed_recovery_workflow_sha256=h(self.root/g.WORKFLOW_REL),asymmetric_transport_supersession_sha256=h(self.root/g.SUPERSESSION_REL))
  put(self.root,g.CERT_REL,cert)
  authority=dict(status='ACTIVE_TRANSPORT_ONLY_SUCCESSOR_STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED',frozen_reference=dict(exact_18_series=self.series),staging_certificate_sha256=h(self.root/g.CERT_REL),logical_computation_id='synthetic-only-logical-id')
  for rel in [g.V3_AUTH_REL,g.V4_PROSPECTIVE_REL,g.V4_ACTIVE_REL]:put(self.root,rel,authority)
  put(self.root,g.ACTIVATION_REL,dict(status='ACTIVATED_TRANSPORT_ONLY_AFTER_REAL_PREARM_PREFLIGHT_PASS',active_recovery_authority_sha256=h(self.root/g.V4_ACTIVE_REL)))
  put(self.root,g.PREFLIGHT_REL,dict(conclusion='PASS',fingerprint_status='MATCH',exact_plaintext_series_count=18))
  state=dict(status='FIRST_REAL_MARKET_DESIGN_V2_ASYMMETRIC_RECOVERY_V4_STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED',first_wave={},recovery_v4_preparation=dict(status='STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED',accepted_canonical_result_count=0,arm_present=False,attempt_lock_present=False,real_execution_authorized=False),execution_path_audit=dict(status='READY_FOR_SEPARATE_ARM_GOVERNANCE_DECISION'))
  put(self.root,g.STATE_REL,state)
  put(self.root,runner.AUTHORITY_REL,dict(status='AUTHORIZED_READY_NOT_EXECUTED'))
  self.parent=commit(self.root,'synthetic staged and certified parent')
  self.remote=self.base/'remote.git';cmd(self.base,'git','init','--bare',str(self.remote));cmd(self.root,'git','remote','add','origin',str(self.remote));cmd(self.root,'git','push','origin','HEAD:'+g.BRANCH)
  patches={'ROOT':self.root,'SCI_HEAD':self.scihead,'EXPECTED_SPKI':self.spki,'EXPECTED_MANIFEST_SHA':h(self.root/g.MANIFEST_REL),'EXPECTED_PLAINTEXT_BUNDLE_SHA':h(tar),'EXPECTED_ENCRYPTED_BUNDLE_SHA':h(self.base/'cipher'),'EXPECTED_WRAPPED_SHA':h(wrap),'EXPECTED_PAYLOAD_SHA':h(payload),'PARTS':self.parts}
  self.addCleanup(patch.stopall)
  for k,v in patches.items():patch.object(g,k,v).start()
  patch.object(t,'ROOT',self.root).start()
  self.environ=patch.dict(os.environ,{'GNUPGHOME':str(self.crypto),'GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'synthetic-1','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':self.key},clear=False);self.environ.start()
  self.arm=g.build_arm_document(self.parent,dict(explicit_separate_arm_authorization=True,decision_id='synthetic-only',certified_parent_head=self.parent))
  put(self.root,g.ARM_REL,self.arm);self.armhead=commit(self.root,'synthetic isolated ARM');cmd(self.root,'git','push','origin','HEAD:'+g.BRANCH);os.environ['GITHUB_SHA']=self.armhead
  self.raw=self.base/'raw';self.out=self.base/'out';self.out.mkdir();self.wheels=self.base/'wheels';self.wheels.mkdir()
  self.pre=self.base/'prelock.json'
 def decrypt(self):
  report=g.validate_arm_and_runtime(self.root/g.ARM_REL,self.raw);self.pre.write_text(json.dumps(report));return report
 def worker(self,science,raw,temp,wheels,mode):
  prepared=dict(schema='mxm.v4.prevalidated-frozen-runner.v1',environment=dict(status='PASS_SYNTHETIC_NUMERIC'),provenance=dict(frozen_runner_sha256=g.FROZEN['runner'][1],fixture='SYNTHETIC_NO_MARKET'),response_opened=False)
  if mode=='--prepare':(temp/'prepared.json').write_text(json.dumps(prepared));return
  bundle=runner.PrevalidatedBundle(dict(status='AUTHORIZED_READY_NOT_EXECUTED'),dict(status='SYNTHETIC_AUTHORIZED_NOT_EXECUTED'),{},{},{},(),{}, {},prepared['provenance'])
  with patch.object(runner,'ROOT',self.root),patch.object(runner,'RESPONSE_OPENING_STARTED',False),patch.object(runner.ev,'_evaluate_prevalidated_development_core',return_value={'schema':'mxm.research-core-v4.development-response-result.v2','fixture':'SYNTHETIC_KNOWN_ANSWER'}):
   runner.execute_once(bundle,temp/'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json')
 def transaction(self):
  with patch.object(t,'invoke_worker',side_effect=self.worker):return t.run_transaction(self.science,self.raw,self.out,self.wheels,self.pre)
 def test_constructible_arm_and_real_synthetic_crypto_prelock(self):
  r=self.decrypt();self.assertEqual(r['exact_plaintext_series_count'],18);self.assertTrue(r['all_18_sha256_match']);self.assertNotIn('arm_commit',self.arm)
 def test_success_atomic_result_and_replay_denied(self):
  self.decrypt();r=self.transaction();self.assertEqual(r['status'],'RAW_CANONICAL_RESULT_DURABLE_NOT_INTERPRETED')
  self.assertEqual(t.remote_head(),r['commit']);self.assertEqual(json.loads((self.root/g.STATE_REL).read_text())['recovery_v4_preparation']['accepted_canonical_result_count'],1)
  with self.assertRaises((PermissionError,AssertionError)):self.transaction()
 def test_wrong_event_head(self):
  os.environ['GITHUB_SHA']=self.parent
  with self.assertRaises(PermissionError):self.decrypt()
 def test_rerun_rejected_before_decrypt(self):
  os.environ['GITHUB_RUN_ATTEMPT']='2'
  with self.assertRaises(PermissionError):self.decrypt()
 def test_binding_corruption(self):
  self.arm['bound_files_sha256'][g.WORKFLOW_REL]='0'*64;put(self.root,g.ARM_REL,self.arm)
  with self.assertRaises(PermissionError):self.decrypt()
 def test_ancestor_remote_reset_denied(self):
  cmd(self.base,'git','--git-dir='+str(self.remote),'update-ref','refs/heads/'+g.BRANCH,self.parent)
  with self.assertRaises(PermissionError):self.decrypt()
 def test_preprepare_failure_has_no_fence(self):
  self.decrypt()
  with patch.object(t,'invoke_worker',side_effect=RuntimeError('synthetic prevalidation failure')):
   with self.assertRaises(RuntimeError):t.run_transaction(self.science,self.raw,self.out,self.wheels,self.pre)
  self.assertFalse((self.root/g.LOCK_REL).exists());self.assertEqual(t.remote_head(),self.armhead)
  self.assertEqual(json.loads((self.out/t.FAILURE).read_text())['classification'],'PRE_RESPONSE_INFRASTRUCTURE_FAILURE_NOT_A_SCIENTIFIC_RESULT')
 def test_after_fence_before_worker_is_unknown_not_a_null(self):
  self.decrypt();calls=[]
  def worker(*args):
   calls.append(args[-1])
   if args[-1]=='--execute':raise RuntimeError('synthetic crash before worker')
   self.worker(*args)
  with patch.object(t,'invoke_worker',side_effect=worker):
   with self.assertRaises(RuntimeError):t.run_transaction(self.science,self.raw,self.out,self.wheels,self.pre)
  self.assertTrue((self.root/g.LOCK_REL).exists());self.assertFalse((self.root/g.RESULT_REL).exists())
  self.assertEqual(json.loads((self.out/t.FAILURE).read_text())['classification'],'OPENING_FENCE_DURABLE_RESPONSE_OPENING_UNKNOWN_NO_AUTOMATIC_RETRY')
 def test_result_push_failure_preserves_raw_for_publication_only(self):
  self.decrypt();real=t.publish;calls=[]
  def pub(expected,head):
   calls.append(head)
   if len(calls)==2:raise RuntimeError('synthetic publication outage')
   return real(expected,head)
  with patch.object(t,'publish',side_effect=pub):
   with self.assertRaises(RuntimeError):self.transaction()
  self.assertEqual(json.loads((self.out/t.FAILURE).read_text())['classification'],'RAW_RESULT_RECOVERABLE_PUBLICATION_ONLY_NO_RECOMPUTATION')
  self.assertTrue((self.out/'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json').exists())
  self.assertEqual(real(calls[0],calls[1]),calls[1]) # same commit, never reevaluate
  self.assertEqual(real(calls[0],calls[1]),calls[1]) # acknowledgment-loss/replay publication idempotency
 def test_prepublication_race_even_ancestor_reset(self):
  self.decrypt();real=t.publish
  def pub(expected,head):
   cmd(self.base,'git','--git-dir='+str(self.remote),'update-ref','refs/heads/'+g.BRANCH,self.parent)
   return real(expected,head)
  with patch.object(t,'publish',side_effect=pub):
   with self.assertRaises(PermissionError):self.transaction()
  self.assertFalse((self.out/'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json').exists())
 def test_nonisolated_arm_commit(self):
  (self.root/'extra').write_text('synthetic drift');os.environ['GITHUB_SHA']=commit(self.root,'unexpected extra file');cmd(self.root,'git','push','origin','HEAD:'+g.BRANCH)
  with self.assertRaises(PermissionError):self.decrypt()
 def test_corrupt_ciphertext_rejected(self):
  p=self.root/self.parts[0][0];p.write_bytes(b'corrupt')
  with self.assertRaises(PermissionError):self.decrypt()
 def test_crash_classification_total_state_table(self):
  self.assertEqual(t.classify(False,False),'PRE_RESPONSE_INFRASTRUCTURE_FAILURE_NOT_A_SCIENTIFIC_RESULT')
  self.assertIn('UNKNOWN',t.classify(True,False))
  self.assertIn('STARTED',t.classify(True,False,True))
  self.assertIn('PUBLICATION_ONLY',t.classify(True,False,True,True))
  self.assertIn('DURABLE',t.classify(True,True))

 def test_complete_result_recovery_without_second_worker(self):
  self.decrypt();real=t.publish;calls=[]
  def pub(expected,head):
   calls.append(head)
   if len(calls)==2:raise RuntimeError('synthetic lost result publication')
   return real(expected,head)
  with patch.object(t,'publish',side_effect=pub):
   with self.assertRaises(RuntimeError):self.transaction()
  cmd(self.root,'git','reset','--hard',calls[0])
  candidate=self.out/'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json'
  decision=dict(publication_only_authorized=True,fence_commit=calls[0],result_sha256=h(candidate),decision_id='synthetic-publication-only')
  with patch.object(t,'invoke_worker',side_effect=AssertionError('recovery must never invoke worker')):
   report=t.recover_completed_result(candidate,self.out/'prepared.json',calls[0],decision)
   self.assertEqual(t.remote_head(),report['commit'])
   again=t.recover_completed_result(candidate,self.out/'prepared.json',calls[0],decision)
   self.assertEqual(again['status'],'IDENTICAL_CANONICAL_RESULT_ALREADY_DURABLE')
 def test_corrupted_recovered_prepared_attestation_denied(self):
  self.decrypt();self.transaction()
  candidate=self.out/'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json';fence=json.loads((self.root/t.PUBLICATION).read_text())['fence_commit']
  (self.out/'prepared.json').write_text('{}')
  with self.assertRaises(AssertionError):t.recover_completed_result(candidate,self.out/'prepared.json',fence,dict(publication_only_authorized=True,fence_commit=fence,result_sha256=h(candidate),decision_id='synthetic'))
 def test_worker_partial_opening_failure_never_reexecutes(self):
  self.decrypt()
  def worker(*args):
   if args[-1]=='--prepare':return self.worker(*args)
   (self.out/'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json.opening.lock').write_text('synthetic opened')
   (self.out/'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json.tmp').write_text('partial')
   raise RuntimeError('synthetic interrupted core')
  with patch.object(t,'invoke_worker',side_effect=worker):
   with self.assertRaises(RuntimeError):t.run_transaction(self.science,self.raw,self.out,self.wheels,self.pre)
  self.assertIn('STARTED_OUTCOME_UNKNOWN',json.loads((self.out/t.FAILURE).read_text())['classification'])
  with self.assertRaises(PermissionError):self.transaction()
 def test_push_acknowledgement_loss_is_idempotent(self):
  (self.root/'synthetic-marker').write_text('no market');head=commit(self.root,'synthetic publication only')
  real=subprocess.run;pushes=[]
  def wrapped(args,*a,**kw):
   r=real(args,*a,**kw)
   if isinstance(args,list) and 'push' in args:
    pushes.append(args);r.returncode=1
   return r
  with patch.object(subprocess,'run',side_effect=wrapped):self.assertEqual(t.publish(self.armhead,head),head)
  self.assertEqual(len(pushes),1);self.assertEqual(t.publish(self.armhead,head),head)
 def test_ref_race_after_fetch_before_push_rejects_ancestor_reset(self):
  (self.root/'synthetic-marker').write_text('no market');head=commit(self.root,'synthetic publication only')
  real=subprocess.run
  def wrapped(args,*a,**kw):
   if isinstance(args,list) and 'push' in args:
    real(['git','--git-dir='+str(self.remote),'update-ref','refs/heads/'+g.BRANCH,self.parent],check=True)
   return real(args,*a,**kw)
  with patch.object(subprocess,'run',side_effect=wrapped):
   with self.assertRaises(PermissionError):t.publish(self.armhead,head)
  self.assertEqual(t.remote_head(),self.parent)
