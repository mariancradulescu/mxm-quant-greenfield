"""No-key controls for entire broker-index/M5 source-based shared portfolio."""
import datetime as dt
import unittest
from . import broad_shared_breadth_response as m

class BroadSharedResearch(unittest.TestCase):
    def test_fixed_authentic_crosswalk(self):
        p,latest=m.panel()
        self.assertEqual(len(p),1575)
        self.assertNotIn(515,p)
        self.assertGreater(len({r['group'] for r in p.values()}),15)
        self.assertEqual(latest['current_counts']['current_new_entry_accessible'],1689)
        self.assertEqual(m.frozen()['closed_candidates_rerun'],0)

    def test_exact_causal_choice_no_future_leak(self):
        t=int(dt.datetime(2026,8,24,tzinfo=dt.timezone.utc).timestamp())
        rows=[(t,'US Equities',i,20.,-5.) for i in range(1,26)]
        rows[0]=(t,'US Equities',1,1.,-123.)
        c=m.choice(rows)
        self.assertEqual(c['ordinal'],1)
        self.assertEqual(c['side'],1)
        self.assertEqual(c['n_cohort'],25)
        changed=[(t,g,o,r,1000000. if o%2 else -1000000.) for t,g,o,r,y in rows]
        self.assertEqual(m.choice(changed)['ordinal'],1)

    def test_missing_future_does_not_enable_lucky_reselection(self):
        t=int(dt.datetime(2026,8,24,tzinfo=dt.timezone.utc).timestamp())
        rows=[(t,'US Equities',i,20.,12.) for i in range(1,26)]
        rows[0]=(t,'US Equities',1,1.,None)
        c=m.choice(rows)
        self.assertEqual(c['ordinal'],1)
        self.assertIsNone(c['unobserved_future_bps'])

    def test_insufficient_market_cohort_abstains(self):
        t=int(dt.datetime(2026,8,24,tzinfo=dt.timezone.utc).timestamp())
        rows=[(t,'US Equities',i,50.,3.) for i in range(1,15)]
        self.assertIsNone(m.choice(rows))
        rows += [(t,'US Equities',i,50.,3.) for i in range(15,25)]
        # Market can move, but nobody has lagged -> abstain.
        self.assertIsNone(m.choice(rows))

    def test_no_synthetic_week_account_or_fills(self):
        ts=int(dt.datetime(2026,8,24,tzinfo=dt.timezone.utc).timestamp())
        rows=[]
        for h in range(5):
            t=ts+3600*h
            rows.extend((t,'US Equities',i,30.,15.) for i in range(1,26))
            rows[-25]=(t,'US Equities',1,1.,15.)
        public,detail=m.aggregate(rows,3355389,100,1576)
        self.assertEqual(public['settled'],5)
        self.assertEqual(public['programme_proposals'],5)
        self.assertEqual(public['hypothetical_net_bps_sums']['10'],25.)
        self.assertFalse(public['eur200_funded_and_min_volume_verified'])
        self.assertFalse(public['hard21_executed_entries_certified'])
        self.assertEqual(len(detail),5)

    def test_module_entry_selftest(self):
        m.selftest()

if __name__=='__main__':unittest.main()
