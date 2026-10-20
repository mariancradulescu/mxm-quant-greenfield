"""One finite GitHub-native move of existing credentials into restricted environments.

No broker traffic, new keys, plaintext artifacts or user-provided destinations.
Only the existing App may encrypt copies. Originals are removed only after two
independent environment jobs verified distinct destination names (no repository
secret fallback), native job completion and unchanged original metadata.
"""
import base64
import contextlib
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from .common import need, encoded, digest, LabError
from .native_acl_probe import API, REPO, PREFIX
from research_core_v4.p0_successor_a_20261017.issuer import (
    APP_ID, INSTALLATION_ID, REPO_ID, KEY_FP, http, _b64)

EXECUTION = 'mxm-remediation-p0-p4-20261015-v1'
WORKFLOW = '.github/workflows/mxm-r3-secret-isolation.yml'
OWNER_FP = '464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'
GROUPS = {
    'custody': ('mxm-r3-custody-v1', {
        'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM': 'R3_CUSTODY_PRIVATE_KEY_PEM'}),
    'pepperstone': ('mxm-r3-pepperstone-v1', {
        'CTRADER_CLIENT_ID': 'R3_CTRADER_CLIENT_ID',
        'CTRADER_CLIENT_SECRET': 'R3_CTRADER_CLIENT_SECRET',
        'CTRADER_ACCESS_TOKEN': 'R3_CTRADER_ACCESS_TOKEN',
        'CTRADER_REFRESH_TOKEN': 'R3_CTRADER_REFRESH_TOKEN'}),
}
JOBS = {'copy': 'isolation-copy', 'custody': 'verify-custody',
        'pepperstone': 'verify-pepperstone', 'cleanup': 'isolation-cleanup'}
PERMISSIONS = {'copy': {'environments': 'write', 'secrets': 'read'},
               'cleanup': {'environments': 'read', 'secrets': 'write'}}


def context(stage):
    need(stage in JOBS and os.environ.get('GITHUB_REPOSITORY') == REPO and
         os.environ.get('GITHUB_REF') == 'refs/heads/' + EXECUTION and
         os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and
         os.environ.get('GITHUB_RUN_ATTEMPT') == '1' and
         os.environ.get('GITHUB_JOB') == JOBS[stage], 'ISOLATION_NATIVE_CONTEXT')
    workflow_ref = REPO + '/' + WORKFLOW + '@refs/heads/' + EXECUTION
    need(os.environ.get('GITHUB_WORKFLOW_REF') == workflow_ref and
         os.environ.get('GITHUB_WORKFLOW_SHA') == os.environ.get('GITHUB_SHA'), 'ISOLATION_WORKFLOW_PIN')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    need(source == os.environ.get('ISOLATION_SOURCE_SHA') and len(source) == 40,
         'ISOLATION_CODE_PIN')
    return {'repository': REPO, 'run_id': os.environ['GITHUB_RUN_ID'],
            'attempt': 1, 'execution_sha': os.environ['GITHUB_SHA'],
            'source_sha': source, 'workflow_ref': workflow_ref}


def validate_environment(value, policies, name):
    need(value['name'] == name and value.get('can_admins_bypass') is False,
         'ISOLATION_ENV_BYPASS')
    need(value.get('deployment_branch_policy') == {
        'protected_branches': False, 'custom_branch_policies': True}, 'ISOLATION_ENV_POLICY')
    need(policies.get('total_count') == 1 and
         [(p['name'], p['type']) for p in policies['branch_policies']] == [(EXECUTION, 'branch')],
         'ISOLATION_ENV_EXACT_BRANCH')
    need({r['type'] for r in value.get('protection_rules', [])} == {'branch_policy'},
         'ISOLATION_AUTONOMOUS_ENV')


def environments(token):
    # Environment configuration is public metadata; use native Actions read,
    # never broaden the App token to Administration or Actions.
    token = os.environ['GH_TOKEN']
    for name, _ in GROUPS.values():
        _, value = http(PREFIX + 'environments/' + name, token)
        _, policies = http(PREFIX + 'environments/' + name + '/deployment-branch-policies', token)
        validate_environment(value, policies, name)


