import copy,datetime as dt,json,os,subprocess,tempfile,unittest
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch
from .pathstate_reference import reference,reconcile
from .pathstate_development import ROOT,SPEC,validate_spec,context,first_native_run,decide

def rows(n=2880,direction=1):
    start=dt.datetime(2026,8,20,tzinfo=dt.timezone.utc);result=[]
    price=D(100)
    for i in range(n):
        if i:price=(price*(D(1)+D(direction)/1000)).quantize(D(".000001"))
        result.append(dict(time_utc=(start+dt.timedelta(minutes=5*i)).isoformat().replace('+00:00','Z'),
            open=str(price),high=str(price+D(1)),low=str(price-D(1)),close=str(price),tick_volume=1))
    return result
class PathStateDevelopmentTests(unittest.TestCase):
    def test_frozen_finite_scope(self):
        s=validate_spec(active=True)
        self.assertEqual((s['cells'],s['cell_window'],s['cell_minimum_samples'],s['zero_prior_samples']),(8,32,16,16))
        self.assertEqual((s['delay_bars'],s['hold_bars'],s['model_leaves']),(2,12,1))
        self.assertFalse(s['eur200_account']);self.assertFalse(s['hard21']);self.assertEqual(s['orders'],0)
    def test_matured_targets_not_feature_time_labels(self):
        v=reference(rows(80),trace=True)
        self.assertEqual(v['TrainingLabels'],63) # origins3..65, maturity17..79
        self.assertEqual(v['TrainingCensored'],14)
        self.assertTrue(all(x is None for x in v['ForecastTrace'][:32]))
        self.assertGreater(v['ForecastTrace'][32],0)
        v=reference(rows(2880),trace=True)
        self.assertEqual(v['BySegment']['1']['Complete'],0)
        self.assertGreater(v['Complete'],30);self.assertGreater(v['SumGrossBps'],0)
        for signature in v['EpisodeSignatures']:
            entry,exit,side=map(int,signature.split(','));self.assertEqual(exit-entry,12);self.assertEqual(side,1)
    def test_future_changes_never_rewrite_prefix_forecasts_or_signals(self):
        a=rows();cut=2300;original=reference(a,trace=True);changed=copy.deepcopy(a)
        for row in changed[cut:]:
            for name in ('open','high','low','close'):row[name]=str(D(row[name])*2)
        after=reference(changed,trace=True)
        self.assertEqual(original['ForecastTrace'][:cut],after['ForecastTrace'][:cut])
        self.assertEqual(original['SignalTrace'][:cut],after['SignalTrace'][:cut])
    def test_gap_censors_training_and_active_episode_without_interpolation(self):
        a=rows();before=reference(a);damaged=reference(a[:2050]+a[2051:])
        self.assertLess(damaged['TrainingLabels'],before['TrainingLabels'])
        self.assertGreater(damaged['TrainingCensored'],before['TrainingCensored'])
        self.assertGreaterEqual(damaged['Censored'],1)
        self.assertEqual(reference(rows(17))['TrainingLabels'],0)
    def test_zero_returns_are_not_bearish_states(self):
        a=rows(100)
        for row in a:row.update(open='100',high='101',low='99',close='100')
        v=reference(a);self.assertEqual(v['TrainingLabels'],0);self.assertEqual(v['ReadyForecasts'],0)
    def test_all_eight_contexts_and_both_direction_laws(self):
        a=rows(200);price=D(100);bits=[0,0,0,1,0,1,1,1]
        for i,row in enumerate(a):
            price+=D('.01') if bits[i%8] else -D('.01')
            row.update(open=str(price),high=str(price+1),low=str(price-1),close=str(price))
        self.assertEqual(set(reference(a,trace=True)['Contexts'])-{None},set(range(8)))
        negative=reference(rows(2880,-1),trace=True)
        self.assertGreater(negative['Complete'],30);self.assertTrue(any(x==-1 for x in negative['SignalTrace']))
        self.assertGreater(negative['SumGrossBps'],0)
    def test_invalid_clock_price_or_duplicate_refused(self):
        for key,value in [('time_utc','2026-09-17T00:00:00Z'),('time_utc','2026-08-20T00:01:00Z'),('open','NaN')]:
            a=rows(50);a[0][key]=value
            with self.assertRaises(ValueError):reference(a)
        a=rows(1)
        with self.assertRaises(ValueError):reference(a+a)
    def test_signature_forecast_target_tamper_refused(self):
        v=reference(rows(100));reconcile(v,v)
        for field in ('SignalSha256','ForecastSha256','TrainingSha256','LedgerSha256'):
            changed=copy.deepcopy(v);changed[field]='0'*64
            with self.assertRaises(ValueError):reconcile(changed,v)
    def test_immutable_scope_custody_and_one_native_run_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed=Path(tmp)/'spec';changed.write_bytes(SPEC.read_bytes()+b' ')
            with patch('research_core_v4.laboratory.pathstate_development.SPEC',changed):
                with self.assertRaises(Exception):validate_spec(active=True)
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(Exception,'PATHSTATE_PROTECTED_CONTEXT'):context()
        with patch.dict(os.environ,{'GITHUB_RUN_ID':'123'},clear=True):
            run=dict(id=123,head_sha='a'*40,head_branch='mxm-remediation-p0-p4-20261015-v1',run_attempt=1)
            with patch('subprocess.check_output',return_value=json.dumps(dict(total_count=1,workflow_runs=[run]))):first_native_run('a'*40)
            for history in (dict(total_count=2,workflow_runs=[run]),dict(total_count=1,workflow_runs=[dict(run,id=124)])):
                with patch('subprocess.check_output',return_value=json.dumps(history)):
                    with self.assertRaisesRegex(Exception,'ONE_REGISTERED_NATIVE_ATTEMPT'):first_native_run('a'*40)
    def test_compiled_csharp_matches_independent_complete_array_targets(self):
        assembly=ROOT/'research_core_v4/laboratory/csharp/pathstate/bin/Release/net8.0/MxmPathStateDevelopment.dll'
        if not assembly.exists():
            if os.environ.get('GITHUB_ACTIONS')=='true':self.fail('Required compiled C# comparison cannot be skipped in CI')
            self.skipTest('C# build required before this test in CI')
        a=rows();gap=a[:2050]+a[2051:];b=rows(2880,-1)
        packets=[dict(ordinal=i,rows=a if i==1 else gap if i==2 else b if i==3 else []) for i in range(1,1577)]
        def invoke(p):return subprocess.run(['dotnet',str(assembly),'--development-stream'],
            input=''.join(json.dumps(x)+'\n' for x in p),text=True,capture_output=True)
        result=invoke(packets);self.assertEqual(result.returncode,0,result.stderr)
        actual=json.loads(result.stdout,parse_float=D)
        for packet,value in zip(packets,actual):reconcile(value,reference(packet['rows']))
        self.assertEqual(len(actual),1576)
        bad=copy.deepcopy(packets);bad[0]['rows'][0]['time_utc']='2026-09-17T00:00:00Z'
        for p in (bad,packets[:-1]):self.assertNotEqual(invoke(p).returncode,0)
