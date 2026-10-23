import unittest,tempfile,shutil,json
from pathlib import Path
from .verify_continuous_account_recovery import verify,ROOT
class ContinuousRecoveryEvidenceTests(unittest.TestCase):
    def test_original_encrypted_result_and_native_provenance(self):
        v=verify();self.assertEqual(v['cold_processes'],4);self.assertFalse(v['decrypted'])
        self.assertFalse(v['native_ctrader_recovery']);self.assertEqual(v['new_strategy_trials'],0)
    def test_corrupt_cipher_source_proof_or_false_native_claim_refused(self):
        for mode in ('cipher','source','proof','promotion'):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'evidence';shutil.copytree(ROOT,root)
                if mode=='cipher':(root/'ciphertext-00.b64').write_text('AAAA')
                elif mode=='proof':(root/'recovery-proof.json').write_text('{}')
                else:
                    p=root/'MANIFEST.json';m=json.loads(p.read_bytes())
                    if mode=='source':m['source_commit']='0'*40
                    else:m['native_ctrader_recovery']=True
                    p.write_text(json.dumps(m))
                with self.subTest(mode=mode),self.assertRaises(ValueError):verify(root)
if __name__=='__main__':unittest.main()
