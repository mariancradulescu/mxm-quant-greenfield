"""Only new P0 bootstrap preparation tests; accepted O04.2 tests are not run."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from . import transition as t
from ..writer_staging_o04_20261016.protocol import SyntheticIssuer

ROOT = Path(__file__).resolve().parents[2]

class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mxm-p0-synthetic-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.signers = {role: SyntheticIssuer(self.root / role) for role in t.ROLES}
        self.now = 1000
        self.spec = t.load_spec()
        self.gate = t.SyntheticApprovalGate(self.spec, '1' * 40, '2' * 64,
                                           self.signers, lambda: self.now)
        self.statement = self.gate.statement()
        self.approvals = t.synthetic_approvals(self.gate, self.statement)

    def denied(self, code, fn, *args, **kwargs):
        with self.assertRaisesRegex(t.lab.Denied, '^' + code + '$'):
            fn(*args, **kwargs)

    def bootstrap(self):
        remote = self.root / 'lab.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (remote / 'O04_SYNTHETIC_LAB_ONLY').write_text('synthetic\n')
        transport = t.lab.GitFenceLab(self.root / 'client', remote)
        return t.LocalBootstrap(transport, self.gate)

    def test_01_two_distinct_synthetic_signatures(self):
        self.assertEqual(self.gate.validate(self.statement, self.approvals, 1),
                         t.sha(t.canonical(self.statement)))

    def test_02_same_key_cannot_supply_both_roles(self):
        shared = dict.fromkeys(t.ROLES, self.signers[t.ROLES[0]])
        self.denied('DISTINCT_TRUST_ROOTS', t.SyntheticApprovalGate,
                    self.spec, '1' * 40, '2' * 64, shared, lambda: self.now)

    def test_03_missing_independent_approval(self):
        self.denied('TWO_APPROVALS', self.gate.validate, self.statement, self.approvals[:1], 1)

    def test_04_duplicate_roles(self):
        self.denied('SIGNER_ROLE', self.gate.validate, self.statement, self.approvals[:1] * 2, 1)

    def test_05_untrusted_key_fingerprint(self):
        approvals = copy.deepcopy(self.approvals)
        approvals[1]['key_sha256'] = '0' * 64
        self.denied('TRUST_ROOT', self.gate.validate, self.statement, approvals, 1)

    def test_06_signature_cannot_be_reused_for_other_role(self):
        approvals = copy.deepcopy(self.approvals)
        approvals[1]['signature'] = approvals[0]['signature']
        self.denied('SIGNATURE', self.gate.validate, self.statement, approvals, 1)

    def test_07_each_bound_field_refuses_even_resigned_tamper(self):
        changed = {'schema': 'REAL', 'marker': 'OWNER', 'plan_sha256': '3' * 64,
                   'source_SHA': '4' * 40, 'root_stop_oid': '5' * 40,
                   'staging_oid': '6' * 40, 'target_ref': 'refs/heads/side',
                   'policy_sha256': '7' * 64, 'scope': 'REAL_BOOTSTRAP'}
        for field, value in changed.items():
            with self.subTest(field=field):
                statement = {**self.statement, field: value}
                self.denied('BINDING_' + field.upper(), self.gate.validate,
                            statement, t.synthetic_approvals(self.gate, statement), 1)

    def test_08_unknown_payload_fields(self):
        self.denied('APPROVAL_FIELDS', self.gate.validate,
                    {**self.statement, 'PRODUCTION_GO': True}, self.approvals, 1)

    def test_09_expired_approval(self):
        self.now = self.statement['expires_at']
        self.denied('APPROVAL_TIME', self.gate.validate, self.statement, self.approvals, 1)

    def test_10_future_approval(self):
        self.now = self.statement['not_before'] - 1
        self.denied('APPROVAL_TIME', self.gate.validate, self.statement, self.approvals, 1)

    def test_11_overlong_approval_and_boolean_times(self):
        for changes in ({'expires_at': 1400}, {'not_before': True}, {'expires_at': True}):
            with self.subTest(changes=changes):
                self.denied('APPROVAL_TIME', self.gate.validate,
                            {**self.statement, **changes}, self.approvals, 1)

    def test_12_epoch_and_version_are_exact_integers(self):
        for changes, code in [({'epoch': 2}, 'EPOCH'), ({'epoch': True}, 'EPOCH'),
                              ({'version': 2}, 'VERSION'), ({'version': True}, 'VERSION')]:
            with self.subTest(changes=changes):
                self.denied(code, self.gate.validate, {**self.statement, **changes}, self.approvals, 1)

    def test_13_no_go_cannot_be_changed_or_numeric(self):
        for value in (True, 0, None):
            with self.subTest(value=value):
                flags = {**t.FLAGS, 'PRODUCTION_GO': value}
                statement = {**self.statement, 'permissions': flags}
                self.denied('BINDING_PERMISSIONS', self.gate.validate,
                            statement, t.synthetic_approvals(self.gate, statement), 1)

    def test_14_spec_escalation_denied(self):
        for field, value, code in [('mode', 'PRODUCTION', 'SPEC_MODE'),
                                  ('future_authority_ref', 'refs/heads/other', 'FIXED_FUTURE_REFERENCE')]:
            with self.subTest(field=field):
                self.denied(code, t.validate_spec, {**self.spec, field: value})

    def test_15_spec_real_go_or_privilege_denied(self):
        spec = copy.deepcopy(self.spec)
        spec['invariants']['PRODUCTION_GO'] = True
        self.denied('SPEC_REAL_GO_FORBIDDEN', t.validate_spec, spec)
        spec = copy.deepcopy(self.spec)
        spec['permissions']['App_key'] = True
        self.denied('PREPARATION_PRIVILEGES', t.validate_spec, spec)

    def test_16_real_backend_always_closed(self):
        self.denied('REAL_WRITER_NOT_IMPLEMENTED_NO_GO', t.production_checkpoint,
                    approvals=self.approvals, PRODUCTION_GO=True, epoch=1)

    def test_17_all_144_historical_routes_denied(self):
        paths = (ROOT / self.spec['historical_policy']['expected_paths_file']).read_bytes()
        self.assertEqual(t.sha(paths), self.spec['historical_policy']['expected_paths_sha256'])
        historical = paths.decode().splitlines()
        self.assertEqual(len(historical), 144)
        for path in historical:
            with self.subTest(path=path):
                self.assertEqual(t.select_route(t.TARGET, path, set(historical)), 'DENIED_HISTORICAL_ROUTE')

    def test_18_all_75_other_candidates_get_no_write_route(self):
        catalog = json.loads((ROOT / self.spec['historical_policy']['other_candidate_inventory']).read_bytes())
        self.assertEqual(len(catalog['items']), 75)
        for item in catalog['items']:
            with self.subTest(path=item['path']):
                self.assertEqual(t.select_route(t.TARGET, item['path'], set()), 'NOT_AUTHORIZED')

    def test_19_fixed_read_routes_and_side_refs(self):
        self.assertEqual(t.select_route('refs/heads/mxm-o04-accepted-owner-1807-v1', 'new', set()), 'OBSERVE_STOP_ONLY')
        self.assertEqual(t.select_route('refs/heads/mxm-o04-stage-authority-v1', 'new', set()), 'OBSERVE_ACCEPTED_STAGING_ONLY')
        for ref in (t.TARGET, 'refs/heads/side', 'releases/412686323', 'refs/heads/mxm-o04-stage-spoof-20261016-v1'):
            self.assertEqual(t.select_route(ref, 'new', set()), 'NOT_AUTHORIZED')

    def test_20_bootstrap_plan_commit_remains_no_go(self):
        b = self.bootstrap()
        initial = b.initialize()
        prepared = b.prepare(initial, self.statement, self.approvals)
        committed = b.commit(prepared)
        oid, state = b.read()
        self.assertEqual(oid, committed)
        self.assertEqual(state['phase'], 'SIMULATED_BOOTSTRAP_NO_GO')
        self.assertEqual(state['permissions'], t.FLAGS)
        self.assertEqual(state['owner_generation'], 1807)
        self.assertEqual(state['root_stop_oid'], t.STOP)

    def test_21_uncertain_ack_is_resolved_without_second_bootstrap(self):
        b = self.bootstrap()
        prepared = b.prepare(b.initialize(), self.statement, self.approvals)
        with self.assertRaises(t.lab.Unknown):
            b.commit(prepared, lose_ack=True)
        digest = self.gate.validate(self.statement, self.approvals, 1)
        self.assertEqual(b.resolve(self.statement['operation_id'], digest)['decision'], 'SIMULATED_COMMIT_FOUND_NO_REPLAY')
        before = b.read()[0]
        self.denied('BOOTSTRAP_STATE', b.commit, prepared)
        self.assertEqual(b.read()[0], before)
        self.assertEqual(b.resolve('different-operation', digest)['decision'], 'UNKNOWN_STOP_NO_RETRY')

    def test_22_expiry_between_prepare_and_commit_stops(self):
        b = self.bootstrap()
        prepared = b.prepare(b.initialize(), self.statement, self.approvals)
        self.now = self.statement['expires_at']
        self.denied('APPROVAL_TIME', b.commit, prepared)
        self.assertEqual(b.read()[0], prepared)

    def test_23_stale_bootstrap_and_replay_do_not_advance(self):
        b = self.bootstrap()
        initial = b.initialize()
        prepared = b.prepare(initial, self.statement, self.approvals)
        self.denied('PREPARE_STATE', b.prepare, initial, self.statement, self.approvals)
        final = b.commit(prepared)
        self.denied('BOOTSTRAP_STATE', b.commit, prepared)
        self.assertEqual(b.read()[0], final)

    def test_24_missing_approval_leaves_synthetic_stop_unchanged(self):
        b = self.bootstrap()
        initial = b.initialize()
        self.denied('TWO_APPROVALS', b.prepare, initial, self.statement, [])
        self.assertEqual(b.read()[0], initial)

    def test_25_non_lab_transport_rejected(self):
        self.denied('FILESYSTEM_LAB_ONLY', t.LocalBootstrap, object(), self.gate)

    def test_26_operation_and_signature_shape_denied(self):
        self.denied('OPERATION', self.gate.validate,
                    {**self.statement, 'operation_id': '../OWNER'}, self.approvals, 1)
        approvals = copy.deepcopy(self.approvals)
        approvals[0]['signature'] = 'INVALID'
        self.denied('SIGNATURE', self.gate.validate, self.statement, approvals, 1)

def main():
    records = []
    class Result(unittest.TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test)
            records.append({'test': test.id(), 'status': 'PASS'})
    from .live_probe import TransportTests
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(TransitionTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(TransportTests)])
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=2, resultclass=Result).run(suite)
    receipt = {'schema': 'mxm.p0.preparation.tests.v1', 'run_id': os.environ.get('GITHUB_RUN_ID'),
               'source_SHA': os.environ.get('GITHUB_SHA'), 'tests_run': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors),
               'scope': 'NEW_P0_PREPARATION_ONLY_NOT_O04_2_RERUN', 'tests': records,
               'github_write_calls': 0, 'OWNER_checkpoints_accepted': 0, **t.FLAGS}
    out = Path('verification/p0-preparation')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'tests.json').write_bytes(t.canonical(receipt) + b'\n')
    print('MXM_P0_TESTS=' + t.canonical(receipt).decode(), flush=True)
    if not result.wasSuccessful():
        print(json.dumps({'failed_cases': [x.id() for x, _ in result.failures + result.errors]}))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
