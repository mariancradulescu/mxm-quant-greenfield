import unittest,math
from research_core_v4.native_body_persistence_v1 import kernel_v1 as k
class Contracts(unittest.TestCase):
    def full(self):return dict(preciseTradingCommissionRate=300000000,preciseMinCommission=100000000,commissionType=2,minCommissionType=1,minCommissionAsset='USD',lotSize=10000000,pnlConversionFeeRate=30)
    def test_floor_currency_is_string(self):
        f=self.full();self.assertAlmostEqual(k.commission(f,1000,1.2,{'bid':1.2,'ask':1.21}),1/1.2)
        f['minCommissionAsset']='EUR';self.assertEqual(k.commission(f,1000,1.2,{'bid':1.2,'ask':1.21}),1)
    def test_sides_and_signed_FX(self):
        f=self.full();f.update(preciseMinCommission=0,preciseTradingCommissionRate=0,pnlConversionFeeRate=0)
        q0={'bid':100,'ask':101};q1={'bid':102,'ask':103};fx={'bid':1.2,'ask':1.21}
        self.assertAlmostEqual(k.account(1,1,q0,q1,fx,fx,f,0,0)['net_eur'],1/1.21)
        self.assertAlmostEqual(k.account(-1,1,q0,q1,fx,fx,f,0,0)['net_eur'],-3/1.2)
    def test_exit_missing_does_not_change_direction(self):
        t=k.START+900;bars={t-3900+i*300:{'open':100.,'close':100*math.exp((i+1)*.001),'high':103.,'low':99.} for i in range(12)}
        x=k.observations(bars)[0];bars.update({t+i*300:{'open':100.,'close':101.,'high':102.,'low':99.} for i in range(12)});y=k.observations(bars)[0]
        self.assertEqual((x['d'],x['b']),(y['d'],y['b']));self.assertIsNone(x['y']);self.assertIsNotNone(y['y'])
    def test_new_information_not_close_location(self):
        # Identical close/high/low at every bar => identical old close-location statistic.
        def prior(r):return [{'open':100*math.exp(-x),'close':100.,'high':102.,'low':98.} for x in r]
        a=k.direction(prior([.001*(i+1) for i in range(12)]))
        b=k.direction(prior([.001 if i%2 else -.001 for i in range(12)]))
        self.assertEqual(a[1],b[1]);self.assertNotEqual(a[0],b[0])
    def test_fee_base_is_PNL_not_notional(self):
        f=self.full();f.update(preciseMinCommission=0,preciseTradingCommissionRate=0)
        fx={'bid':1,'ask':1};z=k.account(1,1,{'bid':100,'ask':100},{'bid':110,'ask':110},fx,fx,f,0,0)
        self.assertAlmostEqual(z['conversion_fee_eur'],.03)
        q=k.account(1,1,{'bid':100,'ask':100},{'bid':90,'ask':90},fx,fx,f,0,0,True);self.assertAlmostEqual(q['conversion_fee_eur'],.03)
    def test_denominators(self):
        rr=[{'entry':{'eligible':False}},{'entry':{'eligible':False,'flat_cost_eur':1}},{'entry':{'eligible':True,'flat_cost_eur':1}}]
        self.assertEqual(k.cost_stats(rr)['entries'],2);self.assertEqual(k.cost_stats(rr,True)['entries'],1)
if __name__=='__main__':unittest.main()
