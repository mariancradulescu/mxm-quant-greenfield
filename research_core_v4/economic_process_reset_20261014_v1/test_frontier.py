import unittest
from .frontier import capacity_plan,max_concurrent
def event(sid,t,risk,margin,exit_support=True):return {'sid':sid,'t':t,'h':900,'mode':'STRICT5S','iso':'2026-W35','margin_eur_current':margin,'endpoint_cost_support':exit_support,'scenarios':{'2':{'feasible':True,'cost_eur':.1,'risk_eur':risk}}}
class FrontierTests(unittest.TestCase):
    def test_simultaneous_positions_respect_sum_not_single_ticket(self):
        v=[event(1,1000,1,30),event(2,1000,1,50),event(3,1000,.01,0)]
        z=capacity_plan(v,900,2,'STRICT5S');self.assertEqual(z['admitted_ticket_opportunities'],2);self.assertEqual(z['maximum_simultaneous'],2);self.assertEqual(z['peak_reference_margin_eur'],80)
    def test_missing_exit_is_not_replaced_using_future_knowledge(self):
        v=[event(1,1000,1,10,False),event(2,1900,1,10,True)]
        z=capacity_plan(v,900,2,'STRICT5S',True);self.assertEqual(z['admitted_ticket_opportunities'],1);self.assertIsNotNone(z['halt'])
    def test_exit_releases_capital_before_new_entry_same_timestamp(self):
        self.assertEqual(max_concurrent([event(1,1000,1,10),event(2,1900,1,10)],900),1)
if __name__=='__main__':unittest.main()
