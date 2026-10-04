"""Fictional signed-delta wire events only. No market data, network or retry grant."""
import copy,random,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from research_core_v4.quote_probe_transport_v1 import decode_ticks,ProbeTransport
from tests.test_v4_quote_support_probe import TickBroker,PLAN,SmallMetadata,Clock
from tests.test_v4_android_current_metadata import FAKE_AID
from m6.ctrader_proto import OpenApiMessages_pb2 as oa

def encode(rows):
    reverse=list(reversed(rows));out=[];previous=None
    for t,p in reverse:
        out.append(SimpleNamespace(timestamp=t if previous is None else t-previous[0],tick=p if previous is None else p-previous[1]))
        previous=(t,p)
    return out

class SignedWireDecoderTests(unittest.TestCase):
 def test_negative_zero_and_positive_price_deltas(self):
  original=[[1000,20],[1001,22],[1002,22],[1003,21]]
  self.assertEqual(decode_ticks(encode(original),1000,1003),original)
 def test_multiple_same_ms_revisions_not_sorted_by_price_or_deduplicated(self):
  rows=[[1000,20],[1000,22],[1000,22],[1000,19],[1001,21]]
  self.assertEqual(decode_ticks(encode(rows),1000,1001),rows)
 def test_random_roundtrip_independent_encoder(self):
  rng=random.Random(20261004)
  for _ in range(100):
   t,p=1000,100000;rows=[]
   for _ in range(100):
    t+=rng.randrange(3);p+=rng.randrange(-5,6);rows.append([t,p])
   self.assertEqual(decode_ticks(encode(rows),1000,t),rows)
 def test_positive_subsequent_time_delta_rejected(self):
  with self.assertRaises(PermissionError):decode_ticks([SimpleNamespace(timestamp=1000,tick=20),SimpleNamespace(timestamp=1,tick=0)],999,1001)
 def test_reconstructed_nonpositive_price_rejected(self):
  for dp in [-20,-21]:
   with self.assertRaises(PermissionError):decode_ticks([SimpleNamespace(timestamp=1000,tick=20),SimpleNamespace(timestamp=-1,tick=dp)],999,1000)
 def test_reconstructed_outside_range_rejected(self):
  with self.assertRaises(PermissionError):decode_ticks([SimpleNamespace(timestamp=1000,tick=20),SimpleNamespace(timestamp=-2,tick=0)],999,1000)
 def test_parity_existing_signed_decoder(self):
  from m6.cost_evidence import decode_ctrader_tick_page
  rows=[[1000,20],[1000,22],[1001,21],[1003,25]];wire=encode(rows)
  prior=decode_ctrader_tick_page([{'timestamp':x.timestamp,'tick':x.tick} for x in wire])
  self.assertEqual(decode_ticks(wire,1000,1003),[[x.timestamp_ms,x.raw_tick] for x in prior])
 def test_fictional_66_tick_page_and_terminal_stop_preserved(self):
  slot=copy.deepcopy(PLAN['slots'][0]);slot.update(from_ms=1000,to_ms=1065)
  rows=[[1000+i,100000+(i%3)] for i in range(66)]
  broker=TickBroker();calls=[]
  def request(msg):
   calls.append(type(msg).__name__);res=oa.ProtoOAGetTickDataRes(ctidTraderAccountId=FAKE_AID,hasMore=False)
   for x in encode(rows):res.tickData.add(timestamp=x.timestamp,tick=x.tick)
   return res
  broker.request=request
  with tempfile.TemporaryDirectory() as d:
   clock=Clock();tr=ProbeTransport(SmallMetadata(broker),[slot],FAKE_AID,d,clock=clock,sleep=clock.sleep)
   self.assertEqual(tr.capture(slot)[0],rows);self.assertEqual(len(calls),1)
   self.assertEqual(tr.capture_cached(slot)[0],rows);self.assertEqual(len(calls),1)
   from research_core_v4.quote_probe_transport_v1 import atomic,seal
   from research_core_v4.quote_probe_plan_v1 import canonical
   terminal=Path(d)/'terminal_transport_stop.json';atomic(terminal,canonical(seal({'status':'STOP','automatic_retry_authorized':False})));before=terminal.read_bytes()
   with self.assertRaises(PermissionError):ProbeTransport(SmallMetadata(broker),[slot],FAKE_AID,d,clock=clock,sleep=clock.sleep)
   self.assertEqual(terminal.read_bytes(),before);self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
