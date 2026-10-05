import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from research_core_v4 import online_change_v1 as v
from research_core_v4.online_change_calibration_v1 import first_passage,normalize,wilson
R=Path(__file__).resolve().parents[1]

class Adversarial(unittest.TestCase):
    def setUp(self):
        self.d=json.loads((R/'research_core_v4/state/ONLINE_CHANGE_DESIGN_V1.json').read_bytes())
        self.small=copy.deepcopy(self.d)
        self.small.update(training_start=0,normalization_end=1500000,training_end=3000000,evaluation_start=3010000,evaluation_end_exclusive=3400000)
        rng=np.random.default_rng(32);returns=rng.normal(0,.001,12000)
        self.p={i*300:math.exp(float(x)) for i,x in enumerate(np.cumsum(returns))}
    def test_first_passage_matches_online_recursion(self):
        u=np.random.default_rng(73).uniform(-1,1,600)
        d=copy.deepcopy(self.d);d['detector']['threshold']=.7
        positive=negative=0.;first=601;direction=0
        for i,x in enumerate(u,1):
            positive,negative,state,alarm=v.detector_step(positive,negative,float(x),d)
            if alarm:first=i;direction=alarm;break
        a,b=first_passage(u[None,:],d)
        self.assertEqual((int(a[0]),int(b[0])),(first,direction))
    def test_signed_symmetry_and_alarm_reset(self):
        d=copy.deepcopy(self.d);d['detector']['threshold']=.1
        p,n,x,a=v.detector_step(0,0,1.,d)
        p2,n2,x2,a2=v.detector_step(0,0,-1.,d)
        self.assertEqual((p,n,p2,n2),(0,0,0,0));self.assertEqual(a,-a2);self.assertEqual(x,-x2)
    def test_true_sequential_memory_not_fixed_router(self):
        d=self.d;pos=neg=0
        for u in [1.]*20:pos,neg,state,alarm=v.detector_step(pos,neg,u,d)
        p,n,a,_=v.detector_step(pos,neg,0.,d);p2,n2,b,_=v.detector_step(0,0,0.,d)
        self.assertNotEqual(a,b)
    def test_prefix_models_ignore_development_future_prices(self):
        m,rows=v.fit_prefix(self.p,self.small)
        q={t:(p if t<=self.small['training_end'] else p*math.exp(.0001*((t//300)%7))) for t,p in self.p.items()}
        m2,rows2=v.fit_prefix(q,self.small)
        self.assertEqual(m,m2)
    def test_future_mutation_cannot_move_prior_states(self):
        model=v.fit_normalization(self.p,self.small);t=3180000
        q={k:(p if k<=t else p*1.1) for k,p in self.p.items()}
        a=[x for x in v.state_rows(self.p,model,self.small) if x['t']<=t]
        b=[x for x in v.state_rows(q,model,self.small) if x['t']<=t]
        self.assertEqual(a,b)
    def test_gap_resets_and_no_history_bridge(self):
        p=dict(self.p);del p[3150000];m=v.fit_normalization(p,self.small);rows=v.state_rows(p,m,self.small)
        self.assertFalse(any(3150000<=r['t']<3153900 for r in rows))
    def test_prefix_ols_independent_normal_equations(self):
        m,rows=v.fit_prefix(self.p,self.small)
        selected=[r for r in rows if self.small['normalization_end']+3600<=r['t']<=self.small['training_end']-3600 and all(r['t']+300*k in self.p for k in range(1,13))]
        z=np.array([r['z'] for r in selected]);x=np.array([r['state'] for r in selected])
        np.testing.assert_allclose(np.linalg.solve(z.T@z,z.T@x),m['x_beta'],atol=1e-10)
    def test_timestamp_support_does_not_access_responses(self):
        series={c:{sid:self.p for sid in ids} for c,ids in self.small['memberships'].items()}
        with patch.object(v,'response',side_effect=AssertionError('future response accessed')):
            s,pop=v.prepare(series,self.small)
        self.assertFalse(s['pass']);self.assertFalse(s['real_response_opened'])
    def test_default_runner_denied_independent_of_published_phase(self):
        from tools import online_change_development as runner
        with tempfile.TemporaryDirectory() as td,patch.object(runner,'ROOT',Path(td)):
            with self.assertRaisesRegex(ValueError,'NO_REAL_OPENING_AUTHORITY'):runner.authority()
        with self.assertRaisesRegex(ValueError,'REAL_RESPONSE_NOT_AUTHORIZED'):v.raw_result({},self.d,{}, {})
    def test_prospective_precision_and_horizon(self):
        f=self.d['sequential_calibration'];self.assertEqual(f['campaign_clocks'],84672)
        self.assertLess(18*wilson(0,4096,f['simultaneous_wilson_z'])[1],.05)
        self.assertAlmostEqual(self.d['detector']['threshold'],math.log(2*18*84672/.01))
    def test_normalization_matches_independent_scalar_reference(self):
        p=np.random.default_rng(4).normal(size=(2,4001));phi,b,s=normalize(p)
        for i,row in enumerate(p):
            x=row[:-1];y=row[1:];mx=float(x.mean());my=float(y.mean());a=sum((x-mx)*(y-my))/sum((x-mx)**2)
            self.assertAlmostEqual(phi[i],a,places=12);self.assertAlmostEqual(b[i],my-a*mx,places=12)

if __name__=='__main__':unittest.main()
