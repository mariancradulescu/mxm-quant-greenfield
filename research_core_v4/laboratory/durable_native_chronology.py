"""Restore exact existing encrypted DEVELOPMENT bytes, offline, without keys.

The CLI pins the native GitHub artifact digest independently of its manifest.
No archive paths are extracted, no plaintext market data is decrypted.
"""
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

ARCHIVE_SHA = '354b16bd329335314996d1334cab37b7029b5aa883ea93f2bde0bbc58c38650a'
CIPHER_SHA = 'f1d828d94b304e2af1f310701f92dcb31db935a8db7fc3f8772087adf5499346'
ROOT = Path('docs/economic-development/20261023/native-chronology-39660692230')
LIMIT = 2_000_000


def need(ok, code):
    if not ok:
        raise ValueError('DURABLE_NATIVE_' + code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode_archive(root, expected_archive_sha):
    """Byte-only integrity helper; callers decide scientific/source authority."""
    root = Path(root)
    m = json.loads((root / 'MANIFEST.json').read_text())
    need(m['schema'] == 'mxm.durable-encrypted-native-chronology.v1', 'SCHEMA')
    need(m['archive_sha256'] == expected_archive_sha, 'PINNED_ARCHIVE_DIGEST')
    need(type(m['archive_bytes']) is int and 0 < m['archive_bytes'] <= LIMIT, 'ARCHIVE_SIZE')
    need(type(m['parts']) is list and 0 < len(m['parts']) <= 128, 'PART_COUNT')
    chunks = []
    total = 0
    for i, part in enumerate(m['parts']):
        need(part['index'] == i and part['path'] == f'part-{i:02d}.b64', 'PART_ORDER_OR_PATH')
        need(type(part['bytes']) is int and 0 < part['bytes'] <= 16384, 'PART_SIZE')
        path = root / part['path']
        need(not path.is_symlink() and path.stat().st_size <= 22000, 'PART_FILE')
        raw = base64.b64decode(path.read_text().strip(), validate=True)
        need(len(raw) == part['bytes'] and digest(raw) == part['sha256'], 'PART_DIGEST')
        total += len(raw)
        need(total <= LIMIT, 'TOTAL_SIZE')
        chunks.append(raw)
    archive = b''.join(chunks)
    need(len(archive) == m['archive_bytes'] and digest(archive) == expected_archive_sha,
         'ARCHIVE_DIGEST')
    allowed = {'capture.mxmenc', 'producer.json'}
    need(set(m['members']) == allowed, 'MEMBER_MANIFEST')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        # Do not extractall: neither traversal nor duplicate member names allowed.
        names = z.namelist()
        need(len(names) == 2 and set(names) == allowed, 'MEMBER_PATHS_OR_DUPLICATES')
        need(sum(v.file_size for v in z.infolist()) <= LIMIT, 'MEMBER_SIZE')
        result = {}
        for name in sorted(allowed):
            data = z.read(name)
            need(len(data) == m['members'][name]['bytes'] and
                 digest(data) == m['members'][name]['sha256'], 'MEMBER_DIGEST')
            result[name] = data
    return m, result


def restore_native(root=ROOT, destination=Path('verification/r3-chronology')):
    m, files = decode_archive(root, ARCHIVE_SHA)
    need(m['source_run_id'] == 39660692230 and m['artifact_id'] == 12373706797 and
         m['artifact_name'] == 'r3-chronology-39660692230' and
         m['source_head'] == '36ffe2999aae332b2d408c9d12d32bfabfa70802' and
         m['decoder_source'] == 'd2fae5641b759b1c8c24161d83d62d39e104eafd' and
         m['partition'] == 'DEVELOPMENT_ALREADY_EXPOSED' and
         m['new_broker_requests'] == m['orders'] == 0, 'SOURCE_IDENTITY')
    need(digest(files['capture.mxmenc']) == CIPHER_SHA, 'PINNED_CIPHERTEXT')
    receipt = json.loads(files['producer.json'])
    need(receipt['run_id'] == 39660692230 and receipt['accepted'] is True and
         receipt['source_sha'] == m['decoder_source'] and
         receipt['trigger_sha'] == m['source_head'] and
         receipt['ciphertext_sha256'] == CIPHER_SHA and receipt['orders'] == 0 and
         receipt['bid_events'] == 14003 and receipt['ask_events'] == 14209 and
         receipt['chronological_events_processed'] == 28212, 'ORIGINAL_RECEIPT')
    destination = Path(destination)
    need(not destination.is_symlink(), 'DESTINATION_SYMLINK')
    for name, data in files.items():
        path = destination / name
        need(not path.is_symlink(), 'OUTPUT_SYMLINK')
        need(not path.exists() or path.read_bytes() == data, 'OUTPUT_CONFLICT')
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = destination / name
        if not path.exists():
            # Exclusive creation: never replace a concurrent or conflicting input.
            with path.open('xb') as output:
                output.write(data)
    return {'schema': 'mxm.durable-native-ciphertext-restore.v1',
            'source_run_id': 39660692230, 'archive_sha256': ARCHIVE_SHA,
            'ciphertext_sha256': CIPHER_SHA, 'quote_events': 28212,
            'decrypted': False, 'new_broker_requests': 0, 'orders': 0,
            'independent_confirmation': False}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, default=Path('verification/r3-chronology'))
    args = p.parse_args()
    print(json.dumps(restore_native(destination=args.out), sort_keys=True))
