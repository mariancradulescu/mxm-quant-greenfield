import base64
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from .durable_native_chronology import decode_archive
from .durable_week36_chronology import ROOT,ARCHIVE_SHA,restore_week36

class DurableWeek36ChronologyTests(unittest.TestCase):
    def test_native_full_week_bytes_restore_offline_and_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'restored';r=restore_week36(destination=out)
            self.assertEqual(r,restore_week36(destination=out))
            self.assertEqual(sorted(x.name for x in out.iterdir()),['capture.mxmenc','cold.json','producer.json'])
            self.assertEqual(r['quote_events'],761196)
            self.assertFalse(r['decrypted']);self.assertFalse(r['hard21_proven'])
            self.assertEqual(r['orders'],r['strategy_trials'])
    def test_legacy_decoder_default_budget_still_refuses_larger_archive(self):
        with self.assertRaisesRegex(ValueError,'ARCHIVE_SIZE'):decode_archive(ROOT,ARCHIVE_SHA)
    def altered(self,change,message):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'archive';shutil.copytree(ROOT,root)
            m=json.loads((root/'MANIFEST.json').read_text());change(root,m)
            (root/'MANIFEST.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,message):restore_week36(root,Path(tmp)/'out')
    def test_changed_authoritative_source_ref_rejected(self):
        self.altered(lambda root,m:m.update(code_source='0'*40),'WEEK_SOURCE_IDENTITY')
    def test_crossed_or_missing_part_refused(self):
        self.altered(lambda root,m:m['parts'].reverse(),'PART_ORDER_OR_PATH')
    def test_exact_ciphertext_part_mutation_refused(self):
        def mutate(root,m):
            p=root/m['parts'][0]['path'];raw=bytearray(base64.b64decode(p.read_text()));raw[-1]^=1
            p.write_text(base64.b64encode(raw).decode())
        self.altered(mutate,'PART_DIGEST')
    def test_self_consistent_archive_rehash_cannot_replace_github_pin(self):
        self.altered(lambda root,m:m.update(archive_sha256='0'*64),'PINNED_ARCHIVE_DIGEST')
    def test_cold_receipt_copy_must_be_original_native_bytes(self):
        self.altered(lambda root,m:(root/'cold.json').write_text('{}'),'WEEK_COLD_COPY')
    def test_producer_receipt_copy_must_be_original_native_bytes(self):
        self.altered(lambda root,m:(root/'producer.json').write_text('{}'),'WEEK_PRODUCER_COPY')
    def test_conflicting_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'producer.json').write_text('other evidence')
            with self.assertRaisesRegex(ValueError,'WEEK_OUTPUT_CONFLICT'):restore_week36(destination=out)
            self.assertEqual((out/'producer.json').read_text(),'other evidence')
            self.assertFalse((out/'capture.mxmenc').exists())

if __name__=='__main__':unittest.main()
