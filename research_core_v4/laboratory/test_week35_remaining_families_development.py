from decimal import Decimal as D
import unittest
from .week35_remaining_families_development import validate_spec,disposition,LABEL
from .test_week35_breakout_development import W35BreakoutTests
from .csharp_native_portfolio_independent_mark import MarkParityError
class RemainingFamiliesTests(W35BreakoutTests):
    def test_two_fixed_families_and_four_dependent_leaves(self):
        s=validate_spec();self.assertEqual(s['strategies'],['TrendOnly','RangeFade'])
        self.assertEqual(s['budget']['dependent_model_leaves'],4)
        self.assertEqual(s['budget']['mechanisms'],2)
        self.assertTrue(disposition([D(199),D(198)]).startswith('REJECT'))
        self.assertTrue(disposition([D(201),D(198)]).startswith('INCONCLUSIVE'))
    def test_new_label_routes_only_exact_w35_snapshot(self):
        self.reference(self.w35(),LABEL)
        a=self.w35();a['source_run']=39917922508
        with self.assertRaisesRegex(MarkParityError,'W35_NATIVE_BINDING'):self.reference(a,LABEL)
    def test_complete_ledger_gate_checks_family_and_terminal_stop_suffix(self):
        import tempfile,json,hashlib
        from pathlib import Path
        from unittest.mock import patch
        from .test_terminal_open_stop_completeness import fixture
        from .csharp_native_portfolio_independent_mark import independent_terminal_mark
        for family in ('TrendOnly','RangeFade','Breakout'):
            book,source,terms,report=fixture(1,False)
            report['classification']=LABEL;report['modeled_parameters']['strategy']=family
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'synthetic.json';raw=json.dumps(terms).encode();path.write_bytes(raw)
                report['captured_terms_sha256']=hashlib.sha256(raw).hexdigest()
                with patch('research_core_v4.laboratory.csharp_native_portfolio_independent_mark.authenticated_shape_quotes',return_value=(book,source)):
                    if family=='Breakout':
                        with self.assertRaisesRegex(MarkParityError,'W35_FIXED_DEVELOPMENT_SCOPE'):
                            independent_terminal_mark('synthetic',report,path)
                    else:
                        result=independent_terminal_mark('synthetic',report,path)
                        self.assertEqual(result['terminal_open_stop_paths_independently_checked'],1)
class RemainingResultPreservationTests(unittest.TestCase):
    def test_original_archive_and_receipt_verify_without_key(self):
        from .verify_week35_remaining_result import verify
        self.assertFalse(verify()['decrypted'])
    def test_changed_part_receipt_or_source_cannot_be_accepted(self):
        import shutil,tempfile,json
        from pathlib import Path
        from .verify_week35_remaining_result import ROOT,verify
        for mode in ('part','receipt','source'):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'evidence';shutil.copytree(ROOT,root)
                if mode=='part':(root/'part-00.b64').write_text('AAAA')
                elif mode=='receipt':(root/'receipt.json').write_text('{}')
                else:
                    p=root/'MANIFEST.json';m=json.loads(p.read_bytes());m['source_commit']='0'*40;p.write_text(json.dumps(m))
                with self.subTest(mode=mode),self.assertRaises(ValueError):verify(root)
if __name__=='__main__':unittest.main()
