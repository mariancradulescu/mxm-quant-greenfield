"""Compact-only intake adversarial checks; no raw/device/broker operation."""
import hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from tools.intake_v4_quote_support_probe_return import intake,NAMES
ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT.parent/'upload/MXM_V4_QUOTE_SUPPORT_TRANSPORT_PROBE_RETURN_V1.zip'
@unittest.skipUnless(INPUT.exists(),'uploaded compact return fixture not present')
class UploadedCompactIntakeTests(unittest.TestCase):
 def mutate(self,name,edit,extra=None):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);out=Path(self.tmp.name)/'mutated.zip'
  with zipfile.ZipFile(INPUT) as z:files={n:z.read(n) for n in NAMES}
  if name:
   value=json.loads(files[name]);edit(value);files[name]=json.dumps(value,sort_keys=True).encode()
   files['CHECKSUMS.sha256']=''.join(hashlib.sha256(files[n]).hexdigest()+'  '+n+'\n' for n in sorted(NAMES-{'CHECKSUMS.sha256'})).encode()
  if extra:files[extra]=b'forbidden'
  with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
   for n,b in files.items():z.writestr(n,b)
  return out
 def test_valid_compact_does_not_invent_raw_checkpoint_proof(self):
  result=intake(ROOT,INPUT);self.assertEqual(result['support_readout']['contexts_meeting8_of10'],0)
  self.assertFalse(result['verification']['checkpoint_integrity']);self.assertFalse(result['verification']['lossless_reconstruction'])
  self.assertEqual(result['observed_transport']['historical_wire_attempts'],1155)
 def test_resealed_count_mask_disagreement_rejected(self):
  def edit(m):m[0]['support']['cells'][0]['attempt_seconds_mask_hex']='0x0'
  with self.assertRaises(ValueError):intake(ROOT,self.mutate('SUPPORT_ONLY_MATRIX.json',edit))
 def test_resealed_trace_scope_change_rejected(self):
  def edit(m):m['logical_requests'][0]['traces'][0]['to_ms']-=1
  with self.assertRaises(ValueError):intake(ROOT,self.mutate('TRANSPORT_METRICS.json',edit))
 def test_resealed_raw_binding_change_rejected(self):
  def edit(m):m[0]['raw_sha256']='0'*64
  with self.assertRaises(ValueError):intake(ROOT,self.mutate('LOCAL_RAW_CHUNK_SHA256_MANIFEST.json',edit))
 def test_raw_member_rejected_without_opening(self):
  with self.assertRaises(ValueError):intake(ROOT,self.mutate(None,None,extra='raw.json.gz'))
if __name__=='__main__':unittest.main()
