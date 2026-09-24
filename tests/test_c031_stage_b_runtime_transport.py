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
 def test_envelope_lifecycle_is_fail_closed_and_exact_head_bound(self):
  p=pathlib.Path('research_v3/ai_director/economic_operations/C031_STAGE_B_RUNTIME_OPERATION_V1.json')
  self.assertTrue(p.exists())
  d=json.loads(p.read_text())
  n=json.loads(pathlib.Path('research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json').read_text())
  self.assertIn(d['status'],{'PENDING_EXACT_HEAD_GREEN','AUTHORIZED_EXACT_HEAD_GREEN'})
  if d['status']=='PENDING_EXACT_HEAD_GREEN':
   self.assertNotIn('runtime_operation_envelope_ref',n)
  else:
   self.assertEqual(d['exact_head_authorization']['run_id'],35922246231)
   result=pathlib.Path('m6/results/V2-C031_STAGE_B_CURRENT_CONFIG_V1.json')
   if result.exists():
    r=json.loads(result.read_text())
    self.assertEqual(r['economic_execution_id'],'econ_561ca1cabbc351f3fdde2e0bddaed830')
    self.assertNotIn('runtime_operation_envelope_ref',n)
    self.assertNotIn('expected_operation_id',n)
   else:
    self.assertEqual(n['runtime_operation_envelope_ref'],str(p))
    self.assertEqual(n['expected_operation_id'],'op_cdcf9d2bae1f2bc2355e79efbbcdaf50')
if __name__=='__main__': unittest.main()