@contextlib.contextmanager
def app_token(stage):
    need(stage in PERMISSIONS, 'ISOLATION_TOKEN_STAGE')
    token = None
    with tempfile.TemporaryDirectory() as directory:
        key = Path(directory) / 'key'
        key.write_text(os.environ.pop('SUCCESSOR_APP_PRIVATE_KEY'))
        key.chmod(0o600)
        public = subprocess.check_output(['openssl', 'pkey', '-in', str(key), '-pubout', '-outform', 'DER'],
                                         stderr=subprocess.DEVNULL)
        need('SHA256:' + base64.b64encode(hashlib.sha256(public).digest()).decode() == KEY_FP,
             'ISOLATION_EXISTING_APP_KEY')
        now = int(time.time())
        message = (_b64(encoded({'alg': 'RS256', 'typ': 'JWT'})) + '.' +
                   _b64(encoded({'iss': str(APP_ID), 'iat': now - 30, 'exp': now + 300}))).encode()
        signature = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', str(key)],
            input=message, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
        jwt = message.decode() + '.' + _b64(signature)
        _, app = http('/app', jwt)
        _, installation = http('/app/installations/' + str(INSTALLATION_ID), jwt)
        need(app['id'] == APP_ID and installation['app_id'] == APP_ID and
             installation['account']['id'] == 322088485, 'ISOLATION_APP_INSTALLATION')
        _, issued = http('/app/installations/' + str(INSTALLATION_ID) + '/access_tokens', jwt, 'POST',
            {'repository_ids': [REPO_ID], 'permissions': PERMISSIONS[stage]})
        token = issued.pop('token')
        try:
            actual = {k: v for k, v in issued['permissions'].items() if k != 'metadata'}
            need(actual == PERMISSIONS[stage], 'ISOLATION_TOKEN_EXACT_PERMISSIONS')
            need([r['id'] for r in issued.get('repositories', [])] == [REPO_ID],
                 'ISOLATION_TOKEN_EXACT_REPOSITORY')
            yield token
        finally:
            status, _ = http('/installation/token', token, 'DELETE')
            need(status == 204, 'ISOLATION_TOKEN_REVOCATION')


def commitment(value, challenge, name):
    need(isinstance(value, str) and len(value) >= 8 and len(challenge) == 64, 'ISOLATION_VALUE_MISSING')
    return hmac.new(value.encode(), ('mxm.r3.secret-move.v1:' + challenge + ':' + name).encode(),
                    hashlib.sha256).hexdigest()


def owner_fingerprint(value):
    with tempfile.TemporaryDirectory() as directory:
        key = Path(directory) / 'owner-key'
        key.write_text(value)
        key.chmod(0o600)
        der = subprocess.check_output(['openssl', 'pkey', '-in', str(key), '-pubout', '-outform', 'DER'],
                                      stderr=subprocess.DEVNULL)
    need(hashlib.sha256(der).hexdigest() == OWNER_FP, 'ISOLATION_OWNER_RECIPIENT')
    return OWNER_FP


def set_copy(token, environment, destination, value):
    need((environment, destination) in [(env, dst) for env, mapping in GROUPS.values()
                                       for dst in mapping.values()], 'ISOLATION_FIXED_DESTINATION')
    # gh seals using GitHub's public key. Values go only through stdin. The child
    # receives no repository credentials, App private key, or other source values.
    with tempfile.TemporaryDirectory() as directory:
        result = subprocess.run(['gh', 'secret', 'set', destination, '--repo', REPO,
                                 '--env', environment], input=value.encode(),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={'PATH': '/usr/bin:/bin', 'HOME': directory, 'GH_CONFIG_DIR': directory,
                 'GH_HOST': 'github.com', 'GH_TOKEN': token, 'GH_PROMPT_DISABLED': '1'}, timeout=45)
        need(result.returncode == 0, 'ISOLATION_SEALED_COPY_FAILED')


def secret_metadata(token, suffix):
    status, metadata = http(PREFIX + suffix, token)
    need(status == 200, 'ISOLATION_SECRET_METADATA')
    return {key: metadata[key] for key in ('name', 'created_at', 'updated_at')}


def emit(stage, proof):
    Path('isolation-' + stage + '.json').write_bytes(encoded(proof))
    # Public HMAC commitments and native identities only, never secret values.
    print('MXM_SECRET_ISOLATION ' + encoded(proof).decode(), flush=True)


def copy(ctx):
    challenge = secrets.token_hex(32)
    values = {src: os.environ.pop(src, '') for _, mapping in GROUPS.values() for src in mapping}
    for name, value in values.items():
        commitment(value, challenge, name)
    owner_fingerprint(values['MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'])
    rows = []
    with app_token('copy') as token:
        environments(token)
        # Verify the entire move before the first write; partial failure never deletes originals.
        originals = {name: secret_metadata(token, 'actions/secrets/' + name) for name in values}
        for environment, mapping in GROUPS.values():
            for src, dst in mapping.items():
                set_copy(token, environment, dst, values[src])
                metadata = secret_metadata(token, 'environments/' + environment + '/secrets/' + dst)
                rows.append({'source': src, 'destination': dst, 'environment': environment,
                             'original': originals[src], 'copy': metadata,
                             'commitment': commitment(values[src], challenge, src)})
        environments(token)
    emit('copy', {'schema': 'mxm.secret-isolation.copy.v1', 'context': ctx, 'challenge': challenge,
                  'owner_public_spki_sha256': OWNER_FP, 'rows': rows})


