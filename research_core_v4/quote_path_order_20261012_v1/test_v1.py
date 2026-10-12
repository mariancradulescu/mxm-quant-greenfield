"""Synthetic implementation checks only; never market evidence."""
import math
import unittest
from .kernel_v1 import feature,admit,portfolio,analyze_saved
from types import SimpleNamespace

def synthetic_path(price_first=True):
    bid=[]; ask=[]
    for sec in range(-60,0):
        x,y=0.,0.
        if sec>=-35:
            x,y=(2.,0.) if price_first else (0.,2.)
        if sec>=-25:
            x,y=2.,2.
        if sec>=-15:
            x,y=2.2,2.2
        mid=100*math.exp(x/10000); ratio=math.exp((2+y)/10000)
        b=2*mid/(1+ratio); a=ratio*b
        bid.append((sec*1000,b)); ask.append((sec*1000,a))
    return bid,ask

def candidate(t,sid=1):
    return {'t':t,'sid':sid,'entry':{'eligible':True,'margin_eur':20.,'risk_eur':1.,'cost_eur':.1},
            'feature':{'state':'SUPPORTED_FEATURE','model_side':1,'midpoint_baseline_side':-1,'quote_count_baseline_side':0}}

class Checks(unittest.TestCase):
    def test_order_is_not_endpoint_information(self):
        b1,a1=synthetic_path(); b2,a2=synthetic_path(False)
        f1,f2=feature(b1,a1,0),feature(b2,a2,0)
        self.assertAlmostEqual(f1['area_bps2'],4.,places=7)
        self.assertAlmostEqual(f2['area_bps2'],-4.,places=7)
        self.assertEqual((f1['model_side'],f2['model_side']),(-1,1))
        self.assertEqual((b1[-1],a1[-1]),(b2[-1],a2[-1]))
        self.assertEqual(f1['quote_count_baseline_side'],f2['quote_count_baseline_side'])
        self.assertEqual(f1['midpoint_baseline_side'],f2['midpoint_baseline_side'])
        self.assertEqual(b1[-6:],b2[-6:]); self.assertEqual(a1[-6:],a2[-6:])
    def test_future_prices_cannot_change_features(self):
        b,a=synthetic_path(); f=feature(b,a,0)
        self.assertEqual(f,feature(b+[(0,-1),(900000,float('nan'))],a+[(0,-99)],0))
    def test_conflicting_side_millisecond_censored(self):
        b,a=synthetic_path()
        self.assertEqual(feature(b+[(-1000,1)],a,0)['state'],'AMBIGUOUS_SIDE_MILLISECOND')
    def test_incomplete_page_not_repaired(self):
        self.assertEqual(feature(*synthetic_path(),0,True)['state'],'INCOMPLETE_PAGE')
    def test_stale_path_censored(self):
        b,a=synthetic_path(); b=[z for z in b if z[0]<-10000]
        self.assertEqual(feature(b,a,0)['state'],'STALE_OR_SKEWED_PATH')
    def test_constant_spread_no_float_signal(self):
        b=[(s*1000,100+s*.01) for s in range(-60,0)]
        a=[(t,p*1.0002) for t,p in b]
        self.assertEqual(feature(b,a,0)['state'],'DEGENERATE_PATH')
    def test_absolute_capital_limits(self):
        e={'eligible':True,'margin_eur':80.,'risk_eur':2.,'cost_eur':.1}
        self.assertTrue(admit(e)); self.assertFalse(admit(e,cash=199.))
        self.assertFalse(admit({**e,'risk_eur':2.01}))
        self.assertFalse(admit({**e,'margin_eur':80.01}))
    def test_unknown_cost_is_not_zero(self):
        e=candidate(0)['entry'].copy(); e.pop('cost_eur')
        self.assertFalse(admit(e))
    def test_no_future_exit_filter_or_replacement(self):
        selected=[]
        def account(e,d): selected.append((e['t'],d)); return None
        r=portfolio([candidate(0),candidate(1000,2)],account)
        self.assertEqual(r['halt'],'FIRST_SELECTED_UNKNOWN_EXIT')
        self.assertEqual(r['selected'],[{'sid':1,'entry':0}]); self.assertEqual(r['closed'],[])
        self.assertEqual(selected,[(0,1)]); self.assertIsNone(r['complete_net_eur'])
    def test_one_position_and_same_cohort_comparators(self):
        r=portfolio([candidate(0),candidate(100),candidate(900)],lambda e,d: -.1 if d==1 else -.2)
        self.assertEqual(len(r['closed']),2)
        self.assertAlmostEqual(r['cash_from_known_closes_eur'],199.8)
        self.assertAlmostEqual(r['shadow_comparator_net_eur']['midpoint'],-.4)
        self.assertEqual(r['shadow_comparator_net_eur']['quote_count'],0.)
        self.assertFalse(r['HARD21_demonstrated'])
    def test_saved_adapter_ignores_old_predictions_and_targets(self):
        b,a=synthetic_path()
        q={'symbol_id':1,'boundary_ms':0,'pages':[
            {'side':'bid','encoded':b,'hasMore':False},
            {'side':'ask','encoded':a,'hasMore':False}]}
        e={'sid':1,'t':0,'h':15,'entry':candidate(0)['entry'],'prediction':'POISON_OLD_MODEL','net_sides':'POISON_OLD_TARGET'}
        full={'raw_quote_receipts':[q],'all_identity_status':[{'sid':1}],
              'catalog':{'full':{'1':{}}},'events':[e,e.copy()]}
        native=SimpleNamespace(graph=lambda rows:{},account=lambda *args:{'net_eur':-.1})
        decoder=lambda pairs:[SimpleNamespace(timestamp_ms=t,raw_tick=p*100000) for t,p in pairs]
        r=analyze_saved(full,decoder,native)
        self.assertEqual(r['candidate_boundaries'],1)
        self.assertEqual(r['feature_states'],{'SUPPORTED_FEATURE':1})
        self.assertAlmostEqual(r['portfolio']['complete_net_eur'],-.1)
        self.assertEqual(r['new_broker_requests'],0)

if __name__=='__main__':
    unittest.main()
