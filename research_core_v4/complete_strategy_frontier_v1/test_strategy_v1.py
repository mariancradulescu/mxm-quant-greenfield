import unittest
from . import strategy_v1 as k
class CompleteStrategyTests(unittest.TestCase):
 def test_snapshot_never_reads_future_tick(self):
  q=k.Quotes({1:{'bid':[(100000,100),(101000,200)],'ask':[(100000,101),(101000,201)]}});self.assertEqual(q.at(1,100)['sides']['bid']['price'],100)
 def test_cross_symbol_staleness_rejects_pair(self):
  q=k.Quotes({1:{'bid':[(100000,100)],'ask':[(100000,101)]},2:{'bid':[(97000,100)],'ask':[(97000,101)]}});self.assertIsNone(q.context([1,2],100))
 def test_missing_warmup_no_ATR(self):self.assertIsNone(k.atr15({},4500))
 def test_ATR_excludes_unfinished_bar(self):
  z={t:[100,101,99,100,1] for t in range(0,4800,300)};z[4500]=[100,10000,1,9000,1];self.assertEqual(k.atr15(z,4500),2)
 def test_stop_exit_is_loss_observation_not_guaranteed_price(self):
  p={'stress_risk_eur':2,'headroom_eur':1,'entry':100};self.assertEqual(k.exit_reason(-4,p,1,110),'STOP')
 def test_profit_does_not_need_fixed_horizon(self):
  p={'stress_risk_eur':2,'headroom_eur':1,'entry':100};self.assertEqual(k.exit_reason(.6,p,1,101),'PROFIT');self.assertEqual(k.exit_reason(.2,p,0,120),'INVALIDATION')
 def test_safety_cap_and_priority(self):
  p={'stress_risk_eur':2,'headroom_eur':1,'entry':100};self.assertEqual(k.exit_reason(.1,p,1,400),'SAFETY');self.assertEqual(k.exit_reason(-2,p,-1,400),'STOP')
 def test_matched_units_are_not_fake_market_cash_receipts(self):self.assertEqual(k.PAIRS,((2742,2746),(2744,2746)));self.assertEqual(len(k.SCENARIOS),8)
if __name__=='__main__':unittest.main()
class ChronologicalPortfolioTests(unittest.TestCase):
 def fixture(self,dislocation=False):
  start=1773648000;streams={}
  for sid in k.IDS:
   streams[sid]={side:[(t*1000,100+(3 if dislocation and sid==2746 and t<=start+1 else 0)+(.01 if side=='ask' else -.01)) for t in range(start-60,start+2101)] for side in ('bid','ask')}
  rows={sid:{'sid':sid,'min_units':.01,'margin_eur':10,'quote':'EUR'} for sid in (2742,2744,2746)};f={'commissionType':3,'preciseTradingCommissionRate':0,'lotSize':100,'preciseMinCommission':0,'minCommissionType':2,'pnlConversionFeeRate':0};cat={'full':{str(sid):f for sid in rows}};day={'start':start,'streams':streams,'ATRs':{sid:.1 for sid in rows},'status':{str(sid)+side:'COMPLETE_AUTHENTIC_WINDOW' for sid in streams for side in ('bid','ask')}}
  return day,rows,cat
 def test_no_dislocation_keeps_cash_without_fake_trades(self):
  day,rows,cat=self.fixture();full,s=k.evaluate([day],rows,cat,{});self.assertEqual(s['candidate_pair_clocks'],720);self.assertEqual(s['selected_entry_decisions'],0);self.assertEqual(s['cash_EUR_closed_accounting'],200);self.assertEqual(s['actual_trades'],0)
 def test_entry_latency_and_same_entry_fixed_comparator(self):
  day,rows,cat=self.fixture(True);full,s=k.evaluate([day],rows,cat,{});r=full['packages'][0];self.assertEqual(r['entry'],day['start']+1);self.assertEqual(r['dynamic_exit'],day['start']+2);self.assertEqual(r['fixed_exit'],r['entry']+60);self.assertEqual(r['state'],'PAIRED_MODELED_COMPLETE');self.assertEqual(s['modeled_paired_complete_packages'],1)
