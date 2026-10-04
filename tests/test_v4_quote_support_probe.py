"""Offline proof; all protocol traffic uses fictional in-memory broker messages."""
import base64,copy,gzip,json,math,os,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from research_core_v4.quote_probe_plan_v1 import build,rank,roster,materialize,day_intervals,canonical,sha,STATE
from research_core_v4.quote_probe_support_v1 import completion_mask,count_support
from research_core_v4.quote_probe_transport_v1 import ProbeTransport,decode_ticks,atomic
from research_core_v4.pydroid_quote_probe_v1 import verify,logical_capture,run_device,PLAN_SHA,RETURN_NAME,Heartbeat
from research_core_v4.quote_metadata_android_v1 import MetadataTransport,Secrets
from tools.audit_v4_quote_support_geometry import run as audit
from tools.build_v4_quote_probe_package import build as package
from m6.ctrader_proto import OpenApiMessages_pb2 as oa
from tests.test_v4_android_current_metadata import FakeOAuth,FakeTransport,FAKE_AID,PRIVATE_SECRET,PRIVATE_CODE
ROOT=Path(__file__).resolve().parents[1]
PLAN=build(ROOT)
class Clock:
 def __init__(self):self.value=0;self.delays=[]
 def __call__(self):return self.value
 def sleep(self,n):self.delays.append(n);self.value+=n
class TickBroker(FakeTransport):
 def __init__(self,mode='EMPTY'):
  super().__init__();self.mode=mode;self.tick_calls=[];self.once=False
 def request(self,msg):
  if type(msg) is oa.ProtoOAGetTickDataReq:
   self.tick_calls.append((int(msg.fromTimestamp),int(msg.toTimestamp)));lo,hi=self.tick_calls[-1]
   if self.mode=='TIMEOUT_ONCE' and not self.once:self.once=True;raise TimeoutError('fiction-secret-DO-NOT-LOG')
   if self.mode=='TIMEOUT':raise TimeoutError('private auth URL must never leave exception')
   if self.mode=='UNAVAILABLE':return oa.ProtoOAErrorRes(errorCode='SYMBOL_NOT_FOUND',description=PRIVATE_SECRET)
   r=oa.ProtoOAGetTickDataRes(ctidTraderAccountId=FAKE_AID,hasMore=self.mode in ['SPLIT','SATURATED'] and hi-lo>=1)
   if self.mode=='SATURATED':r.hasMore=True
   if self.mode!='EMPTY':r.tickData.add(timestamp=hi,tick=100000)
   return r
  return super().request(msg)
class SmallMetadata:
 def __init__(self,broker):self._inner=broker;self.scope_view_verified=True;self.account_auth_verified=True
 def _restore(self):self._inner.connect()
