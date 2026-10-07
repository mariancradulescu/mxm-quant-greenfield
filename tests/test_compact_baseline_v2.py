import ast
import copy
import unittest
from fractions import Fraction
from pathlib import Path
from research_core_v4.compact_baseline_v2 import baseline, ORDER

def bars():
 return [dict(timestamp=s,available_at=s+300,open=2,high=4,low=1,close=3,tick_volume=2) for s in range(0,3600,300)]
class CompactBaselineTests(unittest.TestCase):
 def test_exact_vector(self):
  self.assertEqual(baseline(3600,bars()),(2,4,1,3,2,Fraction(2,3),3,24,3,12)); self.assertEqual(len(ORDER),10)
 def test_activity_path_not_retained(self):
  a=bars();b=bars();a[0]['tick_volume']=1;a[1]['tick_volume']=3;b[0]['tick_volume']=3;b[1]['tick_volume']=1
  self.assertEqual(baseline(3600,a),baseline(3600,b));self.assertNotEqual(a,b)
 def test_price_path_not_retained(self):
  a=bars();b=bars();b[0]['open']=3;self.assertEqual(baseline(3600,a),baseline(3600,b))
 def test_flat_range(self):
  a=bars()
  for b in a:
   for k in ('open','high','low','close'): b[k]=2
  self.assertEqual(baseline(3600,a)[5:7],(Fraction(1,2),0))
 def test_missing_bar(self): self.assertIsNone(baseline(3600,bars()[:-1]))
 def test_missing_fields(self):
  for k in ('open','high','low','close','tick_volume','available_at'):
   with self.subTest(k=k):
    b=bars();del b[2][k];self.assertIsNone(baseline(3600,b))
 def test_delayed_bar(self):
  b=bars();b[0]['available_at']=3601;self.assertIsNone(baseline(3600,b))
 def test_forming_bar(self):
  b=bars();b[0]['available_at']=1;self.assertIsNone(baseline(3600,b))
 def test_no_older_hour_fallback(self): self.assertIsNone(baseline(7200,bars()))
 def test_partial_hour(self):
  b=bars()+[dict(bars()[-1],timestamp=3600,available_at=3900)]
  self.assertIsNotNone(baseline(3900,b));b[-1]['tick_volume']=9;self.assertEqual(baseline(3900,b)[7],24)
 def test_duplicate(self): self.assertIsNone(baseline(3600,bars()+[bars()[0]]))
 def test_bad_grid(self):
  with self.assertRaises(ValueError): baseline(3601,bars())
 def test_zero_counts(self):
  b=bars()
  for x in b:x['tick_volume']=0
  self.assertEqual(baseline(3600,b)[7],0)
 def test_invalid_count(self):
  for v in (-1,1.5,True):
   b=bars();b[0]['tick_volume']=v;self.assertIsNone(baseline(3600,b))
 def test_nonfinite_price(self):
  b=bars();b[0]['open']=float('nan');self.assertIsNone(baseline(3600,b))
 def test_invalid_ohlc(self):
  b=bars();b[0]['close']=9;self.assertIsNone(baseline(3600,b))
 def test_utc_clock(self):
  t=86400+3600;b=[dict(x,timestamp=x['timestamp']+86400,available_at=x['available_at']+86400) for x in bars()]
  self.assertEqual(baseline(t,b)[-2:],(4,12))
 def test_no_mutation(self):
  b=bars();orig=copy.deepcopy(b);baseline(3600,b);self.assertEqual(b,orig)
 def test_builder_has_no_io_or_candidate_import(self):
  tree=ast.parse(Path('research_core_v4/compact_baseline_v2.py').read_text())
  imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
  self.assertEqual(imports,['datetime','fractions'])
  names=[n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
  self.assertNotIn('open',names);self.assertNotIn('eval',names);self.assertNotIn('exec',names);self.assertNotIn('__import__',names)
