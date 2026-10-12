import unittest
from . import policy_v1 as p
class CausalExitTests(unittest.TestCase):
 def setUp(self):
  p.BAR_TIMES.clear();self.bars={i*300:[100,100.2,99.8,100,1] for i in range(70)};self.r={'t':4560,'grid':4500,'sid':1,'h':15,'model_side':1,'entry':{'notional_eur':100,'cost_eur':.01,'eligible':True,'margin_eur':1},'exit':5460};self.par={'d':1,'price':100,'atr':.4,'R':1,'cost_price':.1,'eur_per_price':1,'stress_risk_eur':1.8,'stress_eligible':True}
 def test_atr_excludes_future(self):
  original=p.atr(self.bars,4500);self.bars[4500]=[100,10000,1,200,1];self.assertEqual(original,p.atr(self.bars,4500))
 def test_first_partial_bar_not_favorable(self):
  self.bars[4500]=[100,103,98,100,1];self.assertEqual(p.m5_geometry(self.r,self.bars,self.par,'BRACKET_R1_TP2')['state'],'M5_PARTIAL_BAR_AMBIGUOUS')
 def test_same_bar_double_touch_NA(self):
  self.bars[4800]=[100,103,98,100,1];self.assertEqual(p.m5_geometry(self.r,self.bars,self.par,'BRACKET_R1_TP2')['state'],'M5_DOUBLE_TOUCH_AMBIGUOUS')
 def test_stop_gap_fills_observed_price(self):
  ticks={'bid':[(4559000,100),(4600000,98)],'ask':[(4559000,100.1),(4600000,98.1)]};z=p.tick_exit(self.r,self.bars,self.par,'BRACKET_R1_TP2',ticks,True,None);self.assertEqual(z['reason'],'STOP');self.assertEqual(z['quote']['bid'],98);self.assertEqual(z['stop_level'],99)
 def test_short_trigger_uses_ask(self):
  par={**self.par,'d':-1};r={**self.r,'model_side':-1};ticks={'bid':[(4559000,100),(4600000,100.5)],'ask':[(4559000,100.1),(4600000,101.5)]};z=p.tick_exit(r,self.bars,par,'BRACKET_R1_TP2',ticks,True,None);self.assertEqual(z['reason'],'STOP')
 def test_incomplete_tick_path_stays_NA(self):
  self.assertEqual(p.tick_exit(self.r,self.bars,self.par,'BRACKET_R1_TP2',{},False,None)['state'],'TICK_PATH_INCOMPLETE')
 def test_trailing_is_monotonic(self):
  s=p.initial(self.par,'ATR_TRAIL_2');self.bars[4500]=[100,102,99.8,102,1];p.advance(s,self.par,'ATR_TRAIL_2',self.bars,4800,4560);stop=s['stop'];self.bars[4800]=[102,102.2,100,100,1];p.advance(s,self.par,'ATR_TRAIL_2',self.bars,5100,4560);self.assertGreaterEqual(s['stop'],stop)
 def test_unknown_exit_cannot_skip_into_later_profit(self):
  rows=[{'sid':1,'t':100,'h':15,'policy':'X','exit':None,'fixed_exit':1000,'dynamic_net':None,'fixed_net':0,'margin_eur':1,'stress_risk_eur':.5,'stress_eligible':True},{'sid':2,'t':101,'h':15,'policy':'X','exit':20000,'fixed_exit':1001,'dynamic_net':100,'fixed_net':0,'margin_eur':1,'stress_risk_eur':.5,'stress_eligible':True}];z=p.portfolio(rows,15,'X',2);self.assertEqual(z['cash_closed_accounting_eur'],200);self.assertEqual(z['closed'],0);self.assertEqual(z['halt'],'FIRST_SELECTED_UNKNOWN_EXIT_OR_COST')
 def test_no_future_extreme_trailing_update(self):
  s=p.initial(self.par,'CHANDELIER_3');self.bars[4800]=[100,10000,99,100,1];p.advance(s,self.par,'CHANDELIER_3',self.bars,4800,4560);self.assertLess(s['stop'],100)
 def test_stale_or_skewed_pair_not_fill(self):
  self.assertIsNone(p.fresh((1000,100),(8000,100.1),8000))
if __name__=='__main__':unittest.main()
