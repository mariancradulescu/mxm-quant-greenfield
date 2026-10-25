"""Reject account refund, wrong conversion side and false native qualification in actual original artificial proof."""
import copy,json,tempfile,shutil,unittest
from pathlib import Path
from decimal import Decimal as D
from .shared_usd_account_checks import original,verify
ROOT=Path(__file__).resolve().parents[2]/'docs/economic-development/20261025/shared-usd-account-40202484274'
class SharedUsdEvidence(unittest.TestCase):
    def test_actual_original(self):self.assertTrue(original()['original_archive_verified'])
    def test_refund_or_invented_equity(self):
        p=json.loads((ROOT/'proof.json').read_bytes(),parse_float=D)
        for field,value in [('cash_eur',D(200)),('equity_eur',D(201))]:
            v=copy.deepcopy(p);v['proofs'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):verify(v)
    def test_commission_cannot_use_instrument_price_for_fx(self):
        v=json.loads((ROOT/'proof.json').read_bytes(),parse_float=D)
        v['fee_case']['fx_bid']=v['fee_case']['execution_price']
        with self.assertRaises(ValueError):verify(v)
    def test_false_native_promotion(self):
        v=json.loads((ROOT/'proof.json').read_bytes(),parse_float=D);v['native_ctrader_runtime_reception']=True
        with self.assertRaises(ValueError):verify(v)
    def test_original_copy_substitution(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'evidence';shutil.copytree(ROOT,folder);(folder/'proof.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'ORIGINAL_PROOF_COPY'):original(folder)
if __name__=='__main__':unittest.main()
