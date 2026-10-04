"""Precision, evidence adoption and real entry-point pre-network regressions."""
import json,math,tempfile,unittest,zipfile,copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import nullcontext
from tests.test_v4_exact_decoder_recovery import ExactRecoveryTests,seed_recovery_fixture,ROOT
from tests.test_v4_quote_support_probe import PLAN,SmallMetadata
from tests.test_v4_android_current_metadata import FakeOAuth,FAKE_AID
from tests.test_v4_signed_tick_decoder_fix import encode
from research_core_v4.quote_probe_transport_v1 import *
from research_core_v4.pydroid_quote_probe_v1 import PLAN_SHA
from m6.ctrader_proto import OpenApiMessages_pb2 as oa
class DevicePrecisionTests(unittest.TestCase):
 setUp=ExactRecoveryTests.setUp
 put=ExactRecoveryTests.put
 gate=ExactRecoveryTests.gate
 transport=ExactRecoveryTests.transport
 def test_nonrounded_exact_bytes_value_charged_and_forward(self):
  value=5.563847219;self.put(self.w/'active_seconds.json',{'active_seconds':value});raw=(self.w/'active_seconds.json').read_bytes()
  state=self.gate();self.assertEqual(state['original_active_seconds_charged'],value)
  self.assertEqual(state['original_file_sha256']['active_seconds.json'],sha(raw));self.assertEqual((self.w/'ORIGINAL_DECODER_STOP_EVIDENCE/active_seconds.json').read_bytes(),raw)
  self.put(self.w/'active_seconds.json',{'active_seconds':value+1.123456789});self.assertEqual(self.gate()['original_active_seconds_charged'],value)
 def test_other_positive_precise_value_accepted(self):
  self.put(self.w/'active_seconds.json',{'active_seconds':7.123456789123});self.assertEqual(self.gate()['original_active_seconds_charged'],7.123456789123)
 def test_valid_duration_below_display_is_accepted(self):
  self.put(self.w/'active_seconds.json',{'active_seconds':5.559999999});self.assertEqual(self.gate()['original_active_seconds_charged'],5.559999999)
 def test_invalid_numeric_domain_fails(self):
  for value in [-1,0,float('nan'),float('inf'),-float('inf'),'5.56',None,True,7200.000001]:
   with self.subTest(value=value):
    if type(value) is float and not math.isfinite(value):(self.w/'active_seconds.json').write_text(json.dumps({'active_seconds':value,'checkpoint_sha256':'0'*64}))
    else:self.put(self.w/'active_seconds.json',{'active_seconds':value})
    with self.assertRaises(PermissionError):self.gate()
    self.assertFalse((self.w/'decoder_recovery_binding.json').exists());self.assertFalse((self.w/'ORIGINAL_DECODER_STOP_EVIDENCE').exists())
 def test_active_seal_tamper_fails(self):
  self.put(self.w/'active_seconds.json',{'active_seconds':5.563847219});p=self.w/'active_seconds.json';body=json.loads(p.read_bytes());body['active_seconds']=7.0;p.write_bytes(canonical(body))
  with self.assertRaises(PermissionError):self.gate()
 def test_dynamic_original_floor_cannot_be_reset(self):
  self.put(self.w/'active_seconds.json',{'active_seconds':7.123456789});self.gate();self.put(self.w/'active_seconds.json',{'active_seconds':7.123456788})
  with self.assertRaises(PermissionError):self.gate()
 def test_binding_charge_must_match_original_exact_number(self):
  self.put(self.w/'active_seconds.json',{'active_seconds':5.563847219});state=self.gate();state['original_active_seconds_charged']=5.56;self.put(self.w/'decoder_recovery_binding.json',state)
  with self.assertRaises(PermissionError):self.gate()
 def test_immutable_archive_not_readopted_if_binding_missing(self):
  self.gate();(self.w/'decoder_recovery_binding.json').unlink();self.put(self.w/'active_seconds.json',{'active_seconds':7.1234})
  with self.assertRaises(PermissionError):self.gate()
 def test_interrupted_archive_staging_reused_only_byte_exact(self):
  staging=self.w/'ORIGINAL_DECODER_STOP_EVIDENCE.staging';staging.mkdir();raw=(self.w/'active_seconds.json').read_bytes();(staging/'active_seconds.json').write_bytes(raw)
  self.gate();self.assertFalse(staging.exists());self.assertEqual((self.w/'ORIGINAL_DECODER_STOP_EVIDENCE/active_seconds.json').read_bytes(),raw)
 def test_changed_staged_bytes_fail_closed(self):
  staging=self.w/'ORIGINAL_DECODER_STOP_EVIDENCE.staging';staging.mkdir();(staging/'active_seconds.json').write_bytes(b'changed')
  with self.assertRaises(PermissionError):self.gate()
 def test_valid_resealed_schedule_change_after_binding_rejected(self):
  self.gate();p=self.w/'current_schedule_preflight.json';body=unseal(json.loads(p.read_bytes()));body['fresh_calendar_metadata_sha256']='changed';self.put(p,body)
  with self.assertRaises(PermissionError):self.gate()
 def test_original_outcome_prefix_change_rejected(self):
  self.gate();p=self.w/'wire_outcomes.jsonl';body=unseal(json.loads(p.read_bytes()));body['latency_seconds']=2.0;p.write_bytes(canonical(seal(body))+b'\n')
  with self.assertRaises(PermissionError):self.gate()
 def test_private_registry_bytes_bound(self):
  self.gate();p=self.private/('v4_probe_'+PLAN_SHA+'.json');p.write_bytes(p.read_bytes()+b'\n')
  with self.assertRaises(PermissionError):self.gate()
 def test_binding_seal_tamper_rejected(self):
  state=self.gate();state['replacement_consumed']=True;p=self.w/'decoder_recovery_binding.json';body=json.loads(p.read_bytes());body['replacement_consumed']=True;p.write_bytes(canonical(body))
  with self.assertRaises(PermissionError):self.gate()
 def test_replacement_node_tamper_rejected_before_network(self):
  tr=self.transport(self.gate());tr.capture(self.slot);node=self.w/'nodes'/RECOVERY_ID/f"{self.slot['from_ms']}_{self.slot['to_ms']}.json.gz";node.write_bytes(b'changed')
  with self.assertRaises(PermissionError):self.gate()
 def test_storage_cap_before_network(self):
  original=Path.stat
  def stat(p,*args,**kw):
   result=original(p,*args,**kw)
   return SimpleNamespace(st_size=2000000001,st_mode=result.st_mode) if p.name=='padding' else result
  (self.w/'padding').write_bytes(b'fictional')
  with patch.object(Path,'stat',stat):
   with self.assertRaises(PermissionError):self.gate()
 def test_wire_cap_before_network(self):
  p=self.w/'wire_attempts.jsonl';p.write_bytes(p.read_bytes()*11201)
  with self.assertRaises(PermissionError):self.gate()

class PrenetworkEntryPointTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from tools.build_v4_quote_probe_package import build
  cls.tmp=tempfile.TemporaryDirectory();cls.archive=Path(cls.tmp.name)/'package.zip';build(ROOT,cls.archive,ROOT.parent/'probe-wheels')
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_all_failing_gate_predicates_keep_oauth_and_transport_at_zero(self):
  mutations=['negative','zero','nan','infinite','text','boolean','above_cap','active_seal','stop','attempt_scope','outcome_shape','outcome_duplicate','schedule','raw','completed','nodes','registry','later_stop','binding','partial_archive','registry_folder','schedule_counts','retry_index','attempt_index','outcome_more','wire_cap','storage_cap','active_reserve','consumed_fence','bound_schedule','bound_outcome']
  from research_core_v4.pydroid_quote_probe_v1 import run_device
  for case in mutations:
   with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
    base=Path(d)
    with zipfile.ZipFile(self.archive) as z:z.extractall(base)
    root=base/'MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1';private=base/'private';w=seed_recovery_fixture(root,private)
    def put(n,v):atomic(w/n,canonical(seal(v)))
    values={'negative':-1,'zero':0,'nan':float('nan'),'infinite':float('inf'),'text':'5.56','boolean':True,'above_cap':7200.01}
    if case in ['nan','infinite']:(w/'active_seconds.json').write_text(json.dumps({'active_seconds':values[case],'checkpoint_sha256':'0'*64}))
    elif case in values:put('active_seconds.json',{'active_seconds':values[case]})
    elif case=='active_seal':(w/'active_seconds.json').write_bytes(b'{"active_seconds":5.563847219}')
    elif case=='stop':put('terminal_transport_stop.json',{'status':'OTHER'})
    elif case=='attempt_scope':
     p=w/'wire_attempts.jsonl';q=unseal(json.loads(p.read_bytes()));q['from_ms']+=1;p.write_bytes(canonical(seal(q))+b'\n')
    elif case=='outcome_shape':
     p=w/'wire_outcomes.jsonl';q=unseal(json.loads(p.read_bytes()));q['returned_ticks']=65;p.write_bytes(canonical(seal(q))+b'\n')
    elif case=='outcome_duplicate':
     p=w/'wire_outcomes.jsonl';p.write_bytes(p.read_bytes()*2)
    elif case=='schedule':put('current_schedule_preflight.json',{'status':'MISMATCH'})
    elif case in ['raw','completed','nodes']:
     p=w/case/'fictional';p.parent.mkdir();p.write_bytes(b'fictional')
    elif case=='registry':(private/('v4_probe_'+PLAN_SHA+'.json')).unlink()
    elif case=='later_stop':put('terminal_recovery_stop.json',{'status':'STOP'})
    elif case=='registry_folder':
     p=private/('v4_probe_'+PLAN_SHA+'.json');q=unseal(json.loads(p.read_bytes()));q['folder_sha256']='other';atomic(p,canonical(seal(q)))
    elif case=='schedule_counts':
     q=unseal(json.loads((w/'current_schedule_preflight.json').read_bytes()));q['identity_week_windows_checked']=559;put('current_schedule_preflight.json',q)
    elif case in ['retry_index','attempt_index']:
     p=w/'wire_attempts.jsonl';q=unseal(json.loads(p.read_bytes()));q[case]=1;p.write_bytes(canonical(seal(q))+b'\n')
    elif case=='outcome_more':
     p=w/'wire_outcomes.jsonl';q=unseal(json.loads(p.read_bytes()));q['has_more']=True;p.write_bytes(canonical(seal(q))+b'\n')
    elif case=='wire_cap':
     p=w/'wire_attempts.jsonl';p.write_bytes(p.read_bytes()*11201)
    elif case=='storage_cap':(w/'padding').write_bytes(b'fictional')
    elif case=='active_reserve':put('active_seconds.json',{'active_seconds':7200})
    elif case=='consumed_fence':
     state=recovery_gate(root,w,private,PLAN);state['replacement_consumed']=True;put('decoder_recovery_binding.json',state)
    elif case=='bound_schedule':
     recovery_gate(root,w,private,PLAN);q=unseal(json.loads((w/'current_schedule_preflight.json').read_bytes()));q['fresh_calendar_metadata_sha256']='unbound';put('current_schedule_preflight.json',q)
    elif case=='bound_outcome':
     recovery_gate(root,w,private,PLAN);p=w/'wire_outcomes.jsonl';q=unseal(json.loads(p.read_bytes()));q['latency_seconds']=2;p.write_bytes(canonical(seal(q))+b'\n')
    elif case=='binding':put('decoder_recovery_binding.json',{'replacement_consumed':False})
    elif case=='partial_archive':
     p=w/'ORIGINAL_DECODER_STOP_EVIDENCE.staging'/'active_seconds.json';p.parent.mkdir();p.write_bytes(b'changed')
    oauth=FakeOAuth();factory_calls=[]
    def factory():factory_calls.append(1);raise AssertionError('transport reached')
    before=(w/'wire_attempts.jsonl').read_bytes();active_before=(w/'active_seconds.json').read_bytes()
    original_stat=Path.stat
    def stat(path,*args,**kw):
     result=original_stat(path,*args,**kw)
     return SimpleNamespace(st_size=2000000001,st_mode=result.st_mode) if path.name=='padding' else result
    with patch.object(Path,'stat',stat) if case=='storage_cap' else nullcontext():
     with self.assertRaises((PermissionError,FileNotFoundError)):run_device(root,oauth=oauth,transport_factory=factory,private_registry_root=private,progress=lambda _:None)
    self.assertEqual(oauth.ensure_calls,0);self.assertEqual(factory_calls,[]);self.assertEqual((w/'wire_attempts.jsonl').read_bytes(),before);self.assertEqual((w/'active_seconds.json').read_bytes(),active_before)
 def test_exact_precise_state_reaches_one_replacement_boundary_and_keeps_accounting(self):
  from research_core_v4 import pydroid_quote_probe_v1 as module
  from research_core_v4.pydroid_quote_probe_v1 import logical_capture
  for value in [5.563847219,7.123456789123]:
   with self.subTest(value=value),tempfile.TemporaryDirectory() as d:
    base=Path(d)
    with zipfile.ZipFile(self.archive) as z:z.extractall(base)
    root=base/'MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1';private=base/'private';w=seed_recovery_fixture(root,private)
    atomic(w/'active_seconds.json',canonical(seal({'active_seconds':value})));original=(w/'active_seconds.json').read_bytes();calls=[]
    def request(msg):
     calls.append(msg);res=oa.ProtoOAGetTickDataRes(ctidTraderAccountId=FAKE_AID,hasMore=False)
     for x in encode([[PLAN['slots'][0]['from_ms']+i,100000+i%3] for i in range(66)]):res.tickData.add(timestamp=x.timestamp,tick=x.tick)
     return res
    broker=SimpleNamespace(request=request)
    def metadata(inner,*args,**kw):return SimpleNamespace(_inner=inner,scope_view_verified=True,account_auth_verified=True,close=lambda:None)
    def capture(tr,slot,work):
     logical_capture(tr,slot,work);raise KeyboardInterrupt()
    report=unseal(json.loads((w/'current_schedule_preflight.json').read_bytes()))
    with patch.object(module,'authenticate',return_value=FAKE_AID),patch.object(module,'preflight',return_value=report),patch.object(module,'MetadataTransport',side_effect=metadata),patch.object(module,'logical_capture',side_effect=capture),patch.object(module.time,'monotonic',return_value=100.0):
     with self.assertRaises(KeyboardInterrupt):module.run_device(root,oauth=FakeOAuth(),transport_factory=lambda:broker,private_registry_root=private,progress=lambda _:None)
    self.assertEqual(len(calls),1);self.assertEqual(len((w/'wire_attempts.jsonl').read_bytes().splitlines()),2)
    self.assertEqual((w/'ORIGINAL_DECODER_STOP_EVIDENCE/active_seconds.json').read_bytes(),original)
    self.assertEqual(unseal(json.loads((w/'active_seconds.json').read_bytes()))['active_seconds'],value)
    state=recovery_gate(root,w,private,PLAN);self.assertEqual(state['original_active_seconds_charged'],value);self.assertTrue(state['replacement_consumed'])
