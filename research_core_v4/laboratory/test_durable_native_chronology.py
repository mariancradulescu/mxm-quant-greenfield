import base64
import hashlib
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from .durable_native_chronology import ROOT, CIPHER_SHA, restore_native


class DurableNativeChronologyTest(unittest.TestCase):
    def test_preserved_native_workflow_archives_match_github_digests(self):
        # Original downloaded GitHub archive digests, independent of manifests.
        pins = {39899227676: '63b692a455fc679ef45a9c106e62c485221449f4810dafa794f4e267fac61fa9',
                39900816580: '89b9dc5bc2676ab37b04c4948d0a49700e490e184324a5cdd179d7703c6a3ddf'}
        for run, pin in pins.items():
            root = ROOT.parent / 'protected-evidence' / str(run)
            m = json.loads((root/'MANIFEST.json').read_text())
            self.assertEqual(m['run_id'], run)
            self.assertEqual(m['archive_sha256'], pin)
            chunks = []
            for i, part in enumerate(m['parts']):
                self.assertEqual(part['index'], i)
                self.assertEqual(part['path'], f'part-{i:02d}.b64')
                raw = base64.b64decode((root/part['path']).read_text().strip(), validate=True)
                self.assertEqual(len(raw), part['bytes'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), part['sha256'])
                chunks.append(raw)
            archive = b''.join(chunks)
            self.assertEqual(hashlib.sha256(archive).hexdigest(), pin)
            with zipfile.ZipFile(io.BytesIO(archive)) as z:
                self.assertEqual(sorted(z.namelist()), ['modeled-reference.mxmenc', 'receipt.json'])
                receipt = json.loads(z.read('receipt.json'))
                self.assertEqual(receipt['orders'], 0)
                self.assertEqual(receipt['original_source_run'], 39660692230)
                self.assertEqual(hashlib.sha256(z.read('modeled-reference.mxmenc')).hexdigest(),
                                 receipt['modeled_ciphertext_sha256'])

    def test_original_archive_matches_github_artifact_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'restored'
            receipt = restore_native(destination=out)
            self.assertFalse(receipt['decrypted'])
            self.assertEqual(receipt, restore_native(destination=out))
            self.assertEqual(hashlib.sha256((out/'capture.mxmenc').read_bytes()).hexdigest(), CIPHER_SHA)
            self.assertEqual(sorted(p.name for p in out.iterdir()), ['capture.mxmenc', 'producer.json'])

    def mutated(self, change, message):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'archive'
            shutil.copytree(ROOT, root)
            manifest = json.loads((root/'MANIFEST.json').read_text())
            change(root, manifest)
            (root/'MANIFEST.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, message):
                restore_native(root=root, destination=Path(tmp)/'out')

    def test_swapped_part_order_rejected(self):
        self.mutated(lambda root,m: m['parts'].reverse(), 'PART_ORDER_OR_PATH')

    def test_path_traversal_rejected(self):
        self.mutated(lambda root,m: m['parts'][0].update(path='../part-00.b64'), 'PART_ORDER_OR_PATH')

    def test_altered_ciphertext_part_rejected(self):
        def alter(root, m):
            path = root / m['parts'][0]['path']
            data = bytearray(base64.b64decode(path.read_text()))
            data[-1] ^= 1
            path.write_text(base64.b64encode(data).decode())
        self.mutated(alter, 'PART_DIGEST')

    def test_self_consistent_manifest_rehash_cannot_replace_pinned_archive(self):
        self.mutated(lambda root,m: m.update(archive_sha256='0'*64), 'PINNED_ARCHIVE_DIGEST')

    def test_false_source_provenance_rejected(self):
        self.mutated(lambda root,m: m.update(source_run_id=39660692231), 'SOURCE_IDENTITY')

    def test_member_hash_mutation_rejected(self):
        self.mutated(lambda root,m: m['members']['capture.mxmenc'].update(sha256='0'*64), 'MEMBER_DIGEST')

    def test_conflicting_destination_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            path = out/'producer.json'
            path.write_text('conflicting evidence')
            with self.assertRaisesRegex(ValueError, 'OUTPUT_CONFLICT'):
                restore_native(destination=out)
            self.assertEqual(path.read_text(), 'conflicting evidence')
            self.assertFalse((out/'capture.mxmenc').exists())


if __name__ == '__main__':
    unittest.main()
