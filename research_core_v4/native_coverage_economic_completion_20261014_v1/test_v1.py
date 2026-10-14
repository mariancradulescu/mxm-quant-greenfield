import unittest
from .runner_v1 import primary_cost
class TestCost(unittest.TestCase):
 def test_break_even_identity(self):
  r={'commission_RT_eur':.20,'funding_stress_eur':.01,'break_even_eur':.61,'notional_eur':100,'planned_risk_eur':.66,'eligible':True}
  rate=.002;v=primary_cost(r,rate)
  spread_slip=.40
  self.assertAlmostEqual((v['break_even_eur']-spread_slip)*(1-rate)-.20-.01,0)
  self.assertGreater(v['break_even_eur'],r['break_even_eur'])
 def test_unknown_stays_unknown(self):self.assertNotIn('break_even_eur',primary_cost({'eligible':False,'state':'NA'},.002))
 def test_risk_cap_fails_with_fee(self):
  r={'commission_RT_eur':1.,'funding_stress_eur':0,'break_even_eur':1.5,'notional_eur':100,'planned_risk_eur':1.999,'eligible':True}
  self.assertFalse(primary_cost(r,.01)['eligible'])
if __name__=='__main__':unittest.main()