class ProbeProof(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.archive=Path(cls.temp.name)/'input.zip'
  package(ROOT,cls.archive,ROOT.parent/'probe-wheels')
  with zipfile.ZipFile(cls.archive) as z:z.extractall(cls.temp.name)
  cls.deploy=Path(cls.temp.name)/'MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1'
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def tr(self,broker,slot=None,work=None):
  slot=copy.deepcopy(slot or PLAN['slots'][0]);clock=Clock();tmp=tempfile.TemporaryDirectory() if work is None else None
  if tmp:self.addCleanup(tmp.cleanup)
  tr=ProbeTransport(SmallMetadata(broker),[slot],FAKE_AID,work or Path(tmp.name),clock=clock,sleep=clock.sleep)
  return tr,slot,clock
 def test_exact_roster_seed_and_classes(self):
  self.assertEqual(len(PLAN['identities']),56);self.assertEqual(len({x['asset_class'] for x in PLAN['identities']}),29)
  self.assertEqual(sum(x['transport_only_singleton'] for x in PLAN['identities']),2)
  self.assertEqual(len(PLAN['slots']),1120);self.assertEqual(PLAN['base_request_count'],1120)
  self.assertEqual(sha((ROOT/(STATE+'NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json')).read_bytes()),PLAN_SHA)
 def test_roster_invariant_to_input_order(self):
  import zlib
  d=json.loads(zlib.decompress(base64.b64decode((ROOT/(STATE+'NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_LOCALIZATION_V1.json.zlib.b64')).read_bytes())))
  self.assertEqual(roster(d['rows']),roster(list(reversed(d['rows']))))
 def test_every_slot_frozen_calendar_and_padding(self):
  self.assertEqual(PLAN['week_indices'],[0,6,12,18,24,30,36,42,48,51])
  for s in PLAN['slots']:
   self.assertEqual(s['signal_to_ms']-s['signal_from_ms'],3600000);self.assertEqual(s['from_ms'],s['signal_from_ms']-120000);self.assertEqual(s['to_ms'],s['signal_to_ms']+105000-1)
 def test_metadata_holiday_empty_and_no_replacement(self):
  f={'scheduleTimeZone':'UTC','schedule':[],'holiday':[]}
  self.assertEqual(materialize(f,'2025-09-15',0)['status'],'NO_WINDOW')
  f['schedule']=[{'startSecond':86400,'endSecond':172800}];f['holiday']=[{'holidayDate':20346,'startSecond':0,'endSecond':0}]
  self.assertEqual(materialize(f,'2025-09-15',0)['status'],'NO_WINDOW')
 def test_weekday_cycle_and_dst(self):
  f={'scheduleTimeZone':'America/New_York','schedule':[{'startSecond':86400,'endSecond':518400}],'holiday':[]}
  a=materialize(f,'2025-10-27',0);b=materialize(f,'2025-11-03',0)
  self.assertEqual(b['signal_from_ms']-a['signal_from_ms'],(7*86400+3600)*1000)
 def test_contract_and_all_source_hashes(self):
  manifest,p=verify(self.deploy);self.assertEqual(p,PLAN)
  self.assertTrue(all(sha((self.deploy/n).read_bytes())==h for n,h in manifest['file_sha256'].items()))
 def test_plan_tamper_denied_before_oauth(self):
  p=self.deploy/(STATE+'NEXT_QUOTE_SEQUENCE_SUPPORT_TRANSPORT_PROBE_PLAN_V1.json');raw=p.read_bytes()
  try:
   p.write_bytes(raw+b' ')
   with self.assertRaises(PermissionError):verify(self.deploy)
  finally:p.write_bytes(raw)
 def test_no_old_collector_or_evaluator_in_source_zip(self):
  with zipfile.ZipFile(self.archive) as z:
   self.assertFalse(any('research_core_v3/' in n or 'evaluator' in n or 'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT' in n for n in z.namelist()))
 def test_forbidden_order_trendbar_spots_envelope_and_payload_override(self):
  broker=TickBroker();tr,s,c=self.tr(broker);tr.active=s['request_id'];tr._authorized_ranges={(s['from_ms'],s['to_ms'])}
  from m6.ctrader_proto import OpenApiCommonMessages_pb2 as common
  for cls in [oa.ProtoOANewOrderReq,oa.ProtoOACancelOrderReq,oa.ProtoOAGetTrendbarsReq,oa.ProtoOASubscribeSpotsReq,common.ProtoMessage]:
   with self.assertRaises(PermissionError):tr.request(cls(),0)
  msg=oa.ProtoOAGetTickDataReq(ctidTraderAccountId=FAKE_AID,symbolId=s['symbol_id'],type=1,fromTimestamp=s['from_ms'],toTimestamp=s['to_ms'],payloadType=int(oa.ProtoOAApplicationAuthReq().payloadType))
  with self.assertRaises(PermissionError):tr.request(msg,0)
  self.assertFalse(broker.tick_calls)
 def test_wrong_identity_side_account_range_and_unbound_split(self):
  broker=TickBroker();tr,s,c=self.tr(broker);tr.active=s['request_id'];tr._authorized_ranges={(s['from_ms'],s['to_ms'])}
  kw=dict(ctidTraderAccountId=FAKE_AID,symbolId=s['symbol_id'],type=1,fromTimestamp=s['from_ms'],toTimestamp=s['to_ms'])
  for k,v in [('ctidTraderAccountId',7),('symbolId',9999),('type',2),('fromTimestamp',s['from_ms']-1),('toTimestamp',s['to_ms']-1)]:
   wrong={**kw,k:v}
   with self.assertRaises(PermissionError):tr.request(oa.ProtoOAGetTickDataReq(**wrong),0)
  self.assertFalse(broker.tick_calls)
 def test_account_gate_before_historical(self):
  with tempfile.TemporaryDirectory() as d:
   meta=SmallMetadata(TickBroker());meta.scope_view_verified=False
   with self.assertRaises(PermissionError):ProbeTransport(meta,PLAN['slots'],FAKE_AID,d)
 def test_lossless_delta_and_same_millisecond_order(self):
  a=SimpleNamespace(timestamp=1000,tick=3);b=SimpleNamespace(timestamp=0,tick=-1);c=SimpleNamespace(timestamp=-5,tick=-1)
  self.assertEqual(decode_ticks([a,b,c],995,1000),[[995,1],[1000,2],[1000,3]])
  with self.assertRaises(PermissionError):decode_ticks([a,SimpleNamespace(timestamp=1,tick=2)],0,1000)
 def test_has_more_disjoint_checkpoint_resume_no_redownload(self):
  s=copy.deepcopy(PLAN['slots'][0]);s['from_ms']=1000;s['to_ms']=1003
  broker=TickBroker('SPLIT');tr,s,c=self.tr(broker,s)
  rows,trace=tr.capture(s);self.assertEqual(rows,[[1000,100000],[1001,100000],[1002,100000],[1003,100000]])
  calls=len(broker.tick_calls);self.assertEqual(tr.capture(s)[0],rows);self.assertEqual(len(broker.tick_calls),calls)
 def test_saturated_one_millisecond_fail_closed(self):
  s=copy.deepcopy(PLAN['slots'][0]);s['from_ms']=s['to_ms']=1000
  tr,s,c=self.tr(TickBroker('SATURATED'),s)
  with self.assertRaises(PermissionError):tr.capture(s)
 def test_rate_retry_reauth_and_metrics(self):
  tr,s,c=self.tr(TickBroker('TIMEOUT_ONCE'));rows,trace=tr.capture(s)
  self.assertEqual(len(tr.attempts),2);self.assertEqual(tr.attempts[0]['status'],'TRANSPORT_FAILURE_OR_ACK_LOSS');self.assertEqual(tr.attempts[1]['retry_index'],1)
  self.assertGreaterEqual(sum(c.delays),1)
 def test_symbol_error_is_transport_failure_not_support_absence(self):
  tr,s,c=self.tr(TickBroker('UNAVAILABLE'))
  with self.assertRaises(PermissionError):tr.capture(s)
  self.assertEqual(tr.attempts[0]['status'],'BROKER_ERROR_FAIL_CLOSED');self.assertNotIn(PRIVATE_SECRET,str(tr.attempts))
 def test_hard_wire_budget(self):
  tr,s,c=self.tr(TickBroker());tr.attempts=[{}]*11200
  with self.assertRaises(PermissionError):tr.capture(s)
 def test_malformed_response_type_or_account_fail_closed(self):
  for response in [oa.ProtoOAAccountAuthRes(ctidTraderAccountId=FAKE_AID),oa.ProtoOAGetTickDataRes(ctidTraderAccountId=7,hasMore=False)]:
   broker=TickBroker();broker.request=lambda _:response;tr,s,c=self.tr(broker)
   with self.assertRaises(PermissionError):tr.capture(s)
 def test_atomic_completion_replay_and_orphan_recovery(self):
  tr,s,c=self.tr(TickBroker());d=tr.workdir
  r=logical_capture(tr,s,d);n=len(tr.meta._inner.tick_calls)
  self.assertEqual(logical_capture(tr,s,d),r);self.assertEqual(len(tr.meta._inner.tick_calls),n)
  (d/'completed'/f"{s['request_id']}.json").unlink();self.assertEqual(logical_capture(tr,s,d),r);self.assertEqual(len(tr.meta._inner.tick_calls),n)
 def test_completed_checksum_corruption_rejected(self):
  tr,s,c=self.tr(TickBroker());r=logical_capture(tr,s,tr.workdir);(tr.workdir/r['raw_path']).write_bytes(b'changed')
  with self.assertRaises(PermissionError):logical_capture(tr,s,tr.workdir)
 def test_timestamp_mask_has_no_price_input_and_right_censor(self):
  self.assertTrue(completion_mask([1000,11000],[1000,11000],0,10));self.assertFalse(completion_mask([1000,11000],[1000],0,10))
 def test_empty_support_has_all24_cells_no_values(self):
  d=count_support([],[],100000,3700000);self.assertEqual(len(d['cells']),24);self.assertTrue(all(c['nonoverlap_attempts']==0 for c in d['cells']));self.assertFalse(d['response_values_read'])
 def test_causal_features_unchanged_by_future_padding_prices(self):
  start=120000;end=start+3600000
  bid=[[t,100000+(t//1000)%3] for t in range(0,end+106000,1000)];ask=[[t,100010+(t//1000)%3] for t in range(0,end+106000,1000)]
  changed=[[t,p if t<end else 200000] for t,p in ask]
  self.assertEqual(count_support(bid,ask,start,end),count_support(bid,changed,start,end))
 def test_same_ms_does_not_censor_later_baseline(self):
  bid=[[t,100000] for t in range(0,3720000,1000)];bid.insert(120, [119000,100001]);ask=[[t,100010] for t in range(0,3720000,1000)]
  d=count_support(bid,ask,120000,3720000);self.assertEqual(d['ambiguous_causal_seconds'],0);self.assertGreater(d['baseline_qualified_seconds'],0)
 def test_method_retained_population_target_not_support_selection(self):
  a=audit(ROOT);self.assertFalse(a['prospective_supersession']);self.assertTrue(a['exhaustive_synthetic_sign_symmetry_with_fixed_support_mask']['pass'])
  self.assertEqual(set(a['singleton_contexts']),{'Energies (Spot)','Forwards - Commodities'})
  self.assertLess(0.99**743,0.001)
 def test_heartbeat_true_progress_eta(self):
  clock=Clock();messages=[];h=Heartbeat(1120,100,messages.append,clock);clock.value=20;h.done=110;h.show();self.assertIn('110/1120',messages[0]);self.assertIn('ETA',messages[0])
 def test_full1120_fictional_roundtrip_and_replay_zip_sanitization(self):
  from research_core_v4 import pydroid_quote_probe_v1 as module
  broker=TickBroker();clock=Clock();oauth=FakeOAuth()
  # All selected current identities are returned; no real endpoint is touched.
  original=broker.request
  def request(msg):
   if type(msg) is oa.ProtoOASymbolsListReq:
    res=oa.ProtoOASymbolsListRes(ctidTraderAccountId=FAKE_AID)
    for i in PLAN['identities']:res.symbol.add(symbolId=i['symbol_id'],symbolName=i['symbol'],enabled=True)
    return res
   if type(msg) is oa.ProtoOASymbolByIdReq:
    import zlib
    from google.protobuf.json_format import ParseDict
    d=json.loads(zlib.decompress(base64.b64decode((ROOT/(STATE+'NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_LOCALIZATION_V1.json.zlib.b64')).read_bytes())))
    full=next(x['current_full_metadata'] for x in d['rows'] if x['symbol_id']==msg.symbolId[0]);full=copy.deepcopy(full)
    for h in full.get('holiday',[]):h['scheduleTimeZone']=full['scheduleTimeZone'] # explicitly fictional broker fixture
    out=oa.ProtoOASymbolByIdRes(ctidTraderAccountId=FAKE_AID);ParseDict(full,out.symbol.add());return out
   if type(msg) is oa.ProtoOAGetTickDataReq and int(msg.fromTimestamp)==PLAN['slots'][0]['from_ms'] and int(msg.toTimestamp)==PLAN['slots'][0]['to_ms'] and int(msg.symbolId)==PLAN['slots'][0]['symbol_id'] and int(msg.type)==1:
    broker.tick_calls.append((int(msg.fromTimestamp),int(msg.toTimestamp)))
    out=oa.ProtoOAGetTickDataRes(ctidTraderAccountId=FAKE_AID,hasMore=False)
    from tests.test_v4_signed_tick_decoder_fix import encode
    for x in encode([[int(msg.fromTimestamp)+i,100000+i%3] for i in range(66)]):out.tickData.add(timestamp=x.timestamp,tick=x.tick)
    return out
   return original(msg)
  broker.request=request
  from tests.test_v4_exact_decoder_recovery import seed_recovery_fixture
  seed_recovery_fixture(self.deploy,self.deploy.parent/'private-registry')
  mt=lambda inner,o,secrets,progress:MetadataTransport(inner,o,secrets,progress=progress,clock=clock,sleep=clock.sleep)
  pt=lambda meta,slots,aid,d,**kw:ProbeTransport(meta,slots,aid,d,clock=clock,sleep=clock.sleep,**kw)
  with patch('m6.ctrader_capture.account_fingerprint',return_value=module.__dict__.get('FINGERPRINT','b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636')),patch('os.fsync',return_value=None),patch.object(module,'MetadataTransport',side_effect=mt),patch.object(module,'ProbeTransport',side_effect=pt):
   output=run_device(self.deploy,oauth=oauth,transport_factory=lambda:broker,progress=lambda _:None,private_registry_root=self.deploy.parent/'private-registry')
   self.assertEqual(len(broker.tick_calls),1120)
   output2=run_device(self.deploy,oauth=oauth,transport_factory=lambda:broker,progress=lambda _:None,private_registry_root=self.deploy.parent/'private-registry');self.assertEqual(len(broker.tick_calls),1120)
  with zipfile.ZipFile(output2) as z:
   m=json.loads(z.read('PROBE_EXECUTION_MANIFEST.json'));self.assertEqual(m['historical_wire_attempts_including_retry'],1121);self.assertGreaterEqual(m['elapsed_active_seconds_all_resumes'],5.56);self.assertEqual(m['base_requests_completed'],1120);self.assertFalse(m['response_values_computed']);self.assertFalse(m['full_capture_started'])
   matrix=json.loads(z.read('SUPPORT_ONLY_MATRIX.json'));self.assertEqual(len(matrix),560);self.assertTrue(all(len(x['support']['cells'])==24 for x in matrix))
   for line in z.read('CHECKSUMS.sha256').decode().splitlines():h,n=line.split('  ');self.assertEqual(sha(z.read(n)),h)
   for name in z.namelist():
    raw=z.read(name);raw=gzip.decompress(raw) if name.endswith('.gz') else raw
    self.assertNotIn(PRIVATE_SECRET.encode(),raw);self.assertNotIn(str(FAKE_AID).encode(),raw);self.assertNotIn(PRIVATE_CODE.encode(),raw)
   self.assertFalse(any(n.startswith('RAW_AUDIT') or n.endswith('.gz') for n in z.namelist()));self.assertFalse(m['raw_quote_prices_exported'])
 def test_interrupted_split_resumes_cached_root_and_left(self):
  s=copy.deepcopy(PLAN['slots'][0]);s['from_ms']=1000;s['to_ms']=1003
  broker=TickBroker('SPLIT');old=broker.request;failing=[True]
  def request(msg):
   if type(msg) is oa.ProtoOAGetTickDataReq and msg.fromTimestamp>=1002 and failing[0]:raise TimeoutError('fiction private value')
   return old(msg)
  broker.request=request;tr,s,c=self.tr(broker,s)
  with self.assertRaises(RuntimeError):tr.capture(s)
  original_calls=list(broker.tick_calls);failing[0]=False
  rows,trace=tr.capture(s);self.assertEqual(len(rows),4)
  self.assertTrue(all(lo>=1002 for lo,hi in broker.tick_calls[len(original_calls):]))
 def test_completed_metric_tamper_rejected(self):
  tr,s,c=self.tr(TickBroker());r=logical_capture(tr,s,tr.workdir)
  path=tr.workdir/'completed'/f"{s['request_id']}.json";r['compressed_bytes']+=1;path.write_bytes(canonical(r))
  with self.assertRaises(PermissionError):logical_capture(tr,s,tr.workdir)
 def test_nonempty_feature_thresholds_and_direction_geometry_same(self):
  bid=[];ask=[]
  for t in range(60000,3826000,1000):
   p=100000+max(0,min(6,t//1000-122)) if 123000<=t<=128000 else 100000
   bid.append([t,p]);ask.append([t,p+20 if t<129000 else p+10])
  r=count_support(bid,ask,120000,3720000);cells=r['cells'];self.assertGreater(cells[0]['nonoverlap_attempts'],0)
  for a,b in zip(cells[::2],cells[1::2]):
   self.assertEqual(a['timestamp_completable_mask_hex'],b['timestamp_completable_mask_hex']);self.assertEqual(a['nonoverlap_attempts'],b['nonoverlap_attempts'])
 def test_historical_rate_spacing_for_separate_pages(self):
  s=copy.deepcopy(PLAN['slots'][0]);s['from_ms']=1000;s['to_ms']=1001
  tr,s,c=self.tr(TickBroker('SPLIT'),s);tr.capture(s)
  self.assertTrue(all(d>=0.219999 for d in c.delays));self.assertEqual(len(tr.attempts),3)
 def test_pure_python_android_deployment_preflight_no_network(self):
  code="import sys,socket;from pathlib import Path;r=Path(sys.argv[1]);sys.path[:0]=[str(r/'vendor'),str(r)];socket.create_connection=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network prohibited'));import zoneinfo;zoneinfo.reset_tzpath([]);from research_core_v4.pydroid_quote_probe_v1 import verify;from research_core_v4.quote_metadata_android_v1 import verify_runtime;verify(r);verify_runtime(r);print('OK')"
  r=subprocess.run([os.sys.executable,'-I','-c',code,str(self.deploy)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
if __name__=='__main__':unittest.main()
