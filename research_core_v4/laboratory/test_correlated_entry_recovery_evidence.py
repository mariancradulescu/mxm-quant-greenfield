"""Reject corruption and promotion; applicability is distinct from original integrity."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from .verify_correlated_entry_recovery import ROOT, REL, verify
from .correlated_entry_recovery_checks import proof
class Evidence(unittest.TestCase):
    def test_original(self):
        self.assertTrue(verify()['original_archives_verified'])
    def mutate(self, file, action):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(ROOT/REL,root/REL)
            target=root/REL/file
            target.write_bytes(action(target.read_bytes()))
            with self.assertRaises((ValueError,KeyError)):
                verify(root)
    def test_part_corruption(self):
        self.mutate('recovery-00.b64',lambda b: b'A'+b[1:])
    def test_receipt_substitution(self):
        self.mutate('cli-receipt.json',lambda b: b+b' ')
    def test_source_substitution(self):
        self.mutate('MANIFEST.json',lambda b:b.replace(b'e1064495',b'a1064495'))
    def test_false_native_promotion(self):
        self.mutate('MANIFEST.json',lambda b:b.replace(b'"native_runtime_reception": false',b'"native_runtime_reception": true'))
    def test_false_economic_promotion(self):
        self.mutate('MANIFEST.json',lambda b:b.replace(b'"economic_edge_proven": false',b'"economic_edge_proven": true'))
    def test_proof_semantics(self):
        original=json.loads((ROOT/REL/'proof.json').read_bytes())
        for key in ('native_ctrader_execution','native_storage_durability_proven','economic_edge_proven','hard21_proven'):
            value=copy.deepcopy(original);value[key]=True
            with self.assertRaises(ValueError):proof(value)
        for key in ('resubmissions','unique_recorded_entries'):
            value=copy.deepcopy(original);value['cases'][1][key]+=1
            with self.assertRaises(ValueError):proof(value)
    def test_future_code_is_not_original_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);shutil.copytree(ROOT/REL,root/REL)
            result=verify(root)
            self.assertFalse(result['current_implementation_matches_original'])
            self.assertTrue(result['changed_implementation_paths'])
            self.assertTrue(result['original_archives_verified'])
if __name__=='__main__':unittest.main()
