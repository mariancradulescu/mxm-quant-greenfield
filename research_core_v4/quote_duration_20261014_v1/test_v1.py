import unittest
from . import kernel_v1 as k
class Tests(unittest.TestCase):
 def path(self,change_times):
  levels=[100,101,100,101,100,101,100];j=0;out=[]
  for t in range(45):
   while j<len(change_times) and change_times[j]<=t:j+=1
   out.append((t*1000,levels[j]))
  return out
 def test_marked_durations_distinct_from_counts_endpoint_and_amplitudes(self):
  a=k.durations(self.path([1,9,10,18,19,27]));b=k.durations(self.path([1,2,10,11,19,20]))
  self.assertEqual((a['up_n'],a['down_n'],a['count_side'],a['momentum_side']),(b['up_n'],b['down_n'],b['count_side'],b['momentum_side']))
  self.assertEqual(a['model_side'],1);self.assertEqual(b['model_side'],-1)
 def test_first_wait_is_left_censored(self):
  a=k.durations(self.path([1,9,10,18,19,27]));self.assertEqual(a['up_n'],2);self.assertEqual(a['down_n'],3)
 def test_same_ms_conflict_censors(self):
  self.assertEqual(k.feature([(0,100),(0,101)],[(0,102)],60)['state'],'AMBIGUOUS_SIDE_MS')
 def test_hasmore_censors(self):self.assertEqual(k.feature([],[],60,True)['state'],'INCOMPLETE_PAGE')
 def test_future_ticks_cannot_change_feature(self):
  b=[(i*1000,100+i%3) for i in range(61)];a=[(i*1000,110+i%3) for i in range(61)]
  self.assertEqual(k.feature(b,a,60),k.feature(b+[(61000,1000)],a+[(61000,1001)],60))
 def test_duplicate_unchanged_updates_cannot_refresh_changed_price(self):
  b=[(i*1000,100 if i==0 else 101) for i in range(61)];a=[(i*1000,110 if i==0 else 111) for i in range(61)]
  self.assertEqual(k.feature(b,a,60)['state'],'STALE_OR_SKEWED_CHANGED_SIDE')
 def test_risk_and_margin_shrink_with_cash(self):
  e={'eligible':True,'margin_eur':79.,'risk_eur':1.9,'cost_eur':.1};self.assertTrue(k.admit(e));self.assertFalse(k.admit(e,190.))
 def test_unknown_future_exit_is_not_used_to_replace_selected_entry(self):
  f={'state':'SUPPORTED','model_side':1};en={'eligible':True,'margin_eur':1.,'risk_eur':.5,'cost_eur':.1}
  r=[{'sid':1,'t':10,'entry':en,'feature':f},{'sid':2,'t':10,'entry':{**en,'cost_eur':.2},'feature':f}]
  out=k.ledger(r,lambda e,d:None if e['sid']==1 else {'net_eur':1.});self.assertEqual(out['selected'],[{'sid':1,'t':10}]);self.assertEqual(out['halt'],'FIRST_SELECTED_UNKNOWN_EXIT_OR_FX')
if __name__=='__main__':unittest.main()
