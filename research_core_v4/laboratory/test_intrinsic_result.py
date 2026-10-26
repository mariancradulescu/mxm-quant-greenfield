import shutil,tempfile,unittest
from pathlib import Path
from .verify_intrinsic_result import FOLDER,verify
class OriginalBytes(unittest.TestCase):
    def test_original_and_later_code_are_distinct_claims(self):
        self.assertTrue(verify()['current_pinned_dependencies_match'])
        with tempfile.TemporaryDirectory() as t:
            r=verify(code_root=Path(t));self.assertTrue(r['original_archives_verified']);self.assertFalse(r['current_pinned_dependencies_match'])
    def test_corrupt_each_archive_receipt_and_precommit(self):
        for n in ('result.zip.b64','evaluator.zip.b64','receipt.json','recovery.json','MANIFEST.json','original-scientific-spec.json','original-technical-recovery.json','source-compatibility-public.json'):
            with self.subTest(file=n),tempfile.TemporaryDirectory() as t:
                d=Path(t)/'copy';shutil.copytree(FOLDER,d);p=d/n;b=bytearray(p.read_bytes());b[5]^=1;p.write_bytes(b)
                with self.assertRaises((ValueError,KeyError)):verify(d)
    def test_symlink_not_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)/'copy';shutil.copytree(FOLDER,d);p=d/'receipt.json';p.unlink();p.symlink_to(FOLDER/'receipt.json')
            with self.assertRaises(ValueError):verify(d)
if __name__=='__main__':unittest.main()
