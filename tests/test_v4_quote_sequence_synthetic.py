import unittest
import numpy as np
from research_core_v4.quote_sequence_synthetic_v1 import family_test,holm,wilson

class SyntheticInferenceTests(unittest.TestCase):
    def test_holm_stepdown_preserves_all_families(self):
        self.assertEqual(holm([[.001,.02,.9,1.,1.]]).tolist(),[[True,False,False,False,False]])
        self.assertEqual(holm([[1.,1.,1.,1.,1.]]).tolist(),[[False]*5])
    def test_manual_enumerated_sign_reference(self):
        import itertools
        x=np.array([[[[1.,2.,3.,4.],[-1.,-2.,-3.,-4.]]]])
        signs=np.array(list(itertools.product([-1.,1.],repeat=4)))
        p,rej,adj=family_test(x,signs)
        vals=x[0,0];obs=vals.mean(1)/(vals.std(1,ddof=1)/2)
        maxima=[]
        for s in signs:
            v=vals*s;maxima.append(max(v.mean(1)/(v.std(1,ddof=1)/2)))
        expected=[(1+sum(m>=t for m in maxima))/17 for t in obs]
        np.testing.assert_allclose(adj[0,0],expected)
        self.assertFalse(rej[0,0])
    def test_wilson_not_false_precision(self):
        lo,hi=wilson(0,300);self.assertAlmostEqual(lo,0);self.assertGreater(hi,0)
    def test_identical_statistics_repeat_exactly(self):
        rng=np.random.default_rng(17);x=rng.normal(size=(2,5,24,21));s=rng.choice([-1.,1.],size=(127,21))
        a=family_test(x,s);b=family_test(x,s)
        for av,bv in zip(a,b):np.testing.assert_array_equal(av,bv)

if __name__=='__main__':unittest.main()
