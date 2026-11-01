import itertools,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
NATIVE=ROOT/'research_core_v4/native_tick_replay_v1/csharp'
PROJECT=ROOT/'research_core_v4/laboratory/csharp/native_run/MxmNativeRun.csproj'
def method(source,name):
 start=source.index(name+'(');start=source.index('{',start);level=1;i=start+1
 while level:
  if source[i]=='{':level+=1
  if source[i]=='}':level-=1
  i+=1
 return source[start+1:i-1]
class Compiled(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS'):raise AssertionError('CSharp required')
   raise unittest.SkipTest('local .NET absent')
  subprocess.run(['dotnet','build',str(PROJECT),'-c','Release'],check=True,capture_output=True)
 def run_cases(self,cases):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'in.json';o=Path(tmp)/'out.json';p.write_text(json.dumps(cases))
   subprocess.run(['dotnet','run','--project',str(PROJECT),'-c','Release','--no-build','--',str(p),str(o)],check=True,capture_output=True)
   return json.loads(o.read_bytes())
 def test_real_csharp_minimum_ticket_capacity_fixture(self):
  # Runs the EXISTING compiled C# fixture against EUR200/150.9078 margin,
  # stop risk, spread, cash reserve and corrupted data, never a broker account.
  p=ROOT/'research_core_v4/native_tick_replay_v1/operational/MxmNativeEstimatedFrictionGuardFixture.csproj'
  result=subprocess.run(['dotnet','run','--project',str(p),'-c','Release'],
                        check=True,capture_output=True,text=True,timeout=120)
  self.assertIn('MXM_READ_ONLY_NATIVE_EUR200_MINIMUM_TICKET_COMBINED_NECESSARY_CAPACITY_PASS_NO_ORDERS',
                result.stdout)
 def test_all_mode_environment_permission_combinations(self):
  cases=[dict(obs=o,demo=d,sim=s,env=e,actions=[]) for o,d,s in itertools.product((False,True),repeat=3) for e in ('Desktop','CLI','Cloud','UNKNOWN')]
  # explicit product above is three Boolean dimensions; env is separate
  reports=self.run_cases(cases)
  for c,r in zip(cases,reports):
   known=c['env']!='UNKNOWN';observe=known and c['obs'] and not c['demo'] and not c['sim'];legacy=known and not c['obs'] and (c['sim'] or c['env']=='Desktop')
   self.assertEqual(r['first'],observe or legacy,c);s=r['stages'][0];self.assertEqual(s['observing'],observe,c);self.assertEqual(s['permit'],legacy,c)
   self.assertEqual(s['latched'],c['obs']);self.assertEqual(r['orders'],0);self.assertFalse(r['native_callbacks_received'])
 def test_observation_cannot_escalate_or_restart_and_stopped_legacy_cannot_mutate(self):
  cases=[dict(obs=True,demo=False,sim=False,env=e,actions=['escalate','stop','escalate']) for e in ('Desktop','CLI','Cloud')]
  cases.append(dict(obs=False,demo=True,sim=False,env='Desktop',actions=['stop','escalate']))
  for c,r in zip(cases,self.run_cases(cases)):
   for s in r['stages'][1:]:self.assertFalse(s['permit']);self.assertEqual(s['mode'],'Stopped')
   if c['obs']:self.assertTrue(all(s['latched'] and s['syntheticPermits']==0 for s in r['stages']))
 def test_existing_book_observation_still_does_not_certify_liquidity_or_transport(self):
  r=self.run_cases([dict(obs=True,demo=False,sim=False,env='Cloud',actions=[])])[0];v=r['view']
  self.assertEqual(v['Events'],2);self.assertEqual(v['AskChanges'],1);self.assertIsNone(v['BidServerMs']);self.assertEqual(v['ReportedTransport'],0)
  self.assertFalse(v['ExecutabilityProven']);self.assertFalse(v['ContinuousObservationProven']);self.assertFalse(r['cloud_activated'])
class NativeIntegration(unittest.TestCase):
 def setUp(self):self.s=(NATIVE/'MxmReferenceProductBot.cs').read_text()
 def test_observation_branches_before_roster_storage_and_strategy(self):
  s=method(self.s,'OnStart');self.assertLess(s.index('if(nativeRun.IsObserving)'),s.index('bool onlineAr1='));self.assertLess(s.index('if(nativeRun.IsObserving)'),s.index('entryCheckpoint=new'))
  self.assertIn('Application.EnvironmentType!=cAlgo.API.EnvironmentType.Desktop',s)
  self.assertIn('[Parameter("Native Observation Only",DefaultValue=false)]',self.s)
  self.assertIn('RunningMode!=cAlgo.API.RunningMode.RealTime',s)
 def test_all_broker_mutation_paths_and_storage_access_are_fenced(self):
  for name in ('ApplyPortfolioDecision','TryDefensiveClose','OnTimer','LatchProtectionHalt','OnPortfolioTick','OnPortfolioBarClosed','OnBrokerPositionClosed'):
   # match declaration rather than an earlier call site
   import re
   match=re.search(r'\b(?:void) '+name+r'\(',self.s);body=method(self.s[match.start():],name)
   self.assertTrue(body.strip().startswith('if(nativeRun.BlocksAccountMutation)return;'),name)
  for name in ('ReadEntryCheckpoint','WriteEntryCheckpoint','ReadConfirmedEntries','WriteConfirmedEntries'):
   import re
   match=re.search(r'(?:string\?|void) '+name+r'\(',self.s);body=method(self.s[match.start():],name)
   self.assertTrue(body.strip().startswith('nativeRun.DemandAccountMutationPath();'),name)
 def test_readonly_callbacks_do_not_call_trading_storage_or_strategy(self):
  s=self.s[self.s.index(' void StartNativeObservation()'):self.s.index(' long? BrokerPositionId(')]
  for forbidden in ('LocalStorage','ExecuteMarketOrder','ClosePosition','PrepareRecoverable','Initialize(','ApplyPortfolioDecision','Timer.Start','OnCompletedBar','new MxmDecision'):
   self.assertNotIn(forbidden,s)
  self.assertIn('ReportBrokerOpeningFacts();',s);self.assertIn('nativeReceptionBook.Observe',s);self.assertIn('nativeReceptionRunId',s);self.assertIn('durableRecovery=false',s)
 def test_stop_and_exception_cannot_fall_through_to_account_recovery(self):
  s=method(self.s,'OnStop');self.assertLess(s.index('ObservationLatched'),s.index('Timer.Stop'));self.assertNotIn('nativeRun.Stop()',s[s.index('Timer.Stop'):])
  s=method(self.s,'OnException');self.assertLess(s.index('ObservationLatched'),s.index('entryStorageFault'))
 def test_native_causal_target_and_selected_symbol_economic_join_is_one_readonly_bot(self):
  root=ROOT/'research_core_v4/native_tick_replay_v1'
  policy=(root/'csharp/MxmRelativeStrengthNativeObservation.cs').read_text()
  runtime=(root/'operational/MxmReferenceProductBot.cs').read_text()
  join=(root/'operational/MxmNativeCausalOpportunityObservation.cs').read_text()
  economy=(root/'operational/MxmNativeEconomicObservation.cs').read_text()
  project=(root/'operational/MxmOperationalProductBot.csproj').read_text()
  historical=(root/'csharp/MxmReferenceBot.csproj').read_text()
  # Historical reference adapter remains FROZEN, not instrumented or
  # remapped into a new economic experiment.
  self.assertNotIn('OnNativeCausalPortfolioTarget(',policy)
  self.assertIn('StartRelativeStrengthObservation()',policy)
  self.assertIn('MxmNativeCausalOpportunityObservation.cs',project)
  self.assertNotIn('MxmNativeCausalOpportunityObservation.cs',historical)
  self.assertIn('StartNativeCausalOpportunityObservation();',runtime)
  self.assertIn('StopNativeCausalOpportunityObservation();',runtime)
  self.assertNotIn('StartRelativeStrengthObservation();',runtime)
  self.assertNotIn('StopRelativeStrengthObservation();',runtime)
  self.assertIn('observedPortfolioPolicy=new MxmRelativeStrengthPortfolio(roster);',join)
  self.assertIn('observedPortfolioPolicy.Observe(',join)
  self.assertEqual(join.count('observedPortfolioPolicy.Observe('),1)
  self.assertIn('bars.BarClosed+=OnNativeJointPolicyBarClosed;',join)
  self.assertIn('bars.BarClosed-=OnNativeJointPolicyBarClosed;',join)
  self.assertIn('causalQuoteBooks.TryGetValue(target.Symbol,out var selectedBook)',join)
  self.assertIn('ReportNativeMinimumTicketAperture(selected,selectedBook)',join)
  self.assertIn('target.Reason!="JOINT_RELATIVE_STRENGTH_TARGET"',join)
  self.assertIn('target.AvailableUtc>now',join)
  self.assertIn('observedNonFlatCandidates',join)
  self.assertIn('completeRoundTripCostEUR=UNKNOWN',join)
  self.assertIn('economicQualified=false entryAuthorized=false orders=false',join)
  self.assertIn('string ReportNativeMinimumTicketAperture(Symbol? selectedSymbol',economy)
  self.assertIn('var book=selectedBook.ReadBook(Environment.TickCount64)',economy)
  self.assertIn('var symbol=selectedSymbol;',economy)
  for forbidden in ('ExecuteMarketOrder(', 'ClosePosition(', 'LocalStorage', 'MarkSubmitted(',
                    'new MxmDecisionKernel(', 'ApplyPortfolioDecision(', 'System.Net.'):
   self.assertNotIn(forbidden,join)
  self.assertEqual(join.count('ReportNativeMinimumTicketAperture(selected,selectedBook)'),1)
  self.assertIn('if(!nativeRun.IsObserving)return;',join)
  self.assertIn('symbol.Tick+=OnNativeCausalQuoteTick;',join)
  self.assertIn('pair.Value.Tick-=OnNativeCausalQuoteTick;',join)
 def test_operational_native_minimum_ticket_observation_is_readonly_and_not_order_admission(self):
  root=ROOT/'research_core_v4/native_tick_replay_v1/operational'
  observe=(root/'MxmNativeEconomicObservation.cs').read_text()
  guard=(root/'MxmNativeEstimatedFrictionGuard.cs').read_text()
  bot=(root/'MxmReferenceProductBot.cs').read_text()
  self.assertIn('MxmNativeEstimatedFrictionGuard.MinimumTicketNecessaryCapacity(',observe)
  self.assertIn('MXM_NATIVE_EUR200_MIN_TICKET_JOINT_NECESSARY_ONLY',observe)
  self.assertIn('actualCommissionEUR=UNKNOWN',observe)
  self.assertIn('orderAdmission=false accountMutation=false cloudActivation=false',observe)
  self.assertIn('PASSES_VISIBLE_NECESSARY_ONLY_NO_ADMISSION',guard)
  self.assertIn('if(phase=="BAR_CALLBACK")ReportNativeMinimumTicketAperture();',bot)
  segment=method(observe,'ReportNativeMinimumTicketAperture')
  for banned in ('ExecuteMarketOrder(', 'ClosePosition(', 'LocalStorage', 'MarkSubmitted(',
                 'MxmBrokerIntentFence','EntryCheckpoint'):
   self.assertNotIn(banned,segment)
if __name__=='__main__':unittest.main()
