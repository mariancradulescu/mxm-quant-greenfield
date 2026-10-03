"""Execute the installed workflow shell against disposable Git repositories.

Synthetic completed-staging fixtures exercise publication, not decryption or
market evaluation. The audit fixture deliberately requires a complete state.
No production repository, secret, input bundle or market outcome is used.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/v4-asymmetric-staging-bootstrap.yml'
BRANCH = 'performance-research-v3-20260922'
PAYLOAD = 'research_core_v4/runtime_inputs/MXM_V4_ASYMMETRIC_STAGING_PAYLOAD_V1.zip'
STATE = 'research_core_v4/state'


def shell_step(name, source=None):
    lines = (source or WORKFLOW.read_text()).splitlines()
    start = lines.index('      - name: ' + name)
    run = next(i for i in range(start + 1, len(lines)) if lines[i] == '        run: |')
    end = run + 1
    while end < len(lines) and (not lines[end] or lines[end].startswith('          ')):
        end += 1
    return '\n'.join(line[10:] for line in lines[run + 1:end]) + '\n'


class StagingPublishTests(unittest.TestCase):
    def git(self, *args, cwd=None):
        return subprocess.check_output(['git', *args], cwd=cwd or self.work,
                                       stderr=subprocess.DEVNULL, text=True).strip()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mxm-synthetic-publish-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base / 'remote.git'
        self.work = self.base / 'runner'
        self.git('init', '--bare', str(self.remote), cwd=self.base)
        self.git('clone', str(self.remote), str(self.work), cwd=self.base)
        self.git('config', 'user.name', 'Synthetic publication test')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('checkout', '-b', BRANCH)
        gate = self.work / 'research_core_v4/asymmetric_recovery_v4_gate.py'
        gate.parent.mkdir(parents=True)
        gate.write_text("from pathlib import Path\n"
                        "assert Path('research_core_v4/state/synthetic-complete').read_text() == 'PASS'\n")
        self.git('add', '.')
        self.git('commit', '-m', 'synthetic infrastructure')
        self.parent = self.git('rev-parse', 'HEAD')
        payload = self.work / PAYLOAD
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b'synthetic encrypted-only restart fixture')
        self.git('add', PAYLOAD)
        self.git('commit', '-m', 'synthetic isolated payload upload')
        self.upload = self.git('rev-parse', 'HEAD')
        self.git('push', 'origin', 'HEAD:' + BRANCH)
        for phase in ('staging-data', 'certificate', 'preflight', 'final-certificate', 'activation'):
            p = self.work / STATE / ('synthetic-' + phase)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('PASS')
            if phase == 'activation':
                (p.parent / 'synthetic-complete').write_text('PASS')
            self.git('add', STATE)
            self.git('commit', '-m', 'synthetic ' + phase)
        self.final = self.git('rev-parse', 'HEAD')
        self.envfile = self.base / 'github-env'
        self.envfile.write_text('')
        self.log = self.base / 'push-log'
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        realgit = shutil.which('git')
        wrapper = self.bin / 'git'
        wrapper.write_text('#!/bin/bash\nset -euo pipefail\n'
                           'if [ "${1:-}" = push ]; then\n'
                           '  echo push >> "$TEST_PUSH_LOG"\n'
                           '  if [ "${TEST_INTERRUPT:-}" = before ]; then exit 75; fi\n'
                           '  if [ -n "${TEST_RACE_HEAD:-}" ]; then\n'
                           '    "$TEST_REAL_GIT" --git-dir="$TEST_REMOTE" update-ref "refs/heads/$BRANCH" "$TEST_RACE_HEAD"\n'
                           '  fi\n'
                           '  "$TEST_REAL_GIT" "$@"\n'
                           '  if [ "${TEST_INTERRUPT:-}" = after ]; then exit 75; fi\n'
                           'else\n  "$TEST_REAL_GIT" "$@"\nfi\n')
        wrapper.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'BRANCH': BRANCH, 'PAYLOAD': PAYLOAD, 'GITHUB_SHA': self.upload,
                    'FINAL_ACTIVATION_HEAD': self.final,
                    'EXPECTED_PAYLOAD_SHA256': hashlib.sha256(payload.read_bytes()).hexdigest(),
                    'GITHUB_ENV': str(self.envfile), 'TEST_REAL_GIT': realgit,
                    'TEST_PUSH_LOG': str(self.log), 'TEST_REMOTE': str(self.remote)}
        self.env.pop('PUBLISHED_FINAL_HEAD', None)
        self.publish = shell_step('Publish completed staging transaction with one branch ref update')
        self.post = shell_step('Final local exact-head fail-closed audit')

    def remote_head(self):
        return self.git('--git-dir=' + str(self.remote), 'rev-parse', 'refs/heads/' + BRANCH)

    def execute(self, script=None, **env):
        return subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script or self.publish],
                              cwd=self.work, env={**self.env, **env}, capture_output=True, text=True)

    def assert_unpublished(self, result, expected=None):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_head(), expected or self.upload)
        self.assertNotIn('PUBLISHED_FINAL_HEAD=', self.envfile.read_text())
        self.assertEqual(self.git('show', self.upload + ':' + PAYLOAD),
                         'synthetic encrypted-only restart fixture')

    def test_actual_publish_and_next_step_environment(self):
        self.assertEqual(self.git('rev-parse', 'origin/' + BRANCH), self.upload)
        self.assertNotEqual(self.final, self.upload)
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_head(), self.final)
        self.assertEqual(self.log.read_text().splitlines(), ['push'])
        inherited = dict(line.split('=', 1) for line in self.envfile.read_text().splitlines())
        self.assertEqual(inherited['PUBLISHED_FINAL_HEAD'], self.final)
        result = self.execute(self.post, **inherited)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_original_undefined_variable_is_detected(self):
        self.assert_unpublished(self.execute('set -euo pipefail\ntest "$(git rev-parse HEAD)" = "$PUBLISHED_FINAL_HEAD"\n' + self.publish))

    def test_original_remote_equals_local_contradiction_is_detected(self):
        self.assert_unpublished(self.execute('set -euo pipefail\ntest "$(git rev-parse origin/$BRANCH)" = "$FINAL_ACTIVATION_HEAD"\n' + self.publish))

    def test_missing_activation_head_fails_closed(self):
        del self.env['FINAL_ACTIVATION_HEAD']
        self.assert_unpublished(self.execute())

    def test_dirty_worktree_fails_closed(self):
        (self.work / 'unexpected').write_text('dirty')
        self.assert_unpublished(self.execute())

    def test_payload_changed_in_local_transaction_fails_closed(self):
        p = self.work / PAYLOAD
        p.write_bytes(b'changed')
        self.git('add', PAYLOAD)
        self.git('commit', '-m', 'synthetic corrupt payload')
        self.assert_unpublished(self.execute(FINAL_ACTIVATION_HEAD=self.git('rev-parse', 'HEAD'),
                                            EXPECTED_PAYLOAD_SHA256=hashlib.sha256(p.read_bytes()).hexdigest()))

    def test_audit_failure_prevents_publication(self):
        (self.work / STATE / 'synthetic-complete').write_text('FAIL')
        self.git('add', STATE)
        self.git('commit', '-m', 'synthetic audit failure')
        self.assert_unpublished(self.execute(FINAL_ACTIVATION_HEAD=self.git('rev-parse', 'HEAD')))

    def test_arm_lock_and_result_each_prevent_publication(self):
        for name in ('FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V4_ARM_V1.json',
                     'FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V4_ATTEMPT_LOCK_V1.txt',
                     'FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json'):
            with self.subTest(name=name):
                p = self.work / STATE / name
                p.write_text('synthetic forbidden boundary')
                self.git('add', str(p.relative_to(self.work)))
                self.git('commit', '-m', 'synthetic forbidden boundary')
                self.assert_unpublished(self.execute(FINAL_ACTIVATION_HEAD=self.git('rev-parse', 'HEAD')))
                self.git('reset', '--hard', self.final)

    def test_stale_remote_ref_fails_closed(self):
        self.git('--git-dir=' + str(self.remote), 'update-ref', 'refs/heads/' + BRANCH, self.parent)
        self.assert_unpublished(self.execute(), self.parent)

    def test_race_after_fetch_rejected_even_for_ancestor(self):
        # An ordinary push would allow this ancestor reset. Explicit lease must reject it.
        self.assert_unpublished(self.execute(TEST_RACE_HEAD=self.parent), self.parent)
        self.assertEqual(self.log.read_text().splitlines(), ['push'])

    def test_pre_publish_interruption_then_restart(self):
        self.assert_unpublished(self.execute(TEST_INTERRUPT='before'))
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_head(), self.final)

    def test_acknowledgement_loss_leaves_complete_remote_and_replay_closed(self):
        result = self.execute(TEST_INTERRUPT='after')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.remote_head(), self.final)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'show',
                                  self.final + ':' + STATE + '/synthetic-complete'), 'PASS')
        self.assertNotIn('PUBLISHED_FINAL_HEAD=', self.envfile.read_text())
        self.assert_unpublished(self.execute(), self.final)
        self.assertEqual(self.log.read_text().splitlines(), ['push'])


if __name__ == '__main__':
    unittest.main()
