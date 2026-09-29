import gzip,hashlib,json,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'research_core_v3/state'
def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
class BroadSurfaceIntegrity(unittest.TestCase):
 def test_complete_hash_bound_primary_grid(self):
  m=json.loads((ROOT/'BROAD_145_DEVELOPMENT_SURFACE_MANIFEST_V1.json').read_text());digest=m.pop('sha256');self.assertEqual(hashlib.sha256(canonical(m)).hexdigest(),digest);m['sha256']=digest
  p=json.loads((ROOT/'PRIMARY_145_INPUT_MANIFEST_V1.json').read_text());self.assertEqual(m['input_manifest_sha256'],p['sha256'])
  s=json.loads((ROOT/'FROZEN_EXPERIMENT_SPEC_V1.json').read_text());ids=set();cell_count=0
  for shard in m['shards']:
   blob=(ROOT/shard['path']).read_bytes();self.assertEqual(hashlib.sha256(blob).hexdigest(),shard['sha256']);content=json.loads(gzip.decompress(blob));self.assertEqual(content['input_manifest_sha256'],p['sha256'])
   for x in content['symbols']:
    sid=x['symbol_id'];self.assertNotIn(sid,ids);ids.add(sid)
    saved=x.pop('sha256');self.assertEqual(hashlib.sha256(canonical(x)).hexdigest(),saved);x['sha256']=saved
    self.assertEqual(len(x['cells']),55);cell_count+=55
    self.assertEqual({c['mechanism'] for c in x['cells']},{z['name'] for z in s['mechanisms']})
    for c in x['cells']:
     self.assertEqual(set(c['horizons']),{'1','3','6','12'})
     self.assertEqual(set(c['missingness_sensitivity']['response_sensitivity_by_horizon']),{'1','3','6','12'})
  self.assertEqual(ids,{r['symbol_id'] for r in p['primary_series']});self.assertEqual(cell_count,7975)
  self.assertFalse(ids & {r['symbol_id'] for r in p['supplementary_original_series']})
if __name__=='__main__':unittest.main()
