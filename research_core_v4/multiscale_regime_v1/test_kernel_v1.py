"""Synthetic witnesses/causality, never authentic market performance."""
import copy,unittest,json
from pathlib import Path
from research_core_v4.multiscale_regime_v1.kernel_v1 import observations,evaluate,NAMES,n,Fit
from research_core_v4.compact_baseline_v2 import baseline
from research_core_v4.multiscale_regime_v1.cost_universe_v1 import eligibility
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT
def bars():
    return {t:{'timestamp':t,'available_at':t+300,'open':100.,'high':102.,'low':98.,'close':100.,'tick_volume':100} for t in range(n.START-18000,n.START+86400,300)}
class Test(unittest.TestCase):
    def test_occupancy_not_compact_endpoint_or_sign_alignment(self):
        a=bars();b=copy.deepcopy(a);b[n.START-3000]['close']=101.
        required=set(range(n.START-3600,n.START,300))|{n.START+600}
        self.assertEqual(baseline(n.START+900,[a[t] for t in required]),baseline(n.START+900,[b[t] for t in required]))
        self.assertNotEqual(observations(a)[NAMES[0]][0]['x'][-1],observations(b)[NAMES[0]][0]['x'][-1])
    def test_order_not_wasserstein_sorted_marginal(self):
        a=bars();b=copy.deepcopy(a);seq1=[.2]*6+[.8]*6;seq2=[.2,.8]*6
        for seq,d in ((seq1,a),(seq2,b)):
            for t,l in zip(range(n.START-3600,n.START,300),seq):d[t]['close']=98+4*l
        required=set(range(n.START-3600,n.START,300))|{n.START+600}
        self.assertEqual(sorted(seq1),sorted(seq2));self.assertEqual(baseline(n.START+900,[a[t] for t in required]),baseline(n.START+900,[b[t] for t in required]))
        self.assertNotEqual(observations(a)[NAMES[1]][0]['x'][-1],observations(b)[NAMES[1]][0]['x'][-1])
    def test_late_missing_and_future(self):
        a=bars();b=copy.deepcopy(a);b[n.START-300]['available_at']=n.START+901
        self.assertIsNone(observations(b)[NAMES[0]][0]['x']);del b[n.START-600]
        self.assertIsNone(observations(b)[NAMES[1]][0]['x'])
        b=copy.deepcopy(a);b[n.START+6000]['close']=101
        for name in NAMES:self.assertEqual(observations(a)[name][0]['x'],observations(b)[name][0]['x'])
    def test_strict_matured_fit_and_future_label_invariance(self):
        obs=[{'x':[float((j+k)%9) for k in range(11)],'feature':'FEATURE_VALID','y':float(j%7),'label':'SUPPORTED','entry_reference_price':100.} for j in range(672)]
        alt=copy.deepcopy(obs)
        for r in alt[81:]:r['y']+=10000
        a=evaluate(1,obs);b=evaluate(1,alt)
        self.assertEqual([t['model'] for t in a['trials'] if t['clock']<=80],[t['model'] for t in b['trials'] if t['clock']<=80])
        self.assertEqual(a['trials'][0]['training'],32)
        self.assertEqual(a['trials'][0]['clock'],36)
        self.assertEqual(sum(w['calendar'] for w in a['four_weeks']),168)
    def test_capital_unknown_not_zero_and_public_guard(self):
        r={'buy_eligible_current':True,'sell_eligible_current':True,'min_volume_cents':100,'step_volume_cents':100,'lot_size':10000,'buy_margin_eur':2,'sell_margin_eur':3,'product_type':'FX_SPOT_OR_MARGIN_CFD'}
        self.assertTrue(eligibility(r)[0]);r['sell_margin_eur']=None;self.assertFalse(eligibility(r)[0])
        with self.assertRaises(Exception):validate_public_blob(ROOT+'OWNER_MULTIREGIME_RESEARCH_V1.json',{'private_results':[1,2,3]})
if __name__=='__main__':unittest.main()
