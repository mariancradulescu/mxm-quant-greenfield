import json,shutil,tempfile,unittest
from pathlib import Path
from .verify_spread_reversion_result import FOLDER,verify,restore,sha
class OriginalSpreadResult(unittest.TestCase):
    def test_original_native_result_is_one_trial_not_net_or_full_account(self):
        r=verify();self.assertEqual((r['source_rows'],r['source_groups']),(1275114,812355));self.assertEqual(r['disposition'],'DATA_LIMITED')
        self.assertEqual(r['model_trials'],1);self.assertFalse(r['source_or_result_decrypted']);self.assertFalse(r['net_edge_proven'])
    def test_changed_or_missing_part_is_not_reconstructed_as_an_original(self):
        for missing in (True,False):
            with self.subTest(missing=missing),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'copy';shutil.copytree(FOLDER,p);f=p/'part-003.b64'
                if missing:f.unlink()
                else:f.write_bytes(b'AAAA'+f.read_bytes()[4:])
                with self.assertRaises(ValueError):verify(p)
    def test_verdict_fee_or_capital_substitution_cannot_replace_original_receipt(self):
        for k,v in [('disposition','CONFIRMED'),('costs_defaulted_to_zero',True),('capital_replay',True)]:
            with self.subTest(k=k),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'copy';shutil.copytree(FOLDER,p);f=p/'receipt.json';r=json.loads(f.read_bytes());r[k]=v;f.write_text(json.dumps(r))
                with self.assertRaisesRegex(ValueError,'EXACT_NATIVE_RECEIPT_COPY'):verify(p)
    def test_manifest_or_symlink_substitutions_refused(self):
        for name in ('MANIFEST.json','cold.json','part-000.b64'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'copy';shutil.copytree(FOLDER,p);f=p/name;f.unlink();f.symlink_to(FOLDER/name)
                with self.assertRaisesRegex(ValueError,'REGULAR'):verify(p)
    def test_restore_exact_evaluator_and_ciphertext_without_key_replay_or_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'restored';r=restore(p);self.assertFalse(r['source_or_result_decrypted'])
            self.assertEqual(sorted(x.name for x in p.iterdir()),['cold.json','evaluator.dll','full-result.mxmenc','receipt.json'])
            self.assertEqual(sha((p/'evaluator.dll').read_bytes()),'4bc0b433c5d25e512e4f045af505de938bf96c080eb220ffb770ce98cfebcfd1')
            with self.assertRaisesRegex(ValueError,'NEW_REGULAR_OUTPUT_DIRECTORY'):restore(p)
if __name__=='__main__':unittest.main()
