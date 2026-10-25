"""Verify immutable original artificial/metadata evidence offline; never execute a product."""
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile
from .correlated_entry_recovery_checks import need, proof
ROOT = Path(__file__).resolve().parents[2]
REL = Path('docs/economic-development/20261025/correlated-entry-recovery-40166874813')
MANIFEST_SHA = '01bb6a6876535ef09692506a550e300fd7af349961bd60d1d92ab91d7789878d'
def sha(data):
    return hashlib.sha256(data).hexdigest()
def verify(root=ROOT):
    folder = root / REL
    raw = (folder/'MANIFEST.json').read_bytes()
    need(sha(raw)==MANIFEST_SHA, 'IMMUTABLE_MANIFEST')
    manifest = json.loads(raw)
    originals = {}
    for name, archive in manifest['archives'].items():
        chunks = []
        for part in archive['parts']:
            encoded = (folder/part['path']).read_bytes()
            need(len(encoded)<50000, 'BOUNDED_PART')
            chunk = base64.b64decode(b"".join(encoded.split()), validate=True)
            need(len(chunk)==part['bytes'] and sha(chunk)==part['sha256'], 'PART_INTEGRITY')
            chunks.append(chunk)
        data = b''.join(chunks)
        need(len(data)==archive['bytes'] and sha(data)==archive['sha256'], 'ORIGINAL_ZIP')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            need(len(z.infolist())==len(archive['members']) and set(z.namelist())==set(archive['members']), 'EXACT_MEMBERS')
            for member, expected in archive['members'].items():
                need(z.getinfo(member).file_size==expected['bytes'] and expected['bytes']<200000, 'BOUNDED_MEMBER')
                value=z.read(member)
                need(sha(value)==expected['sha256'], 'MEMBER_INTEGRITY')
                originals[member]=value
    for copy, member in [('proof.json','proof.json'), ('cli-receipt.json','verification/ctrader-cli-metadata/receipt.json')]:
        need((folder/copy).read_bytes()==originals[member], 'EXACT_ORIGINAL_COPY')
    p=json.loads(originals['proof.json'])
    result=proof(p)
    need(p['source_sha']==manifest['pr_test_merge'] and p['checks']==182, 'EXECUTED_SOURCE')
    receipt=json.loads(originals['verification/ctrader-cli-metadata/receipt.json'])
    need(receipt['source_sha']==manifest['pr_test_merge'] and receipt['product_target_framework']=='net6.0' and
         receipt['native_metadata_returncode']==0 and receipt['native_malformed_returncode']==1 and
         receipt['native_vendor_metadata_read'] is True, 'METADATA_ONLY_RECEPTION')
    for key in ('backtest_command_invoked','broker_credentials_supplied','broker_network_available','cloud_activated',
                'economic_edge_proven','hard21_proven','native_storage_recovery_proven','native_trading_callbacks_proven','run_command_invoked'):
        need(receipt[key] is False, 'NO_NATIVE_OR_ECONOMIC_PROMOTION')
    need(receipt['broker_orders']==receipt['new_research_trials']==0, 'ZERO_TRADING_OR_TRIALS')
    for suffix, key in [('native_tick_replay_v1.algo','artifact_sha256'), ('MxmReferenceBot.dll','product_assembly_sha256')]:
        data=originals['research_core_v4/native_tick_replay_v1/csharp/bin/Release/net6.0/'+suffix]
        need(sha(data)==receipt[key], 'COMPILED_PRODUCT_HASH')
    need(sha(originals['verification/ctrader-cli-metadata/metadata.stdout.txt'])==receipt['metadata_stdout_sha256'], 'VENDOR_OUTPUT_HASH')
    changed=[path for path,digest in manifest['implementation_sha256'].items() if not (root/path).is_file() or sha((root/path).read_bytes())!=digest]
    result.update(original_run=manifest['run_id'], original_job=manifest['job_id'], original_source=manifest['pr_test_merge'],
                  original_archives_verified=True, current_implementation_matches_original=not changed, changed_implementation_paths=changed,
                  economic_edge_proven=False, hard21_proven=False)
    return result
if __name__=='__main__':
    print(json.dumps(verify(),sort_keys=True))
