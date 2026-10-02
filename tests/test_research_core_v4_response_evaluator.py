from __future__ import annotations
import math
import unittest
from datetime import datetime,timedelta,timezone
import numpy as np
from research_core_v4 import response_evaluator_v2 as ev

UTC=timezone.utc

def bars(start,n,step=.001,gap_indices=()):
    out=[];p=100.0
    for i in range(n):
        if i in gap_indices: continue
        p*=math.exp(step if (i//12)%2==0 else -step/2)
        out.append(ev.M5Bar(start+timedelta(minutes=5*i),p))
    return out

class Tests(unittest.TestCase):
 def test_bucket_completion_and_gap_no_fill(self):
    s=datetime(2026,1,1,tzinfo=UTC); b=bars(s,20,gap_indices={2})
    m15=ev.completed_buckets(b,15)
    self.assertFalse(any(x.start==s for x in m15))
 def test_no_lookahead_bucket_end(self):
    s=datetime(2026,1,1,tzinfo=UTC); h4=ev.completed_buckets(bars(s,48),240)
    self.assertEqual(len(h4),1);self.assertEqual(h4[0].end,s+timedelta(hours=4))
 def test_dst_and_session_labels(self):
    a=datetime(2026,3,6,14,30,tzinfo=UTC); b=datetime(2026,3,9,13,30,tzinfo=UTC)
    self.assertEqual(ev.session_diagnostics("US_EQUITY_EXTENDED_HOURS",a),("REGULAR","STANDARD"))
    self.assertEqual(ev.session_diagnostics("US_EQUITY_EXTENDED_HOURS",b),("REGULAR","DST"))
 def test_m15_transition_state(self):
    bs=[ev.CompletedBucket(datetime(2026,1,1,tzinfo=UTC)+timedelta(minutes=15*i),datetime(2026,1,1,tzinfo=UTC)+timedelta(minutes=15*(i+1)),100+i) for i in range(7)]
    self.assertEqual(ev.directional_state(bs,4)[bs[-1].end],1)
 def test_full_baseline_and_low_high_assignment(self):
    events=ev.build_signal_support(bars(datetime(2025,1,1,tzinfo=UTC),12*24*8,step=.002),"FX_SPOT","X",1)
    self.assertTrue(all(e.arm in ("FULL","BASELINE") for e in events))
    self.assertTrue(all(e.vol_state in ("LOW","HIGH") for e in events))
 def test_response_right_censoring(self):
    t=datetime(2026,1,1,tzinfo=UTC)
    e=ev.SignalEvent("FX_SPOT","X",1,t,1,"LOW","FULL",100,.01,"2026-W01",(True,False,False,False),0,"Thursday","ASIA_UTC",None)
    close={t:101,t+timedelta(minutes=10):103}
    self.assertIsNotNone(ev.response_for_event(e,3,close));self.assertIsNone(ev.response_for_event(e,6,close))
 def test_paired_unit_construction(self):
    t=datetime(2026,1,1,tzinfo=UTC); t2=t+timedelta(minutes=15)
    e1=ev.SignalEvent("FX_SPOT","X",1,t,1,"LOW","FULL",100,.01,"2026-W01",(True,False,False,False),0,"Thursday","ASIA_UTC",None)
    e2=ev.SignalEvent("FX_SPOT","X",1,t2,1,"LOW","BASELINE",100,.01,"2026-W01",(True,False,False,False),0,"Thursday","ASIA_UTC",None)
    u=ev.construct_paired_units([e1,e2],{("X",t,3):2.0,("X",t2,3):1.0})
    self.assertEqual(len(u),1);self.assertEqual(u[0].contrast,1.0)
 def test_equal_direction_weighting(self):
    u=[ev.PairedUnit("C","S","2026-W01",1,"LOW",3,4,1),ev.PairedUnit("C","S","2026-W01",-1,"LOW",3,2,1)]
    self.assertAlmostEqual(ev.aggregate_direction_to_symbol_week(u)[("C","S","2026-W01","LOW",3)],2.0)
 def test_equal_symbol_weighting(self):
    sw={("C","A","2026-W01","LOW",3):1,("C","B","2026-W01","LOW",3):3}
    self.assertEqual(ev.aggregate_symbol_to_context_week(sw,2)[("C","2026-W01","LOW",3)],2)
 def test_two_week_blocks(self):
    cw={}
    for w,v in [(38,1.0),(39,3.0),(40,5.0),(41,7.0)]: cw[("C",f"2025-W{w:02d}","LOW",3)]=v
    ids,x=ev.two_week_blocks(cw,datetime(2025,9,15,tzinfo=UTC),"C","LOW",3)
    self.assertEqual(ids.tolist(),[0,1]);self.assertEqual(x.tolist(),[2,6])
 def test_shared_maxT_resampling(self):
    ids=np.arange(14);x=np.linspace(.5,1.5,14)
    r=ev.local_shared_maxT([(ids,x),(ids,np.zeros(14))],1023,123)
    self.assertLessEqual(r["adjusted_p"][0],.05)
 def test_holm_context_control(self):
    self.assertEqual(ev.holm_reject([.01,.03,.2]),[True,False,False])
 def test_temporal_gate(self):
    self.assertTrue(ev.chronological_gate({i:(1 if i<9 else -1) for i in range(12)},4,3))
 def test_breadth_gate(self):
    self.assertTrue(ev.breadth_gate({"a":1,"b":1,"c":1,"d":-1},3))
    self.assertTrue(ev.breadth_gate({"a":1,"b":1,"c":-1,"d":-1},2))
 def test_concentration_gate(self):
    self.assertTrue(ev.concentration_gate({"a":1,"b":1,"c":1}))
    self.assertFalse(ev.concentration_gate({"a":9,"b":1,"c":1}))
 def test_support_fail_closed(self):
    self.assertTrue(ev.support_fail_closed(full_events=100,baseline_events=100,paired_units=120,blocks=12,min_full=80,min_baseline=80,min_paired=120,min_blocks=10))
    self.assertFalse(ev.support_fail_closed(full_events=79,baseline_events=100,paired_units=120,blocks=12,min_full=80,min_baseline=80,min_paired=120,min_blocks=10))
 def test_real_execution_denied_without_authority(self):
    with self.assertRaises(PermissionError): ev.require_real_response_authority({})
 def test_fixed_calendar_gates(self):
    self.assertTrue(ev.development_quarter_gate({0:1,14:1,27:1,40:-1},3))
    self.assertTrue(ev.confirmation_tertile_gate({0:1,8:1,16:-1},2))
 def test_confirmation_single_leaf_known_answer(self):
    ids=np.arange(12);x=np.ones(12)
    self.assertLessEqual(ev.confirmation_single_leaf_test(ids,x,1023,99),.05)

if __name__=="__main__":unittest.main()
