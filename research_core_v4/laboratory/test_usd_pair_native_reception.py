"""Finite native admission/role boundaries; no key, broker, market decryption or strategy."""
import json,os,unittest
from pathlib import Path
from unittest.mock import patch
from . import usd_pair_native_reception as n
class PairNativeAdmission(unittest.TestCase):
    def test_only_registered_originals_and_identical_development_window(self):
        self.assertEqual(n.SOURCES['EURUSD']['run'],39917922508)
        self.assertEqual(n.SOURCES['GBPUSD']['run'],40179011821)
        self.assertEqual(n.END-n.START,604800000)
        self.assertEqual(sum(x['bid']+x['ask'] for x in n.SOURCES.values()),1960588)
    def test_wrong_context_stops_before_key_git_or_network(self):
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'other/repo'}),patch.object(n.subprocess,'check_output') as git:
            with self.assertRaisesRegex(ValueError,'NATIVE_CONTEXT'):n.admit()
            git.assert_not_called()
    def test_second_native_attempt_or_retry_refused(self):
        good={'total_count':1,'workflow_runs':[{'id':3,'run_attempt':1}]};n.one_shot(good,3)
        for bad in ({'total_count':2,'workflow_runs':good['workflow_runs']},{'total_count':1,'workflow_runs':[{'id':3,'run_attempt':2}]},
                    {'total_count':1,'workflow_runs':[{'id':4,'run_attempt':1}]}):
            with self.assertRaisesRegex(ValueError,'ONE_REGISTERED'):n.one_shot(bad,3)
    def test_custody_key_not_available_to_compiler_receipt_or_admission(self):
        workflow=n.build_workflow();job=workflow['jobs']['usd-pair-source']
        self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
        self.assertEqual(job['environment'],'mxm-r3-custody-v1')
        secret_steps=[s for s in job['steps'] if 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in s.get('env',{})]
        self.assertEqual(len(secret_steps),1)
        self.assertIn('export EURUSD',secret_steps[0]['run']);self.assertIn('export GBPUSD',secret_steps[0]['run'])
        self.assertNotIn('dotnet',secret_steps[0]['run'])
        self.assertNotIn('R3_CTRADER_',json.dumps(workflow));self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(workflow))
        upload=job['steps'][-1]['with']['path'];self.assertEqual(upload,'verification/usd-pair-source/receipt.json')
    def test_installed_workflow_exact_generated_contract(self):
        p=Path(n.PATH)
        if p.exists():self.assertEqual(json.loads(p.read_bytes()),n.build_workflow())
if __name__=='__main__':unittest.main()
