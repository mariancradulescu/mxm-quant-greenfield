import copy,json,os,shutil,subprocess,tempfile,unittest
from decimal import Decimal as D
from pathlib import Path
from .quote_innovation_reference import reference,reconcile,forecast_errors
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'research_core_v4/laboratory/csharp/quote_innovation/MxmQuoteInnovation.csproj'
class InnovationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS'):raise AssertionError('CSharp required')
   raise unittest.SkipTest('local .NET absent')
  subprocess.run(['dotnet','build',str(PROJECT),'-c','Release'],check=True,capture_output=True)
  cls.command=['dotnet','run','--project',str(PROJECT),'-c','Release','--no-build','--']
 def path(self,folder,variant=0):
  p=folder/f'{variant}.ndjson';lines=[];t=1787554800000+variant*604800000
  for i in range(130*60):
   # deterministic distinct feature/return relationships, no market data
   minute=i//60;wave=(minute%9)-4;bid=110000+wave*3+(i%60)*(1 if minute%3 else -1)
   if variant==1 and i==6000:
    lines.append({'t':t+i*1000,'side':'bid','raw':bid});continue
   for side,v in [('bid',bid),('ask',bid+5)]:lines.append({'t':t+i*1000,'side':side,'raw':v})
  p.write_text(''.join(json.dumps(e)+'\n' for e in lines));return p
 def run_policy(self,paths,folder):
  out=folder/'out.json';subprocess.run(self.command+[str(out),'d'*64,'a'*64]+[str(p) for p in paths],check=True,capture_output=True)
  return json.loads(out.read_bytes(),parse_float=D)
 def test_completed_minutes_predictions_decisions_and_one_account(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp);paths=[self.path(f,i) for i in range(3)];a=self.run_policy(paths,f);e=reference(paths)
   self.assertTrue(reconcile(a,e));self.assertGreater(a['predictions'],100);self.assertEqual(a['learned_samples'],256)
   self.assertEqual(a['rows'],46800-1);self.assertEqual(a['initial_funding_count'],1)
   for key in ('prediction_sha256','decision_sha256'):
    bad=copy.deepcopy(a);bad[key]='0'*64
    with self.assertRaises(ValueError):reconcile(bad,e)
 def test_causal_prefix_and_gap_do_not_train_on_future(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp);p=self.path(f);a=self.run_policy([p],f)
   raw=p.read_text().splitlines();prefix=f/'prefix.ndjson';prefix.write_text('\n'.join(raw[:110*120])+'\n')
   b=self.run_policy([prefix],f)
   self.assertEqual(a['summaries'][0]['forecasts'][:len(b['summaries'][0]['forecasts'])],b['summaries'][0]['forecasts'])
 def test_kernel_cold_exact_and_duplicate_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp);p=f/'kernel.json';rows=[{'t':i*60000,'x':(i%7-3)/3,'mid':1.1+(i%5)/10000} for i in range(100)]
   p.write_text(json.dumps(rows));a=json.loads(subprocess.check_output(self.command+['--kernel',str(p)]))
   rows.insert(75,{'cold':True});p.write_text(json.dumps(rows));b=json.loads(subprocess.check_output(self.command+['--kernel',str(p)]))
   self.assertEqual(a,b);self.assertIsNotNone(a[-1])
   rows.append(rows[-1]);p.write_text(json.dumps(rows));r=subprocess.run(self.command+['--kernel',str(p)],capture_output=True)
   self.assertNotEqual(r.returncode,0)
 def test_strict_exposure_loss_is_not_capital_refund(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp);p=f/'exposure.ndjson';t=1787554800000;lines=[]
   for i in range(70*60):
    bid=110000+i
    for side,v in [('bid',bid),('ask',bid if i==3902 else bid+5)]:lines.append({'t':t+i*1000,'side':side,'raw':v})
   p.write_text(''.join(json.dumps(e)+'\n' for e in lines));a=self.run_policy([p],f)
   self.assertTrue(reconcile(a,reference([p])));self.assertIsNone(a['account']);self.assertIn('UNPRICEABLE',a['fault'])
   prefix=a['last_verified_prefix_account'];self.assertGreater(prefix['AcceptedEntries'],0);self.assertEqual(prefix['OpenPositions'],1)
   self.assertLess(prefix['FinalCashEur'],200);self.assertEqual(a['rows'],8400)
   self.assertFalse(a['economic_edge_proven']);self.assertFalse(a['hard21_proven'])
 def test_reference_error_includes_missing_targets(self):
  s=[{'forecasts':[{'bucket':0,'mid':'1','prediction':'2'},{'bucket':60000,'mid':'1.0001','prediction':'1'},{'bucket':180000,'mid':'1.1','prediction':'1'}]}]
  e=forecast_errors(s)[0];self.assertEqual(e['matched'],1);self.assertEqual(e['missing_target'],2);self.assertFalse(e['model_beats_zero_mse'])
 def test_frozen_scope_and_key_separation(self):
  from .quote_innovation_development import spec,workflow
  s=spec();self.assertEqual(s['models'],1);self.assertFalse(s['independent_confirmation'])
  w=workflow();self.assertNotIn('CTRADER_ACCESS_TOKEN',json.dumps(w));self.assertNotIn('contents: write',json.dumps(w))
if __name__=='__main__':unittest.main()
