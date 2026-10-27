import unittest
from .spot_observation_profile import SpotProfile
class ReceiptSourceTests(unittest.TestCase):
    def event(self,p,n,*,t=None,server=None,bid=100,ask=102,symbol=1):
        t=n*3000 if t is None else t
        p.observe(symbol=symbol,sequence=n+1,arrival_ns=t*1_000_000,received_ms=t,
          server_ms=t if server is None else server,bid=bid,ask=ask)
    def test_initial_snapshot_even_two_sided_is_not_new_quote_proof(self):
        p=SpotProfile([1]);self.event(p,0);self.event(p,1,bid=100,ask=None)
        self.assertEqual(p.result()['1']['healthy'],0)
    def test_independent_sides_then_exact_five_minute_observed_span(self):
        p=SpotProfile([1]);self.event(p,0)
        for n in range(1,102):self.event(p,n)
        r=p.result()['1'];self.assertEqual((r['events'],r['healthy'],r['unavailable']),(102,101,1))
        self.assertEqual(r['stretches_at_least_5min'],1);self.assertFalse(r['between_receipt_liquidity_proven'])
    def test_no_interpolation_across_silence_or_tail(self):
        p=SpotProfile([1]);self.event(p,0);self.event(p,1);self.event(p,2,t=600000)
        r=p.result()['1'];self.assertEqual(r['stretches'],2);self.assertEqual(r['stretches_at_least_5min'],0)
    def test_crossed_locked_zero_future_and_stale_retained(self):
        for kw in ({'bid':103},{'ask':100},{'bid':0},{'server':4000},{'server':-3000}):
            p=SpotProfile([1]);self.event(p,0)
            self.event(p,1,**kw);r=p.result()['1']
            self.assertEqual(r['events'],2);self.assertEqual(r['unavailable'],2)
    def test_missing_server_stamp_is_not_fresh(self):
        p=SpotProfile([1]);p.observe(symbol=1,sequence=1,arrival_ns=1,received_ms=1,server_ms=None,bid=100,ask=102)
        r=p.result()['1'];self.assertEqual(r['healthy'],0)
    def test_local_order_and_utc_cannot_reverse(self):
        for changes in ({'sequence':1},{'arrival_ns':0},{'received_ms':0},{'symbol':2}):
            p=SpotProfile([1]);p.observe(symbol=1,sequence=1,arrival_ns=1,received_ms=1,server_ms=1,bid=100,ask=102)
            a=dict(symbol=1,sequence=2,arrival_ns=2,received_ms=2,server_ms=2,bid=100,ask=102);a.update(changes)
            with self.assertRaises(ValueError):p.observe(**a)
    def test_server_regression_cannot_be_hidden_by_fresh_arrival(self):
        p=SpotProfile([1]);self.event(p,0);self.event(p,1);self.event(p,2,server=2999)
        self.assertEqual(p.result()['1']['unavailable'],2)
    def test_all_instruments_retained_without_best_subset(self):
        p=SpotProfile([1,2,250]);self.event(p,0)
        r=p.result();self.assertEqual(set(r),{'1','2','250'});self.assertEqual(r['250']['events'],0)
if __name__=='__main__':unittest.main()
