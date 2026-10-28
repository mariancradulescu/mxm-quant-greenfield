import copy,json,os,shutil,subprocess,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .peer_residual_reference import reference,verdict
ROOT=Path(__file__).resolve().parents[2];PROJECT='research_core_v4/laboratory/csharp/peer_residual/MxmPeerResidual.csproj'
def packets(sign=1):
 start=datetime(2026,8,27,tzinfo=timezone.utc);out=[]
 for ordinal in range(1,13):
  rows=[]
  for k in range(24):
   p='100';c=str(100+sign) if ordinal==1 and k==11 else '100'
   if ordinal==1 and k>=13:p=c='100' # future entry is not the feature closing price
   rows.append(dict(time_utc=(start+timedelta(minutes=5*k)).isoformat().replace('+00:00','Z'),open=p,close=c,high='102',low='98',tick_volume='4'))
  out.append(dict(ordinal=ordinal,group=0,eligible=True,rows=rows))
 return out
class Compiled(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required CSharp missing')
   raise unittest.SkipTest('Actual CSharp in required CI')
 def check(self,ps):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'in').write_text(''.join(json.dumps(x)+'\n' for x in ps))
   subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',str(p/'in'),str(p/'out')],check=True,capture_output=True)
   actual=json.loads((p/'out').read_bytes());self.assertEqual(actual,reference(ps));return actual
 def test_peer_residual_both_directions_and_delayed_future_open(self):
  for sign in (-1,1):
   a=self.check(packets(sign));r=next(r for r in a['Ledger'] if r['Status']=='COMPLETE');self.assertEqual((r['Ordinal'],r['Direction']),(1,-sign));self.assertEqual(r['Exit']-r['Entry'],3000)
 def test_insufficient_peers_and_nontradable_targets_never_filled(self):
  a=self.check(packets()[:10]);self.assertTrue(all(r['Status']=='NO_SIGNAL' for r in a['Ledger']))
  ps=packets();ps[0]['eligible']=False;a=self.check(ps);self.assertTrue(all(r['Status']=='NO_SIGNAL' for r in a['Ledger']))
 def test_missing_future_target_does_not_replace_it_with_available_runner_up(self):
  ps=packets();ps[0]['rows'].pop(13);ps[1]['rows'][11]['close']='100.5'
  a=self.check(ps);r=next(r for r in a['Ledger'] if r['Status']=='CENSORED');self.assertEqual(r['Ordinal'],1);self.assertIsNone(r['GrossUnits'])
 def test_future_price_changes_do_not_change_causal_selection(self):
  ps=packets();old=self.check(ps);ps[0]['rows'][23].update(open='99',close='99');new=self.check(ps)
  old=next(r for r in old['Ledger'] if r['Status']=='COMPLETE');new=next(r for r in new['Ledger'] if r['Status']=='COMPLETE')
  self.assertEqual({k:v for k,v in old.items() if k!='GrossUnits'},{k:v for k,v in new.items() if k!='GrossUnits'})
 def test_ties_use_ordinal_and_class_medians_exclude_target(self):
  ps=packets();ps[1]['rows'][11]['close']='101';a=self.check(ps);r=next(r for r in a['Ledger'] if r['Status']=='COMPLETE');self.assertEqual(r['Ordinal'],1)
 def test_warmup_and_gap_invalidate_feature_without_interpolating(self):
  ps=packets();ps[0]['rows'].pop(10);a=self.check(ps);self.assertTrue(all(r['Status']=='NO_SIGNAL' for r in a['Ledger']))
class Scope(unittest.TestCase):
 def test_support_precedes_quoted_gross_and_no_zero_cost_assumption(self):
  x=dict(Ledger=[dict(Status='COMPLETE',GrossUnits=10**12,Ordinal=1,Entry=1787882400)])
  self.assertEqual(verdict(x)[0],'DATA_LIMITED')
 def test_frozen_manifest_single_attempt_and_source_scope(self):
  from . import peer_residual_development as n
  self.assertEqual(json.loads((ROOT/n.PATH).read_bytes()),n.workflow());self.assertEqual(n.validate()['policy'],n.POLICY)
  self.assertFalse(n.POLICY['historical_costs_proven']);self.assertFalse(n.POLICY['capital_replay']);self.assertEqual(n.POLICY['model_trials_max'],1)
  self.assertEqual(n.POLICY['reference_roundtrip_bps'],[5,10,20,40]);self.assertNotIn('workflow_dispatch',n.workflow()['on'])
  self.assertNotIn('R3_CTRADER_',json.dumps(n.workflow()));self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(n.workflow()))
 def test_wrong_native_context_fails_before_source_or_keys(self):
  from . import peer_residual_development as n
  from unittest.mock import patch
  with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
   with self.assertRaises(ValueError):n.context(custody=True)
   git.assert_not_called()
