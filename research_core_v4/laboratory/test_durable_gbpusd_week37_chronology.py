"""Original encrypted GBPUSD source integrity and false-promotion negatives, no decryption."""
import base64,json,shutil,tempfile,unittest
from pathlib import Path
from .durable_gbpusd_week37_chronology import ROOT,restore_gbpusd_week37
class DurableGbpWeek(unittest.TestCase):
    def test_exact_restore_idempotence_and_no_economic_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'source';r=restore_gbpusd_week37(destination=out)
            self.assertEqual(r,restore_gbpusd_week37(destination=out))
            self.assertEqual(r['quote_events'],1275114)
            self.assertEqual(sorted(p.name for p in out.iterdir()),['capture.mxmenc','cold.json','producer.json'])
            self.assertFalse(r['decrypted']);self.assertFalse(r['economic_edge_proven']);self.assertFalse(r['hard21_proven'])
            self.assertEqual(r['new_broker_requests'],0)
    def altered(self,change,reason):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'archive';shutil.copytree(ROOT,root)
            change(root)
            with self.assertRaisesRegex(ValueError,reason):restore_gbpusd_week37(root,Path(tmp)/'out')
    def test_ciphertext_part_corruption(self):
        def mutate(root):
            p=root/'part-00.b64';b=bytearray(base64.b64decode(p.read_bytes()));b[-1]^=1
            p.write_bytes(base64.b64encode(b)+b'\n')
        self.altered(mutate,'PART_DIGEST')
    def test_original_cold_zip_corruption(self):
        def mutate(root):
            p=root/'cold-artifact.zip.b64';b=bytearray(base64.b64decode(p.read_bytes()));b[-1]^=1
            p.write_bytes(base64.b64encode(b)+b'\n')
        self.altered(mutate,'GBP_COLD_ARCHIVE')
    def test_both_original_receipt_copies_required(self):
        for name in ('producer.json','cold.json'):
            with self.subTest(name=name):self.altered(lambda r:(r/name).write_text('{}'),'GBP_EXACT_RECEIPT_COPY')
    def test_changed_source_or_favourable_manifest_cannot_replace_original(self):
        for key,value in [('code_source','0'*40),('quote_events',2000000),('economic_edge_proven',True),
                          ('hard21_proven',True),('merged_economic_replay_executed',True),('historical_costs_proven',True)]:
            def mutate(root):
                p=root/'MANIFEST.json';m=json.loads(p.read_bytes());m[key]=value;p.write_text(json.dumps(m))
            with self.subTest(key=key):self.altered(mutate,'GBP_IMMUTABLE_MANIFEST')
    def test_conflicting_destination_is_not_partially_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'cold.json').write_text('other evidence')
            with self.assertRaisesRegex(ValueError,'GBP_OUTPUT_CONFLICT'):restore_gbpusd_week37(destination=out)
            self.assertFalse((out/'capture.mxmenc').exists())
            self.assertEqual((out/'cold.json').read_text(),'other evidence')
    def test_symlink_part_refused(self):
        def mutate(root):
            p=root/'part-00.b64';copy=root/'original.b64';p.rename(copy);p.symlink_to(copy)
        self.altered(mutate,'PART_FILE')
if __name__=='__main__':unittest.main()
