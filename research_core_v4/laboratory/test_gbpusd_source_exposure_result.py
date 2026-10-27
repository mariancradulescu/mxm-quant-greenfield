import base64,json,shutil,tempfile,unittest
from pathlib import Path
from .verify_gbpusd_source_exposure_result import FOLDER,verify
class OriginalGbpSourceResult(unittest.TestCase):
    def test_original_artifact_source_counts_and_positive_support_are_not_edge(self):
        r=verify();self.assertEqual(r['events'],1275114)
        self.assertEqual(r['groups'],r['healthy_groups']+r['unavailable_groups'])
        self.assertEqual(r['observed_stretches_at_least_5min'],6)
        self.assertFalse(r['economic_edge_proven']);self.assertFalse(r['hard21_proven'])
    def test_corrupt_native_archive_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'result';shutil.copytree(FOLDER,p)
            raw=bytearray(base64.b64decode((p/'artifact.zip.b64').read_bytes()));raw[-1]^=1
            (p/'artifact.zip.b64').write_bytes(base64.b64encode(raw))
            with self.assertRaisesRegex(ValueError,'ORIGINAL_NATIVE_ARCHIVE'):verify(p)
    def test_receipt_substitution_and_favourable_promotion_rejected(self):
        for field,value in [('orders',1),('after_cost_edge_proven',True),('source_sha','bad')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'result';shutil.copytree(FOLDER,p)
                r=json.loads((p/'receipt.json').read_bytes());r[field]=value
                (p/'receipt.json').write_text(json.dumps(r))
                with self.assertRaisesRegex(ValueError,'EXACT_ORIGINAL_RECEIPT'):verify(p)
    def test_symlink_receipt_or_archive_rejected(self):
        for name in ('artifact.zip.b64','receipt.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'result';shutil.copytree(FOLDER,p);(p/name).unlink();(p/name).symlink_to(FOLDER/name)
                with self.assertRaisesRegex(ValueError,'BOUNDED_REGULAR'):verify(p)
if __name__=='__main__':unittest.main()
