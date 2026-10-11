import unittest
from research_core_v4.integrated_alpha_campaign_v1 import economics_v1 as e,kernel_v1 as k
class CausalPortfolio(unittest.TestCase):
    def event(self,sid,t):return {'sid':sid,'t':t,'family':k.NAMES[0],'d':1,'b':-1,'entry':{'eligible':True,'flat_cost_eur':.1,'range_eur':1,'margin_eur':10},'scenarios':None}
    def test_missing_future_exit_does_not_replace_entry(self):
        a=self.event(1,1);b=self.event(2,1);z,ledger=e.allocator([a,b]);self.assertEqual(z[0]['sid'],1);self.assertEqual(ledger['halt'],'FIRST_SELECTED_EXIT_CENSORED');a['scenarios']={n:{'model':{'net_eur':-100},'baseline':{'net_eur':100}} for n in e.SCENARIOS};self.assertEqual(e.allocator([a,b])[0][0]['sid'],1)
    def test_conflicting_mechanisms_abstain_instrument(self):
        a=self.event(1,1);b=dict(a,d=-1,family=k.NAMES[1]);self.assertEqual(e.allocator([a,b])[0],[])
    def test_simultaneous_assets_do_not_multiply_portfolio(self):
        z,_=e.allocator([self.event(i,1) for i in range(1,101)]);self.assertEqual(len(z),1)
    def test_unknown_quote_keeps_signal_entry_censored(self):
        r={'sid':1,'t':k.START,'d':1,'b':1,'feature':{'range':.01}};z=e.pre_cost(r,{}, {},{});self.assertFalse(z['eligible']);self.assertEqual(z['reason'],'ENTRY_OR_FX_QUOTE_UNAVAILABLE')
if __name__=='__main__':unittest.main()
