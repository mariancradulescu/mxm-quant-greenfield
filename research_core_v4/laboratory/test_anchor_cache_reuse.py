import ast,json,unittest
from pathlib import Path
from . import commodity_anchor_cache_reuse as r
from . import commodity_anchor_development as original
class CacheReuseScope(unittest.TestCase):
 def test_transport_preserves_original_economic_code_and_roles(self):
  # Shared core evolved; the closed economic identity must reject this tree.
  with self.assertRaisesRegex(ValueError,'ANCHOR_IMPLEMENTATION'):r.frozen()
  a=ast.parse(Path(r.__file__).read_text());b=ast.parse(Path(original.__file__).read_text())
  # Actual economics and cold original readback are unchanged; public count fields may differ.
  fa=next(x for x in a.body if isinstance(x,ast.FunctionDef) and x.name=='evaluate');fb=next(x for x in b.body if isinstance(x,ast.FunctionDef) and x.name=='evaluate')
  ea=next(x for x in fa.body if isinstance(x,ast.If));eb=next(x for x in fb.body if isinstance(x,ast.If))
  self.assertEqual(ast.dump(ea),ast.dump(eb));self.assertEqual(r.SPEC_SHA,original.SPEC_SHA)
  w=r.workflow();self.assertEqual(len(w['jobs']),3);self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(w))
  for job in w['jobs'].values():
   self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
   for step in job['steps']:
    env=step.get('env',{});self.assertFalse('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in env and 'R3_CTRADER_ACCESS_TOKEN' in env)
  s=Path(r.__file__).read_text();self.assertIn('for sid in (7393,):',s);self.assertIn("Panel({'H1':3",s);self.assertIn('ANCHOR_PREDECESSOR_ZERO_MODELS',s)
  self.assertIn('cache-input.mxmenc',json.dumps(w));self.assertEqual(json.loads((r.HOME/r.PATH).read_bytes()),w)
if __name__=='__main__':unittest.main()
