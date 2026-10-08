"""Offline synthetic fixtures only; no broker, tokens, historical payloads or network."""
import copy
import json
import pathlib
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from research_core_v4.telemetry_quarantine_v1 import core as c
from research_core_v4.telemetry_quarantine_v1 import adapter as a
ROOT=pathlib.Path(__file__).resolve().parents[1]
P=json.loads((ROOT/a.PARTITION_PATH).read_bytes())
START=P['not_before_ns']; END=START+P['limits']['duration_ns']
class MemoryStore:
    def __init__(self):self.records=[]
    def commit(self,r):self.records.extend(copy.deepcopy(r))
class Fixtures(unittest.TestCase):
    def setUp(self):
        # Any accidental Python network use is a test failure.
        self.net=patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN'));self.net.start();self.addCleanup(self.net.stop)
        self.mem=MemoryStore();self.p=copy.deepcopy(P);self.cap=c.Capture(self.p,START,END,self.mem)
    def pair(self,offset,cap=None):
        cap=cap or self.cap;mono=offset
        w={'source':'ATTESTED_SYNC_CLOCK_V1','offset_ns':0,'error_ns':1000,'sample_mono_ns':mono,'max_age_ns':30_000_000_000,'drift_ppm':1,'witness_sha256':'a'*64,'synchronized':True}
        return cap.clock.pair(mono,START+offset,mono,w)
    def event(self,offset=1_000_000_000,**kw):
        return dict(kind='SPOT',symbol_id=3,provider_ms=(START+offset)//1_000_000,bid=100000,ask=100020,**kw)
    def ingest(self,offset,event=None,raw=None):
        e=event or self.event(offset);return self.cap.ingest(raw or c.canonical(e),e,self.pair(offset))
    def denied(self,reason,fn):
        with self.assertRaisesRegex(c.Denied,reason):fn()
    def test_local_utc_monotonic_pair_and_event_ordering(self):
        self.ingest(1_000_000_000);r=self.cap.buffer[-1]
        self.assertLessEqual(r['provider_fields']['provider_ms']*1_000_000,r['receipt']['utc_upper_ns'])
        self.assertEqual(r['arrival_ordinal'],1);self.assertEqual(r['receipt']['utc_ns'],START+1_000_000_000)
        self.denied('EVENT_AFTER_RECEIPT_BOUND',lambda:self.ingest(2_000_000_000,self.event(3_000_000_000)))
    def test_clock_uncertainty_staleness_and_wall_step_fail_closed(self):
        w=self.pair(1_000_000_000)['witness'];w['error_ns']=50_000_001
        self.denied('CLOCK_UNCERTAINTY',lambda:c.Clock().pair(1,START,1,w|{'sample_mono_ns':1}))
        self.denied('CLOCK_STALE',lambda:c.Clock().pair(40_000_000_000,START,40_000_000_000,w))
        w['error_ns']=1000
        self.denied('WALL_CLOCK_STEP',lambda:self.cap.clock.pair(2_000_000_000,START+10_000_000_000,2_000_000_000,w|{'sample_mono_ns':2_000_000_000}))
    def test_unpaired_clock_rejected(self):
        q=self.pair(1_000_000_000);q=dict(q,utc_ns=q['utc_ns']+1)
        self.denied('UNPAIRED_CLOCK',lambda:self.cap.ingest(b'x',self.event(),q))
    def test_late_duplicate_out_of_order(self):
        e=self.event(1_000_000_000);raw=c.canonical(e)
        self.ingest(1_000_000_000,e,raw)
        f=self.ingest(4_000_000_000,e,raw)
        self.assertIn('PAYLOAD_DUPLICATE_NOT_PROVIDER_ID_PROOF',f);self.assertIn('LATE_OR_STALE',f)
        f=self.ingest(5_000_000_000,self.event(500_000_000));self.assertIn('OUT_OF_ORDER_PROVIDER_TIME',f)
    def test_missing_revision_incomplete_bars(self):
        b=dict(open_minute=START//60_000_000_000,period='M5',low=100000,deltaOpen=1,deltaHigh=20,deltaClose=2,volume=10)
        self.denied('INCOMPLETE_BAR',lambda:self.ingest(1_000_000_000,self.event(bars=[b])))
        self.cap=c.Capture(self.p,START,END,self.mem)
        self.ingest(301_000_000_000,self.event(301_000_000_000,bars=[b]))
        f=self.ingest(302_000_000_000,self.event(302_000_000_000,bars=[b|{'volume':11}]))
        self.assertIn('OBSERVED_BAR_REVISION',f)
        self.assertGreater(self.cap.finish()['counts']['EXPECTED_GRID_BARS_NOT_OBSERVED'],0)
    def test_initial_snapshot_side_age_and_spread(self):
        f=self.ingest(1_000_000_000);self.assertIn('INITIAL_SNAPSHOT_UNTRUSTED_FRESHNESS',f)
        self.assertIsNone(self.cap.buffer[-1]['quoted_spread_raw'])
        self.ingest(2_000_000_000);self.assertEqual(self.cap.buffer[-1]['quoted_spread_raw'],20)
        e=self.event(5_000_000_000);del e['ask'];self.ingest(5_000_000_000,e)
        self.assertIsNone(self.cap.buffer[-1]['quoted_spread_raw'])
        e=self.event(6_000_000_000);e['ask']=99999;self.ingest(6_000_000_000,e)
        self.assertIsNone(self.cap.buffer[-1]['quoted_spread_raw'])
    def test_historical_available_at_not_fabricated(self):
        self.denied('EVENT_OUTSIDE_SCOPE',lambda:self.ingest(1_000_000_000,self.event(-1_000_000_000)))
        self.ingest(2_000_000_000);self.assertEqual(self.cap.buffer[-1]['original_historical_available_at'],'NOT_APPLICABLE_LIVE_ONLY')
        self.assertNotIn('available_at',self.cap.buffer[-1]['provider_fields'])
    def test_exact_request_budget_and_no_orders(self):
        self.p['limits']['max_requests']=2
        for _ in range(2):self.cap.request('ProtoHeartbeatEvent')
        self.denied('REQUEST_BUDGET',lambda:self.cap.request('ProtoHeartbeatEvent'))
        for name in ['ProtoOANewOrderReq','ProtoOAGetTrendbarsReq','ProtoOAClosePositionReq']:
            self.denied('REQUEST_NOT_ALLOWED',lambda:self.cap.request(name))
    def test_message_raw_frame_and_runtime_budgets(self):
        for field,limit,reason in [('max_messages',0,'MESSAGE_BUDGET'),('max_raw_bytes',1,'RAW_BYTE_BUDGET'),('max_frame_bytes',1,'FRAME_BUDGET')]:
            self.p=copy.deepcopy(P);self.p['limits'][field]=limit;self.cap=c.Capture(self.p,START,END,self.mem)
            self.denied(reason,lambda:self.ingest(1_000_000_000))
        self.p=copy.deepcopy(P);self.cap=c.Capture(self.p,START,END,self.mem)
        self.denied('RECEIPT_OUTSIDE_SCOPE',lambda:self.ingest(P['limits']['duration_ns']))
    def test_partition_overlap_identity_and_ambiguity(self):
        self.assertTrue(c.check_partition(P,START,END,START-1))
        p=copy.deepcopy(P);p['reserved_identity_ids'].append(3)
        self.denied('RESERVED_IDENTITY',lambda:c.check_partition(p,START,END,START-1))
        for classification in ['PROTECTED','CONFIRMATION','UNKNOWN']:
            p=copy.deepcopy(P);p['assignments'].append(dict(classification=classification,identity_ids=[3],start_ns=START,end_ns=None))
            self.denied('AMBIGUOUS_ASSIGNMENT' if classification=='UNKNOWN' else 'ASSIGNMENT_OVERLAP',lambda:c.check_partition(p,START,END,START-1))
    def test_no_economic_readers_or_payload_diagnostics(self):
        p=copy.deepcopy(P);p['scientific_ingestion']=True
        self.denied('ROUTE',lambda:c.check_partition(p,START,END,START-1))
        self.ingest(1_000_000_000);s=self.cap.finish()
        self.assertFalse(s['economic_response_access']);self.assertFalse(s['payload_values_exported']);self.assertNotIn('100020',json.dumps(s))
    def test_no_broker_without_separate_arm(self):
        with tempfile.TemporaryDirectory() as td:
            factory=unittest.mock.Mock(side_effect=AssertionError('BROKER_FORBIDDEN'))
            self.denied('SEPARATE_ARM_REQUIRED',lambda:a.prepare_live(td,START-1,{},factory))
            factory.assert_not_called()
    def test_exact_terminal_stop_binding(self):
        stop=(ROOT/a.STOP_PATH).read_bytes();self.assertEqual(c.sha(stop),c.STOP_HASH)
        self.denied('SEPARATE_ARM_REQUIRED',lambda:c.arm_gate(None,{},P,stop,'head','parent',[],START-1))
        arm=dict(schema='mxm.telemetry-quarantine.arm.v1',scope_hash='',authorization_hash='',expected_source_head='',start_ns=START,end_ns=END,pilot_id='',key_sha256='',account_fingerprint_sha256='',provider_timestamp_unit='milliseconds')
        self.denied('TERMINAL_STOP_BINDING',lambda:c.arm_gate(arm,{},P,stop+b' ', 'head','parent',[],START-1))
    def test_protected_and_historical_decoder_exact_bytes_unchanged(self):
        bindings={'V2_PROTECTED_FORWARD_START.json':'605829d363c92ff74b0d5027442dd581f2944fb56336d8b6c9b8a3c74a875c1e','research_core_v4/shallow_m5_support_v2_boundary_v4.py':'7f148effd792052e367ce892781123fedc8d9083bfbad27ec9cf8065c48eef52'}
        for path,h in bindings.items():self.assertEqual(c.sha((ROOT/path).read_bytes()),h)
    def store(self,td,sealer=None):
        def default(raw,dest):c.atomic(dest,c.MAGIC+b'SYNTHETIC_FIXTURE_CIPHER')
        return c.Store(pathlib.Path(td)/c.NAMESPACE/'attempt',ROOT,'scope','pilot',sealer or default,1000000)
    def test_atomic_recovery_repeated_arm_and_corruption(self):
        with tempfile.TemporaryDirectory() as td:
            s=self.store(td);s.claim()
            self.denied('REPEATED_ARM',lambda:self.store(td).claim())
            original=c.atomic
            def crash(path,raw):
                if pathlib.Path(path).name=='checkpoint.json':raise RuntimeError('SIMULATED_CRASH_AFTER_JOURNAL')
                return original(path,raw)
            with patch.object(c,'atomic',side_effect=crash):
                with self.assertRaisesRegex(RuntimeError,'SIMULATED_CRASH'):s.commit([{'arrival_ordinal':1}])
            recovered=self.store(td);r=recovered.recover();self.assertEqual(r['last_ordinal'],1);self.assertFalse(r['network_resume_authorized'])
            self.denied('ATTEMPT_NOT_ACTIVE',lambda:recovered.commit([{'arrival_ordinal':2}]))
            c.atomic(s.root/'000001.telemetry-sealed',c.MAGIC+b'CORRUPT')
            self.denied('CIPHERTEXT_CORRUPT',lambda:self.store(td).recover())
    def test_storage_namespace_and_repo_isolation(self):
        self.denied('STORAGE_INSIDE_REPO',lambda:c.Store(ROOT/c.NAMESPACE,ROOT,'s','p',None,100))
        with tempfile.TemporaryDirectory() as td:
            self.denied('STORAGE_NAMESPACE',lambda:c.Store(td,ROOT,'s','p',None,100))
    def test_real_reused_encryption_synthetic_key_and_old_reader_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            key=pathlib.Path(td)/'fixture-private.pem';pub=pathlib.Path(td)/'fixture-public.pem'
            subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(key)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(['openssl','pkey','-in',str(key),'-pubout','-out',str(pub)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            seal=c.Sealer(ROOT/'research_core_v4/shallow_m5_support_v2_production.py',pub,c.sha(pub.read_bytes()))
            dest=pathlib.Path(td)/'test.sealed';seal(b'SYNTHETIC_NO_MARKET_DATA',dest);raw=dest.read_bytes()
            with self.assertRaises(Exception):seal.crypto['_unpackage_cipher'](raw)
            self.assertEqual(seal.crypto['decrypt_synthetic_package'](raw[len(c.MAGIC):],private_key=key),b'SYNTHETIC_NO_MARKET_DATA')
    def test_adapter_receipt_sampling_before_decode_offline(self):
        raw=c.canonical(self.event());chunks=[len(raw).to_bytes(4,'big'),raw];log=[]
        class Transport:
            no_network_fixture=True
            def _recv_exact(_,n,deadline):log.append('read');return chunks.pop(0)
        def decode(r):log.append('decode');return json.loads(r)
        pair=self.pair(1_000_000_000);w=pair['witness'];self.cap.clock=c.Clock()
        ad=a.OfflineFixtureAdapter(Transport(),self.cap,decode,lambda:w,lambda:START+1_000_000_000,lambda:1_000_000_000)
        ad.receive(0);self.assertEqual(log,['read','read','decode']);self.assertEqual(self.cap.ordinal,1)
        self.denied('SCOPE_VIEW_ONLY',lambda:ad.mark_account_scope(1,'a','a'))
if __name__=='__main__':unittest.main(verbosity=2)
