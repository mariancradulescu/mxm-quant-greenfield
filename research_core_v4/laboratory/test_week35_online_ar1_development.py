from decimal import Decimal as D
import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from .week35_online_ar1_development import validate_spec,disposition,LABEL
from .test_week35_breakout_development import W35BreakoutTests
from .csharp_native_portfolio_independent_mark import independent_terminal_mark,MarkParityError
from .test_terminal_open_stop_completeness import fixture
class OnlineAr1Tests(W35BreakoutTests):
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
if __name__=='__main__':unittest.main()
