import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from .common import LabError, digest
from . import secret_isolation as m

class SecretIsolationTest(unittest.TestCase):
    def environment(self):
        return {'name': 'mxm-r3-custody-v1', 'can_admins_bypass': False,
            'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True},
            'protection_rules': [{'type': 'branch_policy'}]}

    def test_wildcards_tags_and_bypass_are_refused(self):
        env = self.environment()
        policies = {'total_count': 1, 'branch_policies': [{'name': m.EXECUTION, 'type': 'branch'}]}
        m.validate_environment(env, policies, env['name'])
        for field, value in [('can_admins_bypass', True), ('deployment_branch_policy', None),
                             ('protection_rules', []), ('name', 'other')]:
            changed = dict(env, **{field: value})
            with self.assertRaises(LabError):
                m.validate_environment(changed, policies, env['name'])
        for name, kind in [('*', 'branch'), (m.EXECUTION, 'tag'), ('other', 'branch')]:
            with self.assertRaises(LabError):
                m.validate_environment(env, {'total_count': 1, 'branch_policies': [{'name': name, 'type': kind}]}, env['name'])

    def test_copy_http_body_contains_only_ciphertext(self):
        value = 'fixture-sensitive-value-1234\n\r\n'
        with patch.object(m, 'http') as http, patch.object(m, 'seal', return_value='fixture-cipher') as seal:
            http.side_effect = [(200, {'key': 'fixture-public', 'key_id': 'fixture-key-id'}), (201, {})]
            m.set_copy('ephemeral-fixture-token', 'mxm-r3-custody-v1', 'R3_CUSTODY_PRIVATE_KEY_PEM', value)
            seal.assert_called_once_with(value, 'fixture-public')
            args = http.call_args_list[-1].args
            self.assertEqual(args[2], 'PUT')
            self.assertEqual(args[3], {'encrypted_value': 'fixture-cipher', 'key_id': 'fixture-key-id'})
            self.assertNotIn(value, repr(http.call_args_list))
        with self.assertRaises(LabError):
            m.set_copy('fixture', 'other', 'R3_CUSTODY_PRIVATE_KEY_PEM', value)
        with patch.object(m, 'http', return_value=(403, {})):
            with self.assertRaises(LabError):
                m.set_copy('fixture', 'mxm-r3-custody-v1', 'R3_CUSTODY_PRIVATE_KEY_PEM', value)

    def test_real_system_sealed_box_preserves_exact_bytes(self):
        import ctypes,base64
        lib = m.sodium_library()
        public, private = ctypes.create_string_buffer(32), ctypes.create_string_buffer(32)
        self.assertEqual(lib.crypto_box_keypair(public, private), 0)
        lib.crypto_box_seal_open.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_ulonglong, ctypes.c_void_p, ctypes.c_void_p]
        for value in ('fixture-key-with-final-newline\n', 'fixture-CRLF\r\n\r\n', 'fixture-utf8-ș\n', 'fixture-NUL-\x00-x'):
            cipher = base64.b64decode(m.seal(value, base64.b64encode(public.raw).decode()))
            raw = value.encode()
            plain = ctypes.create_string_buffer(len(raw))
            self.assertEqual(lib.crypto_box_seal_open(plain, cipher, len(cipher), public, private), 0)
            self.assertEqual(plain.raw, raw)
        with self.assertRaises(LabError):
            m.seal('fixture', base64.b64encode(b'short').decode())

    def test_missing_and_mismatched_values_fail(self):
        nonce = 'a' * 64
        for value in ('', 'short'):
            with self.assertRaises(LabError):
                m.commitment(value, nonce, 'secret')
        a = m.commitment('fixture-secret-one', nonce, 'secret')
        self.assertNotEqual(a, m.commitment('fixture-secret-two', nonce, 'secret'))
        self.assertNotEqual(a, m.commitment('fixture-secret-one', 'b' * 64, 'secret'))
        self.assertNotEqual(a, m.commitment('fixture-secret-one', nonce, 'other'))
        self.assertNotEqual(a, 'fixture-secret-one')

    def test_native_terminal_jobs_and_exact_receipts_required(self):
        ctx = {'run_id': '123'}
        proof = {'fixture': True}
        jobs = [{'name': m.JOBS[g], 'run_id': 123, 'status': 'completed', 'conclusion': 'success'}
                for g in ('copy', 'custody', 'pepperstone')]
        receipts = []
        for group in ('custody', 'pepperstone'):
            env, mapping = m.GROUPS[group]
            receipts.append({'schema': 'mxm.secret-isolation.verified.v1', 'context': ctx,
                'environment': env, 'copy_sha256': digest(proof),
                'destinations': sorted(mapping.values()), 'verified': True})
        m.verify_receipts(ctx, proof, receipts, jobs)
        for field, value in [('conclusion', 'failure'), ('status', 'in_progress'), ('run_id', 124)]:
            changed = copy.deepcopy(jobs)
            changed[1][field] = value
            with self.assertRaises(LabError):
                m.verify_receipts(ctx, proof, receipts, changed)
        with self.assertRaises(LabError):
            m.verify_receipts(ctx, proof, receipts, jobs + [jobs[0]])
        changed = copy.deepcopy(receipts)
        changed[0]['copy_sha256'] = 'favorable-but-other-proof'
        with self.assertRaises(LabError):
            m.verify_receipts(ctx, proof, changed, jobs)
        with self.assertRaises(LabError):
            m.verify_receipts(ctx, proof, receipts[:1], jobs)

    def test_installable_workflow_is_exact_and_has_no_arbitrary_inputs(self):
        workflow = m.build_workflow('a' * 40)
        self.assertEqual(workflow['on'], {'workflow_dispatch': {}})
        self.assertEqual(set(workflow['jobs']), set(m.JOBS.values()))
        for stage in ('copy', 'custody', 'pepperstone', 'cleanup'):
            job = workflow['jobs'][m.JOBS[stage]]
            self.assertEqual(job['permissions'], {'contents': 'read', 'actions': 'read'})
            self.assertEqual(job['steps'][0]['with'], {'ref': 'a' * 40, 'persist-credentials': False})
            env = next(step['env'] for step in job['steps'] if 'run' in step)
            if stage in ('custody', 'pepperstone'):
                self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY', env)
                self.assertEqual(set(env) - {'GH_TOKEN'}, set(m.GROUPS[stage][1].values()))
            if stage == 'cleanup':
                self.assertEqual(set(env), {'GH_TOKEN', 'SUCCESSOR_APP_PRIVATE_KEY'})
                self.assertEqual(set(job['needs']), {'isolation-copy', 'verify-custody', 'verify-pepperstone'})
        for sha in ('main', '', 'a' * 39, 'g' * 40):
            with self.assertRaises(LabError):
                m.build_workflow(sha)

    def test_cleanup_checks_every_metadata_before_first_delete(self):
        import contextlib
        ctx = {'run_id': '123', 'execution_sha': 'execution'}
        rows = [{'source': src, 'destination': dst, 'environment': env,
                 'original': {'name': src}, 'copy': {'name': dst}}
                for env, mapping in m.GROUPS.values() for src, dst in mapping.items()]
        proof = {'rows': rows}
        run = {'head_sha': 'execution', 'run_attempt': 1, 'event': 'workflow_dispatch',
               'path': m.WORKFLOW, 'head_branch': m.EXECUTION}
        class Fake:
            def __init__(self, token):
                pass
            def get(self, suffix):
                return run if not suffix.endswith('/jobs') else {'total_count': 4, 'jobs': [0] * 4}
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'receipts'
            folder.mkdir()
            for group in ('custody', 'pepperstone'):
                (folder / ('isolation-' + group + '.json')).write_text('{}')
            old = Path.cwd()
            import os
            os.chdir(directory)
            try:
                with patch.object(m, 'read_copy', return_value=proof), \
                     patch.object(m, 'verify_receipts'), patch.object(m, 'API', Fake), \
                     patch.object(m, 'app_token', return_value=contextlib.nullcontext('fixture')), \
                     patch.object(m, 'environments'), patch.dict(m.os.environ, {'GH_TOKEN': 'fixture'}), \
                     patch.object(m, 'secret_metadata') as metadata, patch.object(m, 'http') as http:
                    values = []
                    for row in rows:
                        values.extend([row['original'], row['copy']])
                    values[-1] = {'name': 'changed-last-copy'}
                    metadata.side_effect = values
                    with self.assertRaises(LabError):
                        m.cleanup(ctx)
                    http.assert_not_called()
            finally:
                os.chdir(old)
