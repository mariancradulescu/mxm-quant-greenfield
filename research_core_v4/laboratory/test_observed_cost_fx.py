import os,random,shutil,unittest
from . import observed_cost_fx as n

def instrument(source,base,quote):return dict(Source=source,BaseAsset=base,QuoteAsset=quote)
def obs(source,t,bid,ask):return dict(op='observe',source=source,now=t,bid=bid,ask=ask)
def rate(a,b,t):return dict(op='rate',now=t,**{'from':a,'to':b})
class CostFxCompiled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required observed FX CSharp unavailable')
            raise unittest.SkipTest('Compiled actual component required in CI')
    def check(self,inst,actions):
        data=dict(instruments=inst,actions=actions);out=n.run(data);self.assertEqual(out,n.fixture_reference(data));return out
    def test_debit_uses_ask_and_inverse_bid_with_no_credit_or_midpoint_substitution(self):
        r=self.check([instrument('anything','EUR','USD')],[obs('anything',1,1.2,1.21),rate('USD','EUR',1),rate('EUR','USD',1),rate('EUR','EUR',1)])
        self.assertEqual(r[0]['estimate']['Rate'],n.D('0.833333333333333334'));self.assertEqual(r[1]['estimate']['Rate'],n.D('1.21'))
        self.assertFalse(r[0]['estimate']['ExecutabilityProven'])
    def test_same_value_observation_age_is_not_last_change_and_silence_holds(self):
        r=self.check([instrument('x','EUR','USD')],[obs('x',0,1,1.1),rate('USD','EUR',5000),rate('USD','EUR',5001),obs('x',5002,1,None),rate('USD','EUR',5002),obs('x',5003,None,1.1),rate('USD','EUR',5003)])
        self.assertEqual([x['status'] for x in r],['ESTIMATE','HOLD','HOLD','ESTIMATE'])
    def test_backtest_clock_uses_simulated_time_independent_of_process_speed(self):
        r=self.check([], [dict(op='clock',simulation=True,now=1,utc='2026-10-27T00:00:00Z'),
          dict(op='clock',simulation=True,now=2,utc='2026-10-27T00:01:00Z'),
          dict(op='clock',simulation=False,now=3,utc='2026-10-27T00:01:00Z')])
        self.assertEqual(r[1]['value']-r[0]['value'],60000);self.assertEqual(r[2]['value'],3)
    def test_clock_domain_invalid_inputs_do_not_default_to_wall_or_unity(self):
        r=self.check([], [dict(op='clock',simulation=True,now=1,utc='2026-10-27T00:00:00'),
          dict(op='clock',simulation=True,now=1,utc='1960-10-27T00:00:00Z'),
          dict(op='clock',simulation=False,now=-1,utc='2026-10-27T00:00:00Z')])
        self.assertTrue(all(x['status']=='HOLD' for x in r))
    def test_price_observation_lease_has_its_own_age_without_any_foreign_exchange(self):
        r=self.check([instrument('ticket','A','B')],[obs('ticket',0,100,101),
          dict(op='age',source='ticket',now=5000),dict(op='age',source='ticket',now=5001),
          obs('ticket',5002,100,None),dict(op='age',source='ticket',now=5002),
          obs('ticket',5003,None,101),dict(op='age',source='ticket',now=5003)])
        self.assertEqual([x['status'] for x in r],['LEASE','HOLD','HOLD','LEASE'])
        self.assertEqual(r[-1]['age'],1)
    def test_epoch_reset_has_no_inherited_quote(self):
        self.check([instrument('x','EUR','USD')],[obs('x',1,1,1.1),dict(op='end',source='x',now=2),rate('USD','EUR',2),dict(op='begin',source='x',now=3),obs('x',4,1,None),rate('USD','EUR',4),obs('x',5,None,1.1),rate('USD','EUR',5)])
    def test_metadata_shortest_route_selected_before_health_and_no_stale_longer_fallback(self):
        i=[instrument('direct','A','C'),instrument('ab','A','B'),instrument('bc','B','C')]
        r=self.check(i,[obs('ab',1,1,2),obs('bc',1,1,2),rate('A','C',1),obs('direct',2,1,3),rate('A','C',2)])
        self.assertEqual(r[0]['status'],'HOLD');self.assertEqual(r[1]['estimate']['Path'],[dict(Source='direct',Reverse=False)])
    def test_ambiguity_cannot_be_resolved_by_favorable_price_or_source_order(self):
        i=[instrument('x','A','B'),instrument('y','A','B')]
        for inst in (i,i[::-1]):
            r=self.check(inst,[obs('x',1,1,2),rate('A','B',1)]);self.assertEqual(r[0]['reason'],'FX_AMBIGUOUS_SHORTEST_METADATA_PATH')
    def test_unique_two_and_three_leg_paths_locked_and_crossed_book(self):
        i=[instrument('x','A','B'),instrument('y','C','B'),instrument('z','C','D')]
        a=[obs('x',1,1,1),obs('y',1,2,3),obs('z',1,4,5),rate('A','C',1),rate('A','D',1),obs('y',2,4,3),rate('A','C',2)]
        r=self.check(i,a);self.assertEqual(r[0]['estimate']['Rate'],n.D('.5'));self.assertEqual(r[1]['estimate']['Rate'],n.D('2.5'));self.assertEqual(r[2]['status'],'HOLD')
    def test_deterministic_debit_paths_and_upward_rounding_independent_arithmetic(self):
        rng=random.Random(218);i=[instrument('ab','A','B'),instrument('bc','B','C'),instrument('cd','C','D')];actions=[];t=0
        for _ in range(200):
            t+=rng.choice([1,100,6000]);src=rng.choice(i)['Source'];bid=rng.randint(1,100000)/10000
            actions.append(obs(src,t,bid,bid+rng.randint(0,100)/10000));a,b=rng.sample(['A','B','C','D'],2);actions.append(rate(a,b,t))
        self.check(i,actions)
