import ast,json,unittest
from pathlib import Path
from . import commodity_anchor_reference_units as r
from . import commodity_anchor_development as original
class ReferenceUnits(unittest.TestCase):
 def test_exact_source_denominations_and_unchanged_economic_branch(self):
  # Shared core evolved; the closed economic identity must reject this tree.
  with self.assertRaisesRegex(ValueError,'ANCHOR_IMPLEMENTATION'):r.frozen()
  _,by=r.identity();self.assertEqual(by[7393]['quote'],'USC');self.assertEqual(by[250]['quote'],'USD')
  terms=r.terms_from_identity();self.assertEqual(terms['units'],1);self.assertEqual(terms['fee_usd'],0);self.assertEqual(terms['pnl_rate'],0)
  a=ast.parse(Path(r.__file__).read_text());b=ast.parse(Path(original.__file__).read_text())
  def branch(t):return next(x for x in next(f for f in t.body if isinstance(f,ast.FunctionDef) and f.name=='evaluate').body if isinstance(x,ast.If))
  ba=branch(a);bb=branch(b)
  changed=0
  for node in ast.walk(bb):
   if isinstance(node,ast.Tuple) and [x.value for x in node.elts if isinstance(x,ast.Constant)]==[23,24,25,26]:
    node.elts=[ast.Constant(value=x) for x in (32,33,34,35)];changed+=1
  self.assertEqual(changed,1);self.assertEqual(ast.dump(ba),ast.dump(bb));self.assertEqual(r.SPEC_SHA,original.SPEC_SHA)
  w=r.workflow();self.assertEqual(json.loads((r.HOME/r.PATH).read_bytes()),w)
  cache=next(x for x in w['jobs']['source-cache']['steps'] if x.get('id')=='cache')
  self.assertIn('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM',cache['env']);self.assertNotIn('R3_CTRADER_ACCESS_TOKEN',cache['env'])
  for job in w['jobs'].values():
   self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
   for step in job['steps']:
    env=step.get('env',{});self.assertFalse('R3_CTRADER_ACCESS_TOKEN' in env and 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env)
  text=Path(r.__file__).read_text();self.assertIn('ANCHOR_ONE_MARGIN_ONLY',text);self.assertIn("Panel({'H1':3",text);self.assertIn('load_asset(key',text);self.assertIn('TIME_SUPPORT_CANNOT_MEET_UNCHANGED_WEEKLY_GATE',text)
 def test_timestamp_upper_bound_ignores_prices_and_keeps_all_fixed_weeks(self):
  rows=[[v,1,1,1,1] for v in range(r.START,r.END,3600000)]
  by={1:rows,250:rows,7393:rows};self.assertEqual(r.time_capacity(by),{'2026-W32':25,'2026-W33':25,'2026-W34':25,'2026-W35':25})
  from datetime import datetime,timezone
  by[7393]=[z for z in rows if datetime.fromtimestamp(z[0]/1000,timezone.utc).isocalendar().week!=33]
  self.assertEqual(r.time_capacity(by)['2026-W33'],0)
  self.assertEqual(r.EVAL,1785715200000);self.assertEqual(r.END,1788134400000)
if __name__=='__main__':unittest.main()
