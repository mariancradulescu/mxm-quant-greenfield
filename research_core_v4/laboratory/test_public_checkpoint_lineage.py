"""Artificial commit metadata; no private checkpoint or runtime acceptance."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from .common import LabError
from .live_preflight_v3 import EVIDENCE,evidence_origin

class PublicCheckpointLineage(unittest.TestCase):
    def fixture(self):
        records={'a'*40:{'sha':'a'*40,'parents':[{'sha':'b'*40}]},
                 'b'*40:{'sha':'b'*40,'parents':[{'sha':EVIDENCE}]}}
        return records,SimpleNamespace(json=lambda path:records[path.split('/')[-1]])

    def test_exact_original_and_linear_recovery_successor_are_conserved(self):
        records,route=self.fixture()
        self.assertEqual(evidence_origin(route,EVIDENCE)['successor_commits'],0)
        self.assertEqual(evidence_origin(route,'a'*40)['successor_commits'],2)

    def test_fork_cycle_spoof_and_insufficient_history_do_not_authorize_origin(self):
        for mode in ('fork','cycle','spoof','root','bound'):
            records,route=self.fixture()
            if mode=='fork':records['a'*40]['parents'].append({'sha':EVIDENCE})
            elif mode=='cycle':records['b'*40]['parents']=[{'sha':'a'*40}]
            elif mode=='spoof':records['a'*40]['sha']='c'*40
            elif mode=='root':records['b'*40]['parents']=[]
            with self.subTest(mode=mode),self.assertRaises(LabError):
                evidence_origin(route,'a'*40,limit=1 if mode=='bound' else 256)

if __name__=='__main__':unittest.main()
