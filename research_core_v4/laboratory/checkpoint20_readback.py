"""Read the conserved checkpoint20 and corpus; no authority/evidence publication.

This finite native diagnostic supplies real decryption/migration/scale evidence.
It does not admit or execute a programme and cannot issue an E2E certificate.
Existing crypto, cache/archive and TypedTrialBook transition are reused.
"""
import base64
import gzip
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import time
from copy import deepcopy
from .common import need, encoded, digest, bytes_digest, LabError, number
from .live_preflight_v3 import EVIDENCE, SOURCE, OWNER, ACTIVE
from .protocol import verify_checkpoint20_public, typed_source_transition, accounting
from .custody import restore_ciphertext
from .runtime import file_at
from .secret_isolation import REPO, EXECUTION, OWNER_FP
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json, unpack
from research_core_v4.remediation_p0_p4_20261015 import owner

WORKFLOW = '.github/workflows/mxm-r3-checkpoint20-readback.yml'
PRIVATE_SHA = '01227d7a7715a89bc1bfcf6fac183fbaec3b941f8c61281fb3c0e4f01f232fa6'
OUT = Path('verification/checkpoint20-readback')


def authority(state):
    return {'schema': 'mxm.integrated-typed-predecessor.v3', 'evidence_oid': EVIDENCE,
        'source_sha': SOURCE, 'sequence': 20, 'ciphertext_sha256': state['ciphertext_sha256'],
        'private_sha256': PRIVATE_SHA, 'public_state_sha256': digest(state)}


def preserve_check(before, after):
    need(after['sequence'] == before['sequence'] == 20 and
         after['trial_book'] == before['trial_book'] and
         after['shared_catalogue'] == before['shared_catalogue'] and
         after['programmes'] == before['programmes'] and
         accounting(after['trial_book']) == accounting(before['trial_book']), 'CP20_NO_RESET')
    need(after['pending'] is before['pending'] is None, 'CP20_NO_OPEN_EXPOSURE')


def reject(call, label):
    try:
        call()
    except Exception:
        return label
    need(False, 'CP20_NEGATIVE_ACCEPTED_' + label)


def anchors(route):
    for branch, expected in [('mxm-o04-integrated-laboratory-evidence', EVIDENCE),
        ('mxm-o04-successor-code-integrated-p0-r2', SOURCE),
        ('mxm-o04-accepted-owner-1807-v1', OWNER), ('mxm-o04-active-v1', ACTIVE)]:
        need(route.json('git/ref/heads/' + branch)['object']['sha'] == expected,
             'CP20_CONSERVED_REF_CHANGED')
    for branch in ('main', EXECUTION):
        effective = route.json('rules/branches/' + branch)
        need({'pull_request', 'required_status_checks', 'deletion', 'non_fast_forward'} <=
             {x['type'] for x in effective}, 'CP20_CONTROL_PLANE_RULES')


def context(stage, route):
    expected_job = {'produce': 'checkpoint20-readback', 'cold': 'independent-cold-readback'}
    need(stage in expected_job and os.environ.get('GITHUB_REPOSITORY') == REPO and
         os.environ.get('GITHUB_REF') == 'refs/heads/' + EXECUTION and
         os.environ.get('GITHUB_RUN_ATTEMPT') == '1' and
         os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and
         os.environ.get('GITHUB_JOB') == expected_job[stage], 'CP20_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY', 'CTRADER_CLIENT_ID',
         'CTRADER_CLIENT_SECRET', 'CTRADER_ACCESS_TOKEN', 'R3_CTRADER_ACCESS_TOKEN')),
         'CP20_NO_APP_OR_BROKER_KEYS')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    need(source == os.environ['CHECKPOINT_SOURCE_SHA'], 'CP20_EXACT_CODE_PIN')
    trigger = os.environ['GITHUB_SHA']
    need(os.environ['GITHUB_WORKFLOW_SHA'] == trigger and os.environ['GITHUB_WORKFLOW_REF'] ==
         REPO + '/' + WORKFLOW + '@refs/heads/' + EXECUTION, 'CP20_WORKFLOW_PIN')
    workflow = strict_json(file_at(route, WORKFLOW, trigger))
    need(workflow == build_workflow(source), 'CP20_EXACT_WORKFLOW')
    return {'run_id': int(os.environ['GITHUB_RUN_ID']), 'attempt': 1, 'source_sha': source,
            'execution_sha': trigger, 'workflow': WORKFLOW}


