"""Original-public-receipt tamper negatives; no private source reading or reception rerun."""
import base64,json,shutil,tempfile,unittest
from pathlib import Path
from .verify_usd_pair_source_reception import ROOT,REL,verify
class PairSourceEvidence(unittest.TestCase):
    def test_original_archive_and_native_groups(self):
        r=verify();self.assertTrue(r['original_public_archive_verified']);self.assertFalse(r['account_replay_executed'])
    def corrupt(self,edit,code):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/REL;shutil.copytree(ROOT/REL,folder);edit(folder)
            with self.assertRaisesRegex(ValueError,code):verify(root)
    def test_zip_mutation(self):
        def edit(folder):
            p=folder/'artifact.zip.b64';b=bytearray(base64.b64decode(p.read_text()));b[-1]^=1;p.write_text(base64.b64encode(b).decode())
        self.corrupt(edit,'EXACT_NATIVE_ARCHIVE')
    def test_receipt_not_reconstructed_from_favourable_json(self):
        self.corrupt(lambda folder:(folder/'receipt.json').write_text('{}'),'ORIGINAL_RECEIPT_COPY')
    def test_source_and_false_edge_manifest_changes_rejected(self):
        for key,value in [('native_source_sha','0'*40),('economic_edge_proven',True),('hard21_proven',True)]:
            def edit(folder):
                p=folder/'MANIFEST.json';m=json.loads(p.read_bytes());m[key]=value;p.write_text(json.dumps(m))
            with self.subTest(key=key):self.corrupt(edit,'IMMUTABLE_MANIFEST')
if __name__=='__main__':unittest.main()
