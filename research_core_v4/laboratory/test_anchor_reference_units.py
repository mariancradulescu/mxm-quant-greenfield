import ast,json,unittest
from pathlib import Path
from . import commodity_anchor_reference_units as r
from . import commodity_anchor_development as original
class ReferenceUnits(unittest.TestCase):
 def test_exact_source_denominations_and_unchanged_economic_branch(self):
  r.frozen();_,by=r.identity();self.assertEqual(by[7393]['quote'],'USC');self.assertEqual(by[250]['quote'],'USD')
  terms=r.terms_from_identity();self.assertEqual(terms['units'],1);self.assertEqual(terms['fee_usd'],0);self.assertEqual(terms['pnl_rate'],0)
  a=ast.parse(Path(r.__file__).read_text());b=ast.parse(Path(original.__file__).read_text())
  def branch(t):return next(x for x in next(f for f in t.body if isinstance(f,ast.FunctionDef) and f.name=='evaluate').body if isinstance(x,ast.If))
  self.assertEqual(ast.dump(branch(a)),ast.dump(branch(b)));self.assertEqual(r.SPEC_SHA,original.SPEC_SHA)
  w=r.workflow();self.assertEqual(json.loads((r.HOME/r.PATH).read_bytes()),w)
  cache=next(x for x in w['jobs']['source-cache']['steps'] if x.get('id')=='cache')
  self.assertNotIn('env',cache)
  for job in w['jobs'].values():
   self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
   for step in job['steps']:
    env=step.get('env',{});self.assertFalse('R3_CTRADER_ACCESS_TOKEN' in env and 'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env)
  text=Path(r.__file__).read_text();self.assertIn('ANCHOR_ONE_MARGIN_ONLY',text);self.assertIn("Panel({'H1':3",text);self.assertNotIn('load_asset(key',text)
if __name__=='__main__':unittest.main()
