"""Regression for A -> B -> resume A on the sealed laboratory cache.

Artificial market bars, zero broker calls/outcomes; never economic evidence.
"""
import unittest
from copy import deepcopy
from .common import digest
from .data import DataCatalogue
from .programs import Laboratory
from .execution import preserve_node
from .test_integrated_protocol import LaboratoryIntegrationTests

class SharedCatalogueSuccessor(unittest.TestCase):
    def setup(self):
        book, ma, history = LaboratoryIntegrationTests().setup_programme()
        mb = deepcopy(ma)
        mb['id'] = 'INTEGRATION_FIXTURE_B'
        book.register_programme({'id':mb['id'], 'family':'TECH_FIXTURE', 'lane':'V2',
                                 'identity_cap':0, 'observation_cap':0,
                                 'manifest_sha256':digest(mb)})
        return book, ma, mb, history

    @staticmethod
    def manifest(instrument, partition='DEVELOPMENT'):
        return {'instrument':instrument,'resolution':'M5','partition':partition,
                'start_ms':0,'end_ms':1800000,'source':'ARTIFICIAL_CACHE_TEST',
                'source_sha256':'a'*64,'available_at_ms':1800000,
                'session_semantics':'FIXTURE_NO_SESSION_ASSUMPTIONS',
                'completeness':'CONFIRMED_COMPLETE','account_scope':'FIXTURE_ONLY'}

    @staticmethod
    def bar(t, close=1.1, volume=1):
        return {'t':t, 'available_at':t+300000, 'open':1.0,
                'high':1.2, 'low':0.9, 'close':close,'volume':volume}

    def test_A_B_resume_A_keeps_shared_assets_quarantine_and_budgets(self):
        book, ma, mb, history = self.setup()
        private={'programmes':{},'shared_catalogue':DataCatalogue().export()}
        a=Laboratory(ma,history,book)
        aid=a.cache.ingest(self.manifest('A'),[self.bar(0)])
        a.acquisition.budget={'M5':2,'H1':0,'BID_ASK':0,'TOTAL':2}
        a.acquisition.remaining=1
        a.acquisition.receipts=[{'state':'ARTIFICIAL','plan_sha256':'e'*64}]
        a.execute(a.next())
        preserve_node(private,a)
        saved_a=deepcopy(private['programmes'][ma['id']])
        b=Laboratory(mb,history,book,cache=DataCatalogue.restore(private['shared_catalogue']))
        bid=b.cache.ingest(self.manifest('B'),[
            self.bar(300000),self.bar(600000,volume=-1),
            self.bar(900000,close=1.05),self.bar(900000,close=1.1)])
        self.assertGreaterEqual(len(b.cache.quarantine),2)
        b.execute(b.next())
        preserve_node(private,b)
        before=deepcopy(private['shared_catalogue'])
        self.assertEqual(set(before['assets']),{aid,bid})
        self.assertTrue(before['assets'][bid]['conflicts'])
        self.assertTrue(before['assets'][bid]['invalid'])
        self.assertEqual(before['assets'][bid]['source_sha256'],'a'*64)

        # The restored A snapshot predates B; it must see B's valid shared refs.
        a2=Laboratory.restore(saved_a,history,shared_catalogue=private['shared_catalogue'])
        self.assertIn(bid,a2.cache.assets)
        self.assertEqual(a2.acquisition.remaining,1)
        self.assertEqual(a2.acquisition.budget['M5'],2)
        self.assertEqual(a2.acquisition.receipts,saved_a['native_receipts'])
        a2.execute(a2.next())
        preserve_node(private,a2)
        self.assertEqual(private['shared_catalogue'],before)
        self.assertEqual(set(private['programmes']),{ma['id'],mb['id']})
        self.assertEqual(private['programmes'][mb['id']]['progress'],b.checkpoint()['progress'])
        self.assertEqual(private['programmes'][ma['id']]['acquisition_remaining'],1)

        # A direct stale checkpoint must never silently erase B from shared state.
        stale=Laboratory.restore(saved_a,history)
        with self.assertRaises(Exception):preserve_node(private,stale)
        self.assertEqual(private['shared_catalogue'],before)

    def test_conflicting_common_asset_metadata_fails_closed(self):
        book,ma,_,history=self.setup()
        a=Laboratory(ma,history,book)
        a.cache.ingest(self.manifest('A'),[self.bar(0)])
        saved=a.checkpoint()
        shared=deepcopy(saved['catalogue'])
        ident=next(iter(shared['assets']))
        shared['assets'][ident]['source']='FORGED'
        with self.assertRaises(Exception):
            Laboratory.restore(saved,history,shared_catalogue=shared)

    def test_partition_isolation(self):
        cat=DataCatalogue()
        p=cat.ingest(self.manifest('CONFIRMATION_ONLY','CONFIRMATION'),[self.bar(0)])
        self.assertFalse(cat.query('CONFIRMATION_ONLY','M5',0,300000))
        with self.assertRaises(Exception):cat.view(p,300000)

if __name__=='__main__':
    unittest.main()
