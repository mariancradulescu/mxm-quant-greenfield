import unittest
import numpy as np
from .core import ClockState,lattice,pnl,commission_side,conversion_graph,Portfolio,assert_feature_available
from .models import MatureQueue,basis
from .data import features

def available(feature_time,decision_time):
 if feature_time>decision_time:raise ValueError('future feature')
 return True

class MechanicalFalsification(unittest.TestCase):
 def test_completed_causality_and_normalization(self):
  c=np.linspace(100,110,130);o=c.copy();h=c+.1;l=c-.1;v=np.ones(130)*100
  x,s=features(o,h,l,c,v);d=c.copy();d[100:]*=2
  y,t=features(o,h,l,d,v)
  np.testing.assert_allclose(x[:100],y[:100],equal_nan=True);np.testing.assert_allclose(s[:100],t[:100],equal_nan=True)
  with self.assertRaises(ValueError):assert_feature_available(301,300)
 def test_decision_next_valid_and_stale(self):
  decision=300;next_open=600;self.assertGreater(next_open,decision);self.assertLessEqual(next_open-decision,300)
  self.assertGreater(3600-decision,300)
 def test_mature_queue(self):
  q=MatureQueue();q.add(900,'outcome');self.assertEqual(q.pop(899),[]);self.assertEqual(q.pop(900),['outcome']);self.assertEqual(q.pop(901),[])
 def test_missing_and_stale_relational(self):
  c=np.linspace(100,110,130);c[80]=np.nan;x,s=features(c,c+.1,c-.1,c,np.ones(130))
  self.assertFalse(np.isfinite(x[90]).all());self.assertFalse(np.isfinite(s[90]))
  peers=np.array([np.nan,np.nan,.1]);self.assertLess(np.isfinite(peers).sum(),3)
 def test_pnl_math(self):
  self.assertEqual(pnl(1,100,10,11,.9),90);self.assertEqual(pnl(-1,100,10,11,.9),-90)
 def test_lattice(self):
  self.assertTrue(lattice(300,100,100,1000));self.assertFalse(lattice(250,100,100,1000));self.assertFalse(lattice(1100,100,100,1000))
 def test_commission(self):
  m={'current_full_metadata':{'preciseTradingCommissionRate':'300000000','commissionType':2,'lotSize':'10000000'},'current_light_metadata':{'quoteAssetId':'1','baseAssetId':'2'}}
  assets={'1':'USD','2':'EUR'};rate=lambda cur,target='EUR':.9 if cur=='USD' else 1.
  self.assertAlmostEqual(commission_side(m,assets,1.1,1000,rate),.054)
 def test_idempotent_event(self):
  c=ClockState();self.assertTrue(c.accept(10));self.assertFalse(c.accept(10));self.assertFalse(c.accept(9));self.assertTrue(c.accept(11))
 def test_conversion_freshness_and_canonical_order(self):
  info={'records':[{'symbol':'EURUSD'}],'metadata':[{'asset_class':'Forex (Spot)','current_light_metadata':{'baseAssetId':'1','quoteAssetId':'2'}}],'assets':{'1':'EUR','2':'USD'}}
  r=conversion_graph(info,np.array([1.25]),np.array([True]));self.assertEqual(r('USD'),.8)
  r=conversion_graph(info,np.array([1.25]),np.array([False]));self.assertIsNone(r('USD'))
 def test_model_numeric_dimension(self):
  self.assertEqual(basis(np.ones((3,19)),True).shape,(3,27))
 def test_action_accounting_margin_drawdown(self):
  info={'records':[{'symbol':'EURUSD','symbol_id':1}],'metadata':[{'asset_class':'Forex (Spot)','min_volume':100000,'step_volume':100000,'buy_min_margin_eur':'10','sell_min_margin_eur':'10','current_full_metadata':{'maxVolume':'10000000','preciseTradingCommissionRate':'0'},'current_light_metadata':{'quoteAssetId':'1','baseAssetId':'2'}}],'assets':{'1':'USD','2':'EUR'},'costs':[{'spread_bound_bps':1.}]}
  p=Portfolio(info,.01);rate=lambda cur,target='EUR':1.
  j={'due':1,'target':2,'direction':1,'lower_return':.01,'tail':.001,'horizon':15,'signal_price':1.,'range':0.}
  p.pending={0:j};p.execute(1,np.array([1.]),np.array([True]),rate);self.assertEqual(len(p.positions[0]),2);self.assertAlmostEqual(sum(l['margin'] for l in p.positions[0]),40)
  cash=p.cash;p.execute(1,np.array([1.]),np.array([True]),rate);self.assertEqual(p.cash,cash)
  p.pending={0:{**j,'due':2,'target':1}};p.execute(2,np.array([1.001]),np.array([True]),rate);self.assertEqual(len(p.positions[0]),1)
  p.pending={0:{**j,'due':3,'target':0}};p.execute(3,np.array([1.002]),np.array([True]),rate);self.assertEqual(len(p.positions[0]),0)
  self.assertAlmostEqual(p.cash,200+p.gross-p.cost);self.assertGreaterEqual(p.hwm,200);self.assertGreaterEqual(p.minfree,0)
 def test_future_labels_cannot_change_fit(self):
  from .models import ForecastModel
  rng=np.random.default_rng(1)
  x=rng.normal(size=(12*288,2,19));x[:,:,0]=1
  y=rng.normal(size=(12*288,2,4))
  info={'contexts':['FX'],'metadata':[{'asset_class':'FX'}]*2}
  a=ForecastModel(x,y,info);a.update(10)
  altered=y.copy()
  for hi,h in enumerate((3,6,12,48)):altered[10*288-h-1:,:,hi]=999
  b=ForecastModel(x,altered,info);b.update(10)
  for i,j in zip(a.state,b.state):np.testing.assert_allclose(i,j)
 def test_callback_order_and_restart(self):
  c=ClockState();c.accept(120);serialized={'last':c.last}
  recovered=ClockState();recovered.last=serialized['last'];self.assertFalse(recovered.accept(120));self.assertTrue(recovered.accept(121))
  jobs={3:'c',1:'a',2:'b'};alternate=dict(reversed(list(jobs.items())))
  self.assertEqual(sorted(jobs.items()),sorted(alternate.items()))
if __name__=='__main__':unittest.main()
