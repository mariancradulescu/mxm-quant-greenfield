from decimal import Decimal as D
import unittest
from competition.continuous_account_replay_v2 import CapitalEvent as E, FEASIBLE, replay_continuous_account

class ContinuousReplayV2Tests(unittest.TestCase):
 def replay(self,events,**kw):
  return replay_continuous_account(events,starting_equity_eur=200,account_type='HEDGED',total_margin_calculation_type='MAX',**kw)
 def test_external_cashflow_neutral_nav(self):
  r=self.replay([E('2026-01-01T00:00:00Z','DEPOSIT',cashflow_eur=50),E('2026-01-01T01:00:00Z','WITHDRAWAL',cashflow_eur=20)])
  self.assertEqual((r.terminal_broker_equity_eur,r.terminal_strategy_nav_eur,r.external_cashflow_net_eur),(D('230'),D('200'),D('30')))
 def test_rejected_entry_future_events_skip_not_crash(self):
  r=self.replay([E('2026-01-01T00:00:00Z','ENTRY','C','X','p',direction='LONG',direction_feasibility=FEASIBLE,volume_cents=1,min_volume_cents=1,step_volume_cents=1,max_volume_cents=10,margin_eur=300,price=10,base_units=1,quote_to_eur_rate=1),E('2026-01-01T00:05:00Z','MARK','C','X','p',price=11,quote_to_eur_rate=1),E('2026-01-01T00:10:00Z','EXIT','C','X','p',price=11,quote_to_eur_rate=1)])
  self.assertEqual((r.status,r.rejected_entries,r.accepted_entries),('COMPLETE',1,0))
 def test_financing_cost_compounding_and_metrics(self):
  r=self.replay([E('2026-01-01T00:00:00Z','ENTRY','C','X','p',direction='LONG',direction_feasibility=FEASIBLE,volume_cents=1,min_volume_cents=1,step_volume_cents=1,max_volume_cents=10,margin_eur=20,price=10,base_units=1,quote_to_eur_rate=1,transaction_cost_eur=1),E('2026-01-01T00:05:00Z','MARK','C','X','p',price=12,quote_to_eur_rate=1),E('2026-01-01T00:06:00Z','FINANCING','C','X','p',financing_eur=-.5),E('2026-01-01T00:10:00Z','EXIT','C','X','p',price=12,quote_to_eur_rate=1)])
  self.assertEqual(r.terminal_broker_equity_eur,D('200.5')); self.assertEqual(r.financing_eur,D('-0.5')); self.assertEqual(r.transaction_costs_eur,D('1')); self.assertTrue(r.weekly_final_equity_eur); self.assertTrue(r.monthly_final_equity_eur)
 def test_stop_out_unknown_fails_closed(self):
  r=self.replay([E('2026-01-01T00:00:00Z','ENTRY','C','X','p',direction='LONG',direction_feasibility=FEASIBLE,volume_cents=1,min_volume_cents=1,step_volume_cents=1,max_volume_cents=10,margin_eur=100,price=100,base_units=1,quote_to_eur_rate=1),E('2026-01-01T00:05:00Z','MARK','C','X','p',price=50,quote_to_eur_rate=1),E('2026-01-01T00:10:00Z','EXIT','C','X','p',price=100,quote_to_eur_rate=1)],unresolved_stop_out_guard_ratio=D('1.5'))
  self.assertEqual(r.status,'HALT_UNRESOLVED_BROKER_STOP_OUT')
 def test_same_timestamp_marks_are_atomic(self):
  ev=[E('2026-01-01T00:00:00Z','ENTRY','C','A','a',direction='LONG',direction_feasibility=FEASIBLE,volume_cents=1,min_volume_cents=1,step_volume_cents=1,max_volume_cents=10,margin_eur=40,price=100,base_units=1,quote_to_eur_rate=1),E('2026-01-01T00:00:00Z','ENTRY','C','B','b',direction='SHORT',direction_feasibility=FEASIBLE,volume_cents=1,min_volume_cents=1,step_volume_cents=1,max_volume_cents=10,margin_eur=40,price=100,base_units=1,quote_to_eur_rate=1),E('2026-01-01T00:05:00Z','MARK','C','A','a',price=20,quote_to_eur_rate=1),E('2026-01-01T00:05:00Z','MARK','C','B','b',price=20,quote_to_eur_rate=1),E('2026-01-01T00:10:00Z','EXIT','C','A','a',price=100,quote_to_eur_rate=1),E('2026-01-01T00:10:00Z','EXIT','C','B','b',price=100,quote_to_eur_rate=1)]
  r=self.replay(ev,unresolved_stop_out_guard_ratio=D('1.5')); self.assertEqual(r.status,'COMPLETE')
if __name__=='__main__': unittest.main()
