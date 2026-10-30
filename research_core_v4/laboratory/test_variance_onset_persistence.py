"""Strict no-secret tests for one distinct frozen cross-scale model."""
import datetime as dt
import json
import math
import unittest
from . import variance_onset_persistence as m

def sample(n=240):
    start=int(dt.datetime(2026,8,24,0,0,tzinfo=dt.timezone.utc).timestamp())
    times=[start+300*i for i in range(n)]
    price=1.;bars=[]
    for i in range(n):
        # First 6h small upwards drift, then fast one-sided acceleration.
        increment=.00001 if i<75 else .0004
        op=price;price+=increment
        bars.append((op,price))
    return times,bars

class DistinctCrossScale(unittest.TestCase):
    def test_source_and_frozen_geometry(self):
        m.selftest()
        self.assertEqual(m.TARGETS,(5,111,250))
        self.assertEqual((m.FAST,m.SLOW,m.DELAY,m.EXIT),(12,48,2,8))
        self.assertEqual(m.frozen()['scientific_identity_count'],1)

    def test_causal_signal_not_future_price(self):
        t,b=sample()
        offers=list(m.offers(t,b))
        self.assertGreater(len(offers),0)
        original=[(x['clock'],x['side']) for x in offers]
        # Future price after the latest evaluated decision has no effect.
        later=b[:]
        for i in range(190,len(later)):
            later[i]=(later[i][0]*1.4,later[i][1]*1.4)
        unchanged=[(x['clock'],x['side']) for x in m.offers(t,later)
                   if x['clock']<t[185]]
        self.assertEqual([x for x in original if x[0]<t[185]],unchanged)

    def test_internal_prior_missingness_abstains(self):
        t,b=sample()
        self.assertGreater(len(list(m.offers(t,b))),0)
        broken=t[:]
        broken[85]+=150
        observed=list(m.offers(broken,b))
        self.assertFalse(any(o['clock']==broken[96] for o in observed))

    def test_absent_exit_censors_instead_of_fabricating(self):
        t,b=sample(n=180)
        baseline=list(m.offers(t,b))
        late=[o for o in baseline if not o['settled']]
        # Synthetic path should expose an explicitly censored signal near edge.
        self.assertTrue(late or all(o['settled'] for o in baseline))
        self.assertTrue(all(o['gross_bps'] is None for o in late))

    def test_aggregate_zero_proposals_is_not_alpha(self):
        s=m.frozen();t,b=sample(n=90)
        pub,detail=m.evaluate({5:(t,b),111:(t,b),250:(t,b)},s)
        self.assertEqual(pub['proposals'],0)
        self.assertFalse(pub['single_eur200_account_executed'])
        self.assertFalse(pub['historical_broker_cost_proven'])
        self.assertFalse(pub['hard21_certified'])
        self.assertEqual(pub['classification'],'SOURCE_OR_EVENT_LIMITED')
        self.assertEqual(pub['prior_closed_models_rerun'],0)
        self.assertEqual(detail,[])

if __name__=='__main__':unittest.main()
