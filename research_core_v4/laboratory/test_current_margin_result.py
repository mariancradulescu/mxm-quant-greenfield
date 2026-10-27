import base64,json,shutil,tempfile,unittest
from pathlib import Path
from .verify_current_margin_result import FOLDER,verify
class OriginalCurrentMargin(unittest.TestCase):
    def test_original_has_three_instruments_no_full_admission_or_decryption(self):
        r=verify();self.assertEqual(r['instruments'],3);self.assertFalse(r['source_decrypted']);self.assertFalse(r['full_entry_admission'])
    def test_any_zip_mutation_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'copy';shutil.copytree(FOLDER,p);f=p/'artifact.zip.b64';v=bytearray(base64.b64decode(f.read_bytes()));v[-1]^=1;f.write_bytes(base64.b64encode(v))
            with self.assertRaisesRegex(ValueError,'ORIGINAL_NATIVE_ZIP'):verify(p)
    def test_source_unit_and_admission_substitutions_cannot_replace_native_receipt(self):
        for field,val in [('full_entry_admission',True),('source_sha','wrong'),('reference_capital_eur','20000')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'copy';shutil.copytree(FOLDER,p);f=p/'receipt.json';v=json.loads(f.read_bytes());v[field]=val;f.write_text(json.dumps(v))
                with self.assertRaisesRegex(ValueError,'EXACT_NATIVE_RECEIPT'):verify(p)
    def test_symlink_copies_rejected(self):
        for name in ('receipt.json','artifact.zip.b64'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'copy';shutil.copytree(FOLDER,p);f=p/name;f.unlink();f.symlink_to(FOLDER/name)
                with self.assertRaisesRegex(ValueError,'REGULAR'):verify(p)
if __name__=='__main__':unittest.main()
