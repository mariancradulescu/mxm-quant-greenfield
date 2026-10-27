import json,os,random,shutil,subprocess,unittest
from pathlib import Path
from . import spot_source_causes as n

def event(seq,t,symbol=1,server='same',bid=100,ask=102):
    return dict(symbol=symbol,sequence=seq,arrival_ns=t*1000000,received_ms=t,
      server_ms=t if server=='same' else server,bid=bid,ask=ask)
def shape_cases():
    return [event(1,0),event(2,1000,bid=102,ask=None),event(3,2000,bid=None,ask=103),
      event(4,3000,bid=104,ask=104),event(5,4000,bid=105,ask=103),event(6,5000,bid=102,ask=103)]
class PureCauseTests(unittest.TestCase):
    def test_locked_crossed_and_partial_vs_both_fields_separated_without_admission(self):
        r=n.reference(shape_cases());c=r['causes']['1']
        self.assertEqual(c['book_shapes'],{'CROSSED':1,'LOCKED':2,'POSITIVE':3})
        self.assertEqual(c['locked_with_both_fields'],1);self.assertEqual(c['crossed_with_both_fields'],1)
        self.assertEqual(r['profile']['1']['unavailable'],4)
        self.assertFalse(r['original_consumer_policy_changed']);self.assertFalse(r['economic_model_executed'])
    def test_observation_silence_does_not_become_an_invalid_received_price(self):
        r=n.reference([event(1,0,250),event(2,1000,250),event(3,600000,250)])
        c=r['causes']['250'];p=r['profile']['250']
        self.assertEqual((c['gaps_over_5s'],c['healthy_to_healthy_gap_breaks']),(1,1))
        self.assertEqual((p['healthy'],p['unavailable'],p['stretches']),(2,1,2))
        self.assertEqual(p['stretches_at_least_5min'],0)
    def test_initial_missing_clock_and_no_price_never_promote_freshness(self):
        r=n.reference([event(1,0),event(2,1000,server=None),event(3,2000,bid=None,ask=None)])
        self.assertEqual(r['profile']['1']['healthy'],0)
        self.assertEqual(r['causes']['1']['server_clock_failures'],1)
    def test_native_product_wires_geometry_with_separate_source_policy(self):
        base=n.ROOT/'research_core_v4/native_tick_replay_v1/csharp'
        bot=(base/'MxmReferenceProductBot.cs').read_text()
        ticks=bot[bot.index('void OnPortfolioTick'):bot.index('void ApplyPortfolioDecision')]
        self.assertIn('MxmBookShape.NonCrossed(MxmBookShape.ClassifyNative(args.Bid,args.Ask))',ticks)
        self.assertIn('Compile Include="MxmBookShape.cs"',(base/'MxmReferenceBot.csproj').read_text())
        self.assertIn('MxmBookShape.StrictlyPositive(shape)',(n.ROOT/'research_core_v4/laboratory/csharp/spot_source/MxmSpotSourceProfile.cs').read_text())

class CompiledCauseParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required CSharp parity runtime unavailable')
            raise unittest.SkipTest('Compiled CSharp tests required in CI')
    def test_actual_shared_native_predicate_preserves_all_old_cases(self):
        p=subprocess.run(['dotnet','run','--project',str(n.ROOT/n.PROJECT),'-c','Release','--no-build','--','--self-test'],check=True,capture_output=True,text=True)
        r=json.loads(p.stdout);self.assertEqual(r['checks'],106)
        self.assertTrue(r['native_predicate_preserved']);self.assertTrue(r['caller_policy_unchanged'])
    def test_explicit_book_shapes_and_gap_vs_invalid_event_are_reconciled(self):
        for events in (shape_cases(),[event(1,0,250),event(2,1000,250),event(3,600000,250)]):
            r=n.run(events);self.assertEqual(r,n.reference(events))
    def test_exact_span_boundary_and_all_instruments_including_no_events(self):
        events=[event(i+1,i*3000) for i in range(102)]
        r=n.run(events);self.assertEqual(r['profile']['1']['stretches_at_least_5min'],1)
        self.assertEqual(r['profile']['250']['events'],0)
    def test_clock_and_field_presence_fuzz_every_disposition_not_just_totals(self):
        rng=random.Random(617);t=0;events=[]
        for i in range(1000):
            t+=rng.choice([10,100,500,10000]);s=rng.choice([1,2,250])
            bid=rng.choice([None,0,99,100,101]);ask=rng.choice([None,0,99,100,102])
            stamp=rng.choice([None,t,t+1,t-1000,t-6000])
            events.append(event(i+1,t,s,stamp,bid,ask))
        self.assertEqual(n.run(events),n.reference(events))
if __name__=='__main__':unittest.main()
