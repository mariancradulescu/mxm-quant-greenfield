import unittest,math
from research_core_v4.native_economic_frontier_v2 import kernel_v2 as k
class EconomicTests(unittest.TestCase):
 def setUp(self):
  self.full={'preciseTradingCommissionRate':350000000,'preciseMinCommission':0,'commissionType':2,'minCommissionType':1,'lotSize':10000000,'pnlConversionFeeRate':100};self.assets={'1':'EUR','2':'USD'};self.fx={'bid':1.1,'ask':1.1002}
 def test_signed_conversion_and_fee(self):
  self.assertAlmostEqual(k.pnl_convert(110,self.fx),110/1.1002);self.assertAlmostEqual(k.pnl_convert(-110,self.fx),-100)
  r=k.accounting('long',1000,1.2,1.21,self.fx,self.fx,self.full,self.assets,0,.1)
  self.assertGreater(r['entry_commission_eur'],0);self.assertGreater(r['exit_commission_eur'],0);self.assertAlmostEqual(r['pnl_conversion_fee_eur'],abs(r['quote_pnl_eur'])*.01)
  self.assertAlmostEqual(r['scenario_net_eur'],r['quote_pnl_eur']-r['entry_commission_eur']-r['exit_commission_eur']-r['pnl_conversion_fee_eur']-.1)
 def test_short_slippage_and_hurdle(self):
  a=k.accounting('short',1000,1.2,1.19,self.fx,self.fx,self.full,self.assets,0,0);b=k.accounting('short',1000,1.2,1.19,self.fx,self.fx,self.full,self.assets,2,0);self.assertLess(b['scenario_net_eur'],a['scenario_net_eur'])
  h=k.hurdle('short',1000,{'bid':1.2,'ask':1.2002},self.fx,self.full,self.assets,2,.1)
  r=k.accounting('short',1000,1.2,1.2002-h['breakeven_quote_price_move'],self.fx,self.fx,self.full,self.assets,2,.1)
  self.assertAlmostEqual(r['scenario_net_eur'],0,places=8)
 def test_minimum_commission_currency_and_unknown(self):
  f=dict(self.full,preciseTradingCommissionRate=0,preciseMinCommission=50000000,minCommissionAsset=1)
  self.assertAlmostEqual(k.commission_eur(f,self.assets,1000,1.2,self.fx),.5)
  f['minCommissionAsset']=99;self.assertIsNone(k.commission_eur(f,self.assets,1000,1.2,self.fx))
 def test_calendar_is_not_independent_legs(self):
  self.assertEqual(len(k.grid()),40);self.assertEqual(k.PRECISION_N,97)
  for w in ('2026-W35','2026-W36','2026-W37'):self.assertEqual(sum(k.iso(t)==w for t in k.grid()),10)
if __name__=='__main__':unittest.main()
