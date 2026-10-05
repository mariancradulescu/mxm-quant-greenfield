import json,tempfile,unittest,zipfile
from pathlib import Path
from tools.intake_v4_private_proof import intake,NAMES,sha
from V4_QUOTE_SUPPORT_PRIVATE_PROOF_VERIFY import ProofError
ROOT=Path(__file__).resolve().parents[1]
PROOF=ROOT.parent/'upload/MXM_V4_QUOTE_SUPPORT_PRIVATE_PROOF_V1.zip'
COMPACT=ROOT.parent/'upload/MXM_V4_QUOTE_SUPPORT_TRANSPORT_PROBE_RETURN_V1.zip'
class PrivateProofIntakeTests(unittest.TestCase):
 def setUp(self):
  if not PROOF.exists() or not COMPACT.exists():self.skipTest('accepted private proof and compact return attachments required')
 def result(self,path=PROOF):return intake(ROOT,path,COMPACT)
 def altered(self,name,change):
  with zipfile.ZipFile(PROOF) as z:files={n:z.read(n) for n in NAMES}
  value=json.loads(files[name]);change(value);files[name]=(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
  files['CHECKSUMS.sha256']=''.join(sha(b)+'  '+n+'\n' for n,b in sorted(files.items()) if n!='CHECKSUMS.sha256').encode()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'changed.zip'
   with zipfile.ZipFile(p,'w') as z:
    for n,b in files.items():z.writestr(n,b)
   with self.assertRaises((ValueError,ProofError)):self.result(p)
 def test_valid_proof_frozen_decision(self):
  r=self.result();self.assertEqual(r['frozen_decision']['classification'],'DATA_LIMITED_ACQUISITION_NOT_JUSTIFIED');self.assertTrue(r['verification']['checkpoint_integrity']);self.assertTrue(r['verification']['lossless_reconstruction']);self.assertFalse(r['frozen_decision']['economic_null_claimed']);self.assertFalse(r['frozen_decision']['mechanism_closure_declared'])
 def test_wrong_verifier_authority(self):self.altered('PRIVATE_PROOF_MANIFEST.json',lambda v:v.update(private_proof_authority_sha256='0'*64))
 def test_false_lossless_flag(self):self.altered('PRIVATE_PROOF_MANIFEST.json',lambda v:v.update(lossless_reconstruction=False))
 def test_network_count(self):self.altered('PRIVATE_PROOF_MANIFEST.json',lambda v:v.update(network_calls=1))
 def test_raw_hash_changed(self):self.altered('RAW_HASH_TREE.json',lambda v:v['verified_raw_chunk_sha256'].update({next(iter(v['verified_raw_chunk_sha256'])):'0'*64}))
 def test_missing_node(self):self.altered('RAW_HASH_TREE.json',lambda v:v['verified_node_sha256'].pop(next(iter(v['verified_node_sha256']))))
 def test_original_time_changed_even_rechecksummed(self):self.altered('CHECKPOINT_INTEGRITY_PROOF.json',lambda v:v.update(original_active_seconds_charged=5.56))
 def test_support_hash_changed(self):self.altered('SUPPORT_MATRIX_RECOMPUTATION_PROOF.json',lambda v:v.update(sha256='0'*64))
 def test_price_field_rejected(self):self.altered('TRANSPORT_RECOMPUTATION_PROOF.json',lambda v:v.update(price=1))
if __name__=='__main__':unittest.main()
