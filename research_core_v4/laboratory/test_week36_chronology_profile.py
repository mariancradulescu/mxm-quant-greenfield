"""Only the missing middle week; no market outcomes, connection or credentials."""
import copy, importlib, json, os, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from . import week_chronology_reception as c
from .common import DEVELOPMENT_END_MS, LabError
from .test_week_chronology_reception import fixture

class Week36Profile(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'LAB_CHRONOLOGY_PROFILE': 'W36'})
        self.env.start(); importlib.reload(c)
    def tearDown(self):
        self.env.stop(); importlib.reload(c)
    def test_exact_adjacent_development_interval_and_conserved_limits(self):
        lo, hi = (datetime.fromtimestamp(c.POLICY[k] / 1000, timezone.utc) for k in ('from_ms', 'to_ms'))
        self.assertEqual((lo.isoformat(), hi.isoformat()), ('2026-08-31T00:00:00+00:00', '2026-09-07T00:00:00+00:00'))
        self.assertEqual((lo.isocalendar().week, lo.weekday(), lo.hour), (36, 0, 0))
        self.assertEqual(c.POLICY['to_ms'] - c.POLICY['from_ms'], 604800000)
        self.assertLessEqual(c.POLICY['to_ms'], DEVELOPMENT_END_MS)
        self.assertEqual((c.POLICY['symbol_id'], c.POLICY['symbol_name']), (1, 'EURUSD'))
        self.assertEqual([c.POLICY[k] for k in ('history_request_cap', 'max_wire_bytes', 'max_private_bytes', 'max_collection_seconds')], [4096, 70000000, 120000000, 1200])
        self.assertEqual(c.POLICY['orders'], c.POLICY['strategy_trials'])
        self.assertEqual(c.POLICY['strategy_trials'], 0)
        self.assertFalse(c.POLICY['automatic_retry']); self.assertFalse(c.POLICY['confirmation_opened'])
    def test_exact_wire_replay_does_not_substitute_adjacent_week(self):
        from research_core_v4.shallow_m5_support_v2_production import ACCOUNT_FINGERPRINT_SHA256
        with patch('research_core_v4.shallow_m5_support_v2_production._fingerprint', return_value=ACCOUNT_FINGERPRINT_SHA256):
            value = fixture(); result = c.replay(value)
            self.assertTrue(result['provider_window_complete'])
            self.assertEqual(result['economic_outcomes'], 0)
            for field, wrong in [('iso_week', '2026-W37'), ('from_ms', 1787529600000), ('symbol_id', 2)]:
                bad = copy.deepcopy(value); bad['policy'][field] = wrong
                with self.subTest(field=field), self.assertRaisesRegex(LabError, 'AUTH_POLICY'):
                    c.replay(bad)
    def test_exact_workflow_and_separate_roles_no_retry(self):
        w = c.build_workflow('a' * 40)
        self.assertEqual(c.SOURCE_REF, 'mxm-week36-chronology-code-20261026')
        self.assertEqual(c.PATH, '.github/workflows/mxm-week36-chronology-reception.yml')
        self.assertEqual(str(c.OUT), 'verification/week36-chronology')
        self.assertEqual(w['on']['push']['paths'], [c.PATH])
        for name, job in w['jobs'].items():
            self.assertEqual(job['env'], {'LAB_CHRONOLOGY_PROFILE': 'W36'})
            self.assertEqual(job['permissions'], {'contents': 'read', 'actions': 'read'})
            env = next(s['env'] for s in job['steps'] if 'env' in s)
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY', env)
            self.assertEqual('R3_CTRADER_ACCESS_TOKEN' in env, name == 'chronology-collect')
            self.assertEqual('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env, name == 'chronology-cold')
        c.one_shot_history({'total_count': 1, 'workflow_runs': [{'id': 7, 'run_attempt': 1}]}, 7)
        for bad in [{'total_count': 0, 'workflow_runs': []}, {'total_count': 1, 'workflow_runs': [{'id': 7, 'run_attempt': 2}]}]:
            with self.assertRaisesRegex(LabError, 'ONE_SHOT'):
                c.one_shot_history(bad, 7)
    def test_old_three_workflows_have_identical_generated_contracts(self):
        for profile, name in [('W37', 'mxm-week-chronology-reception.yml'), ('W35', 'mxm-week35-chronology-reception.yml'), ('GBPUSD_W37', 'mxm-gbpusd-week37-chronology-reception.yml')]:
            with patch.dict(os.environ, {'LAB_CHRONOLOGY_PROFILE': profile}):
                importlib.reload(c)
                root = Path(__file__).resolve().parents[2]
                installed = root.parent / '.github/workflows' / name
                if not installed.exists(): installed = root / '.github/workflows' / name
                w = json.loads(installed.read_bytes())
                self.assertEqual(c.build_workflow(w['jobs']['chronology-collect']['steps'][1]['with']['ref']), w)
        importlib.reload(c)
    def test_installed_source_bound_workflow(self):
        root = Path(__file__).resolve().parents[2]
        installed = root.parent / c.PATH
        if not installed.exists(): installed = root / c.PATH
        if not installed.exists(): self.skipTest('source-only commit precedes finite workflow installation')
        w = json.loads(installed.read_bytes())
        source = w['jobs']['chronology-collect']['steps'][1]['with']['ref']
        self.assertEqual(c.build_workflow(source), w)

if __name__ == '__main__':
    unittest.main()
