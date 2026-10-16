"""Bounded native GitHub GET observations. No broker, key, environment or writer IO."""
import hashlib
import json
import os
from pathlib import Path
import unittest
import urllib.error
import urllib.request
from . import transition as t

REPO = 'mariancradulescu/mxm-quant-greenfield'
BRANCH = 'mxm-remediation-p0-p4-20261015-v1'
REFS = {
    'owner_stop': ('mxm-o04-accepted-owner-1807-v1', t.STOP),
    'staging': ('mxm-o04-stage-authority-v1', t.STAGING),
    'canonical': ('performance-research-v3-20260922', '9c5f9f1b7f2d73f98bb188a2651fd9a3c00df6b9'),
    'campaign': ('mxm-autonomous-native-20261015-v1', '3cb073e54fe3189063c2737c6337d3404b713710'),
    'issuer': ('mxm-o04-issuer-code-v3', '639ebc99ab2237f1b68cc152537fe919900f338a'),
}
RULES = {
    25222248: ('refs/heads/mxm-o04-*', {'deletion', 'non_fast_forward', 'required_linear_history'}),
    25222426: ('refs/heads/mxm-o04-accepted-*', {'creation', 'update', 'deletion', 'non_fast_forward', 'required_linear_history'}),
    25231211: ('refs/heads/mxm-o04-stage-authority-v1', {'creation', 'update'}),
    25232285: ('refs/heads/mxm-o04-issuer-code-v3', {'creation', 'update'}),
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise t.lab.Denied('AUTHENTICATED_REDIRECT_FORBIDDEN')

class ReadOnlyGitHub:
    def __init__(self, token, run_id, opener=None):
        t.lab.need(str(run_id).isdigit(), 'RUN_ID')
        self.allowed = {'git/ref/heads/' + name for name, _ in REFS.values()}
        self.allowed.update({'rulesets/' + str(rule) for rule in RULES})
        self.allowed.update({'releases/412686323', 'git/ref/heads/' + BRANCH,
                             'git/ref/heads/mxm-o04-active-v1',
                             'branches/' + BRANCH + '/protection', 'actions/runs/' + str(run_id)})
        self.token = token
        self.opener = opener or urllib.request.build_opener(NoRedirect()).open
        self.calls = []

    def request(self, path, method='GET', data=None):
        # Guards run before constructing any authenticated network request.
        t.lab.need(method == 'GET' and data is None, 'READ_ONLY_METHOD')
        t.lab.need(path in self.allowed, 'READ_ONLY_ENDPOINT')
        self.calls.append({'method': 'GET', 'path': path})
        req = urllib.request.Request('https://api.github.com/repos/' + REPO + '/' + path,
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                     'User-Agent': 'MXM-P0-preparation-read-only'}, method='GET')
        try:
            with self.opener(req, timeout=30) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                t.lab.need(len(raw) <= 4 * 1024 * 1024, 'RESPONSE_BUDGET')
                return response.status, json.loads(raw), response.headers.get('Date')
        except urllib.error.HTTPError as ex:
            return ex.code, None, ex.headers.get('Date') if ex.headers else None

