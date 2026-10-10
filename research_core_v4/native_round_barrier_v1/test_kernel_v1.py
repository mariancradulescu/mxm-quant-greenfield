import unittest
from .kernel_v1 import feature
class SoftwareTests(unittest.TestCase):
 def test_native_decimal_levels_not_return_direction(self):
  self.assertEqual(feature(1.1008,1.1010,5)['direction'],1)
  self.assertEqual(feature(1.0988,1.0990,5)['direction'],-1)
 def test_level_midpoint_ambiguity_abstains(self):
  self.assertEqual(feature(1.0999,1.1001,5)['reason'],'ON_LEVEL')
  self.assertEqual(feature(1.1049,1.1051,5)['reason'],'OUTSIDE_BARRIER_ZONE')
 def test_invalid_quotes_abstain(self):
  for b,a,d in [(1,1,5),(2,1,5),(0,1,5),(1,2,-1)]:self.assertEqual(feature(b,a,d)['direction'],0)
 def test_allocator_does_not_replace_missing_future_with_supported_label(self):
  from .kernel_v1 import allocate
  a={'action':1,'sid':1,'causal_eligible':True,'reason':'EXIT_NATIVE_QUOTE_GAP','economics':{'spread_plus_fee_bps':1.,'risk_eur':1.}}
  b={'action':1,'sid':2,'causal_eligible':True,'reason':'SUPPORTED','economics':{'spread_plus_fee_bps':2.,'risk_eur':1.}}
  self.assertEqual(allocate([a,b],[1]),[a])
if __name__=='__main__':unittest.main()
