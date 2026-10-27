"""Compiled production lease versus independent state/expiry oracle. Artificial only."""
import json,os,random,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'research_core_v4/laboratory/csharp/risk_observation/MxmRiskObservation.csproj'
def observe(s,t,b=1,a=2):return dict(op='observe',source=s,now=t,bid=b,ask=a)
def capture(t,*quotes):return dict(op='capture',now=t,quotes=[dict(source=s,bid=b,ask=a) for s,b,a in quotes])
def verify(t):return dict(op='verify',now=t)
def oracle(data):
    books={s:dict(epoch=1,open=True,last=0,fault=False,bid=None,ask=None,bt=None,at=None) for s in data['sources']};lease=None;out=[]
    def touch(b,t):
        if b['fault'] or t<0 or t<b['last']:
            b.update(fault=True,open=False);raise ValueError()
        b['last']=t
    def read(s,t):
        if s not in books:raise ValueError()
        b=books[s];touch(b,t)
        if not b['open'] or b['bid'] is None or b['ask'] is None or b['bid']<=0 or b['ask']<b['bid'] or min(b['bt'],b['at'])<t-5000:raise ValueError()
        return b
    for a in data['actions']:
        t=a['now'];op=a['op']
        try:
            if op in ('observe','begin','end','down'):
                b=books[a['source']];touch(b,t)
                if op=='observe':
                    if not b['open']:raise ValueError()
                    for side,stamp in (('bid','bt'),('ask','at')):
                        if a[side] is not None:b[side]=a[side];b[stamp]=t
                else:
                    b.update(open=op=='begin',bid=None,ask=None,bt=None,at=None)
                    if op=='begin':b['epoch']+=1
            elif op=='capture':
                lease=None;qs=a['quotes']
                if not qs or len(qs)>33 or t<0:raise ValueError()
                snap={};expiry=2**63-1
                for q in qs:
                    s=q['source']
                    if not s.strip() or len(s)>128:raise ValueError()
                    if s in snap:
                        if (q['bid'],q['ask'])!=(snap[s]['bid'],snap[s]['ask']):raise ValueError()
                        continue
                    b=read(s,t)
                    if (q['bid'],q['ask'])!=(b['bid'],b['ask']):raise ValueError()
                    snap[s]=dict(b);expiry=min(expiry,min(b['bt'],b['at'])+5000)
                lease=(t,expiry,snap);out.append(dict(status='CAPTURED',expiry=expiry,sources=len(snap)))
            else:
                if lease is None or not lease[0]<=t<=lease[1]:raise ValueError()
                for s,p in lease[2].items():
                    b=read(s,t)
                    if b['epoch']!=p['epoch'] or (b['bid'],b['ask'])!=(p['bid'],p['ask']) or b['bt']<p['bt'] or b['at']<p['at']:raise ValueError()
                out.append(dict(status='VERIFIED'))
        except ValueError:out.append(dict(status='HOLD'))
    return out
class CompiledRiskObservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required compiled risk observation unavailable')
            raise unittest.SkipTest('Compiled production lease required in CI')
    def check(self,actions,sources=('ticket','owned')):
        data=dict(sources=sources,actions=actions)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'in.json').write_text(json.dumps(data))
            subprocess.run(['dotnet','run','--no-build','-c','Release','--project',str(PROJECT),'--',str(p/'in.json'),str(p/'out.json')],check=True,capture_output=True,text=True)
            actual=json.loads((p/'out.json').read_text());self.assertEqual(actual,oracle(data));return actual
    def test_all_sources_include_oldest_existing_mark_and_inclusive_boundary(self):
        out=self.check([observe('owned',0),observe('ticket',4000),capture(4000,('ticket',1,2),('owned',1,2)),verify(5000),verify(5001)])
        self.assertEqual(out,[dict(status='CAPTURED',expiry=5000,sources=2),dict(status='VERIFIED'),dict(status='HOLD')])
    def test_equal_price_refresh_does_not_extend_admission(self):
        out=self.check([observe('ticket',0),capture(1,('ticket',1,2)),observe('ticket',4999),verify(5001)])
        self.assertEqual(out[-1]['status'],'HOLD')
    def test_new_epoch_cannot_reuse_previous_lease_even_same_timestamp_and_price(self):
        out=self.check([observe('ticket',0),capture(0,('ticket',1,2)),dict(op='begin',source='ticket',now=0),observe('ticket',0),verify(0)])
        self.assertEqual(out[-1]['status'],'HOLD')
    def test_missing_owned_or_native_price_mismatch_never_uses_ticket_only(self):
        out=self.check([observe('ticket',0),capture(0,('ticket',1,2),('owned',1,2)),capture(0,('ticket',2,3))])
        self.assertTrue(all(x['status']=='HOLD' for x in out))
    def test_changed_mark_and_transport_down_hold(self):
        self.check([observe('ticket',0),capture(0,('ticket',1,2)),observe('ticket',1,1,3),verify(1),dict(op='down',source='ticket',now=2),verify(2)])
    def test_partial_fields_preserve_oldest_side_lifetime(self):
        out=self.check([observe('ticket',0),observe('ticket',4000,1,None),capture(4000,('ticket',1,2)),verify(5001)])
        self.assertEqual(out[0]['expiry'],5000)
    def test_duplicate_sources_deduplicate_but_conflicts_and_empty_roster_hold(self):
        self.check([observe('ticket',0),capture(0,('ticket',1,2),('ticket',1,2)),capture(0,('ticket',1,2),('ticket',2,3)),capture(0)])
    def test_clock_regression_and_closed_epoch_hold(self):
        self.check([observe('ticket',10),capture(10,('ticket',1,2)),verify(9),dict(op='end',source='ticket',now=11),verify(12)])
    def test_locked_book_is_descriptive_not_execution_or_zero_cost_proof(self):
        out=self.check([observe('ticket',0,1,1),capture(0,('ticket',1,1)),verify(0)])
        self.assertEqual(out[-1]['status'],'VERIFIED')
    def test_independent_deterministic_multi_source_state_paths(self):
        rng=random.Random(222);actions=[];t=0
        for _ in range(500):
            t+=rng.choice((0,1,10,5001));s=rng.choice(('ticket','owned'));op=rng.randrange(6)
            if op<2:actions.append(observe(s,t,rng.choice((1,2,None)),rng.choice((2,3,None))))
            elif op==2:actions.append(capture(t,('ticket',1,2),('owned',1,2)))
            elif op==3:actions.append(verify(t))
            else:actions.append(dict(op='begin' if op==4 else 'end',source=s,now=t))
        self.check(actions)
class NativeIntegration(unittest.TestCase):
    def test_actual_order_path_uses_complete_mark_lease_after_risk_before_checkpoint_submission(self):
        s=(ROOT/'research_core_v4/native_tick_replay_v1/csharp/MxmReferenceProductBot.cs').read_text()
        path=s[s.index('void ApplyPortfolioDecision'):s.index('sealed record NativeRiskMark')]
        self.assertLess(path.index('riskObservationLease=CaptureRiskObservationLease'),path.index('double newStopRisk='))
        self.assertLess(path.index('double finalNewStopRisk='),path.index('riskObservationLease.Verify('))
        self.assertLess(path.index('riskObservationLease.Verify('),path.index('entryCheckpoint.MarkSubmitted()'))
        self.assertIn('fxSubmissionClock>riskObservationLease.ExpiresAtMs',path)
        self.assertIn('sizingObservationLease.Verify(ObservationClockMs(),ReadNativeRiskObservation)',s)
        self.assertIn('owned.Select(x=>new MxmNativeRiskQuote',s)
        self.assertIn('RISK_OBSERVATION_NATIVE_SOURCE_MISMATCH',s)
if __name__=='__main__':unittest.main()
