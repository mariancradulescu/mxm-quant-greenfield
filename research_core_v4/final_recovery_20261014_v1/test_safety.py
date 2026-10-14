import copy,unittest
from unittest.mock import patch
from . import storage,economic,order_kernel
class SafetyTests(unittest.TestCase):
    def test_ordering_contains_information_beyond_endpoint_and_rv(self):
        a=order_kernel.feature([.02,.01]+[0.]*10);b=order_kernel.feature([.01,.02]+[0.]*10)
        self.assertEqual(a['rv'],b['rv']);self.assertEqual(a['return'],b['return']);self.assertEqual(a['baseline'],b['baseline']);self.assertEqual(a['side'],-b['side'])
    def test_unknown_exit_does_not_select_a_known_profitable_replacement(self):
        e={'sid':1,'t':1000,'iso':'2026-W35','cost_eur':.1,'risk_eur':1.,'margin_eur':10.}
        missing={'event':e,'model':None,'baseline':None};other={'event':{**e,'sid':2,'cost_eur':.2},'model':{'net_eur':100.},'baseline':{'net_eur':0.}}
        p=economic.portfolio([missing,other]);self.assertEqual(p['selected'],1);self.assertEqual(p['closed'],0);self.assertEqual(p['closed_equity_eur'],200.);self.assertIsNotNone(p['halt'])
    def test_failed_publish_preserves_authenticated_raw_and_dirty_rows(self):
        state={'generation':691,'_raw':[{'authentic_response':'PRIVATE'}],'_record_dirty_ids':{1}};original=copy.deepcopy(state)
        def fail(*args):state.pop('_raw');state['generation']+=1;raise ConnectionError()
        with patch.object(storage,'ORIGINAL_PERSIST',fail):
            with self.assertRaises(ConnectionError):storage.persist(None,None,state,'x')
        self.assertEqual(state,original)
    def test_flat_history_has_no_fabricated_direction(self):self.assertEqual(order_kernel.feature([0.]*12)['side'],0)
if __name__=='__main__':unittest.main()
