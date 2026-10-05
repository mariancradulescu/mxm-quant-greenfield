import copy,json,math,unittest
from pathlib import Path
import numpy as np
from research_core_v4 import variance_composition_v1 as v
from research_core_v4.variance_composition_calibration_v1 import complete_lead,wilson
ROOT=Path(__file__).resolve().parents[1]

class Adversarial(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(7)
        self.p={300*i:float(math.exp(x)) for i,x in enumerate(np.cumsum(rng.normal(0,.001,8000)))}
        self.d=json.loads((ROOT/'research_core_v4/state/VARIANCE_COMPOSITION_DESIGN_V1.json').read_bytes())
    def test_future_price_poison_cannot_change_causal_row(self):
        model={'median_rv':1e-5,'q_mean':.2,'sigma_hour':.003,'x_beta':[0]*5,'y_beta':[0]*5,'x_scale':.1}
        t=9000;a=v.causal_row(self.p,t,model)
        p={k:(x if k<=t else float('nan')) for k,x in self.p.items()}
        self.assertEqual(a,v.causal_row(p,t,model))
    def test_q_sign_and_permutation_invariant(self):
        r=np.array([.001,.002,-.004,.003,.001,-.001,.001,.002,-.001,.001,.001,.002])
        def series(rr): return {300*i:math.exp(x) for i,x in enumerate(np.r_[0,np.cumsum(rr)])}
        q=v.feature(series(r),3600)[0]
        self.assertAlmostEqual(q,v.feature(series(-r),3600)[0],places=10)
        self.assertAlmostEqual(q,v.feature(series(r[::-1]),3600)[0],places=10)
        self.assertNotAlmostEqual(q,1/12,places=4)
    def test_gap_is_never_filled(self):
        p=copy.deepcopy(self.p);del p[8700];self.assertIsNone(v.feature(p,9000))
    def test_prefix_unchanged_by_development_mutation(self):
        d={'training_start':0,'training_end':1800000,'support':{'prefix_clocks_min':1000}}
        a=v.fit_prefix(self.p,d);p={k:(x if k<=d['training_end'] else 100*x) for k,x in self.p.items()}
        self.assertEqual(a,v.fit_prefix(p,d))
    def test_prefix_partialling_and_independent_lstsq_reference(self):
        d={'training_start':0,'training_end':1800000,'support':{'prefix_clocks_min':1000}}
        m=v.fit_prefix(self.p,d);rows=[];z=[];raw=[]
        for t in sorted(self.p):
            if 3600<=t<=1796400:
                f=v.feature(self.p,t);z.append(v.controls(t,f[1],f[2],m));raw.append(f[1]*(f[0]-m['q_mean']))
        z=np.array(z);raw=np.array(raw)
        reference=np.linalg.solve(z.T@z,z.T@raw)
        np.testing.assert_allclose(reference,m['x_beta'],atol=1e-10)
        np.testing.assert_allclose(z.T@(raw-z@np.array(m['x_beta'])),0,atol=1e-9)
    def test_family_rejects_context_or_third_cherry_picking(self):
        blocks=list(range(2,20));x=np.full((1,3,18),3.)+np.random.default_rng(8).normal(0,.1,(1,3,18))
        assets=np.repeat(x[:,:,None,:],6,axis=2)
        self.assertTrue(complete_lead(x,assets,blocks,5)[0])
        x[0,2]*=-1;assets=np.repeat(x[:,:,None,:],6,axis=2)
        self.assertFalse(complete_lead(x,assets,blocks,5)[0])
    def test_support_only_never_accesses_response(self):
        from unittest.mock import patch
        d=copy.deepcopy(self.d);d.update(training_start=0,training_end=1800000,evaluation_start=1810000,evaluation_end_exclusive=2200000)
        series={c:{sid:self.p for sid in ids} for c,ids in d['memberships'].items()}
        with patch.object(v,'response',side_effect=AssertionError('response accessed')):
            support,population=v.prepare(series,d)
        self.assertFalse(support['pass']);self.assertFalse(support['real_response_opened'])
    def test_precision_declared_before_trial(self):
        f=self.d['inference'];self.assertEqual(f['null_calibration_trials_per_case'],4096)
        self.assertLess(wilson(82,4096,f['simultaneous_wilson_z'])[1]-.02,.01)
    def test_real_evaluator_and_runner_default_denied(self):
        with self.assertRaisesRegex(ValueError,'REAL_RESPONSE_NOT_AUTHORIZED'):
            v.raw_result({},self.d,{}, {})
        from tools.variance_composition_development import authority
        with self.assertRaisesRegex(ValueError,'NO_REAL_OPENING_AUTHORITY'): authority()
    def test_synthetic_hac_against_scalar_reference(self):
        a=np.random.default_rng(12).normal(size=(3,21));out=[]
        for row in a:
            n=len(row);x=row-row.mean();g=sum(x*x)/n
            for lag in [1,2]:g+=2*(1-lag/3)*sum(x[lag:]*x[:-lag])/n
            out.append(row.mean()/math.sqrt(g/n))
        np.testing.assert_allclose(v.hac_t(a),out,atol=1e-12)

if __name__=='__main__': unittest.main()
