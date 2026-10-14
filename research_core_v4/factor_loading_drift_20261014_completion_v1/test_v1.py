import ast,unittest
from pathlib import Path
from . import runner_v1 as r
class Tests(unittest.TestCase):
 def test_native_projection_preserves_price_and_original_guard(self):
  t=r.k.START;row={'time_utc':'2026-08-20T00:00:00Z','open':'1.00000','high':'1.10000','low':'0.90000','close':'1.05000','tick_volume':'20'}
  out=r.project_native({str(t):row},1,5);self.assertEqual(out[t]['close'],1.05);self.assertEqual(out[t]['available_at'],t+300)
 def test_accepted_producer_vector_schema(self):
  out=r.project_native({str(r.k.START):[1.0,1.1,.9,1.05,20.]},1,5)
  self.assertEqual(out[r.k.START]['close'],1.05);self.assertEqual(out[r.k.START]['tick_volume'],20)
 def test_vector_wrong_width_fail_closed(self):
  with self.assertRaises(Exception):r.project_native({str(r.k.START):[1.,1.,1.]},1,5)
 def test_wrong_timestamp_fail_closed(self):
  row={'time_utc':'2026-08-20T00:00:00Z','open':'1.00000','high':'1.10000','low':'0.90000','close':'1.05000','tick_volume':'20'}
  with self.assertRaises(Exception):r.project_native({str(r.k.START+300):row},1,5)
 def test_no_fit_or_forecast_call_in_completion_source(self):
  tree=ast.parse(Path(r.__file__).read_text());calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
  self.assertFalse(set(calls)&{'forecasts','predict','fit','factors'})
if __name__=='__main__':unittest.main()
