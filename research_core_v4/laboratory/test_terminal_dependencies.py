"""Adversarial terminality/ordering proofs; fixtures are not market evidence."""
import unittest
from copy import deepcopy
from .common import LabError,digest
from .programs import Laboratory
from . import test_integration as integration_fixture

class TerminalDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=integration_fixture.IntegratedReception()
        integration_fixture.IntegratedReception.setUpClass()

    def test_all_tasks_cannot_be_forged_as_skipped(self):
        lab=self.fixture.lab()
        cp=lab.checkpoint()
        cp['progress'].update(skipped={task:'DECLARED_DEPENDENCY_VERDICT' for task in lab.m['tasks']},
                              safe_stop=True,stop_reason='AUTHORIZED_PROGRAMME_COMPLETE')
        with self.assertRaises(LabError):Laboratory.restore(cp,self.fixture.history)

    def test_unfinished_dependency_cannot_justify_skip(self):
        lab=self.fixture.lab();cp=lab.checkpoint()
        cp['progress']['skipped']['cheap_screen']='DECLARED_DEPENDENCY_VERDICT'
        with self.assertRaises(LabError):Laboratory.restore(cp,self.fixture.history)

    def test_rehashed_journal_cannot_reverse_dependency_execution(self):
        lab=self.fixture.finish(self.fixture.lab());cp=lab.checkpoint()
        cp['progress']['journal'].reverse();previous=None
        for i,event in enumerate(cp['progress']['journal'],1):
            event['sequence']=i;event['previous']=previous
            event['sha256']=digest({k:v for k,v in event.items() if k!='sha256'})
            previous=event['sha256']
        with self.assertRaises(LabError):Laboratory.restore(cp,self.fixture.history)

    def test_real_dependency_verdicts_and_transitive_skips_restore(self):
        from .fixtures import programme
        for missing in (False,True):
            manifest=programme()
            if missing:manifest['tasks']['validate_data']['input']['rows']=[]
            lab=self.fixture.finish(self.fixture.lab(manifest))
            restored=Laboratory.restore(lab.checkpoint(),self.fixture.history)
            self.assertEqual(restored.state,lab.state)
            self.assertTrue(restored.state['safe_stop'])
