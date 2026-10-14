import unittest
from .runner_v1 import select,reference,stamp,iso,distribution
class TestCoverage(unittest.TestCase):
 def test_unknown_quote_is_not_zero_cost(self):
  v=reference({'sid':1},{},0,{}, {},2)
  self.assertFalse(v['eligible']);self.assertNotIn('break_even_eur',v)
 def test_selection_does_not_use_returns(self):
  rows=[{'class':str(i%2),'quote':'EUR','margin_eur':10,'sid':i,'future_return':1000-i} for i in range(20)]
  a=select(rows,8)
  for r in rows:r['future_return']=-r['future_return']
  self.assertEqual([r['sid'] for r in a],[r['sid'] for r in select(rows[::-1],8)])
  self.assertEqual({r['class'] for r in a},{'0','1'})
 def test_consecutive_ISO_UTC(self):
  t=stamp('2026-08-24T00:00:00Z');self.assertEqual([iso(t+i*604800) for i in range(3)],['2026-W35','2026-W36','2026-W37'])
 def test_na_distribution(self):self.assertEqual(distribution([None])['median'],None)
if __name__=='__main__':unittest.main()
