import base64,json,shutil,tempfile,unittest
from pathlib import Path
from .verify_observed_cost_fx_result import FOLDER,verify,restore_cipher,sha,MEMBERS
class OriginalObservedFx(unittest.TestCase):
    def test_exact_native_receipts_encrypted_ledger_and_no_policy_reclassification(self):
        r=verify();self.assertEqual((r['events'],r['conditional_component_estimates'],r['unresolved']),(1140,1079,61))
        self.assertFalse(r['source_or_ledger_decrypted']);self.assertTrue(r['original_quality_profile_unchanged'])
    def test_modified_zip_including_opaque_ciphertext_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'copy';shutil.copytree(FOLDER,p);f=p/'artifact.zip.b64';r=bytearray(base64.b64decode(f.read_bytes()));r[len(r)//2]^=1;f.write_bytes(base64.b64encode(r))
            with self.assertRaisesRegex(ValueError,'ORIGINAL_NATIVE_ZIP'):verify(p)
    def test_producer_cold_policy_promotion_and_source_substitutions_refused(self):
        for name,field,value in [('receipt.json','full_entry_admission',True),('receipt.json','source_timestamp_certified',True),('cold.json','source_sha','other')]:
            with self.subTest(name=name,field=field),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'copy';shutil.copytree(FOLDER,p);f=p/name;r=json.loads(f.read_bytes());r[field]=value;f.write_text(json.dumps(r))
                with self.assertRaisesRegex(ValueError,'EXACT_NATIVE_RECEIPT_COPY'):verify(p)
    def test_symlinks_refused(self):
        for name in ('receipt.json','cold.json','artifact.zip.b64'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'copy';shutil.copytree(FOLDER,p);f=p/name;f.unlink();f.symlink_to(FOLDER/name)
                with self.assertRaisesRegex(ValueError,'REGULAR'):verify(p)
    def test_restore_only_exact_ciphertext_never_overwrites_or_decrypts(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'restored';r=restore_cipher(p);self.assertTrue(r['encrypted_ledger_restored'])
            self.assertEqual(sorted(f.name for f in p.iterdir()),['ledger.mxmenc'])
            self.assertEqual(sha((p/'ledger.mxmenc').read_bytes()),MEMBERS['ledger.mxmenc'][1])
            with self.assertRaisesRegex(ValueError,'NEW_REGULAR_OUTPUT_DIRECTORY'):restore_cipher(p)
if __name__=='__main__':unittest.main()
