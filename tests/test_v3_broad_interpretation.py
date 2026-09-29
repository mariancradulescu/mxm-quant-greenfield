import gzip,hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'research_core_v3/state'
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
class BroadInterpretationIntegrity(unittest.TestCase):
 def test_exhaustive_next_open_and_diagnostic_binding(self):
  surf=json.loads((ROOT/'BROAD_145_DEVELOPMENT_SURFACE_MANIFEST_V1.json').read_text())
  lag=json.loads((ROOT/'NEXT_OPEN_GROSS_SENSITIVITY_MANIFEST_V1.json').read_text())
  self.assertEqual(lag['source_surface_sha256'],surf['sha256'])
  ids=set();total=0
  for sh in lag['shards']:
   blob=(ROOT/sh['path']).read_bytes();self.assertEqual(hashlib.sha256(blob).hexdigest(),sh['sha256'])
   for item in json.loads(gzip.decompress(blob))['symbols']:
    self.assertNotIn(item['symbol_id'],ids);ids.add(item['symbol_id']);self.assertEqual(len(item['cells']),55);total+=55
  self.assertEqual((len(ids),total),(145,7975))
  index=json.loads((ROOT/'BROAD_145_DEVELOPMENT_INTERPRETATION_INDEX_V1.json').read_text())
  self.assertEqual(index['source_surface_sha256'],surf['sha256'])
  self.assertEqual(index['next_open_sensitivity_sha256'],lag['sha256'])
  blob=(ROOT/index['interpretation_path']).read_bytes();self.assertEqual(hashlib.sha256(blob).hexdigest(),index['interpretation_gzip_sha256'])
  doc=json.loads(gzip.decompress(blob));digest=doc.pop('sha256');self.assertEqual(hashlib.sha256(canonical(doc)).hexdigest(),digest)
  self.assertEqual(digest,index['interpretation_uncompressed_sha256']);self.assertEqual(len(doc['all_cell_diagnostics']),7975)
  self.assertFalse(doc['protected_forward_opened']);self.assertFalse(doc['final_pnl_certification'])
if __name__=='__main__':unittest.main()
