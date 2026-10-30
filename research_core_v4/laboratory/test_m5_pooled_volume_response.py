"""No-secret synthetic scientific contract; no Pepperstone source or broker."""
import datetime as dt
import json
import math
from pathlib import Path
import tempfile
import unittest
from . import m5_pooled_volume_response as v


def fake(n=200,start="2026-09-03T00:00:00+00:00"):
    t=int(dt.datetime.fromisoformat(start).timestamp())
    stamps=[t+300*i for i in range(n)]
    bars=[]
    for i in range(n):
        price=1.0+.0001*i+.00004*math.sin(i/4)
        bars.append((price,price+.00015,price-.00015,
                     price+.00003*math.sin(i/7),30+i%17))
    return stamps,bars


class OnePooledModel(unittest.TestCase):
    def test_precommitted_selftest(self):
        v.selftest()

    def test_features_dont_depend_on_future_bars_or_outcomes(self):
        stamps,bars=fake()
        before=v.features(stamps,bars,55)
        alt=bars[:]
        for i in range(56,len(alt)):
            op,hi,lo,cl,vol=alt[i]
            alt[i]=(op+1,hi+1,lo+1,cl+1,vol+100)
        self.assertEqual(before,v.features(stamps,alt,55))

    def test_volume_sensitivity_and_missing_internal_bar(self):
        t,b=fake()
        a=v.features(t,b,55)
        modified=b[:]
        op,hi,lo,cl,vol=modified[55]
        modified[55]=(op,hi,lo,cl,vol*100)
        self.assertNotEqual(a,v.features(t,modified,55))
        gap=t[:];gap[40]+=600
        self.assertIsNone(v.features(gap,b,55))

    def test_delayed_entry_and_right_censor(self):
        t,b=fake(n=60)
        rows=list(v.evaluation_rows(t,b))
        self.assertTrue(rows)
        self.assertEqual(rows[0]['time'],t[25])
        self.assertTrue(any(not z['settlement_observed'] for z in rows))
        p=next(x for x in rows if x['settlement_observed'])
        self.assertAlmostEqual(p['gross'],10000*
                (b[(p['time']-t[0])//300+8][0]/
                 b[(p['time']-t[0])//300+2][0]-1))
        self.assertEqual(v.ENTRY_DELAY,2)
        self.assertEqual(v.EXIT_BARS,8)

    def test_train_does_not_overlap_evaluation(self):
        t,b=fake(n=300,start="2026-09-02T00:00:00+00:00")
        training=list(v.training_rows(t,b))
        self.assertTrue(training)
        self.assertTrue(all(len(x)==v.DIM and math.isfinite(y) for x,y in training))
        evals=list(v.evaluation_rows(t,b))
        self.assertTrue(evals)
        self.assertTrue(all(r['time']>=int(dt.datetime(2026,9,3,tzinfo=dt.timezone.utc).timestamp()) for r in evals))

    def test_no_signals_cannot_be_faked_into_portfolio(self):
        t,b=fake(n=200)
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'sample'
            with out.open('w') as f:
                for row in v.evaluation_rows(t,b):
                    row['ordinal']=1
                    f.write(json.dumps(row)+'\n')
            old=v.MIN_EVAL
            try:
                v.MIN_EVAL=10
                details=v.aggregate(([0.]*v.DIM,{'mean_y':0.,'examples':1}),out)
            finally:
                v.MIN_EVAL=old
            self.assertEqual(details['causal_proposals'],0)
            self.assertEqual(details['settled'],0)
            self.assertEqual(details['hypothetical_net_bps_sums']['10.0'],0)
            self.assertFalse(details['eur200_account_executed'])

    def test_authentic_source_has_no_unpermitted_entrypoint(self):
        self.assertEqual(v.FROZEN_ID,'V4-M5-OHLCV-POOLED-RESPONSE-20261030-V1')
        self.assertEqual((v.MIN_TRAIN,v.MIN_EVAL),(5000,5000))
        self.assertEqual(v.COST_STRESS,(10.,20.))


if __name__=='__main__':unittest.main()
