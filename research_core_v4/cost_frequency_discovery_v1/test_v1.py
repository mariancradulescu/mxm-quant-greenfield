"""Synthetic causal, native-accounting and unchanged-capital checks, not alpha evidence."""
import unittest,copy,math
from unittest.mock import Mock
from . import kernel_v1 as k,accounts_v1 as a
from .collector_v1 import Collector
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m,enums
def quote(sid,t,bid,ask,age=0):return {'symbol_id':sid,'boundary_ms':t*1000,'sides':{n:{'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':t*1000-age,'price':v,'age_ms':age,'source_has_more':False} for n,v in [('bid',bid),('ask',ask)]}}
def economic_row(t,sid=1,risk=1.,margin=10.,net=1.):
 return {'sid':sid,'t':t,'exit':t+900,'h':15,'iso':k.iso(t),'entry':{'eligible':True,'features':[1,.1,.1,.5,.1,.5,.5,0],'cost_bin':0,'cost_eur':.1,'risk_eur':risk,'margin_eur':margin},'net_sides':[net,-net-.2],'accounts':{s:[{'net_eur':net},{'net_eur':-net-.2}] for s in a.SCENARIOS}}
class Contracts(unittest.TestCase):
 def test_counters_do_not_cross_block(self):
  c=Collector({'H1':0,'M5':2,'BID_ASK':2,'NONHISTORY':0});c.hrate=Mock();c.tr=Mock()
  c.send(m.ProtoOAGetTrendbarsReq(period=enums.M5),True);c.send(m.ProtoOAGetTickDataReq(),True)
  self.assertEqual(dict(c.counts),{'M5':1,'BID_ASK':1})
 def test_only_frozen_request_types(self):
  c=Collector({'H1':0,'M5':2,'BID_ASK':2,'NONHISTORY':4})
  with self.assertRaises(Exception):c.send(m.ProtoOATraderReq())
 def test_h1_cannot_be_sent(self):
  c=Collector({'H1':0,'M5':2,'BID_ASK':2,'NONHISTORY':0})
  with self.assertRaises(Exception):c.send(m.ProtoOAGetTrendbarsReq(period=enums.H1),True)
 def test_four_edge_route_is_real(self):
  g={'A':[('B',1,True)],'B':[('C',2,True)],'C':[('D',3,True)],'D':[('EUR',4,True)]}
  self.assertEqual(len(a.route('A','EUR',g)),4);self.assertIsNone(a.route('X','EUR',g))
 def test_fx_liability_uses_opposite_side(self):
  q={(1,100):quote(1,100,160,162)};g={'JPY':[('EUR',1,False)]}
  self.assertAlmostEqual(a.convert(162,'JPY','EUR',100,q,g),1);self.assertAlmostEqual(a.convert(-160,'JPY','EUR',100,q,g),-1)
 def test_stale_quote_stays_missing(self):self.assertIsNone(a.point(quote(1,100,1,1.1,5001)))
 def test_quote_side_skew_rejected(self):
  q=quote(1,100,1,1.1);q['sides']['ask']['timestamp_ms']-=2001;self.assertIsNone(a.point(q))
 def test_features_ignore_future_bars(self):
  b={t:[1,1.01,.99,1+(t%900)/100000,10] for t in range(0,300*200,300)};p=k.prior(b,300*120)
  for t in list(b):
   if t>=300*120:b[t]=[1000,2000,1,1000,10**9]
  self.assertEqual(k.prior(b,300*120),p)
 def test_future_net_changes_do_not_change_earlier_forecasts(self):
  rr=[economic_row(1700000000+j*3600,j%4+1,net=.1+math.sin(j)/100) for j in range(150)];old=k.causal_evaluate(rr);mut=copy.deepcopy(rr)
  for r in mut[140:]:r['net_sides']=[1000,-1000]
  new=k.causal_evaluate(mut)
  self.assertEqual([r['prediction'] for r in old if r['t']<rr[140]['t']],[r['prediction'] for r in new if r['t']<rr[140]['t']])
 def test_same_clock_labels_never_train_same_clock(self):
  rr=[economic_row(1700000000+j*3600,j%4+1) for j in range(128)];rr.extend([economic_row(1700000000+129*3600,s) for s in range(1,5)])
  z=k.causal_evaluate(rr);last=[r['prediction']['mature_N'] for r in z if r['t']==rr[-1]['t']];self.assertEqual(last,[128]*8)
 def test_unknown_exit_halts_no_skip_to_profit(self):
  r=economic_row(1700000000);r.update(model_admit=True,baseline_admit=True,model_side=1,baseline_side=1,predicted_net_eur=1,prediction={'baseline_expected_net_eur':1});r['accounts']['S2_F010_DAY']=None
  later=copy.deepcopy(r);later['t']+=3600;later['exit']+=3600;later['accounts']['S2_F010_DAY']=[{'net_eur':100},{'net_eur':-100}]
  p=k.portfolio([r,later],[r['iso']],4);self.assertEqual(p['cash_eur'],200);self.assertEqual(p['closed'],0);self.assertEqual(p['selected'],1);self.assertEqual(p['halt'],'FIRST_SELECTED_UNKNOWN_EXIT')
 def test_concurrency_does_not_relax_risk(self):
  rr=[]
  for sid in range(1,5):
   r=economic_row(1700000000,sid,risk=1.1);r.update(model_admit=True,baseline_admit=True,model_side=1,baseline_side=1,predicted_net_eur=1,prediction={'baseline_expected_net_eur':1});rr.append(r)
  p=k.portfolio(rr,[rr[0]['iso']],4);self.assertEqual(p['selected'],1)
 def test_concurrency_does_not_relax_margin(self):
  rr=[]
  for sid in range(1,5):
   r=economic_row(1700000000,sid,risk=.1,margin=45);r.update(model_admit=True,baseline_admit=True,model_side=1,baseline_side=1,predicted_net_eur=1,prediction={'baseline_expected_net_eur':1});rr.append(r)
  self.assertEqual(k.portfolio(rr,[rr[0]['iso']],4)['selected'],1)
 def test_missing_is_not_zero_in_paired_report(self):
  r=economic_row(1700000000);r.update(model_admit=False,baseline_admit=False,model_side=1,baseline_side=1,prediction={'mature_N':128});r['accounts']['S2_F010_DAY']=None
  z=k.report([r],[r['iso']]);self.assertIsNone(z['scenarios']['S2_F010_DAY']['model_net_eur']);self.assertEqual(z['supported_weeks'],0)
if __name__=='__main__':unittest.main()
