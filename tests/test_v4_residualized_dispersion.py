import unittest,json,math,copy
from pathlib import Path
from unittest.mock import patch
import numpy as np
from research_core_v4 import residualized_dispersion_v1 as v

class Dispersion(unittest.TestCase):
    def design(self):return json.loads(Path('research_core_v4/state/RESIDUALIZED_DISPERSION_DESIGN_V1.json').read_text())
    def panel(self):
        rng=np.random.default_rng(129);T=2800;r=(rng.normal(size=(T,6))+.5*rng.normal(size=(T,1)))*.001;p=np.exp(np.cumsum(r,axis=0));d=self.design();d.update(training_start=0,normalization_end=1200*300,training_end=2400*300,evaluation_start=2500*300,evaluation_end_exclusive=2800*300);d['support']=dict(d['support'],normalization_clocks_min=1000,prefix_clocks_min=1000)
        return {sid:{j*300:float(p[j,i]) for j in range(T)} for i,sid in enumerate(range(6))},d
    def test_panel_order_factor_leaveout(self):
        r=np.arange(24.).reshape(4,6);f=v.factor_returns(r)
        for i in range(6):np.testing.assert_allclose(f[:,i],np.mean(np.delete(r,i,axis=1),axis=1))
    def test_gap_excludes_full_hour_all_members(self):
        p,d=self.panel();del p[2][1500*300];ts,_,_=v.panel_hours(p,d)
        self.assertFalse(any(1500*300<=t<=1512*300 for t in ts));self.assertIn(1499*300,ts);self.assertIn(1513*300,ts)
    def test_prefix_future_invariance(self):
        p,d=self.panel();a=v.fit_prefix(p,d);q=copy.deepcopy(p)
        for sid in q:
            for t in q[sid]:
                if t>2600*300:q[sid][t]*=1.5
        b=v.fit_prefix(q,d);self.assertEqual(v.canonical(a[4]),v.canonical(b[4]));np.testing.assert_array_equal(a[2][a[1]<=2600*300],b[2][b[1]<=2600*300])
    def test_control_projection_is_incremental(self):
        p,d=self.panel();ids,tt,x,y,m,valid=v.fit_prefix(p,d);r=np.array([[math.log(p[s][int(t)]/p[s][int(t)-3600]) for s in ids] for t in tt]);inter,z,D=v.features(tt,r,m);ii=(tt>=d['normalization_end']+3600)&(tt<=d['training_end']-3600)
        for i in range(6):np.testing.assert_allclose(z[ii,i].T@x[ii,i],np.zeros(7),atol=1e-8)
    def test_response_is_own_leg(self):
        self.assertAlmostEqual(v.response({'t':0,'x':2.,'baseline_y':.1},{0:100.,3600:101.},.01),2*(math.log(1.01)/.01-.1))
    def test_default_real_denied(self):
        with self.assertRaisesRegex(ValueError,'REAL_RESPONSE_NOT_AUTHORIZED'):v.raw_result({},self.design(),{}, {})
    def test_ties_not_removed(self):
        d=self.design();self.assertFalse(v.family_rejections(np.zeros((1,2,18)),d)[0])
    def test_exact_binomial_reference(self):
        d=self.design()
        for n in range(18,22):
            k=v.critical_count(n,d['inference']['family_alpha']);self.assertLessEqual(sum(math.comb(n,j) for j in range(k,n+1))/2**n,.01/4);self.assertGreater(sum(math.comb(n,j) for j in range(k-1,n+1))/2**n,.01/4)
    def test_no_best_context_or_direction_rescue(self):
        d=self.design();b=list(range(2,20));x=np.ones((2,18));a=np.ones((2,6,18));self.assertTrue(v.complete_lead(x,a,b,d));x[1]*=-1;self.assertFalse(v.complete_lead(x,a,b,d))
    def test_temporal_and_asset_replication(self):
        d=self.design();b=list(range(2,20));x=np.ones((2,18));a=np.ones((2,6,18));a[0,:3]*=-1;self.assertFalse(v.complete_lead(x,a,b,d));a[:]=1;x[:,np.array(b)//7==1]=-.01;self.assertFalse(v.complete_lead(x,a,b,d))
    def test_support_has_no_response_access(self):
        p,d=self.panel();d['memberships']={'A':list(p),'B':list(range(6,12))};s={'A':p,'B':{sid+6:pp for sid,pp in p.items()}}
        with patch.object(v,'response',side_effect=AssertionError('future response access')):support,pop=v.prepare(s,d)
        self.assertFalse(support['real_response_opened']);self.assertTrue(support['causal_panel_integrity_pass']);self.assertFalse(support['pass'])

if __name__=='__main__':unittest.main()
