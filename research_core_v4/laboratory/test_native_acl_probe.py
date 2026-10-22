import copy
import unittest
from .common import LabError
from .native_acl_probe import APP_ACTOR, TARGETS, probe, rule_rejection, verify_rule


def rules(branch):
    rule_id, types = TARGETS[branch]
    entries = [{'type': name} for name in sorted(types)]
    for entry in entries:
        if entry['type'] == 'required_status_checks':
            entry['parameters'] = {'strict_required_status_checks_policy': True,
                'required_status_checks': [{'context': 'shared-catalogue-regression', 'integration_id': 15368}]}
    return {'id': rule_id, 'target': 'branch', 'enforcement': 'active',
        'conditions': {'ref_name': {'include': ['refs/heads/' + branch], 'exclude': []}},
        'rules': entries, 'bypass_actors': [APP_ACTOR] if branch.endswith('laboratory-evidence') else []}

class NativeACLTest(unittest.TestCase):
    def test_generic_forbidden_is_not_rule_denial(self):
        for status, message in [(403, 'Resource not accessible by integration'),
                                (422, 'Update is not a fast forward'), (200, 'repository rules')]:
            self.assertFalse(rule_rejection(status, {'message': message}))
        self.assertTrue(rule_rejection(422, {'message': 'Repository rule violations found'}))

    def test_effective_rules_not_protected_boolean(self):
        for branch, (rule_id, types) in TARGETS.items():
            rule = rules(branch)
            effective = [{'type': name, 'ruleset_id': rule_id} for name in types]
            verify_rule(branch, rule, effective)
            with self.assertRaises(LabError):
                verify_rule(branch, rule, [])
            with self.assertRaises(LabError):
                verify_rule(branch, rule, [dict(r, ruleset_id=0) for r in effective])
            wrong = copy.deepcopy(rule)
            wrong['bypass_actors'] = [{'actor_type': 'RepositoryRole', 'actor_id': 5, 'bypass_mode': 'always'}]
            with self.assertRaises(LabError):
                verify_rule(branch, wrong, effective)

    def test_successful_write_and_generic_denial_fail(self):
        branch = 'main'
        class Fake:
            update_status = 422
            response = {'message': 'Repository rule violations found'}
            moved = False
            def get(self, suffix):
                if suffix.startswith('rulesets/'):
                    return rules(branch)
                if suffix.startswith('rules/branches/'):
                    return [{'type': t, 'ruleset_id': TARGETS[branch][0]} for t in TARGETS[branch][1]]
                if suffix.startswith('git/ref/'):
                    return {'object': {'sha': 'changed' if self.moved else 'parent'}}
                return {'tree': {'sha': 'tree'}}
            def call(self, method, path, body):
                if method == 'POST':
                    return 201, {'sha': 'proposal', 'tree': {'sha': 'tree'}, 'parents': [{'sha': 'parent'}]}
                return self.update_status, self.response
        api = Fake()
        self.assertEqual(probe(api, branch, {'run_id': 'fixture'})['before'], 'parent')
        api.response = {'message': 'Resource not accessible by integration'}
        api.update_status = 403
        with self.assertRaises(LabError):
            probe(api, branch, {'run_id': 'fixture'})
        api.update_status = 200
        api.response = {'message': 'accepted'}
        with self.assertRaises(LabError):
            probe(api, branch, {'run_id': 'fixture'})
