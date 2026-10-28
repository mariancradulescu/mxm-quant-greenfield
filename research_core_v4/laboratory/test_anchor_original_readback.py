import json,unittest
from .anchor_existing_metadata_readback import workflow,ROOT,PATH
class OriginalReadback(unittest.TestCase):
 def test_only_custody_and_exact_single_readback_route(self):
  w=workflow();self.assertEqual(json.loads((ROOT/PATH).read_bytes()),w)
  self.assertEqual(set(w['on']),{'push'});self.assertEqual(len(w['jobs']),1)
  job=w['jobs']['original-readback'];self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
  raw=json.dumps(w);self.assertNotIn('R3_CTRADER',raw);self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',raw)
  self.assertEqual(sum('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in x.get('env',{}) for x in job['steps']),1)
if __name__=='__main__':unittest.main()
