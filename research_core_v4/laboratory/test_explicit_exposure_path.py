"""Compiled real account, independent event/side-clock oracle; artificial only."""
import json,os,random,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'research_core_v4/laboratory/csharp/exposure_path/MxmExposurePath.csproj'
def q(t,s='A',**kw):return dict(op='quote',t=t,s=s,**kw)
def d(t,seq=1,direction=1,s='A'):return dict(op='decision',t=t,seq=seq,d=direction,s=s)
def opened():return [q(0),d(1),q(2)]
def oracle(case):
    marks={};quote_times={};pending={};sequences={};blocked={};positions={};entries=exits=0;last=None;fault=False;fx=None;out=[]
    cap=min(5000,case.get('maxAge',300)*1000);shared=case.get('shared',False)
    def valid(mark,t,limit):return mark is not None and all(0<=t-v<=limit for v in mark)
    def exposure(t):return all(valid(marks.get(s),t,cap) for s in positions) and (not shared or valid(fx,t,5000))
    for a in case['actions']:
        op=a['op'];t=a['t'];s=a.get('s',case['symbols'][0]);restore=op=='restore-aged'
        try:
            if fault:raise ValueError()
            if restore:
                if positions and not exposure(t):raise ValueError()
                last=t
            elif op not in ('cold','report'):
                if t<0 or last is not None and t<last or positions and not exposure(t):raise ValueError()
                last=t
                if op=='fx':
                    if not shared:raise ValueError()
                    fx=(a.get('bt',t),a.get('at',t))
                    if not valid(fx,t,5000) or max(fx)!=t:raise ValueError()
                elif op=='decision':
                    if a['seq']!=sequences.get(s,0)+1:raise ValueError()
                    sequences[s]=a['seq']
                    pending[s]=(t,t+1,t+min(4000,case.get('maxAge',300)*1000),a['d']) if t>blocked.get(s,-1) else None
                elif op=='missing':
                    pending[s]=None;blocked[s]=t
                    if s in positions:raise ValueError()
                elif op=='quote':
                    if s in quote_times and t<=quote_times[s]:raise ValueError()
                    quote_times[s]=t
                    side=(a.get('bt',t),a.get('at',t))
                    if not valid(side,t,cap) or shared and (not valid(fx,t,5000) or max(fx)>=t):raise ValueError()
                    marks[s]=side;p=pending.get(s)
                    if p is not None:
                        if t>=p[2]:pending[s]=None
                        elif t>=p[1] and t>p[0]:
                            pending[s]=None;desired=p[3]
                            if s in positions and desired!=positions[s]:del positions[s];exits+=1
                            if desired and s not in positions:positions[s]=desired;entries+=1
                else:raise ValueError()
            if positions and not exposure(last):raise ValueError()
            out.append(dict(status='OK',entries=entries,exits=exits,open=len(positions),funding=200,hard21=False,broker_fills=False))
        except ValueError:
            if not restore:fault=True
            out.append(dict(status='HOLD',report_blocked=fault))
    return out
