"""Resource anti-reset checks with a fake collector; no broker requests."""
from copy import deepcopy
from pathlib import Path
import unittest
from .budgets import historical_accounting,TrialBook
from .common import LabError
from .data import Acquisition,DataCatalogue
from .fixtures import programme,T
from .programs import Laboratory


class ResourceContracts(unittest.TestCase):
    def laboratory(self):
        manifest=programme();manifest['budget']['broker_requests']=6
        history=historical_accounting(Path(__file__).resolve().parents[2])
        return Laboratory(manifest,history,TrialBook({'RECEPTION':0,'V2':84},{'RECEPTION':0,'V2':21}))

    def test_inflated_remaining_or_kind_budget_is_rejected_on_restore(self):
        lab=self.laboratory();original=lab.checkpoint()
        for mode in ('total','kind','negative','boolean','inconsistent'):
            value=deepcopy(original)
            if mode=='total':value['acquisition_remaining']=7
            if mode=='kind':value['acquisition_budget']['M5']=7
            if mode=='negative':value['acquisition_budget']['M5']=-1
            if mode=='boolean':value['acquisition_remaining']=True
            if mode=='inconsistent':value['acquisition_remaining']=3
            with self.subTest(mode=mode),self.assertRaisesRegex(LabError,'ACQUISITION'):
                Laboratory.restore(value,lab.history)

    def test_full_page_reservation_conserves_total_and_kind_across_restore(self):
        class FakeCollector:
            def m5(self,*args):return {},[], 'EMPTY_AUTHENTIC_WINDOW'
        lab=self.laboratory();lab.acquisition.collector=FakeCollector()
        lab.acquisition.request({'provider':'PEPPERSTONE_OPEN_API','partition':'DEVELOPMENT','read_only':True,
            'automatic_retries':0,'instrument':'ARTIFICIAL','kind':'M5','start_ms':T-300000,'end_ms':T,
            'max_pages':3,'symbol_id':9,'digits':5,'account_scope':'ARTIFICIAL_ONLY'})
        self.assertEqual(lab.acquisition.remaining,3)
        restored=Laboratory.restore(lab.checkpoint(),lab.history)
        self.assertEqual(restored.acquisition.remaining,3)
        self.assertEqual(restored.acquisition.budget['M5'],3)

    def test_missing_transport_reserves_once_without_refund(self):
        a=Acquisition(DataCatalogue(),None,{'M5':3})
        plan={'provider':'PEPPERSTONE_OPEN_API','partition':'DEVELOPMENT','read_only':True,'automatic_retries':0,
            'instrument':'ARTIFICIAL','kind':'M5','start_ms':T-300000,'end_ms':T,'max_pages':3}
        with self.assertRaisesRegex(LabError,'TRANSPORT'):a.request(plan)
        self.assertEqual(a.remaining,0)
        with self.assertRaisesRegex(LabError,'BUDGET'):a.request(plan)
        self.assertEqual(a.remaining,0)


if __name__=='__main__':unittest.main()
