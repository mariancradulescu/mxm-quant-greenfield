import unittest
from copy import deepcopy
from .common import digest,LabError
from .data import DataCatalogue
from .programs import Laboratory
from .execution import next_admitted_programme,preserve_node
from . import test_integrated_protocol as fixtures

class IntegratedProgrammeSelectionTests(unittest.TestCase):
    def fixture(self,tied=False):
        book,base,history=fixtures.LaboratoryIntegrationTests().setup_programme()
        manifests=[]
        for ident,first,second in [('SCHED_A',10,30),('SCHED_B',20,40)]:
            m=deepcopy(base);m['id']=ident
            if tied:first=10
            m['tasks']['first']['priority']=first;m['tasks']['second']['priority']=second
            book.register_programme({'id':ident,'family':'TECH_FIXTURE','lane':'V2',
                'identity_cap':0,'observation_cap':0,'manifest_sha256':digest(m)})
            manifests.append(m)
        return book,history,{'programmes':{},'shared_catalogue':DataCatalogue().export()}, {'programmes':manifests}

    def test_prospective_priorities_produce_actual_A_B_resume_A(self):
        book,history,private,admission=self.fixture();private['history']=history
        before=book.export();executed=[]
        for _ in range(4):
            m=next_admitted_programme(private,admission,book)
            saved=private['programmes'].get(m['id'])
            lab=Laboratory.restore(saved,history,shared_catalogue=private['shared_catalogue']) if saved else Laboratory(m,history,book,cache=DataCatalogue.restore(private['shared_catalogue']))
            lab.book=book;task=lab.next();lab.execute(task);lab.next();preserve_node(private,lab)
            executed.append((m['id'],task))
        self.assertEqual(executed,[('SCHED_A','first'),('SCHED_B','first'),('SCHED_A','second'),('SCHED_B','second')])
        self.assertIsNone(next_admitted_programme(private,admission,book))
        self.assertEqual(book.export(),before)
        self.assertTrue(all(s['progress']['safe_stop'] for s in private['programmes'].values()))

    def test_ambiguous_pending_programme_is_never_scheduled_around(self):
        book,history,private,admission=self.fixture();private['history']=history
        lab=Laboratory(admission['programmes'][1],history,book)
        saved=lab.checkpoint();saved['progress']['pending']={'task':'first'}
        private['programmes']['SCHED_B']=saved
        with self.assertRaises(LabError):next_admitted_programme(private,admission,book)

    def test_ties_follow_sealed_admission_order(self):
        book,history,private,admission=self.fixture(tied=True);private['history']=history
        self.assertEqual(next_admitted_programme(private,admission,book)['id'],'SCHED_A')
        admission['programmes'].reverse()
        self.assertEqual(next_admitted_programme(private,admission,book)['id'],'SCHED_B')

    def test_global_pending_and_changed_saved_manifest_are_refused(self):
        book,history,private,admission=self.fixture();private['history']=history
        private['pending']={'phase':'UNCERTAIN'}
        with self.assertRaises(LabError):next_admitted_programme(private,admission,book)
        private['pending']=None
        lab=Laboratory(admission['programmes'][1],history,book)
        saved=lab.checkpoint();saved['programme']['version']+=1
        private['programmes']['SCHED_B']=saved
        with self.assertRaises(LabError):next_admitted_programme(private,admission,book)
