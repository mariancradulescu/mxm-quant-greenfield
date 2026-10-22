"""Native, keyless rule-denial probes. No account/corpus/evidence content changes.

A probe proposes an empty successor commit (identical tree). GitHub must reject
its ref update specifically for repository rules. Generic permission failures
are inconclusive. The commit remains an auditable, unattached Git object.
"""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from .common import need, encoded, bytes_digest

REPO = 'mariancradulescu/mxm-quant-greenfield'
PREFIX = '/repos/' + REPO + '/'
TARGETS = {
    'main': (25461184, {'pull_request', 'required_status_checks'}),
    'mxm-remediation-p0-p4-20261015-v1': (25461184, {'pull_request', 'required_status_checks'}),
    'mxm-p0-integrated-cache-successor-20261020': (25461529, {'pull_request', 'required_status_checks'}),
    'mxm-o04-integrated-laboratory-evidence': (25461373, {'update'}),
}
APP_ACTOR = {'actor_id': 5343530, 'actor_type': 'Integration', 'bypass_mode': 'always'}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('ACL_REDIRECT_REFUSED')

class API:
    def __init__(self, token):
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect)

    def call(self, method, path, body=None):
        need(path.startswith(PREFIX) and '..' not in path and '?' not in path, 'ACL_API_PATH')
        request = urllib.request.Request('https://api.github.com' + path, method=method,
            data=None if body is None else encoded(body), headers={
                'Authorization': 'Bearer ' + self.token,
                'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
                'X-GitHub-Api-Version': '2022-11-28'})
        try:
            with self.opener.open(request, timeout=30) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def get(self, suffix):
        status, value = self.call('GET', PREFIX + suffix)
        need(status == 200, 'ACL_GET_' + str(status))
        return value

def verify_rule(branch, rule, effective):
    rule_id, required = TARGETS[branch]
    need(rule['id'] == rule_id and rule['enforcement'] == 'active' and
         rule['target'] == 'branch', 'ACL_RULE_ACTIVE')
    refs = rule['conditions']['ref_name']
    need('refs/heads/' + branch in refs['include'] and refs['exclude'] == [], 'ACL_RULE_TARGET')
    expected_bypass = [APP_ACTOR] if branch.endswith('laboratory-evidence') else []
    # GITHUB_TOKEN may omit administrative bypass_actors. Effective update denial
    # is tested below; owner-visible full actor inventory is a separate witness.
    if 'bypass_actors' in rule:
        need(rule['bypass_actors'] == expected_bypass, 'ACL_BYPASS_ACTORS')
    need(required <= {r['type'] for r in rule['rules']}, 'ACL_CONFIGURED_TYPES')
    applied = {r['type'] for r in effective if r.get('ruleset_id') == rule_id}
    need(required <= applied, 'ACL_EFFECTIVE_TYPES')
    if 'required_status_checks' in required:
        checks = next(r['parameters'] for r in rule['rules'] if r['type'] == 'required_status_checks')
        need(checks['strict_required_status_checks_policy'] is True and
             checks['required_status_checks'] == [{'context': 'shared-catalogue-regression',
                                                   'integration_id': 15368}], 'ACL_REQUIRED_CI')

def rule_rejection(status, response):
    message = response.get('message', '')
    return status in (403, 422) and bool(re.search(
        r'GH013|repository rule violations|repository rules|protected branch', message, re.I))

def probe(api, branch, context):
    rule_id, _ = TARGETS[branch]
    rule = api.get('rulesets/' + str(rule_id))
    effective = api.get('rules/branches/' + branch)
    verify_rule(branch, rule, effective)
    before = api.get('git/ref/heads/' + branch)['object']['sha']
    parent = api.get('git/commits/' + before)
    status, proposed = api.call('POST', PREFIX + 'git/commits', {
        'message': 'MXM TECHNICAL_NONOUTCOME ACL refusal probe run ' + context['run_id'] + ' / ' + branch,
        'tree': parent['tree']['sha'], 'parents': [before]})
    need(status == 201 and proposed['tree']['sha'] == parent['tree']['sha'] and
         [p['sha'] for p in proposed['parents']] == [before], 'ACL_WRITE_TOKEN_POSITIVE_CONTROL')
    # Repeat effective-rule admission immediately before the attempted update.
    verify_rule(branch, api.get('rulesets/' + str(rule_id)), api.get('rules/branches/' + branch))
    need(api.get('git/ref/heads/' + branch)['object']['sha'] == before, 'ACL_TARGET_MOVED_BEFORE_PROBE')
    status, response = api.call('PATCH', PREFIX + 'git/refs/heads/' + branch,
                                {'sha': proposed['sha'], 'force': False})
    after = api.get('git/ref/heads/' + branch)['object']['sha']
    result = {'branch': branch, 'ruleset_id': rule_id, 'before': before, 'after': after,
              'proposal': proposed['sha'], 'tree': parent['tree']['sha'],
              'positive_commit_status': 201, 'update_status': status,
              'response': response, 'response_sha256': bytes_digest(encoded(response)),
              'rule': rule, 'effective_rules': effective}
    print('MXM_ACL_RESULT ' + json.dumps(result, sort_keys=True), flush=True)
    need(after == before and rule_rejection(status, response), 'ACL_NATIVE_RULE_DENIAL_NOT_PROVEN')
    return result

def main():
    need(os.environ.get('GITHUB_REPOSITORY') == REPO and
         os.environ.get('GITHUB_RUN_ATTEMPT') == '1' and
         os.environ.get('GITHUB_EVENT_NAME') == 'push' and
         os.environ.get('GITHUB_REF') == 'refs/heads/mxm-r3-admin-isolation-20261020' and
         os.environ.get('GITHUB_JOB') == 'native-rule-refusals', 'ACL_NATIVE_CONTEXT')
    context = {key: os.environ['GITHUB_' + name] for key, name in [
        ('run_id', 'RUN_ID'), ('run_attempt', 'RUN_ATTEMPT'), ('job', 'JOB'),
        ('source_sha', 'SHA'), ('workflow_ref', 'WORKFLOW_REF'), ('workflow_sha', 'WORKFLOW_SHA')]}
    need(context['source_sha'] == context['workflow_sha'], 'ACL_WORKFLOW_SOURCE')
    api = API(os.environ['GH_TOKEN'])
    results = []
    try:
        for branch in TARGETS:
            results.append(probe(api, branch, context))
    finally:
        Path('native-acl-proof.json').write_bytes(encoded({
            'schema': 'mxm.native-rule-refusals.v1', 'classification': 'TECHNICAL_NONOUTCOME',
            'context': context, 'results': results, 'orders': 0, 'economic_outcomes': 0,
            'operational_acceptance': False}))

if __name__ == '__main__':
    main()
