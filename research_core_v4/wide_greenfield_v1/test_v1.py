import unittest,math,copy
from types import SimpleNamespace
from research_core_v4 import shallow_m5_support_v2 as v2
from research_core_v4.wide_greenfield_v1 import kernel_v1 as k,economics_v1 as e
from research_core_v4.wide_greenfield_v1.collect_v1 import stratified,aggregate_m5,Collector,m,enums

def q(b,a,t):return {'sides':{s:{'state':'AUTHENTIC_CAUSAL_QUOTE','price':p,'timestamp_ms':t*1000,'age_ms':0,'source_has_more':False} for s,p in [('bid',b),('ask',a)]}}
class FrozenTests(unittest.TestCase):
 def setUp(self):
  self.rows=[{'sid':1,'class':'Forex (Spot)','base':'EUR','quote':'USD'},{'sid':2,'class':'Forex (Spot)','base':'EUR','quote':'GBP'}];self.g=e.graph(self.rows);self.qs={(1,0):q(1.1,1.2,0),(2,0):q(.8,.9,0)};self.r={'sid':3,'class':'Stocks','quote':'GBP','min_units':1,'margin_eur':10};self.f={'commissionType':4,'preciseTradingCommissionRate':'100000000','lotSize':100,'preciseMinCommission':'0','minCommissionType':1,'minCommissionAsset':'USD','pnlConversionFeeRate':0}
 def test_receipt_usd_ask(self):self.assertAlmostEqual(e.convert(12,'USD','EUR',0,self.qs,self.g),10)
 def test_liability_usd_bid(self):self.assertAlmostEqual(e.convert(-11,'USD','EUR',0,self.qs,self.g),-10)
 def test_multicurrency_gbp_usd(self):self.assertAlmostEqual(e.convert(-8,'GBP','USD',0,self.qs,self.g),-12)
 def test_quote_commission_currency(self):self.assertAlmostEqual(e.commission(self.r,self.f,1,10,0,self.qs,self.g),1/.8)
 def test_percentage_commission_scaling(self):
  f=dict(self.f,commissionType=3,preciseTradingCommissionRate='500');self.assertAlmostEqual(e.commission(self.r,f,10,100,0,self.qs,self.g),.05/.8)
 def test_minimum_asset_string(self):
  f=dict(self.f,preciseTradingCommissionRate='0',preciseMinCommission='2000000',minCommissionAsset='USD');self.assertAlmostEqual(e.commission(self.r,f,1,10,0,self.qs,self.g),.02/1.1)
 def test_unknown_fx_not_zero(self):self.assertIsNone(e.convert(1,'JPY','EUR',0,self.qs,self.g))
 def test_aged_or_paged_excluded(self):
  z=q(1,2,0);z['sides']['ask']['age_ms']=5001;self.assertIsNone(e.point(z));z=q(1,2,0);z['sides']['bid']['source_has_more']=True;self.assertIsNone(e.point(z))
 def test_horizons_by_contract_class(self):self.assertEqual(k.horizon('Stocks'),24);self.assertEqual(k.horizon('Forex (Spot)'),8)
 def test_features_ignore_future(self):
  bars={k.START+i*3600:[1,1.1,.9,math.exp(.0001*math.sin(i)+.00001*i),1] for i in range(110)};t=k.START+100*3600;a=k.features(bars,t);bars[t]=[999,999,999,999,1];self.assertEqual(a,k.features(bars,t))
 def test_forecast_min_support_and_direction(self):
  self.assertIsNone(k.forecast([0,0],[(i,[0,0],1) for i in range(127)],'return'));f=k.forecast([0,0],[(i,[0,0],1) for i in range(128)],'return');self.assertEqual(f['d'],1);self.assertEqual(f['tail95_bps'],0)
 def test_magnitude_not_directional_alpha(self):
  f=k.forecast([0],[(i,[0],(-1)**i) for i in range(128)],'magnitude');self.assertEqual(f['d'],0);self.assertEqual(f['model'],1)
 def test_sampling_not_outcomes(self):
  rr=[{'sid':i,'class':'Stocks','quote':'GBP','margin_eur':i,'research_contract_eligible':True} for i in range(1,6)];a=stratified(rr,2,2,set());rr[0]['historical_profit']=-1e9;self.assertEqual(a,stratified(rr,2,2,set()))
 def test_complete_m5_aggregation_only(self):
  rr={i*300:[1,2,.5,1+i/100,1] for i in range(12)};self.assertEqual(len(aggregate_m5(rr)),1);rr.pop(300);self.assertEqual(aggregate_m5(rr),{})
 def test_zero_outcome_denominator_na(self):
  z=e.stat([])['groups']['ALL_CALCULABLE'];self.assertEqual(z['entries'],0);self.assertIsNone(z['scenarios']['S0_F0']['model_net_eur'])
 def test_admission_independent_future_quote(self):
  r=dict(self.r,quote='USD',sid=3);f=dict(self.f,preciseTradingCommissionRate='0',scheduleTimeZone='UTC',schedule=[{'startSecond':0,'endSecond':604800}]);t=k.SCORE+300;qs={(1,t):q(1.1,1.2,t),(3,t):q(10,10.01,t)};ev={'t':k.SCORE,'h':8,'forecast':{'d':1,'model':100,'tail95_bps':0}};a=e.admission(ev,r,f,qs,self.g);qs[(3,t+8*3600)]=q(100000,100001,t+8*3600);self.assertEqual(a,e.admission(ev,r,f,qs,self.g))
 def test_h1_accepted_decoder_native_type_bridge(self):
  col=Collector();col.aid=1;res=v2.ProtoOAGetTrendbarsResV2(ctidTraderAccountId=1,symbolId=4,period=enums.H1,hasMore=False);res.trendbar.add(volume=1,low=100000,deltaOpen=100,deltaClose=200,deltaHigh=300,utcTimestampInMinutes=60);col.tr=SimpleNamespace(last_history_envelope=SimpleNamespace(payloadType=v2.PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE,payload=res.SerializeToString(),SerializeToString=lambda:res.SerializeToString()));col.send=lambda req,historical:m.ProtoOAGetTrendbarsRes.FromString(res.SerializeToString())
  bars,receipts,status=col.h1(4,5,3600,7200);self.assertEqual(status,'COMPLETE_EXACT_WINDOW');self.assertEqual(bars[3600][3],1.002);self.assertEqual(receipts[0]['period'],'H1')
 def test_native_tick_price_bridge_and_newest(self):
  col=Collector();col.aid=1;res=m.ProtoOAGetTickDataRes(ctidTraderAccountId=1,hasMore=False);res.tickData.add(timestamp=9999,tick=120000);res.tickData.add(timestamp=-1000,tick=-1000);col.send=lambda req,historical:res
  z=col.quote(1,10);self.assertEqual(z['sides']['bid']['price'],1.2);self.assertEqual(z['sides']['bid']['timestamp_ms'],9999)
 def test_mature_label_forecast_future_mutation(self):
  bars={k.START+i*3600:[math.exp(.00001*i),math.exp(.00001*i+.001),math.exp(.00001*i-.001),math.exp(.00001*i+.0001*math.sin(i)),1] for i in range(1500)}
  t=k.START+1200*3600
  before=k.SCORE; k.SCORE=t
  try:
   a=next(r['forecast'] for r in k.observations(bars,'Forex') if r['t']==t and r['family']==k.NAMES[0]);self.assertIsNotNone(a)
   for x in list(bars):
    if x>=t:bars[x]=[100,100,100,100,1]
   b=next(r['forecast'] for r in k.observations(bars,'Forex') if r['t']==t and r['family']==k.NAMES[0]);self.assertEqual(a,b)
  finally:k.SCORE=before
if __name__=='__main__':unittest.main()
