from decimal import Decimal as D
import copy,unittest
from .week35_breakout_development import validate_spec,disposition,LABEL
from .test_csharp_week_source_routing import WeekCustodyRoutingTests,snapshot
from .csharp_native_portfolio_independent_mark import MarkParityError
class W35BreakoutTests(WeekCustodyRoutingTests):
    def w35(self):
        a=snapshot();a.update(source_run=39946364621,source_code_sha='b54ee59548846ad8013b25965dbe4bcb19d4a978',
          source_private_sha256='2b37063a948d7b761a7f854e59649793ba1d5ff5e30a7e5255b03f4042cadb13',
          source_ciphertext_sha256='0d1badd1a944eeac7a67f1f7c87e05d26c1ea14ea016a0ea25fbb40ce7cb92ee')
        return a
    def test_explicit_w35_provenance_and_cross_week_refusal(self):
        self.assertEqual(self.reference(self.w35(),LABEL)(D(1000),D('1.1'),D('1.1'),D('1.11')),D('.03'))
        with self.assertRaisesRegex(MarkParityError,'W35_NATIVE_BINDING'):self.reference(snapshot(),LABEL)
        for field,bad in [('source_run',39917922508),('source_code_sha','0'*40),
                          ('source_private_sha256','0'*64),('source_ciphertext_sha256','0'*64),
                          ('source_crypto_authenticated_by_week_native_replay',False)]:
            a=self.w35();a[field]=bad
            with self.subTest(field=field),self.assertRaisesRegex(MarkParityError,'W35_NATIVE_BINDING'):
                self.reference(a,LABEL)
    def test_finite_prospective_rules_and_no_positive_promotion(self):
        self.assertEqual(validate_spec()['strategy'],'Breakout')
        self.assertTrue(disposition([D(199),D(198)]).startswith('REJECT'))
        self.assertTrue(disposition([D(201),D(199)]).startswith('INCONCLUSIVE'))
        self.assertTrue(disposition([D(201),D(202)]).startswith('INCONCLUSIVE'))
        with self.assertRaises(ValueError):disposition([D(201)])
        with self.assertRaises(ValueError):disposition([D('NaN'),D(201)])
if __name__=='__main__':unittest.main()
