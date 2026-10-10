import copy,math,unittest
from research_core_v4.activity_clock_cost_v1.kernel_v1 import feature,observations,evaluate,n
from research_core_v4.compact_baseline_v2 import baseline
class ScientificChecks(unittest.TestCase):
    def bars(self):
        out={}
        for k in range(200):
            t=n.START+k*300;o=100+k*.01
            out[t]={'timestamp':t,'available_at':t+300,'open':o,'close':o+.005,'high':o+.02,'low':o-.01,'tick_volume':2}
        return out
    def test_distinct_from_weighted_sign_and_hourly_aggregates(self):
        a=self.bars();h=n.START+3600;t=h+900;ss=list(range(h-3600,h,300));b=copy.deepcopy(a)
        vv=[12]+[1]*10+[2]
        for s,v in zip(ss,vv):b[s]['tick_volume']=v
        self.assertEqual(sum(a[s]['tick_volume'] for s in ss),sum(b[s]['tick_volume'] for s in ss))
        # All bodies have same sign: the closed tick-weighted-sign signal is equal.
        self.assertEqual(sum(a[s]['tick_volume'] for s in ss),sum(b[s]['tick_volume'] for s in ss))
        self.assertEqual(baseline(t,list(a.values())),baseline(t,list(b.values())))
        self.assertNotEqual(feature([a[s] for s in ss]),feature([b[s] for s in ss]))
    def test_future_prices_cannot_change_feature(self):
        a=self.bars();b=copy.deepcopy(a);j=8;action=n.START+j*3600+900
        for t,r in b.items():
            if t>=action:
                for k in ('open','high','low','close'):r[k]*=2
        aa=observations(a)[j];bb=observations(b)[j]
        self.assertEqual(aa['x'],bb['x']);self.assertEqual(aa['causal_reference_price'],bb['causal_reference_price'])
    def test_no_unmatured_label_update(self):
        obs=[]
        for j in range(672):
            a=n.START+j*3600+900
            obs.append({'clock':j,'action':a,'exit':a+14400,'x':[float((j+k)%7) for k in range(13)],
              'feature':'FEATURE_VALID','phi':None,'y':float(j%5),'label':'SUPPORTED'})
        gate=lambda r:{'research_pass':True,'reason':'PASS'}
        changed=copy.deepcopy(obs);changed[99]['y']=1e7
        a=evaluate(obs,gate);b=evaluate(changed,gate)
        self.assertEqual(a[25]['clock'],100)
        self.assertEqual(a[25]['model'],b[25]['model'])
        self.assertNotEqual(a[26]['model'],b[26]['model'])
    def test_missing_or_zero_activity_abstains(self):
        b=self.bars();ss=list(range(n.START,n.START+3600,300));rows=[b[t] for t in ss]
        rows[3]['tick_volume']=0;self.assertIsNone(feature(rows))
        self.assertIsNone(feature(rows[:11]))
    def test_full_calendar_denominators(self):
        obs=observations({});rr=evaluate(obs,lambda r:{'research_pass':False,'reason':'MISSING'})
        self.assertEqual(len(rr),168)
        self.assertTrue(all(sum(r['clock']//168==b for r in rr)==42 for b in range(4)))
        self.assertTrue(all(r['model'] is None for r in rr))
    def test_existing_native_cross_conversion_and_direct_eur(self):
        from research_core_v4.activity_clock_cost_v1.runner_v1 import economic_gate
        t=n.START+10000
        native={'assets':[{'assetId':1,'name':'EUR'},{'assetId':2,'name':'USD'},{'assetId':3,'name':'CFD'}],
          'light':[{'symbolId':99,'baseAssetId':3,'quoteAssetId':2}],
          'full':{'99':{'preciseTradingCommissionRate':0,'preciseMinCommission':0,'commissionType':1,'minCommissionType':2,'lotSize':100}}}
        row={'symbol_id':99,'quote_currency':'USD','min_volume_cents':100,'buy_margin_eur':10,'sell_margin_eur':10,'captured_pnl_conversion_fraction':.003}
        r={'action':t,'causal_reference_price':10.,'causal_h1_range':.1}
        tt=[t-800+i*100 for i in range(8)];vv=[1.]*8
        edges={t:[(10,'EUR','CHF',1.2),(11,'USD','CHF',.9)]}
        out=economic_gate(row,native,edges,tt,vv)(r)
        self.assertTrue(out['research_pass']);self.assertAlmostEqual(out['reference_quote_to_eur'],.75)
        direct={**row,'quote_currency':'EUR'}
        native['light'][0]['quoteAssetId']=1
        out=economic_gate(direct,native,{},tt,vv)(r)
        self.assertTrue(out['research_pass']);self.assertEqual(out['reference_quote_to_eur'],1.)
if __name__=='__main__':unittest.main()
