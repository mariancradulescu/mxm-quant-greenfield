"""New read-only summary interpretation cases; no historical suite execution."""
import copy
import unittest
from unittest.mock import patch
from . import readback as r

def summary():
    return {'schema':'mxm.quote.path.empirical.summary.v1',
            'mechanism':'PRICE_SPREAD_TEMPORAL_ORDER_RESPONSE_V1','design_sha256':r.DESIGN_SHA,
            'broker_requests':0,'orders':0,'fills':0,'protected_forward':False,
            'alpha_certified':False,'HARD21_demonstrated':False,
            'portfolio':{'halt':'END','selected':[{}],'closed':[{}],'complete_net_eur':1.},
            'accounting':{k:{'paired_model_increment_eur':.5,'paired_entries':1,'unknown':0}
                          for k in ('midpoint','quote_count')},
            'temporal_halves':[],'weekly':{},'cost_terms':'SYNTHETIC','uncertainty':'EXPLORATORY'}

class Readback(unittest.TestCase):
    def test_positive_is_not_certification_or_activation(self):
        s=summary();before=copy.deepcopy(s);out=r.assess_summary(s)
        self.assertEqual(s,before)
        self.assertEqual(out['decision'],'EXPLORATORY_POSITIVE_REQUIRES_UNEXPOSED_CONFIRMATION')
        self.assertFalse(out['alpha_certified']);self.assertFalse(out['campaign_armed'])
        self.assertEqual(out['scientific_recalculations'],0)

    def test_negative_is_not_rescued_by_positive_comparator(self):
        s=summary();s['portfolio']['complete_net_eur']=-1.
        self.assertEqual(r.assess_summary(s)['decision'],'NO_ADVANCEMENT_NONPOSITIVE_NET_OR_INCREMENT')

    def test_partial_comparator_is_not_promoted(self):
        s=summary();s['accounting']['midpoint']['paired_entries']=0
        out=r.assess_summary(s)
        self.assertIsNone(out['complete_matched_increment_eur']['midpoint'])
        self.assertEqual(out['decision'],'NO_ADVANCEMENT_INCOMPLETE_SUPPORT')

    def test_unknown_model_stays_unknown(self):
        s=summary();s['portfolio'].update(halt='FIRST_SELECTED_UNKNOWN_EXIT',complete_net_eur=None)
        self.assertIsNone(r.assess_summary(s)['complete_net_eur'])

    def test_invalid_scope_or_nonfinite_stops(self):
        for field,value in (('orders',1),('protected_forward',True)):
            s=summary();s[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):r.assess_summary(s)
        s=summary();s['portfolio']['complete_net_eur']=float('nan')
        with self.assertRaises(ValueError):r.assess_summary(s)

    def test_cold_workload_requires_bound_source_and_fresh_attempt(self):
        env={'GITHUB_REPOSITORY':r.REPO,'GITHUB_RUN_ATTEMPT':'1','GITHUB_EVENT_NAME':'workflow_run',
             'GITHUB_JOB':'cold-economic-readback','C_SOURCE_SHA':'a'*40,'C_EXPECTED_SOURCE_SHA':'a'*40}
        with patch.dict(r.os.environ,env,clear=True):r.workload('cold')
        env['C_SOURCE_SHA']='b'*40
        with patch.dict(r.os.environ,env,clear=True),self.assertRaises(ValueError):r.workload('cold')

if __name__=='__main__':unittest.main()
