from decimal import Decimal as D
import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from .week35_online_ar1_development import validate_spec,disposition,LABEL
from .test_week35_breakout_development import W35BreakoutTests
from .csharp_native_portfolio_independent_mark import independent_terminal_mark,MarkParityError
from .test_terminal_open_stop_completeness import fixture
class OnlineAr1Tests(W35BreakoutTests):
    def test_uploaded_members_match_actual_finalizer_output_directory(self):
        import shlex
        from .week35_online_ar1_development import ROOT
        w=json.loads((ROOT/'.github/workflows/mxm-week35-online-ar1-development.yml').read_bytes())
        steps=w['jobs']['online-ar1-development']['steps']
        finalize=next(x['run'] for x in steps if 'run' in x and 'week35_online_ar1_development' in x['run'] and ' admit' not in x['run'])
        output=shlex.split(finalize)[-1]
        upload=next(x['with'] for x in steps if 'uses' in x and x['uses'].startswith('actions/upload-artifact@'))
        self.assertEqual(set(upload['path'].splitlines()),{output+'/receipt.json',output+'/full-result.mxmenc'})
        self.assertEqual(upload['if-no-files-found'],'error')
    def test_closed_source_is_preserved_but_changed_current_code_cannot_execute_old_study(self):
        validate_spec()
        with self.assertRaisesRegex(ValueError,'W35_FROZEN_IMPLEMENTATION'):
            validate_spec(require_current_implementation=True)
    def test_frozen_one_learner_two_leaves_no_refit(self):
        s=validate_spec();self.assertEqual(s['strategies'],['OnlineAr1'])
        self.assertEqual(s['budget']['dependent_model_leaves'],2)
        self.assertEqual(s['budget']['mechanisms'],1)
        self.assertTrue(disposition([D(200),D(200)]).startswith('REJECT'))
        self.assertTrue(disposition([D(201),D(198)]).startswith('INCONCLUSIVE'))
    def test_exact_w35_source_required(self):
        self.reference(self.w35(),LABEL)
        a=self.w35();a['source_run']=39917922508
        with self.assertRaisesRegex(MarkParityError,'W35_NATIVE_BINDING'):self.reference(a,LABEL)
    def test_wrong_family_or_exit_cannot_enter_online_reconciliation(self):
        for variant in ('valid','family','exit','optin'):
            book,source,terms,report=fixture(1,False)
            report['classification']=LABEL
            p=report['modeled_parameters'];p.update(strategy='OnlineAr1',exit_policy='NeutralFlat',online_ar1=True)
            if variant=='family':p['strategy']='RangeFade'
            if variant=='exit':p['exit_policy']='ReverseOnly'
            if variant=='optin':p['online_ar1']=False
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'synthetic.json';raw=json.dumps(terms).encode();path.write_bytes(raw)
                report['captured_terms_sha256']=hashlib.sha256(raw).hexdigest()
                with patch('research_core_v4.laboratory.csharp_native_portfolio_independent_mark.authenticated_shape_quotes',return_value=(book,source)):
                    if variant=='valid':
                        self.assertEqual(independent_terminal_mark('synthetic',report,path)['terminal_open_stop_paths_independently_checked'],1)
                    else:
                        with self.assertRaises(MarkParityError):independent_terminal_mark('synthetic',report,path)
class OnlineResultPreservationTests(unittest.TestCase):
    def test_pinned_reproduction_original_failure_and_receipt_without_key(self):
        from .verify_week35_online_ar1_result import verify
        result=verify();self.assertFalse(result['decrypted'])
        self.assertFalse(result['original_ciphertext_preserved'])
        self.assertFalse(result['independent_evidence'])
    def test_corrupted_archive_receipt_source_and_false_original_claim_rejected(self):
        import shutil
        from .verify_week35_online_ar1_result import ROOT,verify
        for mode in ('part','receipt','source','original'):
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'evidence';shutil.copytree(ROOT,path)
                if mode=='part':(path/'part-00.b64').write_text('AAAA')
                elif mode=='receipt':(path/'receipt.json').write_text('{}')
                else:
                    p=path/'MANIFEST.json';m=json.loads(p.read_bytes())
                    if mode=='source':m['source_commit']='0'*40
                    else:m['original_ciphertext_preserved']=True
                    p.write_text(json.dumps(m))
                with self.subTest(mode=mode),self.assertRaises(ValueError):verify(path)
if __name__=='__main__':unittest.main()