def read_copy(ctx):
    proof = json.loads(Path('receipts/isolation-copy.json').read_bytes())
    need(proof.get('schema') == 'mxm.secret-isolation.copy.v1' and proof.get('context') == ctx,
         'ISOLATION_COPY_IDENTITY')
    expected = {(env, src, dst) for env, mapping in GROUPS.values() for src, dst in mapping.items()}
    rows = proof.get('rows', [])
    need(len(rows) == len(expected) and
         {(r['environment'], r['source'], r['destination']) for r in rows} == expected,
         'ISOLATION_EXACT_COPY_SET')
    return proof


def verify(group, ctx):
    proof = read_copy(ctx)
    environment, mapping = GROUPS[group]
    for row in proof['rows']:
        if row['environment'] == environment:
            value = os.environ.pop(row['destination'], '')
            need(hmac.compare_digest(commitment(value, proof['challenge'], row['source']),
                                     row['commitment']), 'ISOLATION_COPY_VALUE_MISMATCH')
            if group == 'custody':
                owner_fingerprint(value)
    emit(group, {'schema': 'mxm.secret-isolation.verified.v1', 'context': ctx,
                 'environment': environment, 'copy_sha256': digest(proof),
                 'destinations': sorted(mapping.values()), 'verified': True})


def verify_receipts(ctx, proof, receipts, jobs):
    need(len(receipts) == 2, 'ISOLATION_VERIFIERS_REQUIRED')
    expected_names = [JOBS[x] for x in ('copy', 'custody', 'pepperstone')]
    native = [j for j in jobs if j['name'] in expected_names]
    need(len(native) == 3 and {j['name'] for j in native} == set(expected_names) and
         all(j['status'] == 'completed' and j['conclusion'] == 'success' and
             str(j['run_id']) == ctx['run_id'] for j in native), 'ISOLATION_NATIVE_VERIFIERS')
    for group, receipt in zip(('custody', 'pepperstone'), receipts):
        env, mapping = GROUPS[group]
        need(receipt == {'schema': 'mxm.secret-isolation.verified.v1', 'context': ctx,
            'environment': env, 'copy_sha256': digest(proof),
            'destinations': sorted(mapping.values()), 'verified': True}, 'ISOLATION_VERIFIER_RECEIPT')


def cleanup(ctx):
    proof = read_copy(ctx)
    receipts = [json.loads(Path('receipts/isolation-' + group + '.json').read_bytes())
                for group in ('custody', 'pepperstone')]
    api = API(os.environ['GH_TOKEN'])
    run = api.get('actions/runs/' + ctx['run_id'])
    need(run['head_sha'] == ctx['execution_sha'] and run['run_attempt'] == 1 and
         run['event'] == 'workflow_dispatch' and run['path'] == WORKFLOW and
         run['head_branch'] == EXECUTION, 'ISOLATION_NATIVE_RUN')
    # Exactly four jobs; reject pagination/truncation or unexpected duplicate attempts.
    job_inventory = api.get('actions/runs/' + ctx['run_id'] + '/jobs')
    need(job_inventory['total_count'] == 4 and len(job_inventory['jobs']) == 4,
         'ISOLATION_NATIVE_JOB_SET')
    verify_receipts(ctx, proof, receipts, job_inventory['jobs'])
    removed = []
    with app_token('cleanup') as token:
        environments(token)
        # All original metadata and destination copies are checked before any deletion.
        for row in proof['rows']:
            need(secret_metadata(token, 'actions/secrets/' + row['source']) == row['original'],
                 'ISOLATION_ORIGINAL_CHANGED')
            need(secret_metadata(token, 'environments/' + row['environment'] + '/secrets/' + row['destination'])
                 == row['copy'], 'ISOLATION_COPY_CHANGED')
        for row in proof['rows']:
            status, _ = http(PREFIX + 'actions/secrets/' + row['source'], token, 'DELETE')
            need(status == 204, 'ISOLATION_REMOVE_ORIGINAL_FAILED')
            absent_status, _ = API(token).call('GET', PREFIX + 'actions/secrets/' + row['source'])
            need(absent_status == 404, 'ISOLATION_ORIGINAL_STILL_PRESENT')
            removed.append(row['source'])
            # Public checkpoint is emitted after EACH removal so interruption is reconcilable.
            emit('cleanup', {'schema': 'mxm.secret-isolation.cleanup.v1', 'context': ctx,
                'copy_sha256': digest(proof), 'removed_repository_secrets': list(removed),
                'complete': len(removed) == 5, 'operational_acceptance': False})


