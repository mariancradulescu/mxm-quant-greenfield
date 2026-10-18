import unittest
from .verdict import project,SUMMARY_SHA

def assessment():
    return {'schema':'mxm.c-existing-economic-assessment.v1','existing_summary_sha256':SUMMARY_SHA,
            'decision':'NO_ADVANCEMENT_NONPOSITIVE_NET_OR_INCREMENT','complete_net_eur':-12.,
            'complete_matched_increment_eur':{'midpoint':1.,'quote_count':None},
            'campaign_armed':False,'orders_allowed':False,'alpha_certified':False,
            'HARD21_demonstrated':False,'scientific_recalculations':0,'new_experiment':False,
            'private_vector':['MUST_NOT_LEAVE'],'instrument':'PRIVATE'}

class Projection(unittest.TestCase):
    def test_only_qualitative_allowlist_leaves(self):
        p=project(assessment())
        self.assertEqual(p['model_net_after_costs'],'NEGATIVE')
        self.assertEqual(p['matched_increment'],{'midpoint':'POSITIVE','quote_count':'UNKNOWN'})
        self.assertNotIn('private_vector',p);self.assertNotIn('instrument',p)
        self.assertNotIn('complete_net_eur',p)
        self.assertFalse(p['experiment_repeated'])
    def test_invalid_identity_or_scope_stops(self):
        for field,value in [('existing_summary_sha256','0'*64),('orders_allowed',True),('decision','UNREVIEWED')]:
            a=assessment();a[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):project(a)
    def test_nonfinite_is_never_a_verdict(self):
        a=assessment();a['complete_net_eur']=float('nan')
        with self.assertRaises(ValueError):project(a)

if __name__=='__main__':unittest.main()
