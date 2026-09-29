import unittest
from datetime import datetime,timedelta,timezone
from research_core_v3.model import Bar,Series
from research_core_v3.fast_engine import Features
from research_core_v3.corrected_semantics import *

class CorrectedSemanticsTests(unittest.TestCase):
    def test_next_open_exit_stays_at_original_horizon(self):
        c=[100,110,121,133.1]; o=[100,105,115,126]
        self.assertAlmostEqual(response(c,o,0,1,1,True),110/105-1)
        self.assertNotAlmostEqual(response(c,o,0,1,1,True),121/105-1)
        self.assertAlmostEqual(response(c,o,0,3,-1,True),-(133.1/105-1))
    def test_exact_dependency_lengths(self):
        i=1000
        self.assertEqual(dependency_start('MEAN_REVERSION',{'lookback':48},{},i),953)
        self.assertEqual(dependency_start('TREND_MOMENTUM',{'lookback':48},{},i),952)
        self.assertEqual(dependency_start('BREAKOUT_VOLATILITY_EXPANSION',{'lookback':24},{},i),976)
        self.assertEqual(dependency_start('VOLATILITY_STATE',{'lookback':24,'reference':240},{},i),737)
        self.assertEqual(dependency_start('SESSION_TIME_SEASONALITY',{}, {},i),i)
    def test_union_and_early_context(self):
        ctx={'kind':'VOLATILITY_QUANTILE','lookback':24,'reference_bars':500}
        p={'variant':{'base':'MEAN_REVERSION','base_params':{'lookback':24,'z':1.5}}}
        self.assertEqual(dependency_start('REGIME_CONTEXT_CONDITIONED',p,ctx,1000),499)
        self.assertEqual(dependency_start('REGIME_CONTEXT_CONDITIONED',p,ctx,100),23)
    def test_authentic_gap_rejects_long_dependency_not_session(self):
        t=datetime(2025,1,1,tzinfo=timezone.utc)
        bars=tuple(Bar(t+timedelta(minutes=5*(i+(1 if i>=10 else 0))),100+i,101+i,99+i,100+i,1) for i in range(80))
        f=Features(Series('T',1,'fixture',bars)); sg=exact_segments(bars)
        self.assertNotEqual(sg[9],sg[10])
        self.assertNotEqual(sg[dependency_start('TREND_MOMENTUM',{'lookback':48},{},55)],sg[55])
        self.assertEqual(sg[dependency_start('SESSION_TIME_SEASONALITY',{}, {},55)],sg[55])
        x=evaluate_corrected(f,'TREND_MOMENTUM',{'lookback':48,'threshold':0},{},[1,3,6,12],3)
        self.assertGreater(x['events_removed_for_backward_dependency_gap'],0)
        self.assertLess(x['strict_dependency_event_count'],x['original_event_count'])
    def test_numeric_immediate_adjacency_only(self):
        g={'lookback':[12,24,48],'z':[1,1.5,2]}
        self.assertTrue(adjacent({'lookback':12,'z':1},{'lookback':24,'z':1},g))
        self.assertFalse(adjacent({'lookback':12,'z':1},{'lookback':48,'z':1},g))
        self.assertFalse(adjacent({'state':'HIGH'},{'state':'LOW'},{'state':['HIGH','LOW']}))
    def test_no_future_signal_dependency(self):
        for mech,p in [('MEAN_REVERSION',{'lookback':12}),('VOLATILITY_STATE',{'lookback':12,'reference':120}),('SESSION_TIME_SEASONALITY',{})]:
            self.assertLessEqual(dependency_start(mech,p,{},200),200)
if __name__=='__main__':unittest.main()
