import json,shutil,tempfile,unittest
from pathlib import Path
from . import verify_usd_leadlag_result as evidence
class LeadLagOriginalEvidenceTests(unittest.TestCase):
    def test_original_ciphertext_and_public_gates_without_decryption(self):
        r=evidence.verify();self.assertTrue(r['original_zip_verified']);self.assertTrue(r['current_implementation_matches_original'])
        self.assertEqual(r['disposition'],'DATA_LIMITED');self.assertFalse(r['screen_gates']['scenario_net_positive'])
        self.assertFalse(r['screen_gates']['censor_at_most_5pct']);self.assertFalse(r['decrypted']);self.assertFalse(r['economic_rerun'])
    def test_corruption_receipt_substitution_manifest_change_and_symlink_refused(self):
        for mode in ('part','receipt','manifest','symlink'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'evidence';shutil.copytree(evidence.ROOT,root)
                if mode=='part':(root/'part-000.b64').write_text('AAAA')
                elif mode=='receipt':
                    r=json.loads((root/'receipt.json').read_bytes());r['edge_confirmed']=True;(root/'receipt.json').write_text(json.dumps(r))
                elif mode=='manifest':
                    p=root/'MANIFEST.json';r=json.loads(p.read_bytes());r['run_id']+=1;p.write_text(json.dumps(r))
                else:
                    p=root/'part-000.b64';p.unlink();p.symlink_to(evidence.ROOT/'part-000.b64')
                with self.assertRaises(ValueError):evidence.verify(root)
    def test_later_source_change_does_not_replace_original_or_claim_current_parity(self):
        original_repo=evidence.REPO
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder);m=json.loads((evidence.ROOT/'MANIFEST.json').read_bytes())
            for path in m['original_source_files']:
                p=source/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((original_repo/path).read_bytes())
            changed='research_core_v4/laboratory/csharp/usd_leadlag/MxmUsdLeadLag.cs'
            (source/changed).write_text('// Later, different implementation\n')
            try:
                evidence.REPO=source;r=evidence.verify()
            finally:evidence.REPO=original_repo
            self.assertTrue(r['original_zip_verified']);self.assertFalse(r['current_implementation_matches_original'])
            self.assertEqual(r['changed_source_paths'],[changed]);self.assertEqual(r['source_run'],40271734532)
if __name__=='__main__':unittest.main()
