"""Exact recovery control and fictional wire regression. No broker data."""
import copy,json,tempfile,unittest
from pathlib import Path
from research_core_v4.quote_probe_transport_v1 import *
from research_core_v4.pydroid_quote_probe_v1 import PLAN_SHA
from tests.test_v4_quote_support_probe import PLAN,SmallMetadata,TickBroker,Clock
from tests.test_v4_android_current_metadata import FAKE_AID
from tests.test_v4_signed_tick_decoder_fix import encode
from m6.ctrader_proto import OpenApiMessages_pb2 as oa
ROOT=Path(__file__).resolve().parents[1]
def seed_recovery_fixture(root,private):
 root=Path(root);private=Path(private);private.mkdir(parents=True,exist_ok=True);w=root/'DEVICE_LOCAL_PROBE_RAW'/PLAN_SHA;w.mkdir(parents=True,exist_ok=True)
 def put(p,v):atomic(p,canonical(seal(v)))
 slot=PLAN['slots'][0]
 put(private/('v4_probe_'+PLAN_SHA+'.json'),{'plan_sha256':PLAN_SHA,'folder_sha256':sha(str(root.resolve()).encode()),'logical_execution_count':1})
 put(w/'terminal_transport_stop.json',{'status':'TRANSPORT_ARCHITECTURE_NOT_FEASIBLE_AS_CURRENTLY_CONFIGURED','request_id':RECOVERY_ID,'automatic_retry_authorized':False})
 trace={'attempt_index':0,'request_id':RECOVERY_ID,'from_ms':slot['from_ms'],'to_ms':slot['to_ms'],'depth':0,'retry_index':0,'status':'SENT_OR_ACK_UNKNOWN'}
 (w/'wire_attempts.jsonl').write_bytes(canonical(seal(trace))+b'\n')
 (w/'wire_outcomes.jsonl').write_bytes(canonical(seal(dict(trace,status='RECEIVED',returned_ticks=66,has_more=False,latency_seconds=0.1)))+b'\n')
 put(w/'current_schedule_preflight.json',{'status':'EXACT_FROZEN_WINDOWS_MATCH','mismatches':[],'identities_checked':56,'base_slot_count':1120,'identity_week_windows_checked':560})
 put(w/'active_seconds.json',{'active_seconds':5.56})
 return w
class ExactRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)/'same';self.root.mkdir();self.w=self.root/'checkpoint';self.w.mkdir();self.private=Path(self.tmp.name)/'private';self.private.mkdir()
  for rel in [RECOVERY_REL,'research_core_v4/state/NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json']:
   p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
  self.slot=copy.deepcopy(PLAN['slots'][0]);self.a=json.loads((ROOT/RECOVERY_REL).read_bytes())
  self.put(self.private/('v4_probe_'+PLAN_SHA+'.json'),{'plan_sha256':PLAN_SHA,'folder_sha256':sha(str(self.root.resolve()).encode()),'logical_execution_count':1})
  self.put(self.w/'terminal_transport_stop.json',{'status':'TRANSPORT_ARCHITECTURE_NOT_FEASIBLE_AS_CURRENTLY_CONFIGURED','request_id':RECOVERY_ID,'automatic_retry_authorized':False})
  self.trace={'attempt_index':0,'request_id':RECOVERY_ID,'from_ms':self.slot['from_ms'],'to_ms':self.slot['to_ms'],'depth':0,'retry_index':0,'status':'SENT_OR_ACK_UNKNOWN'}
  (self.w/'wire_attempts.jsonl').write_bytes(canonical(seal(self.trace))+b'\n')
  out=dict(self.trace,status='RECEIVED',returned_ticks=66,has_more=False,latency_seconds=0.1)
  (self.w/'wire_outcomes.jsonl').write_bytes(canonical(seal(out))+b'\n')
  self.put(self.w/'current_schedule_preflight.json',{'status':'EXACT_FROZEN_WINDOWS_MATCH','mismatches':[],'identities_checked':56,'base_slot_count':1120,'identity_week_windows_checked':560})
  self.put(self.w/'active_seconds.json',{'active_seconds':5.56});self.calls=[]
 def put(self,p,v):atomic(p,canonical(seal(v)))
 def gate(self):return recovery_gate(self.root,self.w,self.private,PLAN)
 def transport(self,state,count=66,more=False,fail=False):
  broker=TickBroker()
  def req(msg):
   self.calls.append(msg.SerializeToString(deterministic=True))
   if fail:raise TimeoutError()
   res=oa.ProtoOAGetTickDataRes(ctidTraderAccountId=FAKE_AID,hasMore=more)
   rows=[[self.slot['from_ms']+i,100000+i%3] for i in range(count)]
   for x in encode(rows):res.tickData.add(timestamp=x.timestamp,tick=x.tick)
   return res
  broker.request=req;clock=Clock()
  return ProbeTransport(SmallMetadata(broker),PLAN['slots'],FAKE_AID,self.w,clock=clock,sleep=clock.sleep,recovery=state)
 def test_exact_once_preserves_stop_and_journal_then_cached_resume(self):
  stop=(self.w/'terminal_transport_stop.json').read_bytes();state=self.gate();tr=self.transport(state)
  rows,_=tr.capture(self.slot);self.assertEqual(len(rows),66);self.assertEqual(len(tr.attempts),2);self.assertEqual(len(self.calls),1)
  self.assertEqual((self.w/'terminal_transport_stop.json').read_bytes(),stop)
  self.assertEqual((self.w/'ORIGINAL_DECODER_STOP_EVIDENCE/active_seconds.json').read_bytes(),canonical(seal({'active_seconds':5.56})))
  self.put(self.w/'active_seconds.json',{'active_seconds':9.0});tr2=self.transport(self.gate());self.assertEqual(tr2.capture(self.slot)[0],rows);self.assertEqual(len(self.calls),1)
 def test_missing_or_other_folder_registry_before_network(self):
  path=self.private/('v4_probe_'+PLAN_SHA+'.json');path.unlink()
  with self.assertRaises(FileNotFoundError):self.gate()
  self.assertEqual(self.calls,[])
 def test_original_stop_tamper_before_network(self):
  self.put(self.w/'terminal_transport_stop.json',{'status':'OTHER'})
  with self.assertRaises(PermissionError):self.gate()
 def test_extra_attempt_before_network(self):
  p=self.w/'wire_attempts.jsonl';p.write_bytes(p.read_bytes()+canonical(seal(dict(self.trace,attempt_index=1)))+b'\n')
  with self.assertRaises(PermissionError):self.gate()
 def test_original_shape_mismatch(self):
  self.put(self.w/'wire_outcomes.jsonl',dict(self.trace,status='RECEIVED',returned_ticks=65,has_more=False))
  with self.assertRaises(PermissionError):self.gate()
 def test_persisted_raw_or_node_or_completed_rejects(self):
  for name in ['raw','nodes','completed']:
   p=self.w/name/'unexpected';p.parent.mkdir(exist_ok=True);p.write_bytes(b'fictional')
   with self.assertRaises(PermissionError):self.gate()
   p.unlink()
 def test_consumed_crash_fence_never_reissues(self):
  state=self.gate();state['replacement_consumed']=True;self.put(self.w/'decoder_recovery_binding.json',state)
  with self.assertRaises(PermissionError):self.gate()
 def test_transport_failure_single_attempt_and_later_stop(self):
  state=self.gate();tr=self.transport(state,fail=True);stop=(self.w/'terminal_transport_stop.json').read_bytes()
  with self.assertRaises(PermissionError):tr.capture(self.slot)
  self.assertEqual(len(self.calls),1);self.assertEqual(len(tr.attempts),2);self.assertEqual((self.w/'terminal_transport_stop.json').read_bytes(),stop)
  with self.assertRaises(PermissionError):self.gate()
 def test_tick_count_change_fails_without_node(self):
  tr=self.transport(self.gate(),count=65)
  with self.assertRaises(PermissionError):tr.capture(self.slot)
  self.assertFalse((self.w/'nodes').exists())
 def test_hasmore_change_fails_without_node(self):
  tr=self.transport(self.gate(),more=True)
  with self.assertRaises(PermissionError):tr.capture(self.slot)
  self.assertFalse((self.w/'nodes').exists())
 def test_second_replacement_same_process_rejected(self):
  tr=self.transport(self.gate());tr.capture(self.slot)
  node=self.w/'nodes'/RECOVERY_ID/f"{self.slot['from_ms']}_{self.slot['to_ms']}.json.gz";node.unlink()
  with self.assertRaises(PermissionError):tr.capture(self.slot)
  self.assertEqual(len(self.calls),1)
 def test_wrong_same_folder_registry(self):
  self.put(self.private/('v4_probe_'+PLAN_SHA+'.json'),{'plan_sha256':PLAN_SHA,'folder_sha256':'another','logical_execution_count':1})
  with self.assertRaises(PermissionError):self.gate()
 def test_calendar_mismatch_before_network(self):
  self.put(self.w/'current_schedule_preflight.json',{'status':'MISMATCH'})
  with self.assertRaises(PermissionError):self.gate()
 def test_original_time_mismatch_before_network(self):
  self.put(self.w/'active_seconds.json',{'active_seconds':0})
  with self.assertRaises(PermissionError):self.gate()
 def test_control_journal_prefix_tamper(self):
  self.gate();self.put(self.w/'wire_attempts.jsonl',dict(self.trace,from_ms=0))
  with self.assertRaises(PermissionError):self.gate()
 def test_symlink_checkpoint_rejected(self):
  (self.w/'link').symlink_to(self.private)
  with self.assertRaises(PermissionError):self.gate()
 def test_later_stop_blocks_even_valid_cached_recovery(self):
  tr=self.transport(self.gate());tr.capture(self.slot);self.put(self.w/'terminal_recovery_stop.json',{'status':'STOP'})
  with self.assertRaises(PermissionError):self.gate()
 def test_immutable_original_copy_tamper(self):
  self.gate();(self.w/'ORIGINAL_DECODER_STOP_EVIDENCE/active_seconds.json').write_bytes(b'altered')
  with self.assertRaises(PermissionError):self.gate()
 def test_pending_resume_keeps_time_charge(self):
  self.gate();self.put(self.w/'active_seconds.json',{'active_seconds':10.0});state=self.gate()
  self.assertEqual(state['original_active_seconds_charged'],5.56)
