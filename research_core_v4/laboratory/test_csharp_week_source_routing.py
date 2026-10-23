"""No-key regression: both fixed W37 development models use W37 custody, not R3."""
import hashlib
from decimal import Decimal as D
import json
import tempfile
import unittest
from pathlib import Path

from .csharp_native_portfolio_independent_mark import captured_fee_reference, MarkParityError

WEEK_CLASSIFICATIONS=(
    'PINNED_PEPPERSTONE_WEEK37_SINGLE_SYMBOL_MODELED_TERMS_DEVELOPMENT_EXPOSED',
    'PINNED_PEPPERSTONE_WEEK37_PRODUCT_DEFAULT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED',
)

def snapshot():
    return {
        'schema':'mxm.captured-native-symbol-terms.v1',
        'symbol_id':1,
        'historical_commission_proven':False,
        'dated_historical_volume_rules_proven':False,
        'source_crypto_authenticated_by_week_native_replay':True,
        'source_run':39917922508,
        'source_code_sha':'120db3391ed1f4105120274b73a9259690eeeb64',
        'source_private_sha256':'8dde8355c79f3f379bf14f1fd47a8ed5815646cafbcfc287762fb68c2c2e7b51',
        'source_ciphertext_sha256':'2403c74dfd81ab410f9b9c3bdabf4f3d5a5a4df0133cd0adc03933a364d539b6',
        'raw_optional_fields':{
            'minVolume':100000,'maxVolume':100000000,'stepVolume':100000,
            'commissionType':1,'preciseTradingCommissionRate':3000000000,
            'preciseMinCommission':1000000,'minCommissionType':1,
            'minCommissionAsset':'USD'
        }
    }

class WeekCustodyRoutingTests(unittest.TestCase):
    def reference(self, payload, classification):
        data=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'terms.json'
            file.write_bytes(data)
            return captured_fee_reference(file,{
                'classification':classification,
                'captured_terms_sha256':hashlib.sha256(data).hexdigest(),
                'modeled_parameters':{'units':1000}
            })

    def test_both_week_modes_use_authenticated_week_custody_not_short_source(self):
        for label in WEEK_CLASSIFICATIONS:
            with self.subTest(label=label):
                fee=self.reference(snapshot(),label)
                self.assertEqual(fee(D('1000'),D('1.10'),D('1.10'),D('1.11')),D('0.03'))

    def test_w37_source_mismatch_refuses_both_modes(self):
        for label in WEEK_CLASSIFICATIONS:
            for field,value in (
                ('source_run',39660692230),
                ('source_crypto_authenticated_by_week_native_replay',False),
                ('source_ciphertext_sha256','not-original-week')):
                with self.subTest(label=label,field=field):
                    a=snapshot();a[field]=value
                    with self.assertRaisesRegex(MarkParityError,'CAPTURED_WEEK_NATIVE_BINDING'):
                        self.reference(a,label)

if __name__=='__main__':
    unittest.main()
