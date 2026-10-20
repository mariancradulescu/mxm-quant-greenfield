import unittest
from copy import deepcopy
from .data import verify_quote_reference
from . import test_nonoutcome_adapter as fixture_module

class RawQuoteReceiptTests(unittest.TestCase):
    def fixture(self):return fixture_module.PreservedCorpusBindingTests.fixture()['raw_quote_receipts'][0]
    def test_async_empty_and_partial_remain_distinct(self):
        q=self.fixture();q['pages'][1]['encoded']=[]
        q['sides']['ask']={'state':'EMPTY_AUTHENTIC_WINDOW','source_has_more':False}
        q['pages'][0]['hasMore']=True;q['sides']['bid']['source_has_more']=True
        before=deepcopy(q);r=verify_quote_reference(q)
        self.assertEqual((r['verified_selected_sides'],r['empty_sides'],r['partial_pages']),(1,1,1))
        self.assertFalse(r['continuous_coverage_verified']);self.assertEqual(q,before)
        q['pages'].pop();q['sides']['ask']={'state':'TRANSPORT_UNRESOLVED','failure_class':'TimeoutError'}
        self.assertEqual(verify_quote_reference(q)['unresolved_sides'],1)
    def test_raw_clock_type_identity_and_duplicate_pages_are_rejected(self):
        for kind in ('future','delta','float','duplicate','age','raw_price','empty_fabrication'):
            q=self.fixture()
            if kind=='future':q['pages'][0]['encoded'][0]['timestamp']=q['boundary_ms']+1
            elif kind=='delta':q['pages'][0]['encoded'].append({'timestamp':1,'tick':0})
            elif kind=='float':q['pages'][0]['encoded'][0]['tick']=101000.1
            elif kind=='duplicate':q['pages'][1]=deepcopy(q['pages'][0])
            elif kind=='age':q['sides']['bid']['age_ms']=0
            elif kind=='raw_price':q['pages'][0]['encoded'][0]['tick']+=1
            else:q['pages'][0]['encoded']=[]
            with self.subTest(kind=kind),self.assertRaises(Exception):verify_quote_reference(q)
    def test_all_same_millisecond_revisions_are_decoded(self):
        q=self.fixture();q['pages'][0]['encoded'].append({'timestamp':0,'tick':1})
        q['sides']['bid']['price']=1.01001
        self.assertEqual(verify_quote_reference(q)['decoded_tick_records'],3)
