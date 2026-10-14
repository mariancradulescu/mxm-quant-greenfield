"""Finite synthetic causality, nonredundancy and minimum-ticket accounting tests."""
import math,unittest
from collections import deque
import numpy as np
from . import kernel_v1 as k,economics_v1 as e
class Tests(unittest.TestCase):
 def panel(self,price=100.):
  a=np.zeros((k.HOURS,3));a[:,0]=[20*math.sin(j*.47) for j in range(k.HOURS)];a[:,1]=.1;a[:,2]=price
  p=np.tile(np.array([[price,price+.04,price-.04,price+.01]]),(k.HOURS,12,1))
  return {'feature':a,'path':p,'entry':np.full(k.HOURS,price),'exit_reference':np.full(k.HOURS,price+.01)}
 def test_same_slow_loading_different_recent_loading(self):
  A=deque((j,(-1.)**j,(-1.)**j*(.5 if j<48 else 2.)) for j in range(72));B=deque((j,(-1.)**j,(-1.)**j) for j in range(72))
  self.assertAlmostEqual(k.beta(A,72),k.beta(B,72));self.assertAlmostEqual(k.beta(A,24),2.);self.assertAlmostEqual(k.beta(B,24),1.)
 def test_leave_own_out(self):
  panel={i:self.panel() for i in range(10)};f,_=k.factors(panel,{'g':list(panel)})
  original=f[0].copy();panel[0]['feature'][:,0]*=10;g,_=k.factors(panel,{'g':list(panel)})
  np.testing.assert_allclose(original,g[0],equal_nan=True)
 def test_missing_peers_not_filled(self):
  panel={i:self.panel() for i in range(10)};panel[1]['feature'][:]=np.nan;panel[2]['feature'][:]=np.nan
  f,_=k.factors(panel,{'g':list(panel)});self.assertTrue(np.isnan(f[0]).all())
 def test_future_outcomes_do_not_change_prior_forecasts(self):
  obs=self.panel();f=np.array([15*math.cos(j*.37) for j in range(k.HOURS)]);a,_=k.forecasts(1,obs,f)
  obs['path'][300:,:,3]*=1.2;b,_=k.forecasts(1,obs,f)
  old={r['j']:r['model'] for r in a if r['j']<=301};new={r['j']:r['model'] for r in b if r['j']<=301};self.assertTrue(old);self.assertEqual(old,new)
 def test_feature_missing_future_path_cannot_change_entry_admission(self):
  obs=self.panel();row={'sid':1,'quote':'EUR','min_units':1.,'margin_eur':10.};f={'commissionType':3,'preciseTradingCommissionRate':0,'lotSize':100,'preciseMinCommission':0,'minCommissionType':2,'pnlConversionFeeRate':0};ev={'sid':1,'j':100,'model':30.,'atr_price':.1}
  a=e.planned(ev,row,f,{1:obs},{})
  obs['path'][100]=np.nan;obs['exit_reference'][100]=np.nan;b=e.planned(ev,row,f,{1:obs},{})
  self.assertEqual(a,b);self.assertTrue(a['eligible']);self.assertIsNone(e.account(ev,1,row,f,{1:obs},{},'PRIMARY_S5_L2_F010'))
 def test_gap_stop_uses_gap_price(self):
  path=np.array([[100.,100.1,99.9,100.],[98.,98.2,97.9,98.]]+[[98.,98.,98.,98.]]*10)
  out=k.stop_path(1,path,.5);self.assertEqual(out['kind'],'BAR_OPEN_GAP_STOP');self.assertEqual(out['price'],98.);self.assertLess(out['price'],out['stop'])
 def test_minimum_ticket_risk_abstention(self):
  obs=self.panel();row={'sid':1,'quote':'EUR','min_units':100.,'margin_eur':10.};f={'commissionType':3,'preciseTradingCommissionRate':0,'lotSize':100,'preciseMinCommission':0,'minCommissionType':2,'pnlConversionFeeRate':0};ev={'sid':1,'j':100,'model':30.,'atr_price':.1}
  out=e.planned(ev,row,f,{1:obs},{});self.assertFalse(out['eligible']);self.assertGreater(out['planned_total_loss_proxy_eur'],2.)
 def test_commission_percentage_and_minimum_max_not_sum(self):
  obs=self.panel();row={'sid':1,'quote':'EUR','min_units':1.,'margin_eur':10.};f={'commissionType':3,'preciseTradingCommissionRate':10000,'lotSize':100,'preciseMinCommission':4000000,'minCommissionType':2,'pnlConversionFeeRate':0}
  self.assertAlmostEqual(e.commission(row,f,1.,100.,10,{1:obs},{}),.1)
 def test_forecast_requires_mature_training_and_loading_prefix(self):
  obs=self.panel();f=np.array([15*math.cos(j*.37) for j in range(k.HOURS)]);r,why=k.forecasts(1,obs,f)
  self.assertTrue(r);self.assertTrue(all(v['train_n']>=32 and v['j']>=105 for v in r));self.assertGreater(why['PRIOR_24_72_FACTOR_LOADING_SUPPORT'],0)
if __name__=='__main__':unittest.main()