class NativeWiring(unittest.TestCase):
    def test_actual_native_uses_shared_observed_cost_graph_and_separate_conversion_roster(self):
        b=n.ROOT/'research_core_v4/native_tick_replay_v1/csharp';s=(b/'MxmReferenceProductBot.cs').read_text()
        self.assertIn('MxmObservedCostFx.ObservationClock(IsBacktesting,Environment.TickCount64,IsBacktesting?BrokerClock():default)',s)
        self.assertNotIn('long now=Environment.TickCount64',s)
        fee=s[s.index('MxmNativeCommissionEstimate CurrentNativeCommission'):s.index('string? ReadEntryCheckpoint')]
        self.assertIn('if((kind==0 || kind==2) && terms.Commission>0m)',fee)
        self.assertIn('MxmObservedCostFx.RequireObservedBookAge(observed,instrument.Name,now)',fee)
        self.assertIn('RetainCostObservationLease(now,age)',fee)
        self.assertIn('NATIVE_FEE_TICKET_BOOK_CHANGED',fee)
        self.assertNotIn('AssetConverter.Convert(',s);self.assertIn('costFx.CostRate(from,to,now',s)
        self.assertIn('conversionNames.Contains(x.Name,StringComparer.OrdinalIgnoreCase)',s)
        self.assertIn('public string CostConversionSymbols',s);self.assertIn('MxmObservedCostFx.cs',(b/'MxmReferenceBot.csproj').read_text())
        tick=s[s.index('void OnPortfolioTick'):s.index('void ApplyPortfolioDecision')]
        self.assertLess(tick.index('.Observe(args.Bid,args.Ask'),tick.index('causalIntents.TryGetValue'))
        self.assertIn('foreach(var instrument in observedSymbols.Values)instrument.Tick+=OnPortfolioTick',s)
        self.assertIn('foreach(var instrument in observedSymbols.Values)instrument.Tick-=OnPortfolioTick',s)
        execution=s[s.index('void ApplyPortfolioDecision'):s.index('sealed record NativeRiskMark')]
        self.assertLess(execution.index('finalCostFxExpires=costFxEstimateValidUntilMs'),execution.index('double finalEquity='))
        self.assertLess(execution.index('double finalEquity='),execution.index('fxSubmissionClock>finalCostFxExpires.Value'))
        self.assertLess(execution.index('fxSubmissionClock>finalCostFxExpires.Value'),execution.index('var submissionClock=BrokerClock()'))
        self.assertLess(execution.index('var submissionClock=BrokerClock()'),execution.index('entryCheckpoint.MarkSubmitted()'))
if __name__=='__main__':unittest.main()
