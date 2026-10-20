"""Cold producer v3: artificial multi-program evidence exercises actual
Laboratory.checkpoint(), restore, catalogue monotonicity and event SHA chain.

Synthetic fixtures are NOT authenticated Pepperstone data and cannot satisfy
the separate native authenticity certification requirement.
"""
import unittest
from copy import deepcopy
from .common import digest
from .data import DataCatalogue
from .programs import Laboratory
from .execution import preserve_node
from .evidence_v3 import cold_attestation,native_adapter_attestation
from .test_integrated_protocol import LaboratoryIntegrationTests
from .protocol import ORIGINAL_PUBLIC

SRC='f'*40
RUN=24681357
HEAD='a'*40

class ColdV3ProducerTests(unittest.TestCase):
    @staticmethod
    def manifest(name):
        return {'instrument':name,'resolution':'M5','partition':'DEVELOPMENT',
                'start_ms':0,'end_ms':1800000,'source':'ARTIFICIAL_V3',
                'source_sha256':'a'*64,'available_at_ms':1800000,
                'session_semantics':'ARTIFICIAL','completeness':'CONFIRMED_COMPLETE',
                'account_scope':'FIXTURE_ONLY'}
    @staticmethod
    def bar(t):
        return {'t':t,'available_at':t+300000,'open':1.,'high':1.2,
                'low':0.9,'close':1.1,'volume':1}
    def fixture(self):
        base=LaboratoryIntegrationTests()
        book,m,history=base.setup_programme()
        mb=deepcopy(m);mb['id']='INTEGRATION_FIXTURE_B'
        book.register_programme({
            'id':mb['id'],'family':'TECH_FIXTURE','lane':'V2',
            'identity_cap':0,'observation_cap':0,
            'manifest_sha256':digest(mb)})
        p={'source_sha':SRC,'sequence':21,'pending':None,'safe_stop':True,
           'history':history,'trial_book':book.export(),
           'programmes':{},'shared_catalogue':DataCatalogue().export(),
           'programme_execution_history':[]}
        def step(lab,task,new_instrument=None):
            before=sorted(p['shared_catalogue']['assets'])
            if new_instrument:
                lab.cache.ingest(self.manifest(new_instrument),
                                 [self.bar(300000)])
            result=lab.execute(task)
            lab.next()
            previous=p['programme_execution_history'][-1]['event_sha256'] if p[
                'programme_execution_history'] else None
            event={'programme':lab.m['id'],'task':task,
                   'result_sha256':digest(result),
                   'native_checkpoint_sequence':21,
                   'within_segment_step':len(p['programme_execution_history'])+1,
                   'catalogue_before_asset_ids':before,
                   'programme_budget_remaining':lab.acquisition.remaining,
                   'previous_event_sha256':previous}
            preserve_node(p,lab)
            event['catalogue_after_asset_ids']=sorted(p['shared_catalogue']['assets'])
            event['event_sha256']=digest(event)
            p['programme_execution_history'].append(event)
        A=Laboratory(m,history,book,cache=DataCatalogue.restore(p['shared_catalogue']))
        step(A,A.next())
        B=Laboratory(mb,history,book,cache=DataCatalogue.restore(p['shared_catalogue']))
        step(B,B.next(),'NEW_B_ONLY')
        A=Laboratory.restore(p['programmes'][m['id']],history,
                             shared_catalogue=p['shared_catalogue'])
        step(A,A.next())
        B=Laboratory.restore(p['programmes'][mb['id']],history,
                             shared_catalogue=p['shared_catalogue'])
        step(B,B.next())
        p['trial_book']=book.export()
        admission={'programmes':[m,mb]}
        public={'source_sha':SRC,'sequence':21,'pending':None,'safe_stop':True,
                'last_run_id':RUN,'ciphertext_sha256':'c'*64,
                'accounting':book.view(),
                'original_public_sha256':ORIGINAL_PUBLIC}
        return p,public,admission
    def attest(self,p,s,a):
        return cold_attestation(p,s,a,HEAD,RUN,SRC)
    def test_actual_lab_A_B_A_bring_B_new_assets_to_A(self):
        p,s,a=self.fixture();proof=self.attest(p,s,a)
        self.assertEqual(proof['schema'],'mxm.integrated-cold-readback.v3')
        self.assertTrue(proof['multi_program_A_B_A_verified'])
        self.assertEqual(len(proof['programme_checkpoints']),2)
        self.assertEqual(proof['orders'],proof['new_outcomes'])
        self.assertGreater(proof['shared_catalogue_asset_count'],0)
        self.assertEqual(proof['authentic_nonoutcome_results'],[])
        with self.assertRaises(Exception):native_adapter_attestation(proof)
    def test_modified_event_hash_cannot_be_certified(self):
        p,s,a=self.fixture()
        p['programme_execution_history'][1]['result_sha256']='0'*64
        with self.assertRaises(Exception):self.attest(p,s,a)
    def test_removed_B_asset_rejected_at_cold_restore(self):
        p,s,a=self.fixture()
        b=list(p['shared_catalogue']['assets'])[0]
        p['shared_catalogue']['assets'].pop(b)
        p['shared_catalogue']['rows'].pop(b)
        with self.assertRaises(Exception):self.attest(p,s,a)
    def test_false_order_or_refund_rejected(self):
        p,s,a=self.fixture()
        s['accounting']['refunds']=1
        with self.assertRaises(Exception):self.attest(p,s,a)
    def test_abandoned_or_unfinished_program_not_accepted(self):
        p,s,a=self.fixture()
        p['programmes'][a['programmes'][1]['id']]['progress']['safe_stop']=False
        with self.assertRaises(Exception):self.attest(p,s,a)

if __name__=='__main__':unittest.main()
