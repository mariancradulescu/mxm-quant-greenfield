import unittest,math
from research_core_v4.owner_recovery_v1 import variance_kernel_v1 as k

def bars():
    out={}
    for i in range(8064):
        ts=k.n.START+i*300;o=100*math.exp(i/100000);c=o*math.exp((1+(i//144)%3)/100000)
        out[ts]={'timestamp':ts,'available_at':ts+300,'open':o,'close':c,'low':min(o,c),'high':max(o,c),'tick_volume':10}
    return out

class Tests(unittest.TestCase):
    def test_future_does_not_change_forecast(self):
        original=bars();changed={t:dict(b) for t,b in original.items()};cut=k.n.START+400*3600
        for t,b in changed.items():
            if t>=cut:
                for key in ('open','close','low','high'):b[key]*=1.03
        a=k.evaluate(original);b=k.evaluate(changed)
        keys=('clock','training_total','training_state','state','forecast_baseline_bps','forecast_state_bps','risk_second_moment_state_bps2')
        self.assertEqual([tuple(r[z] for z in keys) for r in a['trials'] if r['entry_reference']<cut],[tuple(r[z] for z in keys) for r in b['trials'] if r['entry_reference']<cut])
    def test_gaps_abstain(self):
        b=bars();t=k.n.START+200*3600;del b[t-300]
        self.assertEqual(k.feature_at(b,t),(None,'FEATURE_GAP'))
        del b[t+900];self.assertEqual(k.label_at(b,t),(None,'LABEL_GAP'))
    def test_calendar_and_nonoverlap(self):
        r=k.evaluate(bars());self.assertEqual([sum(w['reasons'].values()) for w in r['four_weeks']],[42]*4);self.assertTrue(r['trials'])
        for a,b in zip(r['trials'],r['trials'][1:]):self.assertLessEqual(a['exit_reference'],b['entry_reference'])
    def test_flat_rv_is_not_an_emission(self):
        b=bars()
        for row in b.values():row['close']=row['open'];row['low']=row['high']=row['open']
        r=k.evaluate(b);self.assertFalse(r['trials']);self.assertEqual(sum(w['reasons'].get('ZERO_RV_ABSTENTION',0) for w in r['four_weeks']),167)

if __name__=='__main__':unittest.main()