def snapshot(api, spec, source):
    refs = {}
    for name, (ref, expected) in REFS.items():
        status, value, date = api.request('git/ref/heads/' + ref)
        t.lab.need(status == 200 and value['object']['sha'] == expected, 'PRESERVED_REF_' + name.upper())
        refs[name] = {'ref': ref, 'oid': expected, 'http_date': date}
    status, value, _ = api.request('git/ref/heads/' + BRANCH)
    t.lab.need(status == 200 and value['object']['sha'] == source, 'SOURCE_HEAD_DRIFT')
    status, release, date = api.request('releases/412686323')
    t.lab.need(status == 200 and t.sha(release['body'].encode()) == spec['root_release_body_sha256'], 'OWNER_ANCHOR_DRIFT')
    body = json.loads(release['body'])
    t.lab.need(body['generation'] == 1807 and body['state'] == 'STOP_FAIL_CLOSED' and
               body['current_journal']['id'] == spec['journal_asset_id'] and
               body['current_journal']['canonical_sha256'] == spec['journal_canonical_sha256'], 'OWNER_ROOT')
    rules = {}
    for rule_id, (target, required) in RULES.items():
        status, rule, date = api.request('rulesets/' + str(rule_id))
        t.lab.need(status == 200 and rule['enforcement'] == 'active', 'RULE_INACTIVE')
        t.lab.need(rule['conditions']['ref_name'] == {'include': [target], 'exclude': []} and
                   {r['type'] for r in rule['rules']} == required, 'RULE_SCOPE')
        expected_bypass = [{'actor_id': 5343530, 'actor_type': 'Integration', 'bypass_mode': 'always'}] if rule_id == 25231211 else []
        if 'bypass_actors' in rule:
            t.lab.need(rule['bypass_actors'] == expected_bypass, 'RULE_BYPASS_CHANGED')
        rules[str(rule_id)] = {'canonical_response_sha256': t.sha(t.canonical(rule)),
            'target': target, 'types': sorted(required), 'enforcement': 'active',
            'bypass_observation': 'EXACT_EXPECTED_LIST' if 'bypass_actors' in rule else 'OMITTED_NOT_PROVEN_BY_THIS_GET',
            'http_date': date}
    return {'refs': refs, 'source_head': source, 'rules': rules,
            'OWNER_body_sha256': spec['root_release_body_sha256'], 'OWNER_generation': 1807,
            'OWNER_journal_asset_id': spec['journal_asset_id'], 'OWNER_journal_downloaded': False}

def stable(snapshot_value):
    value = json.loads(json.dumps(snapshot_value))
    for item in list(value['refs'].values()) + list(value['rules'].values()):
        item.pop('http_date', None)
    return value

class TransportTests(unittest.TestCase):
    def test_27_mutation_methods_never_reach_transport(self):
        touched = []
        api = ReadOnlyGitHub('SYNTHETIC_NOT_A_TOKEN', '1', lambda *a, **k: touched.append(True))
        for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'):
            with self.subTest(method=method), self.assertRaisesRegex(t.lab.Denied, '^READ_ONLY_METHOD$'):
                api.request('releases/412686323', method=method)
        self.assertEqual(touched, [])
        self.assertEqual(api.calls, [])

    def test_28_get_with_body_and_unlisted_paths_denied_before_io(self):
        touched = []
        api = ReadOnlyGitHub('SYNTHETIC_NOT_A_TOKEN', '1', lambda *a, **k: touched.append(True))
        with self.assertRaisesRegex(t.lab.Denied, '^READ_ONLY_METHOD$'):
            api.request('releases/412686323', data={})
        for path in ('../secrets', 'https://other.invalid', 'releases/412686323?ref=other', 'git/refs/heads/owner', 'actions/secrets'):
            with self.subTest(path=path), self.assertRaisesRegex(t.lab.Denied, '^READ_ONLY_ENDPOINT$'):
                api.request(path)
        self.assertEqual(touched, [])

    def test_29_redirect_cannot_forward_bearer_credential(self):
        with self.assertRaisesRegex(t.lab.Denied, '^AUTHENTICATED_REDIRECT_FORBIDDEN$'):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')

