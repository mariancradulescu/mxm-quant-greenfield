import unittest
from .economics_v1 import lattice_units,hurdles,quote
class EconomicHurdleTests(unittest.TestCase):
 def test_equal_native_units_respect_both_lattices(self):
  f=lambda mn,st,mx:{'minVolume':mn,'stepVolume':st,'maxVolume':mx};self.assertEqual(lattice_units({},f(3,2,100),{},f(5,3,100)),.06);self.assertIsNone(lattice_units({},f(3,2,5),{},f(5,3,5)))
 def test_spread_and_slippage_require_move(self):
  r={'sid':1,'min_units':1,'quote':'EUR'};f={'commissionType':3,'lotSize':100,'preciseTradingCommissionRate':0,'preciseMinCommission':0,'minCommissionType':2,'pnlConversionFeeRate':0};q={(1,1000):quote(1,1000,99,101)}
  z=hurdles(1,r,f,1000,q,{},0,0);self.assertAlmostEqual(z['break_even_native_price_move'],2,places=5);x=hurdles(1,r,f,1000,q,{},2,.1);self.assertGreater(x['break_even_native_price_move'],2)
 def test_missing_FX_is_unknown(self):
  r={'sid':1,'min_units':1,'quote':'JPY'};f={'commissionType':3,'lotSize':100,'preciseTradingCommissionRate':0,'preciseMinCommission':0,'minCommissionType':2,'pnlConversionFeeRate':0};self.assertIsNone(hurdles(1,r,f,1000,{(1,1000):quote(1,1000,99,101)},{},2,.1))
if __name__=='__main__':unittest.main()
