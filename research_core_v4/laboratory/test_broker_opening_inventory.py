import copy,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'research_core_v4/laboratory/csharp/broker_opening/MxmBrokerOpening.csproj'
SCOPE='["MXM_CSHARP_REFERENCE_V1","ARTIFICIAL",123,"DEMO"]'
def fill(i=1,order=7,units=400):
 return dict(DealId=i,OrderId=order,PositionId=9,Symbol='EURUSD',Direction=1,Units=units,Price=1.1,
  ExecutionUtc='2026-08-24T12:01:00Z',Label='OWNER',Comment='MXM'+'1'*32)
class Compiled(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required compiled broker reconstruction absent')
   raise unittest.SkipTest('Compiled core mandatory in CI')
 def run_case(self,fills,scope=SCOPE,request=None,recover=False):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);data=dict(scope=scope,now='2026-08-24T13:00:00Z',fills=fills,recover=recover)
   if request is not None:data['request']=request
   (p/'in').write_text(json.dumps(data));r=subprocess.run(['dotnet','run','--project',str(PROJECT),'-c','Release','--no-build','--',str(p/'in'),str(p/'out')],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr);return json.loads((p/'out').read_bytes())
 def test_overlapping_partial_close_and_open_book_deduplicate_partial_fills(self):
  rows=[fill(),fill(2,units=600),fill(),fill(2,units=600)]
  a=self.run_case(rows);self.assertEqual(len(a['Fills']),2);self.assertEqual(len(a['Orders']),1)
  self.assertEqual(a['Orders'][0]['ObservedFilledUnits'],1000)
  self.assertEqual(a,self.run_case(list(reversed(rows))))
 def test_changed_duplicate_and_order_identity_refuse_all_facts(self):
  a=fill();b=fill();b['Units']=500
  self.assertEqual(self.run_case([a,b])['status'],'UNAVAILABLE')
  b=fill(2);b['Symbol']='GBPUSD';self.assertEqual(self.run_case([a,b])['status'],'UNAVAILABLE')
 def test_cold_instance_reconstructs_same_facts_and_scope_separates_accounts(self):
  a=self.run_case([fill()]);self.assertEqual(a,self.run_case([fill()]))
  b=self.run_case([fill()],SCOPE+'other');self.assertNotEqual(a['ScopeFingerprint'],b['ScopeFingerprint'])
  self.assertNotEqual(a['FactsSha256'],b['FactsSha256'])
 def test_empty_or_incomplete_history_never_admits_hard21_capital_or_pending_clear(self):
  for rows in ([],[fill()]):
   a=self.run_case(rows)
   for k in ('HistoryCoverageProven','CapitalContinuityProven','Hard21Proven','MaySubmitOrClearPending'):self.assertFalse(a[k])
 def test_pending_positive_partial_full_and_conflicting_orders_never_resubmit(self):
  a=self.run_case([fill()]);scope='MXM_ENTRY_CHECKPOINT_V1_READY_'+a['ScopeFingerprint']
  r=dict(Scope=scope,Attempt='1'*32,Label='OWNER',Symbol='EURUSD',Direction=1,Units=1000,StopPips=12,PipSize=.0001,TickSize=.00001,
   BoundaryUtc='2026-08-24T12:00:00Z',PreparedUtc='2026-08-24T12:00:01Z',DeadlineUtc='2026-08-24T12:05:00Z',BeforeIds=[])
  a=self.run_case([fill()],request=r)['Pending'];self.assertTrue(a['Correlated']);self.assertFalse(a['RequestedUnitsObserved'])
  a=self.run_case([fill(),fill(2,units=600)],request=r)['Pending'];self.assertTrue(a['RequestedUnitsObserved'])
  for k in ('MayResubmit','MayClearPending','StopProtectionProven'):self.assertFalse(a[k])
  a=self.run_case([fill(),fill(2,order=8)],request=r)['Pending'];self.assertFalse(a['Correlated'])
  self.assertFalse(self.run_case([],request=r)['Pending']['Correlated'])
 def test_original_durable_pending_and_ledger_recover_only_with_full_broker_fill_proof(self):
  for rows in ([],[fill()]):
   a=self.run_case(rows,recover=True);self.assertFalse(a['restored']);self.assertTrue(a['pendingRetained']);self.assertEqual(a['confirmed'],0)
  a=self.run_case([fill(),fill(2,units=600),fill()],recover=True)
  self.assertTrue(a['restored']);self.assertFalse(a['pendingRetained']);self.assertEqual(a['confirmed'],1)
  self.assertEqual(a['resubmissions'],0);self.assertFalse(a['MayClearPending']);self.assertFalse(a['MayResubmit'])
 def test_many_overlapping_paths_match_independent_id_and_order_aggregation(self):
  import random,collections
  rng=random.Random(238);rows=[];expected={}
  for i in range(1,301):
   f=fill(i,order=100+i//3,units=rng.randrange(1,1000));rows.extend([f]*rng.randrange(1,4));expected[i]=f
  rng.shuffle(rows);a=self.run_case(rows)
  totals=collections.Counter()
  for f in expected.values():totals[f['OrderId']]+=f['Units']
  self.assertEqual({o['OrderId']:o['ObservedFilledUnits'] for o in a['Orders']},dict(totals))
  self.assertEqual(sorted(x['DealId'] for x in a['Fills']),sorted(expected))
 def test_bad_future_non_utc_or_negative_fields_are_not_fills(self):
  for key,value in [('Units',0),('Price',-1),('DealId',0),('ExecutionUtc','2026-08-25T12:00:00Z'),('ExecutionUtc','2026-08-24T12:01:00')]:
   f=fill();f[key]=value;self.assertEqual(self.run_case([f])['status'],'UNAVAILABLE')
class NativeIntegration(unittest.TestCase):
 def test_actual_robot_reads_broker_deal_links_without_trading_or_storage_writes(self):
  s=(ROOT/'research_core_v4/native_tick_replay_v1/csharp/MxmReferenceProductBot.cs').read_text();p=s[s.index(' MxmBrokerOpeningInventory ReadBrokerOpeningFacts'):s.index(' void ReportRecordedWeeks')]
  self.assertIn('position.Deals',p);self.assertIn('trade.ClosingDeal.Closing',p)
  self.assertIn('DealPositionImpact.Opening',p);self.assertIn('!HasBrokerOpeningRecoveryProof()',s);self.assertIn('proof.Correlated && proof.RequestedUnitsObserved',p);self.assertIn('ReportBrokerOpeningFacts();',s)
  for forbidden in ('ExecuteMarketOrder','ClosePosition(','.Write(','.SetString(','.CompleteReconciled(','.RecordConfirmed('):self.assertNotIn(forbidden,p)