def main():
    spec = t.load_spec()
    plan_digest = t.validate_spec(spec)
    root = Path(__file__).resolve().parents[2]
    registry_bytes = (root / spec['registry_path']).read_bytes()
    t.lab.need(t.sha(registry_bytes) == spec['registry_sha256'], 'REGISTRY_CHANGED')
    registry = json.loads(registry_bytes)
    t.lab.need(len(registry['remaining_contracts']) == 28 and registry['reported_counts'] == spec['reported_counts'], 'REGISTRY_COUNTS_CHANGED')
    source = os.environ['GITHUB_SHA']
    t.lab.need(os.environ['GITHUB_REPOSITORY'] == REPO and os.environ['GITHUB_REF_NAME'] == BRANCH and
               os.environ['GITHUB_RUN_ATTEMPT'] == '1', 'PREPARATION_RUN_SCOPE')
    api = ReadOnlyGitHub(os.environ['GH_TOKEN'], os.environ['GITHUB_RUN_ID'])
    status, run, _ = api.request('actions/runs/' + os.environ['GITHUB_RUN_ID'])
    t.lab.need(status == 200 and run['head_sha'] == source and run['head_branch'] == BRANCH and
               run['event'] == 'push' and run['run_attempt'] == 1 and run['actor']['id'] == 322088485, 'RUN_BINDING')
    before = snapshot(api, spec, source)
    status, _, _ = api.request('branches/' + BRANCH + '/protection')
    admin_observation = {'http_status': status, 'interpretation': 'ADMINISTRATIVE_VISIBILITY_UNAVAILABLE_NOT_SAFE_PROOF' if status in (403, 404) else 'READ_AVAILABLE_NOT_A_GLOBAL_ACL_CERTIFICATE'}
    t.lab.need(status in (200, 403, 404), 'ADMIN_READ_UNEXPECTED_STATUS')
    active_status, active, _ = api.request('git/ref/heads/mxm-o04-active-v1')
    t.lab.need(active_status == 404, 'UNEXPECTED_REAL_AUTHORITY_EXISTS_STOP')
    after = snapshot(api, spec, source)
    t.lab.need(stable(before) == stable(after), 'READ_ONLY_INVARIANT_DRIFT')
    receipt = {'schema': 'mxm.p0.preparation.live-receipt.v1', 'run_id': os.environ['GITHUB_RUN_ID'],
        'attempt': 1, 'job': os.environ['GITHUB_JOB'], 'source_SHA': source,
        'plan_sha256': plan_digest, 'registry_sha256': spec['registry_sha256'],
        'before': before, 'after': after, 'preserved_equal': True,
        'future_active_ref_http_status': active_status, 'future_active_created': False,
        'administrative_read': admin_observation,
        'actions_policy_7689': 'ACCEPTED_PRIOR_EVIDENCE_REUSED;CURRENT_NATIVE_ADMIN_EXPORT_NOT_REACQUIRED',
        'historical_writers_reactivated': False, 'O04_2_reexecuted': False,
        'reported_counts_preserved': registry['reported_counts'],
        'all_28_remain_BLOCKED': True, 'P0_contracts': spec['p0_contracts'],
        'future_dependencies': spec['future_dependencies'],
        'HTTP_methods': {'GET': len(api.calls)}, 'GET_endpoints': api.calls,
        'github_write_requests': 0, 'App_key_used': False, 'OWNER_key_used': False,
        'broker_IO': 0, 'new_checkpoint_acceptances': 0, 'decision': 'PREPARATION_ONLY_NO_GO', **t.FLAGS}
    out = Path('verification/p0-preparation')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'live.json').write_bytes(t.canonical(receipt) + b'\n')
    sources = [Path(__file__).parent / name for name in ('TRANSITION_SPEC.json', 'transition.py', 'test_transition.py', 'live_probe.py')]
    sources += [root / 'research_core_v4/writer_fencing_o04_20261016/git_fence_lab.py',
                root / 'research_core_v4/writer_staging_o04_20261016/protocol.py']
    index = [{'path': str(p.relative_to(root)), 'sha256': t.sha(p.read_bytes())} for p in sources]
    (out / 'sources.json').write_bytes(t.canonical(index) + b'\n')
    sums = [t.sha(p.read_bytes()) + '  ' + p.name for p in sorted(out.glob('*.json'))]
    (out / 'SHA256SUMS.txt').write_text('\n'.join(sums) + '\n')
    print('MXM_P0_SOURCES=' + t.canonical(index).decode(), flush=True)
    print('MXM_P0_LIVE=' + t.canonical(receipt).decode(), flush=True)
    print('MXM_P0_HASHES=' + t.canonical(sums).decode(), flush=True)

if __name__ == '__main__':
    main()
