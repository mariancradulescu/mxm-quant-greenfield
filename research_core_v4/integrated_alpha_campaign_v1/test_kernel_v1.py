import unittest,math
from research_core_v4.integrated_alpha_campaign_v1 import kernel_v1 as k
from research_core_v4.native_body_persistence_v1 import kernel_v1 as cash
class Contracts(unittest.TestCase):
    def bars(self,t):return {t-300-48*300+i*300:[100,102,98,100+(.1 if i%2 else -.1),10] for i in range(48)}
    def test_last_feature_close_is_t_minus300(self):
        t=k.START+4500;b=self.bars(t);a=k.feature(b,t);b[t-300]=[100,110,90,109,99];self.assertEqual(a,k.feature(b,t));b[t-600]=[100,110,90,109,99];self.assertNotEqual(a,k.feature(b,t))
    def test_weekly_matching_never_future(self):
        t=k.START+4500;b=self.bars(t)
        for w in range(1,5):b.update(self.bars(t-w*604800))
        self.assertIsNotNone(k.feature(b,t)['weekly']);del b[t-600-4*604800];self.assertIsNone(k.feature(b,t)['weekly'])
    def test_exit_censor_does_not_change_feature(self):
        t=k.START+4500;b=self.bars(t);f=k.feature(b,t);self.assertIsNone(k.label(b,t));b.update({t+i*300:[100,102,98,101,10] for i in range(48)});self.assertEqual(f,k.feature(b,t));self.assertIsNotNone(k.label(b,t))
    def test_moment_is_order_invariant_not_lag_covariance(self):
        t=k.START+4500;b=self.bars(t);a=k.feature(b,t)['cubic'];last=[b[t-3900+i*300] for i in range(12)];
        for i,x in enumerate(reversed(last)):b[t-3900+i*300]=x
        self.assertAlmostEqual(a,k.feature(b,t)['cubic'])
    def test_calendar_upper_and_complete_weeks(self):
        self.assertEqual(len(list(k.grid(k.START,k.START+604800))),42);self.assertGreaterEqual(len(k.complete_weeks()),40)
    def test_target_cannot_enter_its_peer_statistic(self):
        f={'weekly':[[.01,10]]*4,'volume':30,'body':.01};features={(1,1):f};pairs={1:('EUR','USD')};self.assertEqual(k.peer_direction(1,1,features,pairs),k.peer_direction(1,1,{},pairs))
    def test_weekly_shock_not_adjacent_hour_activity(self):
        f={'weekly':[[.01,10]]*4,'volume':19,'body':.01};self.assertFalse(k.surprise(f));f['volume']=20;self.assertTrue(k.surprise(f))
    def test_signed_receipt_liability_and_sides(self):
        f={'preciseTradingCommissionRate':0,'preciseMinCommission':0,'commissionType':2,'minCommissionType':1,'minCommissionAsset':'USD','lotSize':10000000,'pnlConversionFeeRate':0};fx={'bid':1.2,'ask':1.21}
        self.assertAlmostEqual(cash.account(-1,1,{'bid':100,'ask':101},{'bid':102,'ask':103},fx,fx,f,0,0)['net_eur'],-3/1.2)
    def test_economic_floor_currency(self):
        f={'preciseTradingCommissionRate':300000000,'preciseMinCommission':100000000,'commissionType':2,'minCommissionType':1,'minCommissionAsset':'EUR','lotSize':10000000};self.assertEqual(cash.commission(f,1000,1.2,{'bid':1.2,'ask':1.21}),1)
    def test_no_signal_zero_not_outcome_imputation(self):
        r={'d':0,'b':1,'y':123,'t':k.START,'feature':None,'reason':'FEATURE_GAP'};self.assertEqual(k.stats([r])['paired'],0)
if __name__=='__main__':unittest.main()
