from .test_v2 import CausalExitTests,ExistingCoverageTests
import unittest
from unittest.mock import patch
from .collector_v3 import TickReceiptTransport,Collector
from research_core_v4.native_executable_qualification_v1.runner_v1 import HistoryReceiptTransport
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m
class NativeCaptureTests(unittest.TestCase):
 def test_tick_response_envelope_retained_without_authentication_mutation(self):
  class Envelope:payloadType=m.ProtoOAGetTickDataRes().payloadType
  envelope=Envelope();obj=object.__new__(TickReceiptTransport)
  with patch.object(HistoryReceiptTransport,'receive_envelope',return_value=envelope):self.assertIs(obj.receive_envelope(deadline=1),envelope)
  self.assertIs(obj.last_history_envelope,envelope)
 def test_remaining_budget_never_expands(self):
  c=Collector();self.assertEqual(c.caps['BID_ASK'],1199);self.assertEqual(c.caps['M5'],0);self.assertEqual(c.caps['H1'],0);c.counts['BID_ASK']=1198;self.assertEqual(c.quote_ms(1,1000)['sides']['bid']['state'],'LOCAL_BID_ASK_CAP');self.assertEqual(c.counts['BID_ASK'],1198)
if __name__=='__main__':unittest.main()
