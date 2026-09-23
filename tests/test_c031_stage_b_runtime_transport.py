import gzip,hashlib,json,pathlib,unittest
from m7.c031_stage_b_runtime_v2_adapter import (
 PACK_REF,PACK_GZIP_SHA256,PACK_RAW_SHA256,SPEC_HASH,_load_pack
)
from research_v3.economic_operation_materializer import EconomicEnvelopeError,validate_envelope

class C031RuntimeTransportTests(unittest.TestCase):
 def test_binary_pack_hash_and_counts(self):
  p=pathlib.Path(PACK_REF); b=p.read_bytes()
  self.assertEqual(hashlib.sha256(b).hexdigest(),PACK_GZIP_SHA256)
  raw=gzip.decompress(b); self.assertEqual(hashlib.sha256(raw).hexdigest(),PACK_RAW_SHA256)
  d=json.loads(raw); self.assertTrue(d['pre_economic']); self.assertEqual(d['spec_hash'],SPEC_HASH)
  self.assertEqual((len(d['base']),len(d['stress'])),(1666,1666))
 def test_loader_is_non_economic(self):
  d=_load_pack(pathlib.Path('.')); self.assertTrue(d['pre_economic'])
 def test_no_envelope_authorized_before_transport_acceptance(self):
  self.assertFalse(pathlib.Path('research_v3/ai_director/economic_operations/C031_STAGE_B_RUNTIME_OPERATION_V1.json').exists())
if __name__=='__main__': unittest.main()
