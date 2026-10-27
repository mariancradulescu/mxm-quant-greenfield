import json,os,unittest
from unittest.mock import patch
from . import spot_source_cause_reception as n
class SourceCauseAdmission(unittest.TestCase):
    def test_fixed_original_data_and_no_economic_or_broker_scope(self):
        self.assertEqual(n.POLICY['original_run'],40455704891)
        self.assertEqual(n.POLICY['all_original_events'],1140)
        self.assertEqual(n.POLICY['symbol_ids'],[1,2,250])
        self.assertFalse(n.POLICY['consumer_policy_changed'])
        for name in ('new_broker_requests','orders','new_response_tests','economic_model_runs'):self.assertEqual(n.POLICY[name],0)
    def test_wrong_context_and_keys_stop_before_git_or_rest(self):
        with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
            with self.assertRaisesRegex(ValueError,'NATIVE_CONTEXT'):n.admit()
            git.assert_not_called()
        for name in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'):
            with patch.dict(os.environ,{name:'artificial'},clear=True):
                with self.assertRaisesRegex(ValueError,'SECRET_ROLE'):n.no_keys()
    def test_no_second_attempt_or_history_ambiguity(self):
        n.one_shot({'total_count':1,'workflow_runs':[{'id':7,'run_attempt':1}]},7)
        for v in ({'total_count':2,'workflow_runs':[{'id':7,'run_attempt':1}]},
          {'total_count':1,'workflow_runs':[{'id':7,'run_attempt':2}]},
          {'total_count':1,'workflow_runs':[{'id':8,'run_attempt':1}]}):
            with self.assertRaises(ValueError):n.one_shot(v,7)
    def test_exact_workflow_one_custody_step_no_broker_or_writer_key(self):
        w=n.workflow();self.assertEqual(json.loads((n.ROOT/n.PATH).read_bytes()),w)
        self.assertEqual(w['on'],{'push':{'branches':[n.BRANCH],'paths':[n.PATH]}})
        j=w['jobs'][n.JOB];self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
        self.assertEqual(j['environment'],'mxm-r3-custody-v1')
        secret=[s for s in j['steps'] if 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in s.get('env',{})]
        self.assertEqual(len(secret),1);self.assertIn(' export ',secret[0]['run']);self.assertNotIn('dotnet',secret[0]['run'])
        text=json.dumps(w)
        for forbidden in ('R3_CTRADER_','SUCCESSOR_APP_PRIVATE_KEY','workflow_dispatch','ExecuteMarketOrder','mxm-r3-pepperstone-v1'):
            self.assertNotIn(forbidden,text)
        self.assertEqual(j['steps'][-1]['with']['path'],n.OUT)
if __name__=='__main__':unittest.main()
