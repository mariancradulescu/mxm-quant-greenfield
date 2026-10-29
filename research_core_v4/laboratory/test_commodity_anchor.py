import copy,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from decimal import Decimal as D
from .commodity_anchor_reference import reconcile,reference
ROOT=Path(__file__).resolve().parents[2];PROJECT=ROOT/'research_core_v4/laboratory/csharp/commodity_anchor/MxmCommodityAnchor.csproj'
class AnchorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS'):raise AssertionError('CSharp required')
   raise unittest.SkipTest('local .NET absent')
  subprocess.run(['dotnet','build',str(PROJECT),'-c','Release'],check=True,capture_output=True)
 def data(self):
  start=1779840000000;target=[];anchor=[];fx=[]
  for i in range(33*24):
   t=start+i*3600000;price=70+(i%13)/100;basis=(i%8-4)/2
   target.append([t,price,price+.2,price-.2,price+.05]);anchor.append([t,price-basis,price-basis+.2,price-basis-.2,price-basis+.05]);fx.append([t,1.1,1.101,1.099,1.1])
  return dict(policy='d'*64,start=start,evaluation_start=1780272000000,end=1782691200000,terms=dict(units=1,step_units=1,max_units=100,margin_eur=9.11,fee_usd=0,pnl_rate=.0001),target=target,anchor=anchor,fx=fx)
 def run_model(self,d):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/'in';b=Path(tmp)/'out';a.write_text(json.dumps(d));subprocess.run(['dotnet','run','--project',str(PROJECT),'-c','Release','--no-build','--',str(a),str(b)],check=True,capture_output=True);return json.loads(b.read_bytes(),parse_float=D)
 def test_artificial_adaptive_forecasts_and_shared_funded_account(self):
  d=self.data();a=self.run_model(d);self.assertTrue(reconcile(a,d));self.assertIsNone(a['fault']);self.assertGreater(a['account']['AcceptedEntries'],0);self.assertGreater(a['cold'],0)
  self.assertTrue(any(x['Kind']=='FINANCING' for x in a['account']['Ledger']));self.assertEqual(a['account']['InitialCapitalEur'],200);self.assertFalse(a['actual_fills'])
 def test_prefix_causality_and_source_gap_no_account_healing(self):
  d=self.data();a=self.run_model(d);short=copy.deepcopy(d);short['end']=d['start']+150*3600000
  b=self.run_model(short);self.assertEqual(a['decisions'][:len(b['decisions'])],b['decisions'])
  # Remove a whole source hour *after an admitted entry*, retaining adverse loss.
  first=next(x for x in a['account']['Ledger'] if x['Kind']=='ENTRY')
  from datetime import datetime
  ms=int(datetime.fromisoformat(first['Utc'].replace('Z','+00:00')).timestamp()*1000)
  broken=copy.deepcopy(d);broken['target']=[x for x in d['target'] if x[0]!=ms+3600000]
  r=self.run_model(broken);self.assertTrue(reconcile(r,broken));self.assertIsNone(r['account']);self.assertIsNotNone(r['fault']);self.assertGreater(r['last_verified_prefix']['AcceptedEntries'],0)
 def test_anchor_unit_rescaling_does_not_manufacture_signal_or_cash(self):
  d=self.data();a=self.run_model(d);b=copy.deepcopy(d)
  b['anchor']=[[r[0]]+[v*100 for v in r[1:]] for r in d['anchor']];z=self.run_model(b)
  self.assertTrue(reconcile(z,b));self.assertEqual([r['Direction'] for r in a['decisions']],[r['Direction'] for r in z['decisions']]);self.assertEqual(a['proposals'],z['proposals']);self.assertEqual(a['account'],z['account'])
 def test_cash_and_forecast_tampering_refused(self):
  d=self.data();a=self.run_model(d)
  for kind in ('cash','forecast'):
   b=copy.deepcopy(a)
   if kind=='cash':b['account']['FinalCashEur']+=1
   else:b['decisions'][-1]['Basis']+=1
   with self.assertRaises(ValueError):reconcile(b,d)
class Scope(unittest.TestCase):
 def test_frozen_policy_roles_and_no_automatic_retry(self):
  from .commodity_anchor_development import frozen,workflow,START,EVAL,END
  # Preserve the frozen registration; modern shared core is not its executable.
  with self.assertRaisesRegex(ValueError,'ANCHOR_IMPLEMENTATION'):frozen()
  from .commodity_anchor_development import HOME,SPEC,SPEC_SHA
  from .common import bytes_digest
  raw=(HOME/SPEC).read_bytes();self.assertEqual(bytes_digest(raw),SPEC_SHA)
  s=json.loads(raw);self.assertEqual(s['models_max'],1);self.assertEqual(s['capital_eur'],200);self.assertLess(START,EVAL);self.assertLess(END,1789603200000)
  w=workflow();self.assertEqual(len(w['jobs']),3);self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(w))
  for job in w['jobs'].values():
   self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
   for step in job['steps']:
    env=step.get('env',{});self.assertFalse('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env and 'R3_CTRADER_ACCESS_TOKEN' in env)
  self.assertIn('source-cache',w['jobs']['basis-collect']['needs']);self.assertIn('clear',w['jobs']['basis-collect']['if'])
if __name__=='__main__':unittest.main()
