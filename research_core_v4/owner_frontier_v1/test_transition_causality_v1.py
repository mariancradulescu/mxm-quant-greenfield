import math,unittest
from research_core_v4.owner_frontier_v1 import transition_kernel_v1 as k

def bars():
    out={}
    for i in range(8064):
        ts=k.n.START+i*300;o=100*math.exp(i/100000);c=100*math.exp((i+1)/100000)
        out[ts]={'timestamp':ts,'available_at':ts+300,'open':o,'close':c,'low':o,'high':c,'tick_volume':10}
    return out

class Causality(unittest.TestCase):
    def test_single_state_has_no_incremental_information(self):
        out=k.evaluate(bars());trials=[r for r in out['trials'] if r['support']=='SUPPORTED'];self.assertTrue(trials)
        for r in trials:self.assertAlmostEqual(r['forecast_baseline_bps'],r['forecast_state_bps'],places=10)
    def test_future_change_does_not_change_prior_forecasts(self):
        original=bars();changed={t:dict(b) for t,b in original.items()};cut=k.n.START+400*3600
        for t,b in changed.items():
            if t>=cut:
                for key in ('open','high','low','close'):b[key]*=1.03
        a=k.evaluate(original);b=k.evaluate(changed)
        aa=[(r['clock'],r['forecast_state_bps'],r['training_total']) for r in a['trials'] if r['entry_reference']<cut]
        bb=[(r['clock'],r['forecast_state_bps'],r['training_total']) for r in b['trials'] if r['entry_reference']<cut]
        self.assertEqual(aa,bb)
    def test_gap_is_not_a_flat_label_or_fabricated_quote(self):
        bs=bars();t=k.n.START+200*3600;del bs[t+900]
        value,reason=k.label_at(bs,t);self.assertIsNone(value);self.assertEqual(reason,'LABEL_GAP')
    def test_calendar_and_nonoverlap(self):
        out=k.evaluate(bars());self.assertEqual([sum(m['reasons'].values()) for m in out['four_weeks']],[42]*4)
        for a,b in zip(out['trials'],out['trials'][1:]):self.assertLessEqual(a['exit_reference'],b['entry_reference'])

if __name__=='__main__':unittest.main()
