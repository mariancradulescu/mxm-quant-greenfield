"""Registered W35 transport profile; synthetic wires, no connection or key."""
import copy,importlib,json,os,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from . import week_chronology_reception as c
from .common import LabError
from .test_week_chronology_reception import fixture

class Week35ProfileTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'LAB_CHRONOLOGY_PROFILE':'W35'})
        self.env.start();importlib.reload(c)
    def tearDown(self):
        self.env.stop();importlib.reload(c)
    def test_registered_interval_is_development_whole_iso_week(self):
        start=datetime.fromtimestamp(c.POLICY['from_ms']/1000,timezone.utc)
        end=datetime.fromtimestamp(c.POLICY['to_ms']/1000,timezone.utc)
        self.assertEqual(start.isoformat(),'2026-08-24T00:00:00+00:00')
        self.assertEqual(end.isoformat(),'2026-08-31T00:00:00+00:00')
        self.assertEqual(start.isocalendar().week,35)
        self.assertEqual(c.POLICY['to_ms']-c.POLICY['from_ms'],604800000)
        self.assertEqual(c.POLICY['history_request_cap'],4096)
        self.assertEqual(c.POLICY['strategy_trials'],0)
        self.assertFalse(c.POLICY['confirmation_opened'])
        self.assertFalse(c.POLICY['automatic_retry'])
    def test_exact_existing_profile_replay_and_wrong_week_rejection(self):
        from research_core_v4.shallow_m5_support_v2_production import ACCOUNT_FINGERPRINT_SHA256
        with patch('research_core_v4.shallow_m5_support_v2_production._fingerprint',return_value=ACCOUNT_FINGERPRINT_SHA256):
            value=fixture();r=c.replay(value)
            self.assertTrue(r['provider_window_complete'])
            self.assertEqual(r['economic_outcomes'],0)
            wrong=copy.deepcopy(value);wrong['policy']['iso_week']='2026-W37'
            with self.assertRaisesRegex(LabError,'AUTH_POLICY'):c.replay(wrong)
    def test_unique_source_ref_path_and_profile_in_both_roles(self):
        w=c.build_workflow('a'*40)
        self.assertEqual(w['on']['push']['paths'],['.github/workflows/mxm-week35-chronology-reception.yml'])
        self.assertEqual(c.SOURCE_REF,'mxm-week35-chronology-code-20261023')
        self.assertEqual(str(c.OUT),'verification/week35-chronology')
        for name,j in w['jobs'].items():
            self.assertEqual(j['env'],{'LAB_CHRONOLOGY_PROFILE':'W35'})
            self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
            env=next(s['env'] for s in j['steps'] if 'env' in s)
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',env)
            self.assertEqual('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env,name=='chronology-cold')
            self.assertEqual('R3_CTRADER_ACCESS_TOKEN' in env,name=='chronology-collect')
    def test_default_workflow_remains_byte_equivalent_in_structure(self):
        with patch.dict(os.environ,{'LAB_CHRONOLOGY_PROFILE':'W37'}):
            importlib.reload(c)
            installed=Path('..')/'.github/workflows/mxm-week-chronology-reception.yml'
            if installed.exists():
                self.assertEqual(c.build_workflow('120db3391ed1f4105120274b73a9259690eeeb64'),json.loads(installed.read_bytes()))
            self.assertEqual(c.POLICY['iso_week'],'2026-W37')
            self.assertEqual(c.PATH,'.github/workflows/mxm-week-chronology-reception.yml')
            self.assertTrue(all('env' not in j for j in c.build_workflow('a'*40)['jobs'].values()))
        importlib.reload(c)
    def test_unknown_profile_cannot_import(self):
        with patch.dict(os.environ,{'LAB_CHRONOLOGY_PROFILE':'ARBITRARY'}),self.assertRaisesRegex(LabError,'UNREGISTERED_PROFILE'):
            importlib.reload(c)
        importlib.reload(c)

if __name__=='__main__':unittest.main()
