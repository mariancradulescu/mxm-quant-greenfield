import shutil,tempfile,unittest,json
from pathlib import Path
from .verify_source_exposure_result import RECEIPT,ORIGINAL_BLOB,verify
class OriginalSourceCensusEvidence(unittest.TestCase):
    def test_exact_original_native_result_and_no_promotions(self):
        r=verify()
        self.assertEqual(r['original_run'],40415845622)
        self.assertEqual(r['five_minute_qualified_stretches'],0)
        self.assertFalse(r['historical_execution_liquidity_proven'])
        self.assertFalse(r['native_ctrader_reception_proven'])
        self.assertTrue(r['no_economic_replay'])
        self.assertEqual(r['blob_sha1'],ORIGINAL_BLOB)
    def test_changed_money_or_timing_cannot_rewrite_original(self):
        with tempfile.TemporaryDirectory() as t:
            dst=Path(t)/'receipt.json';shutil.copy2(RECEIPT,dst)
            for field in ('source_sha','market_outcomes','fixed_age_ms','source_groups_reconciled'):
                data=json.loads(RECEIPT.read_bytes())
                data[field]=None
                dst.write_text(json.dumps(data)+'\n')
                with self.subTest(field=field),self.assertRaises(ValueError):verify(dst)
    def test_no_symlink_as_original(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'evidence.json';p.symlink_to(RECEIPT)
            with self.assertRaises(ValueError):verify(p)
if __name__=='__main__':unittest.main()
