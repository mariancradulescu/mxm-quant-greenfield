import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import patch

from research_v3.same_identity_live_equivalent_correction_v1 import (
    c006_live_equivalent_replay,c012_live_equivalent_replay,
    c023_live_equivalent_trades,c025_live_equivalent_trades,
)
from m7 import competition_performance_v3_wave02_evaluator as wave02

UTC=timezone.utc

def m15row(t,p=100.0):
    return {"time_utc":t.isoformat(),"open":p,"high":p+1,"low":p-1,"close":p}

def bar(t,p=100.0): return {"t":t,"o":p,"h":p+1,"l":p-1,"c":p}

class SameIdentityLiveEquivalentCorrectionsV1Tests(unittest.TestCase):
    def test_c006_entry_admission_does_not_query_future_exit(self):
        start=datetime(2026,1,5,14,30,tzinfo=UTC)
        class O:
            exact_open_bar=m15row(start,100.0)
            session=SimpleNamespace(open_utc=start,close_utc=start+timedelta(hours=6,minutes=30))
            def __init__(self,n): self.rows=[m15row(start+timedelta(minutes=15*i),100+i) for i in range(n)]
            def ordered_expected_bars(self): return self.rows
        prev=SimpleNamespace(session_date=datetime(2026,1,2,tzinfo=UTC).date(),close_utc=start-timedelta(days=3)+timedelta(hours=6,minutes=30))
        cal=SimpleNamespace(previous_session=lambda day:prev)
        with patch('research_v3.same_identity_live_equivalent_correction_v1.cash_session_observations',return_value={start.date():O(2)}),\
             patch('research_v3.same_identity_live_equivalent_correction_v1.exact_session_close_price',return_value=110.0),\
             patch('research_v3.same_identity_live_equivalent_correction_v1.prior_valid_true_ranges',return_value=[0.01]*20):
            tail=c006_live_equivalent_replay([],cal)
        with patch('research_v3.same_identity_live_equivalent_correction_v1.cash_session_observations',return_value={start.date():O(14)}),\
             patch('research_v3.same_identity_live_equivalent_correction_v1.exact_session_close_price',return_value=110.0),\
             patch('research_v3.same_identity_live_equivalent_correction_v1.prior_valid_true_ranges',return_value=[0.01]*20):
            full=c006_live_equivalent_replay([],cal)
        self.assertEqual(tail.admitted_entries,1); self.assertEqual(tail.right_censored_entries,1); self.assertEqual(len(tail.settled_intents),0)
        self.assertEqual(full.admitted_entries,1); self.assertEqual(len(full.settled_intents),1)

    def test_c012_entry_exists_before_exit_rows_and_tail_is_right_censored(self):
        b=datetime(2026,1,5,15,0,tzinfo=UTC)
        def pair(i): return (m15row(b+timedelta(minutes=15*i),3.0 if i==2 else 1.0),m15row(b+timedelta(minutes=15*i),1.0))
        tail=[pair(i) for i in range(4)]; full=[pair(i) for i in range(7)]
        with patch('research_v3.same_identity_live_equivalent_correction_v1.synchronized_observed_cash_bars',return_value=tail),\
             patch('research_v3.same_identity_live_equivalent_correction_v1._prior_finite_window',return_value=[1.0,2.0]*260),\
             patch('research_v3.same_identity_live_equivalent_correction_v1._sample_std',return_value=1.0):
            a=c012_live_equivalent_replay([],[],None)
        with patch('research_v3.same_identity_live_equivalent_correction_v1.synchronized_observed_cash_bars',return_value=full),\
             patch('research_v3.same_identity_live_equivalent_correction_v1._prior_finite_window',return_value=[1.0,2.0]*260),\
             patch('research_v3.same_identity_live_equivalent_correction_v1._sample_std',return_value=1.0):
            b2=c012_live_equivalent_replay([],[],None)
        self.assertEqual(a.admitted_entries,1); self.assertEqual(a.right_censored_entries,1); self.assertEqual(len(a.settled_intents),0)
        self.assertEqual(b2.admitted_entries,1); self.assertEqual(len(b2.settled_intents),1)

    def test_c023_pending_exit_is_post_entry_and_sample_tail_does_not_delete_entry(self):
        start=datetime(2026,6,15,8,0,tzinfo=UTC); m5=timedelta(minutes=5); sig=start-m5; first=sig-48*m5
        hist=[bar(first+i*m5,100+i) for i in range(49)]
        tail=hist+[bar(start,200)]
        full=tail+[bar(start+timedelta(hours=4),220)]
        a=c023_live_equivalent_trades({'X':tail},{'X':0.001},start,start+timedelta(hours=4),m5)
        b=c023_live_equivalent_trades({'X':full},{'X':0.001},start,start+timedelta(hours=4,minutes=5),m5)
        self.assertEqual(a.admitted_entries,1); self.assertEqual(a.right_censored_entries,1); self.assertEqual(len(a.settled_trades),0)
        self.assertEqual(b.admitted_entries,1); self.assertEqual(len(b.settled_trades),1)

    def test_c025_missing_post_entry_target_is_data_event_not_retroactive_no_trade(self):
        start=datetime(2026,6,15,0,0,tzinfo=UTC); m5=timedelta(minutes=5)
        rows=[bar(start+i*m5,100+i*.1) for i in range(175)]
        with patch.object(wave02,'decision_boundary',return_value=True), patch.object(wave02,'_c025_state',return_value=(1,1,1,'HIGH','X')):
            normal=c025_live_equivalent_trades({'X':rows},{'X':0.0})
            target=normal.settled_trades[0]['x']-m5
            broken=[r for r in rows if r['t']!=target]
            corrected=c025_live_equivalent_trades({'X':broken},{'X':0.0})
        self.assertGreaterEqual(corrected.admitted_entries,1)
        self.assertEqual(len(corrected.post_entry_settlement_invalid_entries),1)
        self.assertEqual(corrected.post_entry_settlement_invalid_entries[0]['classification'],'POST_ENTRY_SETTLEMENT_DATA_INVALID')

if __name__=='__main__': unittest.main(verbosity=2)
