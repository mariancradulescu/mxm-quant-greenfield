import json,pathlib,unittest
from research_core_v4 import quote_sequence_preparation_v1 as q

class QuotePreparationTests(unittest.TestCase):
    def fixture(self):
        return ([(i*1000,100000+i,0) for i in range(121)],[(i*1000,100040+i,0) for i in range(121)])
    def test_future_prefix_invariance(self):
        b,a=self.fixture();x=q.feature_at(b,a,100000,30)
        self.assertEqual(x,q.feature_at(b[:101],a[:101],100000,30))
        self.assertEqual(x,q.feature_at(b+[(999000,10000000,0)],a+[(999000,10000040,0)],100000,30))
        self.assertEqual(x['directional_revision_count'],60)
        self.assertTrue(x['signal_thresholds']['0.8'])
    def test_left_boundary_excluded(self):
        b,a=self.fixture();self.assertEqual(q.feature_at(b,a,100000,10)['directional_revision_count'],20)
    def test_equal_timestamp_order_and_unchanged(self):
        q.validate_side([(0,100,0),(0,101,1),(0,101,2),(1000,100,0)])
        with self.assertRaises(ValueError):q.validate_side([(0,100,0),(0,101,0)])
        with self.assertRaises(ValueError):q.validate_side([(1000,100,0),(0,101,0)])
    def test_invalid_integer_or_price(self):
        for row in [(0,0,0),(0,1.0,0),(True,1,0),(-1,1,0)]:
            with self.assertRaises(ValueError):q.validate_side([row])
    def test_stale_crossed_or_inadequate_baseline(self):
        b,a=self.fixture();self.assertIsNone(q.feature_at(b[:95],a,100000,10))
        self.assertIsNone(q.feature_at(b,[(i*1000,99000+i,0) for i in range(121)],100000,10))
        self.assertIsNone(q.feature_at(b[90:],a[90:],100000,10))
    def test_real_response_default_deny(self):
        with self.assertRaises(PermissionError):q.deny_response('anything')
    def test_ambiguous_millisecond_price_change_censored(self):
        b,a=self.fixture();b.insert(101,(100000,100102,1))
        self.assertIsNone(q.feature_at(b,a,100000,10))
    def test_unchanged_equal_timestamp_does_not_invent_revision(self):
        b,a=self.fixture();b.insert(101,(100000,100100,1))
        self.assertEqual(q.feature_at(b,a,100000,10)['directional_revision_count'],20)
    def test_lossless_pagination_partition_fail_closed(self):
        self.assertTrue(q.verify_complete_partition(0,1000,[(0,500,False),(501,1000,False)]))
        for intervals in [[(0,500,False),(500,1000,False)],[(0,500,False),(502,1000,False)],[(0,1000,True)],[]]:
            with self.assertRaises(ValueError):q.verify_complete_partition(0,1000,intervals)
    def test_frozen_manifest_and_protected_boundary(self):
        p=pathlib.Path(__file__).resolve().parents[1]/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_DESIGN_V1.json'
        d=json.loads(p.read_text());m=q.request_manifest(d);self.assertEqual(len(m),900)
        d['calendar']['dates_utc'][0]='2026-09-18'
        with self.assertRaises(ValueError):q.request_manifest(d)
    def test_support_fail_closed_empty_and_concentrated(self):
        self.assertFalse(q.support_summary([])['pass'])
        e=[{'date_utc':'2025-10-13','window_index':0,'complete':True} for _ in range(200)]
        self.assertFalse(q.support_summary(e)['pass'])
    def test_support_retention_uses_all_attempts(self):
        d=json.loads((pathlib.Path(__file__).resolve().parents[1]/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_DESIGN_V1.json').read_text())
        e=[{'date_utc':day,'window_index':w,'complete':True} for day in d['calendar']['dates_utc'] for w in range(3) for _ in range(5)]
        self.assertTrue(q.support_summary(e)['pass'])
        e+= [{**e[0],'complete':False} for _ in range(200)]
        self.assertFalse(q.support_summary(e)['pass'])

if __name__=='__main__':unittest.main()
