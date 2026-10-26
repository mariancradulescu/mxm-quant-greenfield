import unittest
from decimal import Decimal as D
from .commission_feasibility import reference,classify
from . import test_universe_commission as fixtures
class Floors(unittest.TestCase):
    def test_unknown_currency_and_price_are_not_free(self):
        i=fixtures.Commission().item(3);i['full']['minCommissionAsset']='JPY';r=reference(i)
        self.assertFalse(r['CompleteFeeKnownWithoutPrice']);self.assertEqual(classify(r),'COST_UNRESOLVED_NOT_ELIGIBLE')
        self.assertIn('MISSING_COST_FX_JPY',r['Unresolved']);self.assertIn('PRICE_DEPENDENT_BASE_FEE',r['Unresolved'])
    def test_minimum_fee_can_reject_without_market_price(self):
        i=fixtures.Commission().item(3);i['full']['preciseMinCommission']=200000000
        r=reference(i);self.assertEqual(r['KnownPerFillFloorEur'],D(2));self.assertEqual(classify(r),'ROUNDTRIP_FEE_FLOOR_EXHAUSTS_INITIAL_REFERENCE_RISK')
    def test_passing_fee_hurdle_is_not_trade_admission(self):
        r=reference(fixtures.Commission().item(2));self.assertEqual(classify(r),'FEE_HURDLE_ONLY_NOT_FULL_ADMISSION')
if __name__=='__main__':unittest.main()
