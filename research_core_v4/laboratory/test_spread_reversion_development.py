import copy,json,os,unittest
from unittest.mock import patch
from . import spread_reversion_development as n
class SpreadScope(unittest.TestCase):
    def test_frozen_budget_source_and_not_net_or_funded_capital(self):
        s=n.spec();self.assertEqual(s['budget']['model_trials'],1);self.assertEqual(s['budget']['automatic_retries'],0)
        self.assertEqual(s['source_run'],40179011821);self.assertEqual(s['entry_delay_ms'],250);self.assertEqual(s['hold_ms'],1000)
        self.assertFalse(s['capital_replay']);self.assertFalse(s['historical_costs_assumed_zero']);self.assertFalse(s['confirmation_opened'])
    def test_wrong_context_or_key_fails_before_git_and_source(self):
        with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
            with self.assertRaisesRegex(ValueError,'NATIVE_CONTEXT'):n.admit()
            git.assert_not_called()
        env=dict(GITHUB_REPOSITORY=n.REPO,GITHUB_REF_NAME=n.BRANCH,GITHUB_EVENT_NAME='push',GITHUB_RUN_ATTEMPT='1',GITHUB_JOB=n.JOB,GITHUB_WORKFLOW_REF=n.REPO+'/'+n.PATH+'@refs/heads/'+n.BRANCH)
        for secret in n.SECRET_NAMES:
            with patch.dict(os.environ,{**env,secret:'artificial'},clear=True),patch.object(n.subprocess,'check_output') as git:
                with self.assertRaisesRegex(ValueError,'NO_KEYS_BEFORE'):n.admit()
                git.assert_not_called()
    def test_read_only_workflow_key_roles_no_broker_or_dispatch(self):
        w=n.workflow();self.assertEqual(json.loads((n.ROOT/n.PATH).read_bytes()),w)
        self.assertEqual(w['on'],{'push':{'branches':[n.BRANCH],'paths':[n.PATH]}})
        j=w['jobs'][n.JOB];self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
        steps=[s for s in j['steps'] if 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in s.get('env',{})]
        self.assertEqual(len(steps),2)
        for s in steps:self.assertNotIn('dotnet',s['run']);self.assertNotIn(' result ',s['run'])
        for key in ('R3_CTRADER_','SUCCESSOR_APP_PRIVATE_KEY','workflow_dispatch','mxm-r3-pepperstone-v1'):self.assertNotIn(key,json.dumps(w))
    def test_frozen_hash_and_implementation_mutations_are_not_fresh_identities(self):
        class Fake:
            def read_bytes(self):return b'{}'
        with patch.object(n,'SPEC',Fake()):
            with self.assertRaisesRegex(ValueError,'FROZEN_SPEC'):n.spec()
        n.one_shot(dict(total_count=1,workflow_runs=[dict(id=7,run_attempt=1)]),7)
        with self.assertRaises(ValueError):n.one_shot(dict(total_count=1,workflow_runs=[dict(id=7,run_attempt=2)]),7)
if __name__=='__main__':unittest.main()