def inspect_corpus(key, tmp):
    from research_core_v4.autonomous_laboratory_20261019_v6.runtime import corpus, registry, ROOT
    registry_value = registry()
    manifest = strict_json((ROOT / registry_value['cached_input']['manifest']).read_bytes())
    size = sum(x['length'] for x in manifest['parts'])
    started = time.perf_counter()
    data = corpus(key, tmp, registry_value)
    elapsed = time.perf_counter() - started
    quotes = data.get('raw_quote_receipts', [])
    need(isinstance(quotes, list) and len(quotes) > 0, 'CP20_PRESERVED_CORPUS_EMPTY')
    sides = 0
    numeric_sides = 0
    symbols = set()
    times = []
    for row in quotes:
        symbols.add(str(row['symbol_id']))
        times.append(row['boundary_ms'])
        sides += len(row['sides'])
        numeric_sides += sum(number(v.get('price')) and v['price'] > 0 and
                             type(v.get('timestamp_ms')) is int for v in row['sides'].values())
    return {'classification': 'PRESERVED_ENCRYPTED_CORPUS_READBACK',
        'archive_sha256': registry_value['cached_input']['archive_sha256'],
        'ciphertext_sha256': registry_value['cached_input']['ciphertext_sha256'],
        'producer_run_id': registry_value['cached_input']['run_id'],
        'producer_source_sha': registry_value['cached_input']['source_sha'],
        'stored_archive_bytes': size, 'archive_parts': len(manifest['parts']),
        'load_verify_decrypt_seconds': elapsed, 'raw_quote_receipts': len(quotes),
        'side_records': sides, 'numeric_price_timestamp_side_records': numeric_sides,
        'count_semantics': 'SIDE_RECORDS_NOT_SYNCHRONOUS_QUOTE_PAIRS_OR_CONTINUOUS_COVERAGE',
        'distinct_symbols': len(symbols),
        'first_boundary_ms': min(times), 'last_boundary_ms': max(times),
        'continuous_coverage_demonstrated': False, 'broker_requests': 0}


