import unittest
from collections import Counter
from types import SimpleNamespace
from research_core_v4.wide_greenfield_v1.complete_quotes_v1 import TickOnlyCompletion,correct_feature_count
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m
class CompletionTests(unittest.TestCase):
 def fixture(self):
  c=TickOnlyCompletion();c.counts=Counter(history=900,nonhistory=1781,tick=0);c.hrate=SimpleNamespace(before_send=lambda:None);self.sent=[];c.tr=SimpleNamespace(request=lambda req,timeout:self.sent.append(type(req).__name__));return c
 def test_h1_cap_does_not_consume_tick_budget(self):
  c=self.fixture();c.send(m.ProtoOAGetTickDataReq(),True);self.assertEqual(c.counts['tick'],1);self.assertEqual(self.sent,['ProtoOAGetTickDataReq']);self.assertEqual(c.counts['history'],900)
 def test_read_only_type_and_cap_fail_before_wire(self):
  c=self.fixture()
  for req in (m.ProtoOAGetTrendbarsReq(),m.ProtoOATraderReq(),m.ProtoOASymbolByIdReq()):
   with self.assertRaises(Exception):c.send(req,True)
  c.counts['tick']=10000
  with self.assertRaises(Exception):c.send(m.ProtoOAGetTickDataReq(),True)
  self.assertEqual(self.sent,[])
 def test_support_render_correction_preserves_paired_outcomes(self):
  z={'global':{'calendar':100,'feature_valid':100,'paired':54,'model_gross_mean_bps':-1.2,'abstention_reasons':{'FEATURE_GAP':31}}};correct_feature_count(z);self.assertEqual(z['global']['feature_valid'],69);self.assertEqual(z['global']['feature_valid_raw_nonnull_packed_flag'],100);self.assertEqual(z['global']['paired'],54);self.assertEqual(z['global']['model_gross_mean_bps'],-1.2)
