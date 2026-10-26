"""Artificial price paths verify the same account; no market/custody inputs."""
import copy,json,os,shutil,subprocess,tempfile,unittest
from decimal import Decimal as D
from pathlib import Path
from .intrinsic_reference import reference,reconcile
from .intrinsic_development import ROOT,PROJECT,run_segments,workflow,spec
class IntrinsicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('MXM_INTRINSIC_DLL'):
            cls.command=['dotnet',os.environ['MXM_INTRINSIC_DLL']]
        else:
            if not shutil.which('dotnet'):
                if os.environ.get('GITHUB_ACTIONS'):raise AssertionError('actual C# required in CI')
                raise unittest.SkipTest('local .NET absent')
            subprocess.run(['dotnet','build',str(ROOT/PROJECT),'-c','Release'],capture_output=True,check=True)
            cls.command=['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--']
    def paths(self,folder):
        paths=[]
        for w,start in enumerate((1787554800000,1788159600000,1788764400000)):
            path=folder/f'week-{w}.ndjson';lines=[]
            for i in range(601):
                x=i%40;raw=110000+4*(x if x<=20 else 40-x)
                for side,price in [('bid',raw),('ask',raw+4)]:lines.append({'t':start+i*1000,'side':side,'raw':price})
            day=start//86400000*86400000
            for offset in (0,250):
                for side,price in [('bid',110000),('ask',110004)]:lines.append({'t':day+57300000+offset,'side':side,'raw':price})
            path.write_text(''.join(json.dumps(x)+'\n' for x in lines));paths.append(path)
        return paths
    def test_actual_policy_latency_expiry_stop_recovery_and_clock_negatives(self):
        r=subprocess.run(self.command+['--selftest'],capture_output=True,text=True,check=True)
        p=json.loads(r.stdout);self.assertGreaterEqual(p['checks'],25);self.assertEqual(p['orders'],p['economic_trials']);self.assertFalse(p['native_ctrader_runtime'])
    def test_three_process_one_capital_full_reference_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);paths=self.paths(folder)
            actual=run_segments(paths,folder,'a'*64,'d'*64,self.command);expected=reference(paths)
            self.assertEqual(len(actual),3);self.assertTrue(reconcile(actual,expected))
            self.assertGreater(actual[-1]['account']['AcceptedEntries'],0)
            self.assertNotEqual(actual[1]['account']['FinalCashEur'],D(200))
            self.assertEqual(actual[1]['account']['Ledger'][:len(actual[0]['account']['Ledger'])],actual[0]['account']['Ledger'])
            for mode in ('refund','fill','fees','counts','decision'):
                bad=copy.deepcopy(actual)
                if mode=='refund':bad[1]['account']['FinalCashEur']=D(200)
                elif mode=='fill':bad[0]['account']['Ledger'][0]['Price']+=D('.0001')
                elif mode=='fees':bad[0]['account']['Ledger'][0]['CommissionEur']=0
                elif mode=='counts':bad[1]['account']['AcceptedEntries']+=1
                else:bad[0]['decision_sha256']='0'*64
                with self.subTest(mode=mode),self.assertRaises(ValueError):reconcile(bad,expected)
    def test_unpriceable_funded_source_is_terminal_not_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/'invalid.ndjson';t=1787554800000;lines=[]
            for offset,bid in [(0,110000),(1000,110060),(1250,110062)]:
                for side,v in [('bid',bid),('ask',bid+4)]:lines.append({'t':t+offset,'side':side,'raw':v})
            lines.append({'t':t+8000,'side':'bid','raw':110064})
            path.write_text(''.join(json.dumps(x)+'\n' for x in lines))
            actual=run_segments([path],folder,'a'*64,'d'*64,self.command)
            self.assertTrue(reconcile(actual,reference([path])))
            self.assertIsNone(actual[0]['account']);self.assertIn('UNPRICEABLE',actual[0]['fault'])
    def test_frozen_registration_and_separate_key_step(self):
        s=spec();self.assertEqual(s['budget']['models'],1);self.assertEqual(s['budget']['native_attempts'],1)
        w=workflow();job=w['jobs']['intrinsic-account-development'];self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
        keys=[x for x in job['steps'] if 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in x.get('env',{})]
        self.assertEqual(len(keys),1);self.assertIn('existing custody',keys[0]['name'])
        self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(w));self.assertNotIn('R3_CTRADER_ACCESS_TOKEN',json.dumps(w))
if __name__=='__main__':unittest.main()
