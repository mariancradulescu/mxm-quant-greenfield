from decimal import Decimal
import unittest
from m6.ctrader_proto import OpenApiModelMessages_pb2 as m
from .captured_symbol_terms import captured_symbol_terms


def fixture():
    return m.ProtoOASymbol(symbolId=1, digits=5, pipPosition=4,
                          minVolume=100000, maxVolume=100000000, stepVolume=100000,
                          lotSize=10000000, commissionType=1,
                          preciseTradingCommissionRate=3000000000,
                          preciseMinCommission=1000000,
                          minCommissionType=1, minCommissionAsset='USD')


class CapturedSymbolTermsTest(unittest.TestCase):
    def test_cents_scale_and_explicit_precise_usd_rate(self):
        r = captured_symbol_terms(fixture())
        self.assertEqual(r['minimum_units'], '1000')
        self.assertEqual(r['lot_units'], '100000')
        self.assertTrue(r['modeled_volume_on_captured_lattice'])
        self.assertEqual(r['commission_rate'], '30')
        self.assertEqual(r['minimum_commission_amount'], '0.01')
        self.assertTrue(r['minimum_commission_semantics_known'])
        self.assertFalse(r['historical_commission_proven'])

    def test_missing_optional_terms_are_unknown_not_zero_or_enum_default(self):
        r = captured_symbol_terms(m.ProtoOASymbol(symbolId=1, digits=5, pipPosition=4))
        self.assertIsNone(r['raw_optional_fields']['commissionType'])
        self.assertIsNone(r['raw_optional_fields']['minCommissionAsset'])
        self.assertIsNone(r['commission_rate'])
        self.assertIsNone(r['modeled_volume_on_captured_lattice'])
        self.assertFalse(r['minimum_commission_semantics_known'])

    def test_out_of_bounds_or_off_step_modeled_order(self):
        self.assertFalse(captured_symbol_terms(fixture(), Decimal('500'))['modeled_volume_on_captured_lattice'])
        self.assertFalse(captured_symbol_terms(fixture(), Decimal('1500'))['modeled_volume_on_captured_lattice'])
        self.assertFalse(captured_symbol_terms(fixture(), Decimal('1000001'))['modeled_volume_on_captured_lattice'])

    def test_ambiguous_volume_anchor_not_certified(self):
        s = fixture(); s.minVolume = 150000
        r = captured_symbol_terms(s)
        self.assertFalse(r['unambiguous_volume_geometry'])
        self.assertIsNone(r['modeled_volume_on_captured_lattice'])

    def test_missing_commission_type_not_inferred_from_proto_default(self):
        s = fixture(); s.ClearField('commissionType')
        self.assertIsNone(captured_symbol_terms(s)['commission_rate'])

    def test_percent_rate_uses_1e5_instead_of_currency_1e8(self):
        s = fixture(); s.commissionType = 3; s.preciseTradingCommissionRate = 10000
        r = captured_symbol_terms(s)
        self.assertEqual(r['commission_rate'], '0.1')
        self.assertEqual(r['commission_rate_unit'], 'PERCENT_OF_VALUE_NOT_FRACTION')

    def test_absent_minimum_asset_stays_unknown(self):
        s = fixture(); s.ClearField('minCommissionAsset')
        self.assertFalse(captured_symbol_terms(s)['minimum_commission_semantics_known'])

    def test_invalid_symbol_volume_and_numeric_metadata_rejected(self):
        for units in ('NaN', 'Infinity', '-1', '1000.001'):
            with self.assertRaises(ValueError): captured_symbol_terms(fixture(), Decimal(units))
        s = fixture(); s.swapLong = float('nan')
        with self.assertRaises(ValueError): captured_symbol_terms(s)
        s = fixture(); s.symbolId = 2
        with self.assertRaises(ValueError): captured_symbol_terms(s)


if __name__ == '__main__': unittest.main()
