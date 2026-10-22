"""Only artificial unit probes here; they do not attest authentic market data."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from .test_integrated_protocol import LaboratoryIntegrationTests
from .programs import Laboratory
from .execution import preserved_pepperstone_nonoutcome

class PreservedCorpusBindingTests(unittest.TestCase):
    def setup_lab(self):
        book,m,history=LaboratoryIntegrationTests().setup_programme()
        return Laboratory(m,history,book)
    @staticmethod
    def fixture():
        t=900000
        return {'catalog':{'full':{'1':{'digits':5}}},
                'raw_quote_receipts':[{'symbol_id':1,'boundary_ms':t,
                  'sides':{'bid':{'state':'AUTHENTIC_CAUSAL_QUOTE',
                                   'timestamp_ms':t-1000,'price':1.01,'age_ms':1000,'source_has_more':False},
                           'ask':{'state':'AUTHENTIC_CAUSAL_QUOTE',
                                   'timestamp_ms':t-1000,'price':1.02,'age_ms':1000,'source_has_more':False}},
                  'pages':[{'side':s,'hasMore':False,'encoded':[{'timestamp':t-1000,'tick':p}]} for s,p in [('bid',101000),('ask',102000)]]}]}
    def test_zero_wire_nonoutcome_operator_preserves_quote_provenance(self):
        lab=self.setup_lab()
        view=lab.book.view();budget=lab.acquisition.remaining
        corpus=self.fixture();original=deepcopy(corpus)
        with patch('research_core_v4.laboratory.runtime.preserved_registry',
                   return_value={'cached_input':{'ciphertext_sha256':'a'*64}}):
            proof=preserved_pepperstone_nonoutcome(lab,corpus,1)
        self.assertEqual(proof['classification'],'AUTHENTIC_CORPUS_NONOUTCOME_VERIFIED')
        self.assertEqual(proof['verified_quote_rows'],2)
        self.assertEqual(proof['broker_requests'],proof['economic_outcomes'])
        self.assertEqual(proof['orders'],0)
        self.assertEqual(lab.book.view(),view)
        self.assertEqual(lab.acquisition.remaining,budget)
        self.assertEqual(corpus,original)
        meta=lab.cache.assets[proof['asset_ids'][0]]
        self.assertEqual(meta['trust'],'AUTHENTICATED_NATIVE_CUSTODY')
        self.assertEqual(meta['completeness'],'UNRESOLVED')
        self.assertEqual(lab.cache.query('1','BID_ASK',840000,900001,authentic_only=True),[])
        self.assertEqual(len(lab.cache.view(proof['asset_ids'][0],900000)),2)
    def test_no_fabrication_on_missing_or_invalid_input(self):
        lab=self.setup_lab()
        with patch('research_core_v4.laboratory.runtime.preserved_registry',
                   return_value={'cached_input':{'ciphertext_sha256':'a'*64}}):
            for c in ({}, {'catalog':{'full':{}},'raw_quote_receipts':[]}):
                with self.assertRaises(Exception):preserved_pepperstone_nonoutcome(lab,c,1)
            bad=self.fixture();bad['raw_quote_receipts'][0]['sides']['bid']['price']=-1
            with self.assertRaises(Exception):preserved_pepperstone_nonoutcome(lab,bad,1)
            with self.assertRaises(Exception):preserved_pepperstone_nonoutcome(lab,self.fixture(),33)

    def test_selected_quote_must_match_conserved_raw_page(self):
        for mutation in ('price','missing_page','pagination'):
            corpus=self.fixture();q=corpus['raw_quote_receipts'][0]
            if mutation=='price':q['sides']['bid']['price']=1.011
            elif mutation=='missing_page':q['pages'].pop(0)
            else:q['pages'][0]['hasMore']=True
            with self.subTest(mutation=mutation),patch('research_core_v4.laboratory.runtime.preserved_registry',
                return_value={'cached_input':{'ciphertext_sha256':'a'*64}}),self.assertRaises(Exception):
                preserved_pepperstone_nonoutcome(self.setup_lab(),corpus,1)

if __name__=='__main__':unittest.main()
