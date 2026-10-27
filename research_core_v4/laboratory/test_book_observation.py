"""Independent artificial state oracle, compiled shared native component, no market data."""
import json,os,random,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'research_core_v4/laboratory/csharp/book_observation/MxmBookObservation.csproj'
def obs(t,bid=100,ask=102,server=None,utc=None):
    return dict(op='observe',now=t,bid=bid,ask=ask,server=server,utc=t if utc is None else utc)
def reference(actions,origin='raw'):
    epoch=events=bf=af=bc=ac=0;active=False;transport='Unknown';last=-1
    bid=ask=bo=ao=bch=ach=bs=ass=event=utc=None;result=[]
    for a in actions:
        t=a['now'];assert t>=last and t>=0;last=t
        if a['op'] in ('begin','end') or a['op']=='transport' and a['status']=='Down':
            bid=ask=bo=ao=bch=ach=bs=ass=event=utc=None
            active=a['op']=='begin'
            if active:epoch+=1
            transport=a['status'] if a['op']=='transport' else 'Unknown'
        elif a['op']=='transport':transport=a['status']
        elif a['op']=='observe':
            assert active
            assert origin!='native' or a['bid'] is not None and a['ask'] is not None
            events+=1;event=t;utc=a['utc']
            if a['bid'] is not None:
                bf+=1
                if bid is not None and bid!=a['bid']:bc+=1;bch=t
                bid=a['bid'];bo=t;bs=a['server']
            if a['ask'] is not None:
                af+=1
                if ask is not None and ask!=a['ask']:ac+=1;ach=t
                ask=a['ask'];ao=t;ass=a['server']
        elif a['op']!='view':raise AssertionError(a)
        shape='Missing' if bid is None or ask is None else 'Invalid' if bid<=0 or ask<=0 else 'Crossed' if bid>ask else 'Locked' if bid==ask else 'Positive'
        age=lambda v:None if v is None else t-v
        result.append(dict(Epoch=epoch,SessionOpen=active,Faulted=False,Origin='RawPartialFields' if origin=='raw' else 'NativeCallbackSnapshot',ReportedTransport=transport,Shape=shape,Events=events,BidFields=bf,AskFields=af,BidChanges=bc,AskChanges=ac,LastEventMs=event,BidObservedMs=bo,AskObservedMs=ao,BidChangedMs=bch,AskChangedMs=ach,BidServerMs=bs,AskServerMs=ass,LastReceivedUtcMs=utc,EventAgeMs=age(event),BidAgeMs=age(bo),AskAgeMs=age(ao),ExecutabilityProven=False,ContinuousObservationProven=False))
    return result

def run(actions,origin='raw',success=True):
    with tempfile.TemporaryDirectory() as d:
        inp=Path(d)/'input.json';out=Path(d)/'output.json';inp.write_text(json.dumps(dict(origin=origin,actions=actions)))
        p=subprocess.run(['dotnet','run','--project',str(PROJECT),'-c','Release','--no-build','--',str(inp),str(out)],capture_output=True,text=True)
        if not success:
            if p.returncode==0 or out.exists():raise AssertionError('Invalid state accepted')
            return
        if p.returncode:raise AssertionError(p.stderr)
        return json.loads(out.read_text())
class CompiledObservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required CSharp observation runtime absent')
            raise unittest.SkipTest('Compiled observation required in CI')
    def check(self,a,origin='raw'):
        actual=run(a,origin);self.assertEqual(actual,reference(a,origin));return actual
    def test_partial_same_price_empty_message_and_silence_keep_distinct_clocks(self):
        a=[dict(op='begin',now=0),obs(1),obs(2,100,None),obs(3,None,None),dict(op='view',now=900000),obs(900001,None,103)]
        v=self.check(a)
        self.assertEqual((v[3]['LastEventMs'],v[3]['BidObservedMs'],v[3]['AskObservedMs']),(3,2,1))
        self.assertEqual((v[4]['Shape'],v[4]['BidAgeMs'],v[4]['BidChangedMs']),('Positive',899998,None))
        self.assertEqual(v[-1]['AskChangedMs'],900001)
        self.assertFalse(v[-1]['ExecutabilityProven']);self.assertFalse(v[-1]['ContinuousObservationProven'])
    def test_native_snapshots_are_not_raw_field_or_change_observations(self):
        v=self.check([dict(op='begin',now=0),obs(1),obs(2),obs(3,101,102),dict(op='view',now=900000)],'native')
        self.assertEqual((v[2]['BidObservedMs'],v[2]['BidChangedMs'],v[2]['ReportedTransport']),(2,None,'Unknown'))
        self.assertEqual(v[3]['BidChangedMs'],3)
        run([dict(op='begin',now=0),obs(1,100,None)],'native',False)
    def test_disconnect_restart_and_reported_up_never_resurrect_carried_book(self):
        a=[dict(op='begin',now=0),obs(1),dict(op='transport',now=2,status='Down'),dict(op='transport',now=3,status='Up'),dict(op='begin',now=4),obs(5,None,102),dict(op='end',now=6)]
        v=self.check(a);self.assertFalse(v[3]['SessionOpen']);self.assertEqual(v[3]['Shape'],'Missing')
        self.assertEqual((v[4]['Epoch'],v[4]['ReportedTransport']),(2,'Unknown'))
        self.assertEqual(v[5]['Shape'],'Missing');self.assertIsNone(v[5]['AskChangedMs'])
        run(a[:4]+[obs(4)],success=False)
    def test_monotonic_failure_and_closed_epoch_are_not_silently_recovered(self):
        for a in ([obs(1)],[dict(op='begin',now=-1)],[dict(op='begin',now=1),obs(0)],
          [dict(op='begin',now=0),dict(op='view',now=100),obs(99)]):run(a,success=False)
    def test_geometry_and_independent_wall_and_server_clocks_are_descriptive(self):
        a=[dict(op='begin',now=0),obs(0,100,None,server=1000),obs(0,None,100,server=999,utc=-5),obs(1,101,None),obs(2,0,None),obs(3,100,102)]
        v=self.check(a);self.assertEqual([x['Shape'] for x in v],['Missing','Missing','Locked','Crossed','Invalid','Positive'])
        self.assertEqual((v[2]['LastReceivedUtcMs'],v[2]['BidServerMs'],v[2]['AskServerMs']),(-5,1000,999))
    def test_exact_raw_integer_prices_are_not_rounded_through_double(self):
        v=self.check([dict(op='begin',now=0),obs(1,9007199254740992,9007199254740993),obs(2,9007199254740993,9007199254740993)])
        self.assertEqual((v[1]['Shape'],v[2]['Shape']),('Positive','Locked'))
    def test_deterministic_state_machine_all_views_reconciled(self):
        for origin in ('raw','native'):
            rng=random.Random(215);a=[dict(op='begin',now=0)];t=0
            for i in range(1000):
                t+=rng.choice([0,1,1000,100000]);op=rng.randrange(10)
                if op==0:a.extend([dict(op='transport',now=t,status='Down'),dict(op='transport',now=t,status='Up'),dict(op='begin',now=t)])
                elif op==1:a.append(dict(op='view',now=t))
                else:
                    values=[0,99,100,101] if origin=='native' else [None,0,99,100,101]
                    a.append(obs(t,rng.choice(values),rng.choice(values),rng.choice([None,t,t-100]),rng.choice([t,t-1,-1])))
            self.check(a,origin)
class Wiring(unittest.TestCase):
    def test_actual_native_callback_uses_snapshot_origin_and_does_not_invent_source_timestamp(self):
        b=ROOT/'research_core_v4/native_tick_replay_v1/csharp';s=(b/'MxmReferenceProductBot.cs').read_text()
        self.assertIn('MxmBookObservations.NativeSnapshots()',s)
        tick=s[s.index('void OnPortfolioTick'):s.index('void ApplyPortfolioDecision')]
        self.assertIn('DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),null)',tick)
        self.assertNotIn('ReportTransport(',s)
        self.assertLess(tick.index('.Observe(args.Bid,args.Ask'),tick.index('queue.TryConsume'))
        self.assertIn('MxmBookShape.NonCrossed(MxmBookShape.ClassifyNative(args.Bid,args.Ask))',tick)
        self.assertIn('Compile Include="MxmBookObservation.cs"',(b/'MxmReferenceBot.csproj').read_text())
if __name__=='__main__':unittest.main()