def build_workflow(source_sha):
    """The only installable workflow. Fixed source/destinations; no user inputs."""
    import re
    need(re.fullmatch('[a-f0-9]{40}', source_sha) is not None, 'ISOLATION_SOURCE_FORMAT')
    checkout = {'uses': 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
                'with': {'ref': source_sha, 'persist-credentials': False}}
    upload = 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
    download = 'actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093'
    guard = ("github.repository == '" + REPO + "' && github.ref == 'refs/heads/" + EXECUTION +
             "' && github.event_name == 'workflow_dispatch' && github.run_attempt == 1")
    jobs = {}
    for stage in ('copy', 'custody', 'pepperstone', 'cleanup'):
        name = JOBS[stage]
        job = {'if': guard, 'runs-on': 'ubuntu-24.04', 'timeout-minutes': 8,
               'permissions': {'contents': 'read', 'actions': 'read'},
               'steps': [checkout.copy()]}
        if stage == 'copy':
            job['environment'] = 'mxm-p0-successor-issuer-v1'
            secret_names = ['SUCCESSOR_APP_PRIVATE_KEY'] + [src for _, mapping in GROUPS.values() for src in mapping]
            predecessors = []
        elif stage == 'cleanup':
            job['environment'] = 'mxm-p0-successor-issuer-v1'
            job['needs'] = [JOBS[x] for x in ('copy', 'custody', 'pepperstone')]
            secret_names = ['SUCCESSOR_APP_PRIVATE_KEY']
            predecessors = ['copy', 'custody', 'pepperstone']
        else:
            job['environment'] = GROUPS[stage][0]
            job['needs'] = [JOBS['copy']]
            secret_names = list(GROUPS[stage][1].values())
            predecessors = ['copy']
        for predecessor in predecessors:
            job['steps'].append({'uses': download, 'with': {
                'name': 'mxm-r3-isolation-' + predecessor + '-${{ github.run_id }}', 'path': 'receipts'}})
        job['steps'].append({'name': 'Finite native secret isolation: ' + stage,
            'run': 'python3 -m research_core_v4.laboratory.secret_isolation ' + stage,
            'env': dict({'GH_TOKEN': '${{ github.token }}'},
                        **{n: '${{ secrets.' + n + ' }}' for n in secret_names})})
        job['steps'].append({'uses': upload, 'if': 'always()', 'with': {
            'name': 'mxm-r3-isolation-' + stage + '-${{ github.run_id }}',
            'path': 'isolation-' + stage + '.json', 'if-no-files-found': 'error', 'retention-days': 90}})
        jobs[name] = job
    return {'name': 'MXM R3 finite credential isolation; no economic execution',
            'on': {'workflow_dispatch': {}}, 'permissions': {},
            'concurrency': {'group': 'mxm-r3-secret-isolation', 'cancel-in-progress': False},
            'env': {'ISOLATION_SOURCE_SHA': source_sha}, 'jobs': jobs}


def verify_installed_workflow(ctx):
    import urllib.parse
    path = PREFIX + 'contents/' + WORKFLOW + '?ref=' + ctx['execution_sha']
    status, value = http(path, os.environ['GH_TOKEN'])
    need(status == 200 and value['encoding'] == 'base64', 'ISOLATION_WORKFLOW_READ')
    actual = json.loads(base64.b64decode(value['content']))
    need(actual == build_workflow(ctx['source_sha']), 'ISOLATION_EXACT_INSTALLED_WORKFLOW')


def main():
    import sys
    try:
        stage = sys.argv[1]
        ctx = context(stage)
        verify_installed_workflow(ctx)
        if stage == 'copy':
            copy(ctx)
        elif stage == 'cleanup':
            cleanup(ctx)
        else:
            verify(stage, ctx)
    except LabError as error:
        print(str(error), flush=True)
        raise SystemExit(1) from None
    except Exception:
        # Never include credential-bearing environment, HTTP bodies or subprocess input.
        print('LAB_ISOLATION_FAILED_CLOSED_RECONCILE_NATIVE_METADATA', flush=True)
        raise SystemExit(1) from None

if __name__ == '__main__':
    main()
