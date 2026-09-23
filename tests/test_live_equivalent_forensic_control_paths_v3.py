import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import m6.tier1_candidate_replay as tier1
import m7.competition_expansion_index_m15 as expansion
import m7.competition_ultra_fast_stage_a_evaluator as ultra
import m7.competition_ultra_fast_stage_a_frontier_v2_evaluator as frontier
import m7.competition_performance_v3_wave02_evaluator as wave02
import m7.competition_performance_v3_wave03_c026_evaluator as wave03
UTC=timezone.utc
def bar(t,px=100.0): return {"t":t,"o":px,"h":px+1,"l":px-1,"c":px}
def trow(t,c): return {"time_utc":t.isoformat(),"open":c,"high":c,"low":c,"close":c}
class ForensicControlPathsV3(unittest.TestCase):
 def test_m6_tail_exit_changes_admission(self):
  b=datetime(2026,1,5,15,0,tzinfo=UTC)
  tail=[(trow(b+timedelta(minutes=15*i),3.0 if i==2 else 1.0),trow(b+timedelta(minutes=15*i),1.0)) for i in range(4)]
  full=tail+[(trow(b+timedelta(minutes=15*i),1.0),trow(b+timedelta(minutes=15*i),1.0)) for i in range(4,7)]
  with patch.object(tier1,"_prior_finite_window",return_value=[1.0,2.0]*260),patch.object(tier1,"_sample_std",return_value=1.0):
   with patch.object(tier1,"synchronized_observed_cash_bars",return_value=tail): self.assertEqual(tier1.c012_replay_intents([],[],None),[])
   with patch.object(tier1,"synchronized_observed_cash_bars",return_value=full): self.assertEqual(len(tier1.c012_replay_intents([],[],None)),1)
 def test_expansion_future_session_and_exit_control_entry(self):
  b=datetime(2026,1,5,14,30,tzinfo=UTC)
  class O:
   def __init__(self,n,complete=True):
    self.complete_grid=complete; self.expected_opens=[b+timedelta(minutes=15*i) for i in range(n)]
    self.x=[{"time_utc":t.isoformat(),"open":100+i,"high":101+i,"low":99+i,"close":100+i} for i,t in enumerate(self.expected_opens)]
   def ordered_expected_bars(self): return self.x
  kw=dict(candidate_id="V2-C013",spec_hash=expansion.CANDIDATE_HASHES["V2-C013"],reverse=False)
  with patch.object(expansion,"_session_bars",return_value={b.date():O(6,True)}): self.assertEqual(expansion.sign_replay_intents([],None,**kw),[])
  with patch.object(expansion,"_session_bars",return_value={b.date():O(9,True)}): self.assertGreaterEqual(len(expansion.sign_replay_intents([],None,**kw)),1)
  with patch.object(expansion,"_session_bars",return_value={b.date():O(9,False)}): self.assertEqual(expansion.sign_replay_intents([],None,**kw),[])
 def test_ultra_future_hold_grid_controls_signal(self):
  b=datetime(2026,6,15,0,0,tzinfo=UTC); full=[bar(b+timedelta(minutes=5*i),100+i) for i in range(25)]
  self.assertEqual(ultra.single(full[:14],"V2-C017","MOM",0.001),[])
  self.assertEqual(len(ultra.single(full,"V2-C017","MOM",0.001)),1)
  self.assertEqual(ultra.single(full[:15]+full[16:],"V2-C017","MOM",0.001),[])
 def test_frontier_c023_future_exit_precheck_contradicts_pending_exit_semantics(self):
  S=datetime(2026,6,15,8,0,tzinfo=UTC); sig=S-timedelta(minutes=5); start=sig-timedelta(minutes=5*48)
  hist=[bar(start+timedelta(minutes=5*i),100+i) for i in range(49)]; tail=hist+[bar(S,200)]; normal=tail+[bar(S+timedelta(hours=4),220)]
  with patch.object(frontier,"S",S),patch.object(frontier,"E",S+timedelta(hours=4,minutes=5)),patch.object(frontier,"MARKETS",("X",)),patch.object(frontier,"COSTS",{"X":0.001}):
   self.assertEqual(frontier.generate_trades({"X":tail}),[])
   self.assertEqual(len(frontier.generate_trades({"X":normal})),1)
 def test_wave02_c024_future_grid_controls_eligibility(self):
  b=datetime(2026,6,15,8,0,tzinfo=UTC); syms=("A","B","C","D")
  tail={s:[bar(b,100),bar(b+timedelta(minutes=5),101)] for s in syms}
  full={s:[bar(b+timedelta(minutes=5*i),100+i) for i in range(13)] for s in syms}
  def snap(rows_by,idx,t): return {s:{"resid":1.0,"i":0} for s in syms}
  with patch.object(wave02,"decision_boundary",return_value=True),patch.object(wave02,"_c024_snapshot",side_effect=snap):
   self.assertEqual(wave02.c024_trades(tail,{s:0.001 for s in syms}),[])
   self.assertGreaterEqual(len(wave02.c024_trades(full,{s:0.001 for s in syms})),1)
 def test_wave03_c026_future_exit_boundary_controls_segment_existence(self):
  t=wave03.START; _,d0=wave03.build_symbol_trades([bar(t,100)],"X",0.001); self.assertEqual(d0["eligible_segments"],0)
  x=wave03.next_boundary(t); _,d1=wave03.build_symbol_trades([bar(t,100),bar(x,101)],"X",0.001); self.assertEqual(d1["eligible_segments"],1)
  _,d2=wave03.build_symbol_trades([bar(t+timedelta(minutes=5),100),bar(x,101)],"X",0.001); self.assertEqual(d2["eligible_segments"],0)
if __name__=="__main__": unittest.main(verbosity=2)
