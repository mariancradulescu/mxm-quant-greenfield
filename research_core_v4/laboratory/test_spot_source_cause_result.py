import base64,json,shutil,tempfile,unittest
from pathlib import Path
from .verify_spot_source_cause_result import FOLDER,verify
class OriginalCauseEvidence(unittest.TestCase):
    def test_exact_native_result_and_original_consumer_remain_distinct(self):
        r=verify();self.assertEqual((r['events'],r['locked'],r['crossed'],r['locked_in_two_sided_message']),(1140,190,0,125))
        self.assertTrue(r['original_profile_unchanged']);self.assertFalse(r['source_decrypted']);self.assertFalse(r['economic_edge_proven'])
    def test_modified_original_zip_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'evidence';shutil.copytree(FOLDER,p);f=p/'artifact.zip.b64'
            raw=bytearray(base64.b64decode(f.read_bytes()));raw[-1]^=1;f.write_bytes(base64.b64encode(raw))
            with self.assertRaisesRegex(ValueError,'ORIGINAL_NATIVE_ZIP'):verify(p)
    def test_source_policy_or_economic_promotion_cannot_replace_receipt(self):
        for field,value in [('economic_edge_proven',True),('original_profile_unchanged',False),('source_sha','bad')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'evidence';shutil.copytree(FOLDER,p);f=p/'receipt.json';r=json.loads(f.read_bytes());r[field]=value;f.write_text(json.dumps(r))
                with self.assertRaisesRegex(ValueError,'EXACT_NATIVE_RECEIPT'):verify(p)
    def test_symlink_copies_rejected(self):
        for name in ('receipt.json','artifact.zip.b64'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'evidence';shutil.copytree(FOLDER,p);f=p/name;f.unlink();f.symlink_to(FOLDER/name)
                with self.assertRaisesRegex(ValueError,'REGULAR'):verify(p)
if __name__=='__main__':unittest.main()
