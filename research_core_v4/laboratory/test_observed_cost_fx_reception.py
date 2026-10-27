import copy,json,os,unittest
from unittest.mock import patch
from . import observed_cost_fx_reception as n
from . import observed_cost_fx as fx
from .test_current_margin_evidence import item

def source_fixture():
    metadata=[]
    for sid in (1,2,250):
        i=item();i['symbol_id']=sid;i['full']['symbolId']=sid
        if sid==250:i['minimum_volume']=100;i['full'].update(minVolume=100,stepVolume=100,lotSize=10000,preciseTradingCommissionRate=0)
        metadata.append(i)
    events=[]
    for sid,t,bid,ask in [(1,0,120000,121000),(2,1000,130000,131000),(2,6000,130001,131001),(250,6001,7000000,7000001),(1,6002,120000,None),(2,6003,130002,131002),(1,6004,None,121000),(2,6005,130003,131003)]:
        events.append(dict(symbol=sid,sequence=len(events)+1,arrival_ns=t*1000000,received_ms=t,server_ms=t,bid=bid,ask=ask))
    return dict(instruments=[dict(Source='1',BaseAsset='EUR',QuoteAsset='USD'),dict(Source='2',BaseAsset='GBP',QuoteAsset='USD')],sources=['1','2','250'],terms=metadata,events=events)
class Scope(unittest.TestCase):
    def test_original_complete_fixed_panel_and_no_directional_or_broker_scope(self):
        self.assertEqual(n.POLICY['original_run'],40455704891);self.assertEqual(n.POLICY['all_original_events'],1140)
        for k in ('new_broker_requests','orders','response_tests','economic_model_runs'):self.assertEqual(n.POLICY[k],0)
        self.assertFalse(n.POLICY['original_quality_policy_changed']);self.assertFalse(n.POLICY['source_clock_certified'])
    def test_wrong_context_and_secret_role_stop_before_git(self):
        with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
            with self.assertRaisesRegex(ValueError,'NATIVE_CONTEXT'):n.admit()
            git.assert_not_called()
        for key in ('R3_CTRADER_ACCESS_TOKEN','SUCCESSOR_APP_PRIVATE_KEY','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM'):
            with patch.dict(os.environ,{key:'artificial'},clear=True):
                with self.assertRaisesRegex(ValueError,'SECRET_ROLE'):n.no_keys()
    def test_exact_one_attempt_and_no_history_ambiguity(self):
        n.one_shot({'total_count':1,'workflow_runs':[dict(id=7,run_attempt=1)]},7)
        for r in ({'total_count':2,'workflow_runs':[dict(id=7,run_attempt=1)]},{'total_count':1,'workflow_runs':[dict(id=7,run_attempt=2)]}):
            with self.assertRaises(ValueError):n.one_shot(r,7)
    def test_workflow_exact_read_only_two_custody_processes_not_keyed_evaluation(self):
        w=n.workflow();self.assertEqual(json.loads((n.ROOT/n.PATH).read_bytes()),w)
        self.assertEqual(w['on'],{'push':{'branches':[n.BRANCH],'paths':[n.PATH]}})
        j=w['jobs'][n.JOB];self.assertEqual(j['permissions'],{'contents':'read','actions':'read'});self.assertEqual(j['environment'],'mxm-r3-custody-v1')
        steps=[s for s in j['steps'] if 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in s.get('env',{})]
        self.assertEqual(len(steps),2);self.assertIn(' export ',steps[0]['run']);self.assertTrue(steps[1]['run'].endswith(' cold'))
        for step in steps:self.assertNotIn('dotnet',step['run']);self.assertNotIn(' finalize ',step['run'])
        for forbidden in ('workflow_dispatch','R3_CTRADER_','SUCCESSOR_APP_PRIVATE_KEY','mxm-r3-pepperstone-v1'):self.assertNotIn(forbidden,json.dumps(w))
        self.assertEqual(j['steps'][-1]['with']['path'].splitlines(),[n.OUT,'verification/observed-cost-fx/ledger.mxmenc','verification/observed-cost-fx/cold.json'])
class CompiledSourceIntegration(unittest.TestCase):
    def test_complete_artificial_source_cost_path_and_explicit_zero_without_fx(self):
        import shutil
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required native cost source integration runtime absent')
            self.skipTest('Required in CI')
        data=source_fixture();actual=fx.run(data,'--source');counts=fx.reconcile_source(data,actual)
        self.assertEqual(sum(sum(c.values()) for c in counts.values()),8)
        self.assertEqual(counts['250'],{'ESTIMATE':1})
        self.assertIsNone(actual[2]['per_side_ceiling_eur']);self.assertEqual(actual[3]['per_side_ceiling_eur'],'0')
        self.assertEqual(actual[-1]['status'],'ESTIMATE')
if __name__=='__main__':unittest.main()
