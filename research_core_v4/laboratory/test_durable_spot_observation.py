import base64,json,shutil,tempfile,unittest
from pathlib import Path
from .durable_spot_observation import FOLDER,verify
class ExactNativeSpotEvidence(unittest.TestCase):
    def test_original_cipher_restores_without_key_and_every_group_reconciles(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'original';r=verify(destination=out)
            self.assertEqual(set(p.name for p in out.iterdir()),{'capture.mxmenc','producer.json','cold.json'})
            self.assertEqual(sum(x['events'] for x in r['profile'].values()),1140)
            self.assertEqual(r['profile']['250']['healthy'],321)
            self.assertFalse(r['source_decrypted']);self.assertFalse(r['economic_edge_proven'])
            self.assertEqual(verify(destination=out),r)
    def test_both_original_artifact_corruptions_refused(self):
        for role in ('producer','cold'):
            with self.subTest(role=role),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)/'evidence';shutil.copytree(FOLDER,folder)
                p=folder/(role+'-artifact.zip.b64');raw=bytearray(base64.b64decode(p.read_bytes()));raw[-1]^=1;p.write_bytes(base64.b64encode(raw))
                with self.assertRaisesRegex(ValueError,'ORIGINAL_'):verify(folder)
    def test_native_manifest_and_public_receipt_substitutions_refused(self):
        for name in ('MANIFEST.json','producer.json','cold.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)/'evidence';shutil.copytree(FOLDER,folder)
                p=folder/name;r=json.loads(p.read_bytes());r['economic_edge_proven']=True;p.write_text(json.dumps(r))
                with self.assertRaises(ValueError):verify(folder)
    def test_symlink_or_conflicting_destination_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'evidence';shutil.copytree(FOLDER,folder)
            p=folder/'producer-artifact.zip.b64';p.unlink();p.symlink_to(FOLDER/p.name)
            with self.assertRaisesRegex(ValueError,'REGULAR'):verify(folder)
            out=Path(tmp)/'conflict';out.mkdir();target=out/'capture.mxmenc';target.write_bytes(b'conflicting')
            with self.assertRaisesRegex(ValueError,'OUTPUT_CONFLICT'):verify(destination=out)
            self.assertEqual(target.read_bytes(),b'conflicting')
if __name__=='__main__':unittest.main()