def main(stage):
    route = GetOnly()
    ctx = context(stage, route)
    anchors(route)
    state = strict_json(file_at(route, 'typed-successor/program-state.json', EVIDENCE))
    auth = authority(state)
    verify_checkpoint20_public(state, auth, EVIDENCE)
    manifest = strict_json(file_at(route, state['ciphertext_path'], EVIDENCE))
    started = time.perf_counter()
    blob = restore_ciphertext(manifest, lambda path: file_at(route, path, EVIDENCE))
    fetch_seconds = time.perf_counter() - started
    need(bytes_digest(blob) == state['ciphertext_sha256'], 'CP20_CIPHER_HASH')
    os.umask(0o077)
    OUT.mkdir(parents=True, exist_ok=True)
    value = os.environ.pop('R3_CUSTODY_PRIVATE_KEY_PEM')
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as folder:
        tmp = Path(folder)
        key = tmp / 'owner.pem'
        key.write_text(value)
        key.chmod(0o600)
        value = None
        der = subprocess.check_output(['openssl', 'pkey', '-in', str(key), '-pubout', '-outform', 'DER'], stderr=subprocess.DEVNULL)
        need(bytes_digest(der) == OWNER_FP, 'CP20_OWNER_FINGERPRINT')
        started = time.perf_counter()
        private = strict_json(unpack(owner.bounded_decrypt(blob, key, tmp)), max_elements=8000000)
        decrypt_seconds = time.perf_counter() - started
        need(digest(private) == PRIVATE_SHA, 'CP20_PRIVATE_HASH')
        successor = typed_source_transition(private, state, auth, ctx['source_sha'], evidence_oid=EVIDENCE)
        preserve_check(private, successor)
        # Exercise the repaired actual restore path on every authentic archived
        # programme. No task is selected/executed and no historic result replayed.
        from .programs import Laboratory
        from .execution import catalogue_extends
        restored_programmes=0
        for saved in private['programmes'].values():
            restored_lab=Laboratory.restore(saved,private['history'])
            need(restored_lab.checkpoint()==saved,'CP20_ARCHIVED_PROGRAMME_RESTORE')
            catalogue_extends(private['shared_catalogue'],saved['catalogue'])
            restored_programmes+=1
        proof = {'schema': 'mxm.checkpoint20-native-readback.v1', 'context': ctx,
            'stage': stage, 'predecessor_evidence_oid': EVIDENCE, 'sequence': 20,
            'ciphertext_sha256': bytes_digest(blob), 'private_sha256': digest(private),
            'migrated_private_sha256': digest(successor),
            'trial_book_sha256': digest(private['trial_book']),
            'shared_catalogue_sha256': digest(private['shared_catalogue']),
            'programmes_sha256': digest(private['programmes']), 'accounting': accounting(private['trial_book']),
            'ciphertext_bytes': len(blob), 'checkpoint_parts': len(manifest['parts']),
            'archived_programmes_restored_without_execution': restored_programmes,
            'fetch_verify_seconds': fetch_seconds, 'decrypt_parse_seconds': decrypt_seconds,
            'orders': 0, 'broker_requests': 0, 'economic_outcomes': 0,
            'authoritative_checkpoint_published': False, 'operational_acceptance': False,
            'research_capability_accepted': False}
        if stage == 'produce':
            bad = deepcopy(auth)
            bad['evidence_oid'] = '0' * 40
            wrong_private = deepcopy(private)
            wrong_private['sequence'] = 19
            bad_blob = bytearray(blob)
            bad_blob[-1] ^= 1
            # Ephemeral adversarial fixture only; never a credential/custodian.
            wrong_key = tmp / 'wrong-test-key.pem'
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt',
                'rsa_keygen_bits:2048', '-out', str(wrong_key)], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, check=True, timeout=30)
            wrong_key.chmod(0o600)
            proof['negative_probes'] = [
                reject(lambda: verify_checkpoint20_public(state, bad, EVIDENCE), 'WRONG_EVIDENCE_PARENT'),
                reject(lambda: typed_source_transition(wrong_private, state, auth, ctx['source_sha'], evidence_oid=EVIDENCE), 'PRIVATE_MIX'),
                reject(lambda: owner.bounded_decrypt(bytes(bad_blob), key, tmp), 'CIPHERTEXT_BITFLIP'),
                reject(lambda: owner.bounded_decrypt(blob, wrong_key, tmp), 'EPHEMERAL_WRONG_KEY'),
                reject(lambda: restore_ciphertext(manifest, lambda path: file_at(route, path, EVIDENCE).strip()[:-4]), 'CIPHERTEXT_PART_TRUNCATION')]
            from research_core_v4.shallow_m5_support_v2_production import encrypt_shard, public_spki_sha256
            pub = Path('research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem')
            need(public_spki_sha256(pub) == OWNER_FP, 'CP20_EXISTING_RECIPIENT')
            archive = OUT / 'migrated-checkpoint.mxmenc'
            encrypt_shard(gzip.compress(encoded(successor), mtime=0), public_key=pub, output=archive)
            proof['migrated_ciphertext_sha256'] = bytes_digest(archive.read_bytes())
            proof['corpus_benchmark'] = inspect_corpus(key, tmp)
        else:
            producer = strict_json((OUT / 'produce.json').read_bytes())
            need(producer['context'] == ctx and producer['private_sha256'] == digest(private)
                 and producer['migrated_private_sha256'] == digest(successor), 'CP20_INDEPENDENT_MIGRATION_MISMATCH')
            archive = (OUT / 'migrated-checkpoint.mxmenc').read_bytes()
            need(bytes_digest(archive) == producer['migrated_ciphertext_sha256'], 'CP20_ENCRYPTED_HANDOFF_HASH')
            restored = strict_json(unpack(owner.bounded_decrypt(archive, key, tmp)), max_elements=8000000)
            need(restored == successor, 'CP20_COLD_ENCRYPTED_RESTORE')
            preserve_check(private, restored)
            proof['producer_proof_sha256'] = digest(producer)
            proof['migrated_ciphertext_sha256'] = bytes_digest(archive)
            proof['fresh_job_encrypted_readback'] = True
        proof['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        anchors(route)
        (OUT / (stage + '.json')).write_bytes(encoded(proof))
        print('MXM_CHECKPOINT20_READBACK ' + encoded(proof).decode(), flush=True)


def build_workflow(source):
    import re
    need(re.fullmatch('[0-9a-f]{40}', source) is not None, 'CP20_SOURCE_FORMAT')
    checkout = {'uses': 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
                'with': {'ref': source, 'persist-credentials': False}}
    jobs = {}
    for stage, job_name in [('produce', 'checkpoint20-readback'), ('cold', 'independent-cold-readback')]:
        steps = [checkout, {'run': 'python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock'}]
        if stage == 'cold':
            steps.append({'uses': 'actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093',
                'with': {'name': 'mxm-r3-checkpoint20-produce-${{ github.run_id }}', 'path': str(OUT)}})
        steps += [{'name': 'Conserved checkpoint20: ' + stage,
            'run': 'python3 -m research_core_v4.laboratory.checkpoint20_readback ' + stage,
            'env': {'GH_TOKEN': '${{ github.token }}',
                    'R3_CUSTODY_PRIVATE_KEY_PEM': '${{ secrets.R3_CUSTODY_PRIVATE_KEY_PEM }}'}},
            {'uses': 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02',
             'with': {'name': 'mxm-r3-checkpoint20-' + stage + '-${{ github.run_id }}',
                      'path': str(OUT), 'if-no-files-found': 'error', 'retention-days': 90}}]
        job = {'if': "github.repository == '" + REPO + "' && github.ref == 'refs/heads/" + EXECUTION + "' && github.run_attempt == 1",
               'runs-on': 'ubuntu-24.04', 'timeout-minutes': 15,
               'environment': 'mxm-r3-custody-v1', 'permissions': {'contents': 'read', 'actions': 'read'}, 'steps': steps}
        if stage == 'cold':
            job['needs'] = ['checkpoint20-readback']
        jobs[job_name] = job
    return {'name': 'MXM R3 conserved checkpoint20 private readback', 'on': {'workflow_dispatch': {}},
            'permissions': {}, 'env': {'CHECKPOINT_SOURCE_SHA': source},
            'concurrency': {'group': 'mxm-r3-checkpoint20-readback', 'cancel-in-progress': False}, 'jobs': jobs}

if __name__ == '__main__':
    import sys
    try:
        main(sys.argv[1])
    except LabError as error:
        print(str(error), flush=True)
        raise SystemExit(1) from None
    except Exception:
        print('LAB_CP20_FAILED_CLOSED_NO_STATE_PUBLICATION', flush=True)
        raise SystemExit(1) from None