class ExposurePathCompiled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required compiled exposure path unavailable')
            raise unittest.SkipTest('Real CSharp account required in CI')
    def check(self,actions,symbols=('A',),**kw):
        cases=[dict(symbols=list(symbols),actions=actions,**kw)]
        return self.batch(cases)[0]
    def batch(self,cases):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'in.json').write_text(json.dumps(cases))
            subprocess.run(['dotnet','run','--no-build','-c','Release','--project',str(PROJECT),'--',str(p/'in.json'),str(p/'out.json')],check=True,capture_output=True)
            out=json.loads((p/'out.json').read_bytes());self.assertEqual(out,[oracle(c) for c in cases]);return out
    def test_new_fresh_same_symbol_quote_cannot_heal_unobserved_open_interval(self):
        out=self.check(opened()+[q(5003),dict(op='report',t=5003)])
        self.assertEqual(out[-2:],2*[dict(status='HOLD',report_blocked=True)])
    def test_inclusive_expiry_boundary_and_one_millisecond_over(self):
        self.assertEqual(self.check(opened()+[q(5002)])[-1]['status'],'OK')
        self.assertEqual(self.check(opened()+[q(5003)])[-1]['status'],'HOLD')
    def test_zero_signal_or_exit_quote_cannot_silently_liquidate_unknown_interval(self):
        out=self.check(opened()+[d(3000,2,0),q(5003)])
        self.assertEqual(out[-1]['status'],'HOLD')
    def test_every_owned_mark_checked_before_other_symbol_decision_or_quote(self):
        for event in (d(5003,s='B'),q(5003,s='B')):
            self.assertEqual(self.check(opened()+[event],symbols=('A','B'))[-1]['status'],'HOLD')
    def test_one_old_source_side_determines_lifetime_even_after_partial_refresh(self):
        actions=[q(0),d(1),q(2,bt=0),q(5001)]
        self.assertEqual(self.check(actions)[-1]['status'],'HOLD')
    def test_parameter_age_stricter_than_five_seconds_is_preserved(self):
        self.assertEqual(self.check(opened()+[q(1002)],maxAge=1)[-1]['status'],'OK')
        self.assertEqual(self.check(opened()+[q(1003)],maxAge=1)[-1]['status'],'HOLD')
    def test_fx_refresh_cannot_hide_overdue_conversion_while_position_marks_are_fresh(self):
        a=[dict(op='fx',t=0),q(1,'GBPUSD'),d(2,s='GBPUSD'),q(3,'GBPUSD'),dict(op='fx',t=5001)]
        self.assertEqual(self.check(a,symbols=('GBPUSD',),shared=True)[-1]['status'],'HOLD')
    def test_restart_preserves_original_deadline_and_does_not_reset_capital(self):
        for suffix in ([dict(op='cold',t=2),q(5003)],[dict(op='cold',t=2),q(5002),dict(op='cold',t=5002),q(10002)]):
            out=self.check(opened()+suffix)
            self.assertEqual(out[-1]['status'],'HOLD' if suffix[1]['t']==5003 else 'OK')
    def test_recomputed_checksum_does_not_approve_stale_open_checkpoint(self):
        out=self.check(opened()+[dict(op='restore-aged',t=5003)])
        self.assertEqual(out[-1],dict(status='HOLD',report_blocked=False))
    def test_flat_gap_can_rewarm_without_fictitious_open_exposure_or_second_funding(self):
        out=self.check([q(0),q(10000),d(10001),q(10002),d(10003,2,0),q(10004),dict(op='cold',t=10004),q(20000)])
        self.assertEqual((out[-1]['entries'],out[-1]['exits'],out[-1]['open'],out[-1]['funding']),(1,1,0,200))
    def test_deterministic_boundary_and_cold_restore_paths_against_independent_oracle(self):
        rng=random.Random(225);cases=[]
        for _ in range(120):
            t=2;actions=opened()
            for _ in range(8):
                if rng.randrange(3)==0:actions.append(dict(op='cold',t=t))
                t+=rng.choice((0,1,999,1000,4999,5000,5001,7000));actions.append(q(t))
            cases.append(dict(symbols=['A'],actions=actions))
        self.batch(cases)
class Wiring(unittest.TestCase):
    def test_check_runs_before_feed_clock_and_every_event_dispatch(self):
        p=(ROOT/'research_core_v4/native_tick_replay_v1/csharp/MxmPortfolioAccountReplay.cs').read_text()
        loop=p[p.index('foreach(var e in feed)'):]
        self.assertLess(loop.index('ValidateOpenValuationAt(e.Utc)'),loop.index('lastFeed=e.Utc'))
        self.assertLess(loop.index('ValidateOpenValuationAt(e.Utc)'),loop.index('ApplyFx(fx)'))
        self.assertLess(loop.index('ValidateOpenValuationAt(e.Utc)'),loop.index('st.Latest=quote'))
if __name__=='__main__':unittest.main()
