import os,random,shutil,unittest
from . import spread_reversion_reference as n
# Monday UTC. All examples are artificial; no source market data is read here.
T=1788739200000
def book(t,b,a):return [dict(t=T+t,side='bid',raw=b),dict(t=T+t,side='ask',raw=a)]
def good_path():return book(0,100,102)+[dict(t=T+100,side='bid',raw=98)]+book(350,99,102)+book(1350,104,106)
class CompiledSpread(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required spread screen CSharp absent')
            raise unittest.SkipTest('Required compiled CSharp in CI')
    def test_long_quote_spread_both_sides_and_later_entry(self):
        r=n.run(good_path())['result'];self.assertEqual((r['Signals'],r['Complete'],r['Censored']),(1,1,0))
        e=r['Episodes'][0];self.assertEqual((e['Entry'],e['Exit']),(T+350,T+1350));self.assertEqual(e['GrossUsd'],n.D('.02'))
    def test_short_requires_ask_only_widening_and_cannot_fill_at_decision(self):
        rows=book(0,100,102)+[dict(t=T+100,side='ask',raw=104)]+book(350,100,103)+book(1350,94,96)
        e=n.run(rows)['result']['Episodes'][0];self.assertEqual((e['Direction'],e['GrossUsd']),(-1,n.D('.04')))
    def test_missing_entry_terminal_and_exit_timeout_all_retained(self):
        for rows in (good_path()[:3],good_path()[:3]+book(1200,99,102),good_path()[:-2]+book(2000,99,102)):
            r=n.run(rows)['result'];self.assertEqual((r['Signals'],r['Complete'],r['Censored']),(1,0,1))
    def test_conflicting_same_ms_never_chooses_favorable_revision(self):
        rows=good_path();rows.insert(3,dict(t=T+100,side='bid',raw=97))
        r=n.run(rows)['result'];self.assertEqual(r['Signals'],0)
    def test_bilateral_revisions_locked_decisions_and_feature_gap_do_not_signal(self):
        for rows in (book(0,100,102)+book(100,98,102),book(0,100,100)+[dict(t=T+100,side='bid',raw=98)],book(0,100,102)+[dict(t=T+1001,side='bid',raw=98)]):
            self.assertEqual(n.run(rows)['result']['Signals'],0)
    def test_unpriceable_open_path_is_counted_not_erased(self):
        rows=good_path()[:-2]+book(700,105,103)+book(1350,104,106)
        r=n.run(rows)['result'];self.assertEqual(r['Complete'],1);self.assertEqual(r['Episodes'][0]['UnmarkedGroups'],1)
        verdict,gates,_=n.decide(r);self.assertEqual(verdict,'DATA_LIMITED');self.assertFalse(gates['all_complete_paths_observed'])
    def test_fixed_holdoff_prevents_overlapping_signals_and_all_groups_hash(self):
        rows=good_path()[:-2]+[dict(t=T+500,side='bid',raw=90)]+book(1350,104,106)+[dict(t=T+1400,side='ask',raw=110)]
        self.assertEqual(n.run(rows)['result']['Signals'],1)
    def test_deterministic_full_group_decision_and_episode_parity(self):
        rng=random.Random(220);rows=[];t=0;b=100000;a=100002
        for _ in range(1000):
            t+=rng.choice([50,250,500,2000]);b+=rng.choice([-4,-2,0,2,4]);a=max(1,b+rng.choice([0,1,2,4,8]))
            rows+=book(t,b,a) if rng.randrange(3)==0 else [dict(t=T+t,side=rng.choice(['bid','ask']),raw=rng.choice([b,a]))]
        n.run(rows)
class HonestVerdict(unittest.TestCase):
    def test_positive_conditional_headroom_never_promotes_to_net_or_funded_capital(self):
        result=dict(Episodes=[],Censored=0)
        verdict,gates,_=n.decide(result);self.assertNotIn(verdict,('CONFIRMED','NET_EDGE','HARD21'));self.assertFalse(gates['at_least_100_complete'])
if __name__=='__main__':unittest.main()
