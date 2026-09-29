import unittest
from datetime import datetime,timedelta,timezone
from research_core_v3.model import Bar,Series
from research_core_v3.engine import evaluate_cell,execute_spec

class CoreV3(unittest.TestCase):
 def series(self,n=240):
  t=datetime(2026,1,1,tzinfo=timezone.utc); bars=[]; px=100.0
  for i in range(n):
   px += (0.12 if (i//20)%2==0 else -0.08) + (0.7 if i%31==0 else 0)
   bars.append(Bar(t+timedelta(minutes=5*i),px-0.05,px+0.2,px-0.2,px,float(i%10)))
  return Series('FIX',1,'fixture',tuple(bars))
 def test_future_not_needed_for_signal_generation(self):
  s=self.series(); c=evaluate_cell(s,'TREND_MOMENTUM',{'kind':'ALL'},{'lookback':12,'threshold':0.0},[1,3],3)
  d=evaluate_cell(Series(s.symbol,s.symbol_id,s.source,s.bars[:-20]),'TREND_MOMENTUM',{'kind':'ALL'},{'lookback':12,'threshold':0.0},[1,3],3)
  self.assertGreater(c['event_count'],0); self.assertGreater(d['event_count'],0); self.assertEqual(c['symbol'],d['symbol'])
 def test_gap_segmentation_blocks_cross_gap_response(self):
  s=self.series(80); bars=list(s.bars); shift=timedelta(hours=4); bars[40:]=[Bar(b.ts+shift,b.open,b.high,b.low,b.close,b.volume) for b in bars[40:]]
  c=evaluate_cell(Series('FIX',1,'gap',tuple(bars)),'TREND_MOMENTUM',{'kind':'ALL'},{'lookback':12,'threshold':0.0},[12],1)
  self.assertGreater(c['missingness_sensitivity']['gap_count'],0)
 def test_all_cells_reported(self):
  spec={'response_horizons_bars':[1],'primary_horizon_bars':1,'mechanisms':[{'name':'MEAN_REVERSION','parameter_grid':{'lookback':[12,24],'z':[1.0,2.0]},'rearm_bars':2},{'name':'TREND_MOMENTUM','parameter_grid':{'lookback':[12,24],'threshold':[0.0]},'rearm_bars':2}]}
  out=execute_spec([self.series()],spec); self.assertEqual(out['cell_count'],6); self.assertEqual(set(out['mechanisms']),{'MEAN_REVERSION','TREND_MOMENTUM'}); self.assertTrue(all('parameter_neighbor_consistency' in c for c in out['cells']))
 def test_regime_variants_are_atomic(self):
  spec={'response_horizons_bars':[1],'primary_horizon_bars':1,'mechanisms':[{'name':'REGIME_CONTEXT_CONDITIONED','contexts':[{'kind':'ALL'}],'parameter_grid':{'variant':[{'base':'TREND_MOMENTUM','base_params':{'lookback':12,'threshold':0.0}},{'base':'MEAN_REVERSION','base_params':{'lookback':12,'z':1.0}}]},'rearm_bars':2}]}
  out=execute_spec([self.series()],spec); self.assertEqual(out['cell_count'],2); self.assertTrue(all('variant' in c['params'] for c in out['cells']))

if __name__=='__main__': unittest.main()
